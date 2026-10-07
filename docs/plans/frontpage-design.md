# Front page: direct routes to the latest sitting and sitting week

Status: design and engineering decisions settled; implementation and verification remain. Planning only, reviewed on 7 October 2026 against the existing local preview. No application changes or commits were made.

The homepage should let a visitor choose between one sitting and a whole sitting week immediately. Today its single-sitting snapshot and its weekly destination both say “Aktueller Puls”; both “Was gerade läuft” actions open the week. The latest sitting itself has no direct homepage link.

The design-review audit used Chrome DevTools at 375, 768 and 1440px, checked light and dark themes, keyboard focus, the weekly comparison and the existing protocol destination. Baseline design score B; AI slop score C. The main problems are unclear destinations, repeated introductory copy, decorative boxes and a mobile header that wraps into four rows.

## Plan design review

- Initial design-completeness impression: **6/10**. The initial gaps were precise layout, mobile navigation, clear periods and the weekly terminology conflict. The final pass ratings below assess completeness of this scoped plan, not measured quality of a rendered redesign.
- **D1 — accepted:** review all seven dimensions evenly (user selected A). This selects review coverage; it does not approve the proposed design remedies below.
- Mockups: skipped because the gstack designer executable is unavailable. Text-based layout/style decisions D4 and D9 are approved; no generated image was reviewed or approved.
- Existing constraints: reuse the palette, theme controls, semantic navigation, date/week helpers and local protocol routes. No `DESIGN.md` exists; the design-system work is already tracked in `TODOS.md`.
- **D3 — accepted:** use **Wochenübersicht** for the weekly destination on the homepage and in the shared header (user selected A). Dates identify the latest available period. This resolves the label conflict with `CONTEXT.md`, which reserves “Sitzungswoche” for the official planned schedule. No route or reporting-period logic changes.
- **D2 — accepted:** add the independent Codex design reviewer. Claude Code is skipped because the user reports its rate limit has been reached; no new Claude invocation was attempted and no cross-provider consensus is claimed.
- Independent native design review: completed by GPT-6 Luna, **7/10** for the initial draft. Its three findings were confirmed by the primary and resolved through D3 (label), D8 (empty-week recovery) and D10 (header/tablet behavior).
- **D4 — accepted:** show the two main destinations side by side at viewport widths of **1024px and wider**, with **Letzte Sitzung** on the left and **Wochenübersicht** on the right. Below 1024px, stack them in that order (user selected A). This approves their arrangement, not the remaining content-removal or header-disclosure proposals.
- **D5 — accepted:** remove the entire four-tile archive-stat block from the homepage (user selected A). Do not replace it with a compact summary line. Existing archive counts and data availability/stand metadata remain available in their existing destinations.
- **D6 — accepted:** remove the “Prinzipien” section and its four cards, with no replacement principles paragraph (user selected A). Keep the source/method destination. Do not relocate or repeat the unsupported “Automatisch aktuell” promise.
- **D7 — accepted:** remove the repeated “Was ist Bundestag-Puls?” block with no replacement sentence (user selected A). Keep the short introduction at the top and lead into the destinations.
- **Pass 1 — information architecture: 7/10 → 10/10.** D3–D7 settle the weekly label, period-section arrangement and removal of the three competing blocks. Scan priorities: latest available sitting, weekly overview, other destinations. Source/data access follows those destinations. Visual styling and compact navigation are evaluated in their later passes.
- **D8 — accepted:** when no dated week can be evaluated, show “Noch keine Woche auswertbar” with **Sitzungen ansehen →** linking to `overview.html` (user selected A). Do not offer a weekly action that implies an available analysis. The catalog may list entries without generated protocols.
- **Pass 2 — interaction states: 8/10 → 10/10.** D8 supplies the missing empty-week recovery. The table below covers success, empty/undated data, running/pinned/partial weeks and data availability. Static generated pages have no client-side loading phase or visitor-operated refresh.
- **Pass 3 — visitor journey: 10/10 → 10/10; no issues found.** The routes and dates support orientation, direct reading and source checking. The storyboard below records existing and approved behavior; it adds no new controls.
- **D9 — accepted:** use plain main sections with spacing and a subtle divider in the existing palette, rather than bordered panels (user selected A). Headings, dates and links provide their hierarchy. Use the existing `--line` divider color; do not add panel fills, shadows or hover lifts to these sections.
- **Pass 4 — generic-design risk: 8/10 → 10/10.** Classification remains Read. D5–D7 remove the baseline metric grid and repetitive explanatory sections; D9 settles the main-section treatment. No supported hard rejection remains in the proposed layout. Typography-system replacement and authored motion remain explicitly excluded; no new evidence justifies reopening them.
- **Pass 5 — design-system alignment: 10/10 → 10/10; no new issues found within this scope.** There is no `DESIGN.md`. Existing renderer variables, theme overrides, type hierarchy and interaction patterns provide the contract below. D9's plain sections use that vocabulary. The already tracked broader system/typeface work is outside this review, rather than a new implementation dependency.
- **D10 — accepted:** below **1024px**, keep **Wochenübersicht** and **Sitzungen** visible and put the other six destinations under a native **Weitere Bereiche** disclosure; place brand and theme control above. At 1024px and wider, show all eight links (user selected A). The latest single sitting remains homepage-only.
- **Pass 6 — responsive/accessibility: 8/10 → 10/10.** D4 settles the main layout and D10 the header/tablet transition. The responsive table and existing semantic/focus contracts below specify operation, contrast and targets for verification.
- **Pass 7 — decision register: no new issues found.** Eight new design decisions, D3–D10, have individual user answers. Original destination/copy requirements remain authorized. D1 and D2 are review-routing choices and are excluded from the design-decision count. No in-scope design finding is unanswered or deferred. Engineering mechanics and rendered validation are next steps, not unresolved design choices.

### Independent design litmus — single provider

| Check | Codex in-host | Claude Code | Consensus |
| --- | --- | --- | --- |
| Product clear in first screen | YES — Bundestag, official sources and period destinations named | Unavailable; not attempted | Not available |
| Strong visual anchor | YES — descriptive H1 and latest-sitting-first arrangement | Unavailable; not attempted | Not available |
| Headlines scannable | YES — H1 and period headings identify content | Unavailable; not attempted | Not available |
| One job per section | YES — distinct periods, other destinations, sources/data | Unavailable; not attempted | Not available |
| Cards necessary | NO — linked rows and plain sections suffice | Unavailable; not attempted | Not available |
| Motion improves hierarchy | NO — no motion needed for this reading index | Unavailable; not attempted | Not available |
| Works without decorative shadows | YES — proposal removes lifts and shadows | Unavailable; not attempted | Not available |

Classification: **Read**. The independent reviewer flagged card grids, stacked cards and repeated introductory sections in the existing renderer. These are baseline problems the draft proposes to remove, not unresolved hard-rejection hits in the proposed design. No other supported hard rejection was identified in the draft. These are text-based judgments; no rendered redesign or cross-provider agreement is claimed.

Primary hard-rejection check of the final plan: no generic SaaS grid (D5/D9); no hero imagery or busy image behind text; headline has direct sitting/week actions; repeated explanatory sections removed (D6/D7); no carousel; no stacked decorative-card layout. All seven checks were assessed. Litmus results above describe the plan; cards and motion are unnecessary on this reading index.

## Page and copy

Keep the existing neutral palette and site identity. Make this an information index with a short introduction and useful destinations.

