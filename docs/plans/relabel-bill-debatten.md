# Relabel bill-page “Debatten”

Status: implementation plan only, 2026-10-21.
Branch: `plan/relabel-bill-debatten`.
Backlog: `TODOS.md`, “Stop calling a Plenarstelle a Debatte on the bill pages” (currently line 441; formerly referenced as line 475).

## Decision and scope

Relabel the existing records as **Beratungen im Plenum**. Keep the current count and list semantics: every collected `protocol_refs` entry counts, including an entry with zero or missing `speech_count`. Filtering by speeches would hide legitimate recorded treatment of a bill and introduce a different metric.

`CONTEXT.md` defines a Plenarstelle as one Tagesordnungspunkt in one Sitzung at which a Vorgang was dealt with; it explicitly rejects “Debatte” as a synonym. Use `#plenarstellen` as the new section anchor. Keep the existing section position, document links, dossier/TOP links, speech counts and collection/deduplication logic.

This is a presentation change. No schema, cache, export, dependency, configuration or acquisition changes are needed. Existing `#debatten` fragments will stop resolving; use the new anchor directly, following the project's pre-release policy in `CLAUDE.md`, without a compatibility alias.

## Implementation

1. **Update the bill renderers in `scripts/build_dip_pulse_site.py`.**
   - In `render_bills_index`, keep `len(bill.get("protocol_refs") or [])`; change the singular/plural labels to “Beratung im Plenum” / “Beratungen im Plenum”. Preserve the existing escaping of the combined count string.
   - In `render_bill_detail`, change the navigation tuple and section ID to `plenarstellen`, and both visible labels to “Beratungen im Plenum”.
   - Change the supporting aside's accessible label to “Beratungen im Plenum und Beteiligte”.
   - Use the empty-state copy “Keine Beratungen im Plenum in den erfassten Daten verknüpft.”
   - Replace the section explanation with: “Jeder Eintrag verknüpft einen Tagesordnungspunkt einer Sitzung, an dem dieses Vorhaben behandelt wurde – auch ohne erfasste Rede. Ein gemeinsamer Tagesordnungspunkt kann mehrere Vorhaben betreffen.” Render “Tagesordnungspunkt” with the existing `render_parliamentary_term` helper and a unique tooltip ID, such as `plenarstellen-top`. The definition stays visible without JavaScript; the existing glossary supplies additional detail on hover/focus and through its native link.
   - Change the Gesetzesvorhaben discovery-card description in the same file from “Debatten, Drucksachen und Verfahrensschritte zu einem Vorhaben.” to “Beratungen im Plenum, Drucksachen und Verfahrensschritte zu einem Vorhaben.”
   - Keep internal `debates` variables, `.bill-debates` styles and existing per-entry tooltip IDs: renaming them adds no user benefit. Other uses such as “Debattenprofil” and the site's general title are outside this task.

2. **Update and extend existing coverage.**
   - In `tests/test_bills.py`, update the expected section IDs in `DetailRenderTests.test_generated_detail_has_reading_order_and_expanded_speakers`, both section-splitting delimiters in `test_detail_tooltip_ids_timeline_grouping_and_unsafe_event_urls`, and the empty-state copy in `test_bare_bill_detail_and_empty_overview_degrade_to_readable_states`.
   - Add one small regression using existing bill fixtures: exercise zero, one and multiple protocol references, including `speech_count=0`, a positive count and a missing count. Assert the overview's singular/plural copy and total, all detail entries and their dossier links remain present, the new heading/navigation target match, and the zero-speech explanation is visible. This protects against accidentally filtering records while relabeling.
   - Reuse `test_every_glossary_link_on_bill_pages_resolves_to_a_sources_page_anchor` and the existing tooltip-ID checks to cover the added explanation link. No new glossary entry or tooltip implementation is needed.
   - In `tests/bills_browser_check.js`, change the expected section sequence to `verlauf,plenarstellen,redner,abstimmungen,dokumente,quellen`. Extend the existing detail check to assert that the new navigation link resolves to the section and the visible heading matches. Reuse the current generated browser fixtures and desktop/mobile checks.

3. **Align documentation when implementation is complete.**
   - Update the current section labels/order and diagram in `docs/designs/gesetzesvorhaben.md`. Add a brief note that this terminology correction supersedes the earlier “Debatten” label while retaining D3's accepted section order.
   - Add wording to the next release's `CHANGELOG.md` entry: “Bill pages now label linked plenary records as ‘Beratungen im Plenum’, including records without speeches; counts are unchanged and the section anchor is now #plenarstellen.” Leave historical release entries intact.
   - Mark the matching `TODOS.md` item completed only after validation, linking this plan and recording the actual result. Do not close adjacent bill-overview polish work.