| Order | Content | Action |
| --- | --- | --- |
| 1 | Shared header; rename “Aktueller Puls” to **Wochenübersicht** (D3 approved) | Existing `puls.html` route; no “Letzte Sitzung” header item |
| 2 | H1 **Debatten und Entscheidungen im Bundestag** | One supporting sentence: “Sitzungsprotokolle, Themen der Woche und Abstimmungen aus offiziellen Quellen.” |
| 3 | **Letzte Sitzung**, exact sitting date and protocol number | **Sitzungsprotokoll öffnen →**, directly to the existing generated protocol page |
| 4 | **Wochenübersicht** (D3 approved), calendar week, date range and number of sittings actually included | **Wochenübersicht und Vergleich öffnen →**, to `puls.html`; without an available comparison, **Wochenübersicht öffnen →** |
| 5 | **Weitere Bereiche**: Sitzungen, Abstimmungen, Gesetzesvorhaben, Abgeordnete, Fakten | Short destination descriptions; concise linked rows |
| 6 | **Quellen und Daten**: method/source link and the existing data-download destination with its availability/stand metadata | Existing source and data routes |

**Approved arrangement (D4):** at 1024px and wider, show two adjacent sections: **Letzte Sitzung** on the left and **Wochenübersicht** on the right. Below 1024px, including the 768px tablet and 375px mobile checks, stack the sitting above the weekly overview. Preserve that order in the document so keyboard and screen-reader navigation follows it. **Approved treatment (D9):** plain sections with spacing and a subtle divider using `--line`; no bordered panels, panel fills, shadows or hover lifts. Dates and descriptions must identify the time scale without reading an explanation.

Accepted destination flow and arrangement:

```text
Homepage                          Header: Wochenübersicht
  >=1024px:                       └── puls.html
  Letzte Sitzung | Wochenübersicht
  <1024px:
  Letzte Sitzung
  Wochenübersicht

Letzte Sitzung ──> newest available generated protocol page
Wochenübersicht ──> puls.html ──> existing weekly comparison
```

The diagram records accepted routes and arrangement. D5–D7 settle removal of the competing blocks; the original request authorizes descriptive copy and a clear homepage path to each period.

Descriptive copy for the requested destinations:

- **Letzte Sitzung:** “Tagesordnung, Reden und vorliegende Abstimmungen der zuletzt verfügbaren Sitzung.”
- **Wochenübersicht:** “Themen und Redeanteile der zuletzt erfassten Woche, mit Vergleich zur vorherigen erfassten Woche.” When no comparison exists, omit that promise from both the description and action label and let the weekly page explain the available period.
- **Sitzungen:** “Sitzungsprotokolle und verfügbare Auswertungen im Archiv.”
- **Abstimmungen:** “Namentliche Abstimmungen, Ergebnisse und einzelne Stimmen.”
- **Gesetzesvorhaben:** “Debatten, Drucksachen und Verfahrensschritte zu einem Vorhaben.”
- **Abgeordnete:** “Reden und erfasste Abstimmungen einzelner Abgeordneter.”
- **Fakten:** “Auswertungen zu Wochen und Monaten mit ihren Belegen.”

Remove every homepage “Was gerade läuft” label as requested. **D5 approved:** remove the four archive-stat tiles with no replacement summary line. **D6 approved:** remove the “Prinzipien” section and its four cards with no replacement paragraph; remove its unsupported “Automatisch aktuell” promise without repeating it elsewhere. **D7 approved:** remove the repeated “Was ist Bundestag-Puls?” block with no replacement sentence. Keep the existing source/method destination and useful data availability/stand metadata. The archive-entry wording “Sitzungen” matches the header. Do not duplicate the weekly destination in a lower feature grid.

## Dates, coverage and destination rules

- “Protokoll” means the existing local sitting page, such as `protocols/plenarprotokoll-21-94.html`, containing the agenda and speeches. Do not introduce a new latest-sitting route, redirect or PDF-only destination.
- The current newest generated dossier is **21/94, 11.09.2026**. The current weekly page is **KW 37/2026** with four generated sittings. These are review examples, never hardcoded values.
- “Letzte Sitzung” must visibly qualify its data as **zuletzt verfügbar**. The catalog contains newer and even future dates; it must not manufacture a missing dossier link or imply the cached dossier is the Bundestag’s latest actual sitting.
- Render German display dates using existing helpers and semantic `<time>` elements. Show the weekly period independently of the last sitting date; the week overview covers every included sitting, not only the last one.
- Reuse the same week selection as `puls.html`. Preserve `--week` and the build clock: an explicitly selected historical week gets a local heading “Ausgewählte Woche” and its exact dates, while the approved shared navigation label remains “Wochenübersicht”.
- A running week remains visibly “bisher erfasst”; a rebuild date never proves a week is fully acquired or completed. Label a prior comparison as the previous **erfasste** sitting week, not necessarily the previous calendar week. Retain the existing comparison and matched-day methodology.
- With no generated sitting, show “Noch kein Sitzungsprotokoll verfügbar” and an archive link; omit the direct protocol action. **D8 approved:** with no dated week, show “Noch keine Woche auswertbar” and **Sitzungen ansehen →** linking to `overview.html`; omit the weekly analysis action. An undated entry must not receive an invented date. Preserve missing-data notes and source/AI labels.

### Interaction-state coverage

This table records the draft's existing behavior and the accepted routes, including D8's empty-week recovery. These static pages load through ordinary browser navigation; no client-side fetch, spinner, retry control or success toast is introduced.

| Feature | Loading | Empty | Error | Success | Partial |
| --- | --- | --- | --- | --- | --- |
| Latest sitting | Ordinary page navigation | “Noch kein Sitzungsprotokoll verfügbar”; archive link; no protocol action | No visitor-operated acquisition. A missing generated destination must not be linked; unexpected file/network errors use the browser's existing behavior | Exact date and protocol number; one direct link to the available generated protocol | “Zuletzt verfügbar”; preserve missing-data notes; no invented date for an undated entry |
| Weekly overview | Ordinary page navigation | “Noch keine Woche auswertbar”; **Sitzungen ansehen →** to `overview.html`; omit analysis action (D8) | No client-side request or refresh error state. An unevaluable period uses the existing empty branch | Calendar week, dates, included sitting count and `puls.html` link | Running week says “bisher erfasst”; historical selection says “Ausgewählte Woche”; comparison promised only when available |
| Data destination | Ordinary page navigation/download | Omit the download destination when its artifact does not exist, preserving existing optional-data behavior | No new downloader or retry UI | Existing available data link and stand metadata | Existing availability and stand metadata remain visible; build date is not acquisition completeness |

### Visitor journey storyboard

| Step | Visitor does | Intended feeling | Supporting behavior |
| --- | --- | --- | --- |
| 1 — first five seconds | Scans the homepage | Oriented: one sitting and a whole week are distinct | Descriptive introduction, separate headings, dates and the approved sitting-first arrangement |
| 2 | Opens the latest sitting | Confident about the destination and period | One direct link to the latest available generated protocol; exact date and protocol number |
| 3 — first five minutes | Reads the protocol or chooses the weekly view | Able to investigate without learning the data model | Existing agenda/speeches, weekly topics and comparison; no new intermediate page |
| 4 | Checks a claim or available data | Able to verify what the site shows | Existing source links, preserved missing-data/AI labels and source/data destinations |
| 5 | Finds no dated weekly analysis | Able to continue instead of reaching a dead end | D8's explanatory empty message and sitting-catalog recovery |
| 6 — repeat visits over time | Returns home from another page | Familiar with a stable route | Existing brand link returns home; latest sitting stays homepage-only; shared weekly label is “Wochenübersicht” |

The long-term trust goal is stable terminology, visible periods and traceable sources. This is an intended journey, not a claim of measured usability or editorial verification.

### Existing design contract to reuse

These values come from the existing homepage and shared header styles; recording them introduces no new theme or typeface decision. Use light mode for ordinary daytime reading and preserve the existing user-selected/system dark theme for dim environments.

| Role | Existing value / behavior |
| --- | --- |
| Light text, secondary text | `--ink: #171a1f`, `--muted: #606a78` |
| Light page, surface, divider | `--paper: #f7f8fa`, `--panel: #ffffff`, `--line: #d9dee6` |
| Light links, visited links | `--blue: #174ea6`, `--teal: #0f766e` |
| Dark text, secondary text | `--ink: #e6edf3`, `--muted: #9da7b3` |
| Dark page, surface, divider | `--paper: #0d1117`, `--panel: #151b23`, `--line: #2d3643` |
| Dark links, visited links | `--blue: #8ab4f8`, `--teal: #4fd1c5` |
| Page width and padding | Existing 1180px maximum shell; 22px padding, reducing to 14px horizontal below 600px |
| Type hierarchy | Existing 46px H1, 34px below 600px; 26px H2 and 20px destination headings; preserve the current stack pending the separate typeface work |
| Descriptions and metadata | Draft's specified minimum 16px descriptions, 12px metadata; reuse existing 1.5–1.55 body line heights |
| Spacing | Reuse existing 16px/24px section spacing and 30px grid gap; headings stay closer to their own content than to the previous section |
| Actions | Existing link/button vocabulary, minimum 44px target height, visible focus and visited content links; no new icon set or animation |

Do not hardcode light colors into new theme-dependent selectors. The divider is decorative; section names and actions must remain legible without it.

## Mobile and accessibility

**Approved header (D10):** below 1024px, keep **Wochenübersicht** and **Sitzungen** visible, group the other six destinations under a native **Weitere Bereiche** disclosure, and put the theme control on the brand row. At 1024px and wider, show all eight destinations. Apply the shared behavior across generated pages and preserve nested relative links, one semantic navigation landmark and the current active-link contract. Engineering review must choose the smallest implementation that exposes all desktop links without duplicate navigation/current-page semantics.

| Viewport | Main sections | Header |
| --- | --- | --- |
| 375px | Sitting, then weekly overview; existing 14px horizontal shell padding | Brand/theme row; two visible destinations plus collapsed disclosure below. Allow its control to occupy a following row if needed; no clipped text or horizontal scroll |
| 768px | Same sitting-first stack; existing 22px shell padding | Compact navigation below the brand/theme row; both primary links and disclosure control fit in the available width |
| 1024px and wider | Adjacent sitting and weekly sections | All eight links visible; navigation can use the full row beneath brand/theme when required to fit |

The native disclosure opens in normal document flow, without an overlay or focus trap. Tab reaches its summary; native Enter/Space operation opens it; Tab then reaches the six links in registry order. Closed content must not remain in the tab order. Preserve each destination's `aria-current="page"` and reflect the active secondary group on its disclosure control using the existing active visual treatment. Resizing across the breakpoint must keep links reachable and focus visible. No new custom-menu role, navigation library or persisted menu preference is needed.

Use at least 16px for descriptions, 12px for metadata, 44px action targets and the existing visible keyboard focus. Preserve visited-link distinction for content/source links. Use a `<main>` landmark, one H1, and H2s for the two period entries. Remove ornamental hover lifts/shadows with the card layout; no new entrance animation is needed for this reading surface. Preserve light/dark color variables and use CSS/native HTML for layout and disclosure.

Verify at least 4.5:1 contrast for normal text and 3:1 for large text and essential control/focus indicators in both themes. Reuse the existing 2px focus outline and 2px offset. The divider and color changes supplement the headings and labels; they must not be the only way to distinguish destinations. Check 200% zoom/reflow and screen-reader landmark/heading order along with keyboard operation.

## Implementation boundaries

1. **`scripts/build_dip_pulse_site.py`**: revise `render_landing_page` (currently line 3719) and remove the obsolete homepage markup/CSS. Reuse `dossier_href`, `entry_protocol`, `sitting_label`, `time_html`, `select_pulse_week` and existing week/date helpers. Pass the existing `today` and `week` values from `render_site` so the homepage describes the weekly page it links to. Keep optional data-page availability and stand metadata.
2. **`scripts/features/__init__.py`**: change the pulse label in `NAV_ITEMS` (currently line 38), preserving its key and `puls.html` path. This updates every shared header.
3. **`scripts/render_dip_pulse_html.py`**: adjust `render_global_header` and its styles for the compact mobile arrangement. Preserve semantic navigation, active-page state, theme control and relative-prefix handling. Reuse `format_date`, `format_sitting_date`, `week_label`, `group_entries_by_week` and `week_stats` rather than creating another week model.
4. **Weekly terminology (D3 approved label)**: update visible “Aktueller Puls” page titles, eyebrows and links in the builder to “Wochenübersicht”, including running/recent week branches. Use “Woche” or “Woche läuft” for local state-dependent wording; retain the actual weekly topic/comparison content. Review all visible occurrences, including footer links. Do not rename the project “Bundestag-Puls” or internal pulse functions. The broader terminology TODO covering unrelated facts/method pages remains outside this label decision.
5. **Focused checks**: add homepage rendering coverage for direct latest-dossier href, distinct week href/period, empty/undated state and pinned week. Update the existing navigation contract’s label expectation. Preserve the current optional-data-card behavior; remove obsolete expectations only where the new homepage contract changes them.

No dependencies, new data acquisition, new summary generation, ranking algorithm, typography system rewrite or dossier redesign. The existing weekly view already delivers the requested overview and comparison.

## Validation and acceptance

- Run `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests` and compile the affected Python files. Use committed fixtures; no network is required.
- Rebuild from cache or the committed demo with supported Python. Do not refresh official data merely to validate design.
- Verify with Chrome DevTools at 375, 768 and 1440px, plus 1023/1024px across the breakpoint, in light and dark themes. Check header/disclosure operation by keyboard/touch, 200% zoom/reflow, contrast, focus, readable descriptions and no horizontal overflow.
- Homepage → **Sitzungsprotokoll öffnen** reaches the newest available protocol directly in one click. Homepage/header → **Wochenübersicht** reaches the existing overview; its comparison anchor still works.
- The single-sitting entry is absent from the header; dates and week metadata match the destination. Verify default, selected historical week, running/partial week and empty data states.
- Verify the shared header on a sitting, weekly, data and nested MP/vote page so compact navigation retains correct relative links and caller-provided active state. Report the existing dossier's pulse-active choice as baseline deferred debt rather than silently expanding this task.
- All user-facing homepage “Was gerade läuft” and section-label “Aktueller Puls” strings are gone. No stale content promises, broken links, new console/network failures or hidden source warnings.
- Capture before/after screenshots and rescan the rendered homepage after implementation. Report measured improvements only then; this planning pass has no after score.

## Deferred observations

Display typography is generic and was flagged by the detector. Keep the current stack for this task; revisit with the still-undecided product identity. The existing dossier highlights the pulse navigation item and the preview has a favicon 404; both are adjacent polish issues, outside this homepage plan.

Evidence: [design-review audit](/Users/Luca/.gstack/projects/LucaAlv-poliwatch/designs/design-audit-20261007/design-audit-localhost.md), including desktop/mobile/tablet and destination screenshots.

## Implementation Tasks

Synthesized from the original request and approved findings. These are implementation and verification tasks, not completed changes. Estimates assume the existing static renderers and fixtures, with no new dependency or acquisition work.

- [ ] **T1 (P1, human: ~2h / CC: ~15min)** — Homepage destinations — Render direct latest-protocol and matching weekly destinations
  - Surfaced by: Original request; Pass 1 destination confusion; Pass 2 dated/empty/pinned states; D8 recovery.
  - Files: `scripts/build_dip_pulse_site.py`
  - Verify: Use existing render helpers; exercise latest href, weekly selection, empty/undated/pinned fixtures through T4.