## Validation and acceptance

Run from the repository root after implementation:

```sh
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p test_bills.py
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests
node tests/run_bills_browser_check.mjs /opt/miniconda3/bin/python3.13
```

The browser command is the existing local fixture harness documented in `CONTRIBUTING.md`; it requires Node 22+ and Chrome/Chromium. If additional interactive diagnostics are needed, use Chrome DevTools MCP per `AGENTS.md`.

Acceptance: overview counts equal the unchanged number of protocol references; zero-speech entries remain linked; copy and accessible labels no longer call those records Debatten; navigation resolves to `#plenarstellen`; empty states remain readable; glossary links resolve; source order and mobile/desktop layout checks pass. Confirm the change contains no edits to collection, persisted data or count calculations. No data migration or old/new data-count audit is needed because only labels and a section fragment change.

## Planning verification

Inspected the TODO, domain definition, renderers and their reference collector, glossary helper, unit tests, browser assertions, contribution instructions, CI and bill design document. A focused read-only subagent checked test/harness scope; findings were checked against source. The local graph query was used for initial navigation; source code supplies the current details.

No implementation, tests, browser run, release bump or publication was performed during planning. The known compatibility effect is the intentional replacement of `#debatten`.

## Engineering review, 2026-10-21

Target and report destination: `docs/plans/relabel-bill-debatten.md`.
Evidence revision: `6941158`; original proposal above preserved. This review authorizes no implementation.

### Scope Challenge

No issues found. Scope accepted as-is. Six proposed changed files, counted from Implementation steps 1–3: one renderer module, two test files, design documentation, changelog and TODO file. No new classes/services. The complexity selector does not apply.

Premise receipts:

| Premise | Receipt | Verdict |
| --- | --- | --- |
| Overview counts every protocol reference | `scripts/build_dip_pulse_site.py:6776`, `len(bill.get("protocol_refs") or [])` | verified |
| Detail lists every reference without speech filtering | `scripts/build_dip_pulse_site.py:6953`, `for index, ref in enumerate(bill.get("protocol_refs") or []):` | verified |
| Domain rejects Debatte for a Plenarstelle | `CONTEXT.md:181`–183 | verified |
| Existing glossary supports the proposed explanation | `scripts/render_dip_pulse_html.py:415`, `:493` | verified |
| Old fragment compatibility can be dropped | `CLAUDE.md:1`, pre-release policy | verified |
| Browser harness covers desktop/mobile detail fixtures | `tests/run_bills_browser_check.mjs:101`–103 | verified |
| Latest remote main has not already implemented this | Remote fetch failed: cannot open `.git/FETCH_HEAD`, operation not permitted | unverified |

REALITY: premise-table pass Source-backed premise table above; unverified=1 docs/plans/relabel-bill-debatten.md:9
REALITY: already-done pass Current source still emits Debatten; cached origin/main history has no matching new change; remote freshness unverified scripts/build_dip_pulse_site.py:7010
REALITY: surface-check pass Python runtime and documented unittest/browser commands checked against existing harness CONTRIBUTING.md:13
REALITY: binding-decisions pass Preserve selected metric and intentionally replace fragment under pre-release policy docs/plans/relabel-bill-debatten.md:9
REALITY: numbers pass Six proposed files enumerated in implementation; no timing or speedup claims docs/plans/relabel-bill-debatten.md:17
REALITY: deferred-asks pass No linked issue; TODO request covered, adjacent overview polish excluded TODOS.md:441
REALITY: pr-count pass One presentation change, one PR; no split proposed docs/plans/relabel-bill-debatten.md:13

Existing design context: `docs/designs/gesetzesvorhaben.md`, especially D3 reading order and historical implementation evidence. The discovered CEO plan belongs to another branch and was not used. Brain context unavailable because its cache refresh requires writes outside the sandbox. Prior learning applied: `node-websocket-version-docs` (confidence 10, 2026-10-20); use the documented Node 22+ minimum.

### 1. Architecture review

No issues found. Dispositions: none required. [Layer 1] Reuse the renderer and existing glossary helper; no new architectural pattern needs research. Source records, deduplication, persistence and exports retain their current contracts. Existing escaped text and URL validation remain in place. Build/publish uses existing generated pages and CI, with no new artifact channel.