- [ ] **T2 (P2, human: ~2h / CC: ~15min)** — Homepage layout and copy — Apply the approved plain layout and remove competing content blocks
  - Surfaced by: D4 desktop/stack arrangement; D5 stats removal; D6 principles removal; D7 repeated intro removal; D9 plain sections.
  - Files: `scripts/build_dip_pulse_site.py`
  - Verify: Confirm descriptive copy and removed blocks in generated HTML; inspect 375/768/1440px in T5.
- [ ] **T3 (P1, human: ~2h / CC: ~20min)** — Shared navigation — Rename the weekly destination and implement compact navigation
  - Surfaced by: D3 Wochenübersicht label; D10 native disclosure; engineering F1/F2 resolved by D1=A/D2=A; G6 shared navigation coverage.
  - Files: `scripts/features/__init__.py`, `scripts/render_dip_pulse_html.py`, `scripts/build_dip_pulse_site.py`
  - Verify: Preserve registry paths, one semantic nav/current-page contract and relative prefixes; verify breakpoint/focus and themes through T4/T5.
- [ ] **T4 (P1, human: ~2h / CC: ~20min)** — Rendering regression checks — Extend existing tests for destination and responsive-header contracts
  - Surfaced by: Pass 2 edge states; Pass 6 navigation semantics; engineering G1–G6 specify the required approved-behavior regression proof.
  - Files: `tests/test_data_pipeline_cli.py`, `tests/test_features.py`, `tests/test_global_header.py`, `tests/test_build_dip_pulse_site.py`
  - Verify: Run /opt/miniconda3/bin/python3.13 -m unittest discover -s tests, then compile affected Python files; use local fixtures without fetching.
- [ ] **T5 (P1, human: ~1h / CC: ~20min)** — Rendered validation — Verify the rebuilt homepage and shared navigation in Chrome DevTools
  - Surfaced by: Pass 4 text-only limitations; Pass 6 contracts; engineering G7 native-state/focus proof; original audit baseline.
  - Files: No source changes expected; generated preview and audit artifacts.
  - Verify: Offline/cache rebuild; widths 375/768/1440 plus 1023/1024, light/dark, keyboard/touch, 200% zoom, contrast and nested paths; capture before/after and check console for new errors.

_No new tasks from Pass 3 (journey) or Pass 5 (system alignment): existing and approved contracts suffice._

Task export: [JSONL artifact](/Users/Luca/.gstack/projects/LucaAlv-poliwatch/tasks-design-review-20261007-173727.jsonl).

## NOT in scope

- New acquisition, refresh schedules or next planned sitting information: this change describes the data already available.
- New analysis, summaries, search or ranking rules: the existing weekly content and comparison meet the requested destination.
- Global typography/identity work or a new `DESIGN.md`: already tracked separately; keep the present stack and palette.
- Broad “Sitzungswoche” terminology cleanup in unrelated facts/method pages: the existing TODO remains separate from the approved destination label.
- Dossier layout/active-key repair and favicon repair: baseline adjacent observations, outside this homepage change.
- Deployment, publishing or commits: this invocation delivers a reviewed plan.

## What already exists

- Python standard-library static rendering; reuse `render_landing_page`, `render_site`, `render_global_header` and `NAV_ITEMS`.
- Protocol/date/week helpers, German dates, generated dossier routes and the existing `puls.html#wochenvergleich` content.
- Shared light/dark variables, theme control, visited links, visible focus and semantic navigation.
- Existing rendering/navigation fixtures and the offline unittest suite; extend their behavioral contracts rather than introducing a new test framework.
- No `DESIGN.md`; its creation and typeface selection are already tracked in `TODOS.md`.

## TODO disposition

No new TODO proposals remain. All in-scope behavior and verification is in T1–T5. Existing system/typeface and terminology TODOs remain unchanged; no adjacent audit observation is silently promoted into implementation scope.

## Approval reconciliation and remaining decisions

Original requirements retained: replace vague homepage copy; provide a direct homepage-only latest-sitting route; rename and expose the weekly destination on the homepage and header. D3–D10 have individual user approvals, applied throughout this plan. D1 (focus) and D2 (reviewers) approve no remedies and are not counted as design decisions. No remedy relies on approval of a different issue.

No unresolved in-scope design decisions remain. The engineering review below validates renderer interfaces/data flow and specifies the native disclosure and required semantic/test proof before implementation. Rendered design quality must be checked after implementation; it is not established by this plan.

No durable learnings this session beyond the already recorded user decision and existing project contracts.

## Completion summary

| Review dimension | Before | After | Evidence / limits |
| --- | --- | --- | --- |
| Step 0 initial impression | 6/10 | — | Separate from the six-pass minimum |
| Pass 1 — information architecture | 7/10 | 10/10 | D3–D7 settle terminology, layout and competing blocks |
| Pass 2 — interaction states | 8/10 | 10/10 | State table; D8 empty-week recovery |
| Pass 3 — visitor journey | 10/10 | 10/10 | No issues found; accepted journey storyboard |
| Pass 4 — generic-design risk | 8/10 | 10/10 | D9 plain sections; all hard-rejection/litmus checks assessed |
| Pass 5 — design-system alignment | 10/10 | 10/10 | No new issues; existing contract recorded, broader system deferred |
| Pass 6 — responsive/accessibility | 8/10 | 10/10 | D4/D10 responsive rules and verification requirements |
| Pass 7 — decision register | Unscored | 8 resolved, 0 deferred | D3–D10 only; no unanswered finding |
| Overall scoped design completeness | **7/10** | **10/10** | Minimum of the six rated passes; not a rendered design-quality score |

Design-review completion status: **DONE_WITH_CONCERNS**. At that checkpoint, the design plan was complete within its stated scope. No mockups were generated or approved, Claude Code coverage is unavailable, engineering review is still required, and implementation/browser regression checks have not run. Five tasks exported; six explicit scope exclusions; no new TODOs or application changes.

## Engineering review

Fixed target/report: `docs/plans/frontpage-design.md`; reviewer: Codex primary; branch: `main`; session: `99231-1791387727-0cdb360e`. Planning only; D3–D10 design approvals remain fixed. Engineering question numbering starts at D1 and is separate from the completed design review.

### Scope Challenge disposition

Scope accepted as-is; FULL_REVIEW. Seven existing source/test files, no new service, class or dependency. The complexity-question threshold is not reached. No scope findings or reductions. The completed homepage design audit supplies the prerequisite design context. Claude Code remains unavailable as directed by the user; no external invocation has been attempted.

### 1. Architecture review

The static build remains the distribution boundary: `render_site` generates the homepage, weekly page and protocol destinations. Homepage and weekly selection will reuse `select_pulse_week` with the same existing `week` and `today` inputs; no acquisition or new route is proposed. The shared header/styles/scripts reach root and nested generated pages, so changes belong there rather than in per-page copies. No new auth, network integration or persistent preference is introduced.

**F1:** [P2] (confidence: 8/10) docs/plans/frontpage-design.md:147 — The proposed responsive disclosure's mechanism is not yet chosen. This is an implementation-plan gap, not a demonstrated deployed bug. Reviewer: Codex primary.

Motivating plan quote: “Engineering review must choose the smallest implementation that exposes all desktop links without duplicate navigation/current-page semantics.”

Existing source evidence, `scripts/render_dip_pulse_html.py:1000`:
```python
def page_scripts(selection: Selection | None = None) -> str:
    return ai_summary_runtime_script() + theme_runtime_script()
```
Existing source evidence, `scripts/render_dip_pulse_html.py:1018`:
```python
f'<nav class="site-nav" aria-label="Globale Navigation">{"".join(links)}</nav>'
```

A bounded Chrome DevTools platform probe on an isolated blank tab (closed afterward) found: closed native details hides its link; `details::details-content { content-visibility: visible; }` reveals it while `details.open` remains false. The link appeared in Chrome's accessibility snapshot and accepted focus. Setting native `open=true` also revealed the link and allowed focus. Driver/browser: Chrome 154; no project code was changed. This does not verify cross-browser or full assistive-technology behavior. [MDN documents ::details-content as newly available across current browsers since September 2025, with older-browser limitations](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/::details-content). [The existing matchMedia API provides viewport state and change observation](https://developer.mozilla.org/en-US/docs/Web/API/Window/matchMedia).

Disposition: R1 accepted through engineering D1=A. R2 was not approved through the mechanism question and was separately resolved by engineering D2=A. The approved reachable-links/visible-focus guarantee itself is already covered by design D10.

**Engineering D1 accepted:** use a small shared viewport listener through the existing `page_scripts()` hook to manage the single native disclosure's open state. Reuse the existing renderer and registry, add no dependency, and preserve the eight destinations, nested relative paths and one nav/current-page contract. This is a plan amendment only; no application edits are authorized by this selection. The CSS-only investigation was not selected.

**Engineering D2 accepted:** initially close the disclosure on a mobile visit; show all eight links at desktop width. On desktop-to-mobile transitions, close it unless a secondary link has focus, in which case leave it open. Do not remember earlier mobile choices or persist menu preferences. Verify both resize directions, the mobile-open → desktop → mobile reset and the focused-link exception. Preserve visible focus when the summary disappears at desktop width as required by design D10; validate the native control and focus handling in the real browser.

## Decision ledger

### R1: Responsive disclosure mechanism

Finding: F1, P2, confidence 8/10, docs/plans/frontpage-design.md:147, reviewer Codex primary.
Plan baseline: Design D10 approved one native disclosure below 1024px, two visible primary links, eight desktop destinations, one nav/current-page contract and reachable links/visible focus on resize. The mechanism is explicitly left for engineering review; none is approved.
Runtime evidence: The existing header has eight flat anchors and shared script hooks; the isolated Chrome 154 probe demonstrated both CSS visibility override and native open-state visibility. Other browsers/assistive technology remain unverified.

Comparison grid:

| Commitment | Current | A — shared script | B — CSS investigation | Approval |
| --- | --- | --- | --- | --- |
| R1 mechanism | Unspecified, pending | Choose small shared viewport listener controlling native disclosure state through page_scripts | Unspecified, pending; investigate CSS only | New choice D1 |
| R2 resize close/restore policy | Unspecified, pending | Unspecified, pending | Unspecified, pending | Independent, not selected here |
| Link destinations and semantics | Two primary links / six disclosed below 1024px; all eight desktop; one nav/current-page contract | Same approved contract | Same approved contract | Design D10 |
| Native keyboard, reachable links and visible focus | Required; implementation proof outstanding | Required; same proof retained | Required; investigate against same contract, proof outstanding | Design D10 |
| Shared renderer and existing routes | Existing shared header; nested prefixes preserved | Reuse shared renderer/hooks and routes | Same boundary; investigation changes no app code | Approved plan boundaries |
| Dependencies/preferences | No new dependency or persisted preference | None | None | Approved plan |
| App implementation authority | Planning only | Planning only; no application edits | Planning only; no application edits | Original invocation |
| Investigation bound | None | No optional CSS investigation | At most 20 minutes; no conditional implementation | New bound belongs to B |
| Work | Mechanism unresolved | Human ~45min / CC ~10min including required checks | Human ~20min / CC ~20min; remedy still pending | D1 estimates, not completion claims |

Question D1:

D1 — How should the shared header adapt?

Reply **A** or **B**.

Project/branch/task: poliwatch / main / homepage engineering plan.

ELI10: The approved header must show all eight links on desktop and collapse six into “Weitere Bereiche” on smaller screens. The plan leaves the implementation open (docs/plans/frontpage-design.md:147). Chrome can reveal the closed disclosure with newer CSS, but that probe does not establish older-browser or screen-reader behavior.

Stakes: A poorly chosen mechanism could hide desktop destinations or make the visible navigation disagree with its accessible state.

Recommendation: **A**, because a small shared script can use the native disclosure state and the existing script hook without adding a dependency.

Note: options differ in kind, not coverage — no completeness score.

Header: Header mechanism

Options:

A) Shared native-state script (recommended)

Add a small viewport listener through the existing `page_scripts()` hook to manage one native disclosure, preserving the approved eight links, one navigation landmark and current-page semantics. This uses established browser APIs and reuses the shared renderer; the cost is a little JavaScript to maintain (human: ~45min / CC: ~10min, including required checks). The separate policy for closing/restoring the disclosure and retaining focus on resize remains pending; this selects the mechanism in the plan and does not authorize application edits.

B) Investigate CSS first

Spend at most 20 minutes probing a CSS-only approach against the approved visibility, keyboard and accessibility requirements, without editing application code. This might eliminate the viewport script, but the current Chrome result alone cannot establish compatibility and the investigation may end without a viable solution (human: ~20min / CC: ~20min). The mechanism and resize policy remain pending; any implementation choice returns for a decision.

Net: choose a small native-state script now, or spend a bounded investigation trying to remove it.

State: approved
Actual answer: A — Shared native-state script (recommended), user's latest typed reply on 7 October 2026 to engineering D1.
Accepted scope: choose the small shared viewport listener through page_scripts controlling the one native disclosure; retain all design D10 semantics and required checks. Planning only; no application edits or optional CSS investigation. R2's separate approval is engineering D2=A, not part of D1's scope.
History: initial state pending, unanswered, no mechanism approved. No earlier engineering mechanism choice. At the D1 answer R2 remained pending; it was later resolved independently by D2=A.

### R2: Resize close/restore policy

Finding: F2, [P2] (confidence: 8/10) docs/plans/frontpage-design.md:155 — Resize visibility/focus is approved, but the native disclosure's close/restore policy is unspecified. Reviewer: Codex primary. This is a proposed-path planning gap, not a deployed bug.
Motivating quote: “Resizing across the breakpoint must keep links reachable and focus visible.”
Plan baseline: Design D10 establishes initial collapsed mobile disclosure, eight visible desktop links and visible focus on resize. Engineering D1=A selects the shared native-state script and explicitly leaves R2 pending. No mobile state restoration policy has been approved.
Runtime evidence: Existing render_global_header at scripts/render_dip_pulse_html.py:1004 emits flat links with no disclosure. No proposed viewport listener exists; actual resize behavior of that future listener is unknown. Native open-state visibility/focus was verified only in the preceding bounded Chrome probe.

Comparison grid:

| Commitment | Current | A — close on mobile | B — remember mobile state | Approval |
| --- | --- | --- | --- | --- |
| R2 desktop-to-mobile transition | Unspecified, pending | Close unless a secondary link has focus | Restore last mobile state unless it would hide a focused link | New choice D2 |
| Initial mobile visit | Disclosure closed | Closed | Closed | Design D10 |
| Desktop visibility | All eight destinations visible | All eight visible | All eight visible | Design D10 |
| Focus when closing would hide it | Must remain visible | Keep disclosure open | Keep disclosure open | Required proof/implementation of design D10; no separate optional guarantee |
| R1 mechanism | Shared native-state viewport script | Same script hook | Same script hook | Engineering D1=A |
| Native semantics/routes/themes | One nav/current-page contract; native disclosure, same routes/theme | Unchanged | Unchanged | Design D10 and approved plan |
| State/persistence | No persisted menu preference | No remembered mobile choice | One in-memory mobile choice; no storage or persistence | R2 implementation alternative; persistence ban design D10 |
| App edit authority | Planning only | Planning only | Planning only | Original invocation |
| Required checks | Initial mobile, desktop, both resize directions and focused secondary link | Same checks, including reset after mobile-open → desktop → mobile | Same checks, including restore for both open/closed mobile choices | Necessary proof of D10/R2 |
| Effort | Policy unresolved | Human ~30min / CC ~8min including checks | Human ~45min / CC ~12min including checks | Estimates only |