```text
Collected protocol_refs (unchanged)
  +--> render_bills_index --> len(refs or []) --> format_count --> escaped summary
  +--> render_bill_detail
         +--> every ref --> source link or plain sitting label
         |                 --> date or missing-date fallback
         |                 --> TOP glossary label or existing other label
         +--> no refs --> readable empty state
         +--> section/nav --> #plenarstellen
         +--> explanation --> existing glossary helper
                                +--> JS hover/focus help
                                +--> native sources link without JS
Reader: overview title --> bill detail --> section navigation --> sitting/TOP link
```

Realistic failure: mismatched section/nav fragments leave the reader at the wrong place. Planned unit assertions and existing browser harness cover the new target. Unsafe existing source URLs still fail publication explicitly. Missing refs retain a readable empty state. No new integration or silent critical failure path is introduced.

### 2. Code quality review

No issues found. Dispositions: none required. Preserve internal `debates`, CSS classes and per-row tooltip IDs. An extraction has no benefit for this literal-label change. Existing `format_count`, `esc`, `render_parliamentary_term` and `_bill_event_href` own the relevant contracts. The new explanation ID is distinct from existing `debate-N` IDs. Existing tooltip uniqueness and source-anchor tests traverse the generated detail, so they cover the added helper invocation. Update the design diagram as already planned; retain historical decisions with an explicit superseding note.

### 3. Test review

Framework: standard-library unittest, authoritative `AGENTS.md:3`. Dedicated source/test reads covered the renderer, fixtures, glossary tests, empty states and browser assertions before this diagram.

```text
CODE PATHS                                      USER FLOWS
Overview count                                  Overview --> detail
  [GAP, PLANNED] zero/one/multiple new labels      [★★ TESTED] title detail links
Detail reference loop                           Detail section navigation
  [GAP, PLANNED] zero/positive/missing speeches    [GAP, PLANNED] new target + heading
  [★★★ TESTED] missing metadata/plain links     Desktop/mobile reading
  [★★★ TESTED] TOP/other labels + unique IDs       [★★★ TESTED] source order/reflow/disclosures
  [★★★ TESTED] unsafe source rejection          Glossary navigation
Detail empty state                                [★★★ TESTED] emitted links resolve to sources
  [★★★ TESTED] readable missing-data fallback
```

Coverage inventory: 6/9 behavior groups currently covered, 3/9 explicitly planned in Implementation step 2. This is a static review inventory, not measured line coverage. The three pending assertions describe the intended future behavior; they are already included in the original proposal and are not new review findings. Existing checks must be updated alongside the renderer as specified. No new test framework, production seam, E2E suite or eval is warranted. No LLM/prompt files change. No tests become obsolete; update the existing expected output rather than retire coverage.

No new issues found. Dispositions: original regression requirement retained, no additional remedy or test-depth decision proposed. The original regression specifies both behavior to preserve (all refs/counts/links) and intended differences (labels/fragment), so no missing regression-contract question is needed.

#### QA Test Plan (not persisted to discovery path)

Generated by /plan-eng-review on 2026-10-21. Branch: `plan-relabel-bill-debatten`. Repo: `LucaAlv/poliwatch`.

The required discovery directory `/Users/Luca/.gstack/projects/LucaAlv-poliwatch/` is outside writable roots. The complete requirements follow here; no discoverable QA artifact is claimed.

Affected pages/routes: `/bills/index.html`, `/bills/<slug>.html`, and the Gesetzesvorhaben discovery card on the overview page.

Key interactions: follow a bill title; activate the renamed section link; follow a sitting/TOP link; open the explanation using existing glossary interactions. Reuse desktop and mobile fixtures.

Critical paths:

- Render zero, one and multiple protocol refs; overview shows the exact unchanged total with correct singular/plural. Detail retains every entry and dossier link, including zero/positive/missing speech counts. Extend `tests/test_bills.py` using existing fixtures.
  Value: protects=all protocol refs remain counted and linked; fails_when=speech-based filtering or count drift is introduced; why_new=existing tests lack this count matrix; seam=none; no_claim=live DIP completeness
- Detail navigation targets `#plenarstellen` and its visible heading says Beratungen im Plenum. Extend the existing unit and browser assertions.
  Value: protects=renamed section stays reachable; fails_when=nav and section fragments diverge; why_new=old assertions expect debatten; seam=none; no_claim=non-Chromium browsers
- Updated explanation uses the existing glossary and unique tooltip ID. Reuse the current glossary-link and ID checks.
  Value: protects=explanation has a valid accessible source link; fails_when=ID collision or sources fragment drifts; why_new=existing traversal covers the new output; seam=none; no_claim=dedicated screen-reader application behavior

Edge cases:

- Empty/missing refs show the new readable empty state. Update the existing missing-data test.
  Value: protects=empty detail remains understandable; fails_when=empty-state branch is dropped or stale; why_new=expected copy intentionally changes; seam=none; no_claim=collection completeness
- At desktop/mobile widths the longer heading and navigation label remain readable with no overflow. Reuse the browser fixture harness.
  Value: protects=longer label fits existing responsive layout; fails_when=new copy causes viewport overflow; why_new=existing harness runs changed generated copy; seam=none; no_claim=all viewport/font combinations

Tests to retire: none. Pending decisions: none.

### 4. Performance review

No issues found. Dispositions: none required. Existing overview and detail loops keep their current reference-count scaling. The added glossary invocation performs one bounded lookup per detail page. No new database access, cache, remote request or unbounded memory structure. No benchmark proposed or executed.

### Outside voice

Outside voice unavailable (OUTSIDE_VOICE_UNAVAILABLE). The standard Claude Code invocation returned `status=unavailable`, `error.code=authentication`, empty result, exit 1. Its diagnostic: “Claude Code authentication failed. Run claude interactively in this execution context to authenticate.” Suggested repair: `claude auth login` in this execution context. No tokens consumed, modelUsage empty, no completed reviewer/model identity claimed. Native fallback unavailable because the required Plan agent type, TaskStop and background-task interface are not offered. No replacement agent dispatched and no independent clean-review credit.

### Decision ledger

No new independently selectable remedies were proposed. Original proposal remains unchanged. Approval readiness: PASS, no accepted review remedies needing an answer; source contract and planned regression remain those specified in Decision and scope and Implementation step 2. This review grants no implementation approval.

### NOT in scope

Preserve the original exclusions: collection/data/count changes, compatibility alias, internal variable/CSS renames, other Debatten terminology and adjacent overview polish. No new TODO proposed. No implementation, release bump or publication.

### What already exists

Reuse `render_bills_index` and `render_bill_detail` in `scripts/build_dip_pulse_site.py`; the glossary helper in `scripts/render_dip_pulse_html.py`; bill fixtures, glossary/ID/empty-state checks in `tests/test_bills.py`; and desktop/mobile checks in `tests/bills_browser_check.js` driven by `tests/run_bills_browser_check.mjs`. Existing CI invokes the browser harness. No shared-code extraction.

### Implementation Tasks

Synthesized from this review's findings. No new tasks from Scope Challenge, Architecture, Code Quality, Test or Performance review. Execute the original three implementation steps; no added task or effort estimate is needed. The zero-task JSONL discovery artifact is not persisted because its required state directory is outside writable roots.

Sequential implementation, no parallelization opportunity. Update the renderer and expectations together, align documentation, then run the planned focused/full unittest and browser validation before completing the TODO.

### Completion summary

- Scope Challenge: scope accepted as-is.
- Reality rows: 7/7 applicable emitted; 1 unverified premise (latest remote freshness).
- Architecture: 0 issues. Code quality: 0 issues. Performance: 0 issues.
- Tests: diagram produced; 0 additional gaps beyond 3 behavior groups already planned.
- NOT in scope and What already exists: written. TODO proposals: 0.
- Failure modes: 0 critical gaps. Unresolved decisions: 0.
- Outside voice: Claude Code unavailable, authentication failure; native fallback unavailable.
- Parallelization: 1 sequential lane, 0 parallel lanes.
- Lake Score: N/A, no completeness-scored answers.
- Evidence: `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p test_bills.py` passed 27 tests at revision `6941158` (0.110s). No renderer/test implementation changes made.
- Full suite, browser run and remote freshness not checked during this review. No durable learnings this session.
- Required global review log and auxiliary discovery artifacts: not persisted under current filesystem restrictions. Saved plan content does not establish saved-review clearance until the required log is recorded.

### Suppressed findings

None.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | NOT RUN | No significant product expansion |
| Outside Review | Claude Code via `codex-plan-review` | Independent 2nd opinion | 1 attempted | UNAVAILABLE, not persisted | Authentication failed; host=codex, outside_provider=claude-code, outside_status=unavailable, phase=plan-review |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR locally, log not persisted | 0 issues, 0 critical gaps; FULL_REVIEW at 6941158 |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 for this plan | NOT RUN | Existing bill design used as context |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | NOT RUN | No new developer surface |

**OUTSIDE COVERAGE:** Claude Code, plan-review, unavailable due to authentication; no independent review completed. Native fallback unavailable.

**VERDICT:** Native engineering review found no plan changes needed. Required review log not persisted; saved-review clearance unavailable, eng review required for dashboard clearance. Implementation validation remains required as specified above.

NO UNRESOLVED DECISIONS