Question D2:

D2 — What happens when desktop becomes mobile?

Reply **A** or **B**.

Project/branch/task: poliwatch / main / homepage engineering plan.

ELI10: The approved script will show all eight links on desktop. When the window becomes narrower than 1024px, the plan does not say whether “Weitere Bereiche” should close or remember its earlier mobile state (docs/plans/frontpage-design.md:155). Both options start closed on an initial mobile visit and keep the disclosure open whenever closing it would hide the currently focused link.

Stakes: Resize handling must not hide keyboard focus or unexpectedly leave navigation inaccessible.

Recommendation: **A**, because it needs less state and gives the compact header a predictable default.

Note: options differ in kind, not coverage — no completeness score.

Header: Resize behavior

Options:

A) Close on mobile (recommended)

When crossing from desktop to mobile width, close “Weitere Bereiche” unless one of its links currently has keyboard focus; in that case keep it open so focus remains visible. This avoids remembering previous menu choices and is simpler to maintain, but a visitor who previously opened the mobile disclosure will need to reopen it after a desktop round trip (human: ~30min / CC: ~8min, including required resize checks). Keep the approved shared native-state script and all existing design contracts; this updates the plan only.

B) Remember mobile state

Remember the visitor’s last open/closed mobile choice in memory and restore it after a desktop round trip, keeping the disclosure open whenever restoration would hide the focused link. This preserves the visitor’s earlier choice without storage or persistence, but adds a small amount of state and extra transitions to verify (human: ~45min / CC: ~12min, including required resize checks). Keep the approved shared native-state script and all existing design contracts; this updates the plan only.

Net: use a simple compact default on each mobile transition, or preserve the visitor’s earlier mobile choice.

State: approved
Actual answer: A — Close on mobile (recommended), user's latest typed reply on 7 October 2026 to engineering D2.
Accepted scope: on desktop-to-mobile transitions close the disclosure unless a secondary link has keyboard focus, then keep it open. Initial mobile visit starts closed. Do not remember mobile choices or persist state. Retain D1's shared script, all design contracts and required resize checks. Planning only; no application edits.
History: R2 was separated from R1 before D1 and explicitly remained pending after D1=A; initial R2 state pending, unanswered, no resize policy approved.

### Architecture disposition and execution flow

F1 (mechanism) accepted by engineering D1=A; F2 (resize policy) accepted by engineering D2=A. Two architecture planning gaps found, both resolved. No additional architecture issues found. Existing sorting, generated protocol routing, week selection and the static publication pipeline remain the boundaries; no new service, runtime data fetch, database write or deployment procedure is introduced.

```text
Existing offline/demo build
  -> render_site(entries, protocols, today, week)
       -> newest-first generated entries (existing entry_sort_key)
       -> render_landing_page [proposed today/week keywords]
       |    -> no entries? empty latest-sitting message + overview link
       |    -> entries? first generated entry
       |    |    -> entry_protocol -> sitting_label (document or page-stem)
       |    |    -> format_date/time_html (valid date or no invented date)
       |    |    -> dossier_href -> direct local protocol link
       |    -> resolve_today (explicit date/datetime > epoch > local date)
       |    |    -> bad epoch? existing ValueError; no silent fabricated date
       |    -> select_pulse_week -> group_entries_by_week -> iso_week_key
       |    |    -> unusable date? exclude from weekly grouping
       |    |    -> explicit unavailable week? existing ValueError
       |    |    -> no dated week? D8 empty message + overview link
       |    |    -> selected week? ISO period + actual included sitting count
       |    |         -> explicit week? local "Ausgewählte Woche"
       |    |         -> running? "bisher erfasst"; otherwise latest recorded period
       |    |         -> closest earlier week within MAX_WEEK_GAP?
       |    |              yes: comparison description/action
       |    |              no: overview description/action only
       |    -> optional data artifact? link + stand : omit that content link
       |    -> escaped German copy / main / ordered plain sections -> index.html
       -> render_front_page [existing weekly renderer] -> same selector -> puls.html
       |    -> existing topic/comparison logic and #wochenvergleich retained
       -> existing generated protocols / overview / other destinations
       -> offline publication validation (existing CI/demo check)

Every generated page
  -> NAV_ITEMS -> render_global_header(depth, active)
  -> one nav: two primary anchors + details(summary, six secondary anchors)
  -> global_header_styles + existing theme hooks
  -> page_scripts -> small native-state viewport listener [D1]
       -> no header/disclosure on page? return without affecting other scripts
       -> initial width <1024? closed; >=1024? open / all links visible
       -> native mobile summary click / Enter / Space -> native toggle
       -> crossing into desktop -> expose all eight; preserve visible focus
       -> crossing into mobile [D2]
            -> secondary link focused? keep open
            -> otherwise close; no remembered choice / storage
```

Only the landing-page anatomy comment needs an inline update: its current hero/stat-band/principles map will be obsolete after T2. The new viewport listener should carry a short transition comment; no architecture document or new diagram module is needed.

### 2. Code Quality review

No additional issues found. Disposition: reuse existing owning functions; no extraction or architecture rewrite proposed.

- Existing callers are verified: `render_site` calls `render_landing_page` at builder:9990 and `render_front_page` at :10002. Passing the same existing `today`/`week` keywords is required by the approved matching-period contract; it does not introduce a second clock or week model.
- Existing `select_pulse_week` (builder:4658), `group_entries_by_week` (renderer:1209), `week_span` (:1198) and `MAX_WEEK_GAP` (:1152) supply selection and comparison eligibility. Use only the needed period/count information for the homepage; do not invoke topic ranking, generate new summaries or rebuild the whole weekly page inside it.
- Header reuse has real root/nested callers: builder:3993/4038 (homepage header/scripts), :5553/5572 (weekly), :4251/4267 (nested votes), and renderer:3818/3857 (dossier). Shared native state must not change each caller's active key, relative prefix, AI-summary controller or theme controller.
- `dossier_href`, `entry_protocol`, `sitting_label`, date helpers and `esc` already define the output contract. No new latest-route resolver, registry, cache or configuration is needed. Generated content still gets escaped; generated relative paths stay in the existing trusted build boundary.
- Remove the retired homepage CSS together with its markup and update its anatomy/docstring. Keep current renderer arguments such as archive counts unless removing them is necessary; avoid expanding into external-caller compatibility changes.
- No shared extraction is accepted: similar date/period rendering alone does not justify a new abstraction. The shared header is already centralized. Net line savings are not claimed; the small disclosure/script and regression coverage add lines while the approved homepage removals delete larger blocks.

Factual test-location correction (no new behavior/approval): the builder's period and wiring tests live in `tests/test_build_dip_pulse_site.py`, not the generic renderer test file. T4 will extend that existing file instead of planning changes to `tests/test_render_dip_pulse_html.py`. Source/test scope stays seven files. Existing helper tests remain in the full suite.

### 3. Test review

Framework: Python standard-library unittest, per AGENTS.md. Supported local command: `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`. CI additionally compiles scripts and builds/validates the zero-network demo on Python 3.11–3.13. This review reads tests; it does not implement or execute proposed checks.

The following seven groups are verification gaps for **proposed behavior**. They are already required by the original homepage request and approved design D3–D10 / engineering D1–D2; no new runtime policy or optional proof depth is added. Multiple assertions in a group belong to the same observable contract. Existing helper coverage is distinct from future homepage integration coverage.

```text
CODE PATHS                                      USER FLOWS / PROPOSED PROOF
render_site -> homepage + weekly output
  [G4 GAP] same clock/week threaded               G4: cache/demo build, compare both periods
  [★★★ TESTED] weekly-only wiring                builder tests:2796; extend, do not duplicate
render_landing_page [proposed output]
  [G1 GAP] latest href / empty / undated          G1: homepage -> exact generated protocol
  [G2 GAP] default / pinned / running / empty     G2: homepage -> matching weekly period
  [G3 GAP] comparison availability / 12wk bound   G3: comparison promise matches destination
  [G5 GAP] copy / removed blocks / main order     G5: scan two period entries and other routes
  [★★ TESTED] optional data link + stand         data pipeline tests:428; preserve/extend
Reused period helpers
  [★★★ TESTED] selection, unavailable, undated    builder tests:2665
  [★★★ TESTED] clock, bad epoch, reproducibility  builder tests:2720–2767
  [★★★ TESTED] weekly empty/partial/comparison    builder tests:3297–3368, 3598–3640
Shared header
  [★★ TESTED] registry / prefixes / one current  features:12; global_header:34,42,92
  [G6 GAP] one set of 2+6 links / group state     G6: root + nested callers keep destinations
Shared native-state listener [proposed]
  [G7 GAP] mobile/desktop/toggle/resize/focus     G7: [->E2E] browser keyboard and resize journey
Themes/layout/destination reachability
  [G7 GAP] widths, light/dark, zoom, links        G7: [->E2E] generated-page browser inspection
```

Legend: ★★★ = behavior plus edge/error coverage; ★★ = behavioral happy-path coverage; GAP = missing coverage of planned behavior. Seven unique gap groups G1–G7; repeated G7 rows are not counted twice. This is a contract map, not a measured line/branch coverage percentage. Proposed tests are not counted as existing coverage. No LLM/prompt change or eval is in scope; existing AI labels/controllers are retained.

**G1 / F3:** [P1] (confidence: 8/10) scripts/build_dip_pulse_site.py:3731 — new latest-protocol link needs homepage-output regression coverage. Motivating quote: `# dossier (entries are ordered newest-first by render_site), or a placeholder`. Extend builder rendering fixtures to assert the exact generated href/date/document, catalog-newer-without-dossier exclusion, empty recovery and undated/no-invented-date behavior. Preserve existing ordering rather than inventing a new latest algorithm.

**G2 / F4:** [P1] (confidence: 8/10) scripts/build_dip_pulse_site.py:9991 — homepage selected-week output is not covered by weekly helper tests. Motivating quote: `render_landing_page(`. Add rows for default, explicit historical selection, running/partial week, no generated entries and all-undated entries; compare homepage period/count with `puls.html` under the same inputs. Unknown week/bad epoch behavior stays the selector's existing error contract.

**G3 / F5:** [P1] (confidence: 8/10) scripts/build_dip_pulse_site.py:5123 — homepage comparison promises need the destination's actual eligibility boundary. Motivating quote: `if earlier and pulse_html.week_span(earlier[-1], selected_week) <= pulse_html.MAX_WEEK_GAP:`. Add one-week/no-earlier, nearest earlier, exactly 12-week and 13-week rows; omit comparison text/action when unavailable. Do not change matched-day comparisons or require new deltas.

**G4 / F6:** [P1] (confidence: 8/10) tests/test_build_dip_pulse_site.py:2810 — existing wiring proof observes only the weekly renderer. Motivating quote: `mock.patch.object(build_dip_pulse_site, "render_front_page", return_value="<html></html>") as front,`. Extend the existing wiring check to both renderers and use an unmocked pinned fixture to catch homepage metadata drift. Same clock/epoch must produce the same homepage bytes; no production testing seam.

**G5 / F7:** [P2] (confidence: 8/10) scripts/build_dip_pulse_site.py:3858 — the retired page anatomy needs output checks for the approved replacements. Motivating quote: `#   block 2     -> the principle cards`. Assert one main/H1, sitting-before-week DOM order, descriptive labels and removal of the requested blocks. Do not lock incidental class names, whitespace or every CSS declaration.

**G6 / F8:** [P1] (confidence: 8/10) tests/test_global_header.py:46 — the existing flat-nav matcher does not cover the proposed multiline disclosure structure. Motivating quote: `nav = re.search(r'<nav[^>]*>(.*?)</nav>', markup).group(1)`. Extend the existing contract using stdlib HTML parsing or a multiline-aware matcher: exactly eight unique ordered nav destinations; two primary/six secondary; native summary; one current link for primary and secondary active cases; active group visual hook; depth 0/1/2. Keep theme controls and fixed registry routes. A source-string assertion for "matchMedia" is insufficient behavior proof.

**G7 / F9:** [P1] (confidence: 8/10) docs/plans/frontpage-design.md:155 — generated text tests cannot prove the accepted native keyboard/focus/viewport behavior. Motivating quote: “Closed content must not remain in the tab order.” T5's already-approved Chrome DevTools browser proof covers initial 375/768/1440, 1023/1024 crossings, native Tab/Enter/Space, hidden links out of tab order, focused secondary-link exception, summary focus entering desktop, mobile-open round trip reset, themes, 200% zoom, contrast and nested callers. Exercise visible output and focus, not only script presence. No new browser framework is required.

Dispositions: all seven gaps accepted as necessary regression proof of the exact approved contracts (G1–G5 original request/design D3–D9; G6–G7 design D10 and engineering D1=A/D2=A). Extend T4/T5; do not reopen those approvals. Existing optional-data coverage stays required. No new test-choice question or test framework. Tests made obsolete: no whole test retirement proposed; update old label assertions and card-identification assertions in place while retaining their route/availability/stand invariants.

### 4. Performance review

No issues found. Disposition: keep the existing static-build architecture.

No new per-request database work, API call, server process or cache. The homepage needs one period grouping/selection over the existing generated entries plus a few metadata fields; it should not repeat weekly topic ranking/comparison aggregation. Grouping sorts each week's entries and is bounded by the existing archive; no throughput benchmark is claimed. A viewport listener runs on initialization and breakpoint changes, not per animation frame, with eight navigation destinations. No polling, resize-loop measurement, observers or animation dependency is needed. A few extra shared script bytes are unmeasured; verify no new requests/errors in T5 rather than adding a benchmark project.

### Failure modes

| New/revised path | Realistic failure | Handling / user-visible result | Required proof |
| --- | --- | --- | --- |
| Latest generated protocol route | Newer catalog row is mistaken for an available dossier | Link only the existing generated-entry route; empty state offers archive; qualify “zuletzt verfügbar” | G1 exact href and unavailable-catalog fixture; T5 click |
| Homepage week metadata | Pinned week/clock is not forwarded; homepage describes a different period | Use the same existing selector/input contract; preserve unknown-week/clock errors | G2/G4 paired output and existing error tests |
| Comparison wording | Lone week or >12-week gap still promises comparison | Omit comparison promise/action; existing weekly page explains available period | G3 boundary rows, T5 destination |
| Compact nav rendering | Duplicate links/current page or wrong nested prefix | One registry-built link set and current-key contract | G6 parsed output, root/nested caller checks |
| Native-state runtime | Missing disclosure or script failure makes CSS hide the only recovery control | Guard missing element; keep native summary reachable until successful desktop state exposes its links. Preserve native recovery if initialization does not complete | G7 inspect native fallback, normal desktop, keyboard and console |
| Resize transition | Focused secondary link disappears or focused summary is hidden | D2 keeps focused secondary disclosure open; D10 requires visible focus on the desktop transition too | G7 focus and active element in both directions |
| New plain sections | Theme selector misses text/controls or narrow page overflows | Token-based colors and existing focus/theme controller; user can still identify labeled destinations | G5 semantics and G7 themes/reflow/contrast |
| Offline/static distribution | Generated target is missing or publication contains development artifacts | Existing publication validation and zero-network demo pipeline; no new publisher | Required existing CI/demo checks and T5 links |

Zero critical gaps: every realistic silent-failure risk above has required proof and handling in the approved implementation plan. This is a review of planned protection, not evidence those implementations or tests have passed.

### Worktree parallelization strategy

Sequential implementation, no parallelization opportunity. T1/T2/T3 share the builder and shared rendering contracts; independent lanes would contend in the same modules. Implement T1 → T2 → T3, extend T4 alongside the owning behavior, then run the complete suite/demo and T5 after rebuilding. No worktrees or extra agent orchestration are needed.

### Outside Voice — unavailable

Outside voice is the standard enabled step; disable with `gstack-config set codex_reviews disabled`. The user already reported Claude Code's reached rate limit, so its external invocation is skipped as directed. The required native Plan/TaskOutput/TaskStop capability set is not present in this host's tool definitions; per the skill's unavailable route, no general-purpose replacement is dispatched. No reviewer completed this engineering outside phase; source=none, host=codex, outside_provider=claude-code, outside_status=unavailable. The earlier Luna design review and narrow header exploration do not count as an engineering outside challenge. No cross-model consensus or clean outside credit is claimed.

### TODO disposition and approval readiness

No new TODO proposals: all in-scope requirements are T1–T5 and the G1–G7 proof above. Retain the previously deferred product identity/typeface, broad terminology, dossier active-key and favicon observations. Do not edit TODOS.md.

Approval readiness: PASS — R1 engineering D1=A, R2 engineering D2=A, design D3–D10 and original descriptive-copy/direct-protocol requirements reconciled against the working plan. G1–G7 carry necessary regression proof of those exact contracts; no independently selectable runtime policy or optional verification depth was added. No unresolved decisions in this engineering review.

### Engineering completion summary

- Step 0 / Scope Challenge: scope accepted as-is; FULL_REVIEW.
- Architecture: 2 planning gaps, resolved by D1=A and D2=A.
- Code Quality: 0 additional issues; existing helpers/shared header reused.
- Test Review: diagrams produced; 7 proposed-behavior coverage gaps mapped into T4/T5, no unapproved test policy.
- Performance: 0 issues; no new runtime request or cache.
- NOT in scope / What already exists: written above; original exclusions retained.
- TODOS.md: 0 new proposals.
- Failure modes: 0 critical gaps in the approved plan.
- Unresolved decisions: 0 in this engineering review.
- Outside voice: Claude Code unavailable; no invocation as directed; native fallback capability unavailable; missing engineering outside coverage.
- Parallelization: 1 sequential lane, 0 parallel.
- Lake Score: N/A (0 scored coverage options; both engineering questions differ in kind).
- Total four-section findings: 9 (2 architecture + 7 test gaps); all mapped to approved work. Status `issues_open` counts resolved/mapped findings per skill; it does not mean unanswered decisions.
- Verification limitation: application code and proposed tests remain unimplemented. No suite/demo rebuild or after-design browser QA was run during this planning review.

### Suppressed findings

None. No speculative deployed bug, benchmark, data-loss claim or unsupported extraction is promoted into the report.

### Engineering artifact references

- [QA test plan](/Users/Luca/.gstack/projects/LucaAlv-poliwatch/Luca-main-eng-review-test-plan-20261007-181340.md) — G1–G7 acceptance and edge-case value cards, saved and read back.
- [Engineering task export](/Users/Luca/.gstack/projects/LucaAlv-poliwatch/tasks-eng-review-20261007-181340.jsonl) — three refinements to existing T3/T4/T5; T1/T2 remain the approved design tasks, not duplicated as new engineering findings.

### Review navigation — D3

All relevant planning reviews are complete. Run /ship when ready after implementation and its required checks. Only the ready-to-implement route applies; no new CEO/DX review or repeat design review is needed for this unchanged scope.

D3 — Close the planning review?

Reply **A** to finish, or describe a change you want to the plan.

Project/branch/task: poliwatch / main / homepage plan.

ELI10: The plan now has no unanswered design or engineering decisions. The remaining work is implementation and the checks already listed in T1–T5. This selection closes the planning review only.

Stakes: The implementation still needs its regression and browser checks before it can be cleared.

Recommendation: **A**, because the relevant planning reviews are complete.

Note: this is navigation only, not a coverage choice.

Header: Next step

A) Ready to implement (recommended)

Finish the planning review with the five reviewed tasks and saved QA checklist. Retain the recorded sequence: T1 → T2 → T3, extend T4 alongside each owning change, then run the suite/demo and T5 after rebuilding. This selection authorizes no application edits, commits or deployment; run /ship when the implementation is done.

Net: finish planning with the reviewed implementation and validation tasks.

Navigation checkpoint (report-write time): awaiting user reply; not an implementation remedy or unresolved design/engineering decision. No implementation authority is granted by this route.

_No new implementation tasks from Scope Challenge, Code Quality or Performance. Engineering task export refines existing T3/T4/T5 only._

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| CEO Review | /plan-ceo-review | Scope and strategy | 0 | Not run | No significant product-direction change in this homepage scope |
| Outside Review | codex-plan-review / Claude Code | Engineering independent challenge | 3 repository records; 1 for this plan | UNAVAILABLE | Current host Codex, provider Claude Code; external skipped as directed, native fallback unavailable; no completed engineering challenge |
| Eng Review | /plan-eng-review | Architecture and tests — required | 3 repository runs; 1 for this plan | ISSUES OPEN (PLAN) | 9 mapped findings: 2 architecture decisions resolved, 7 required proof groups; 0 critical gaps, 0 unresolved decisions; implementation/testing pending |
| Design Review | /plan-design-review | UI/UX decisions | 1 | CLEAR — scoped plan | Six-pass minimum 7/10 → 10/10; 8 approved design decisions retained; engineering additions do not reopen them |
| DX Review | /plan-devex-review | Developer experience | 0 | Not applicable | No new developer-facing workflow |
| Rendered baseline audit | /design-review / Chrome DevTools | Existing homepage evidence | 1 | DONE_WITH_CONCERNS | B design / C generic-design score; no after-implementation score |
| Implementation verification | T4/T5 | Functional and rendered checks | 0 | Pending implementation | Application code/test execution and after-design browser QA remain future work |

**OUTSIDE COVERAGE:** engineering phase host Codex, outside_provider Claude Code, outside_status unavailable, source none. The user reported the reached rate limit; no external invocation was attempted. Native Plan/TaskOutput/TaskStop fallback tools are unavailable. The earlier native GPT-6 Luna design review completed its design phase; it supplies no engineering outside completion. Prior repository engineering outside records retain their recorded provenance (19 September host Claude/provider Codex completed for other scope; 4 October host Claude/provider Codex unavailable). No cross-model consensus is claimed.

**VERDICT:** DESIGN CLEARED within the approved scope; engineering planning review completed with nine findings mapped to implementation/proof. The historical readiness dashboard is NOT CLEARED because the current engineering status is ISSUES OPEN; eng review required for implementation clearance. There are no further unanswered planning choices. Implement the reviewed tasks, then verify their output.

NO UNRESOLVED DECISIONS
