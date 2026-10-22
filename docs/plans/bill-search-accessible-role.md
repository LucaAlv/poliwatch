# Add an accessible role to bill search controls

Status: completed and verified on 2026-10-22.
Branch: `fix/bill-search-accessible-role`.

## Scope and evidence

Give `.bill-controls` `role="search"`, retaining its existing
`aria-label="Gesetzesvorhaben finden"`, so assistive technology can expose a
named search landmark on `/bills/index.html`.

The task was split from “Bill overview polish: controls role, same-day step ties,
diacritic-insensitive search” into its own completed entry in `TODOS.md`.
Same-day event ranking and diacritic/ß folding remain deferred under the larger
polish TODO.

`render_bills_index` in `scripts/build_dip_pulse_site.py` emits the controls only
when bills exist. Its production caller is `write_bill_pages`; the browser fixture
writer and unit tests also call it directly. All receive the same generated HTML.
No caller, fixture, CSS, JavaScript, configuration, export, or bill data changes
are needed.

## Implementation

1. Add `role="search"` to the existing `.bill-controls` div in
   `render_bills_index`. Preserve its label and all contained controls.
2. Extend `test_generated_overview_is_readable_first_and_has_search_metadata`
   in `tests/test_bills.py`. Reuse `parsed()` to select `.bill-controls` by class
   token; assert exactly one container, with `role="search"` and the existing
   German accessible label. Add an assertion to the existing empty-publication
   test that no `.bill-controls` container is emitted.
3. Split the role fix into its own “Add an accessible role to bill search
   controls” entry in `TODOS.md`, recording completion after verification.
   Remove only that requirement from the bundled polish entry, retaining the
   other two requirements and their relevant context.

## Validation and completion

- Run `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p test_bills.py`.
- Run `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`.
- Run the existing browser checks with
  `node tests/run_bills_browser_check.mjs /opt/miniconda3/bin/python3.13`, as
  documented in `CONTRIBUTING.md` and used by CI.
- Inspect the diff for the single markup attribute, focused assertions, and
  scoped TODO bookkeeping. No generated site artifacts need committing.

Done when the rendered nonempty overview contains one named search landmark,
the empty overview still omits controls, and validation passes. The markup
assertions establish the role/name contract; they do not establish announcement
behavior in every screen reader. No dedicated screen-reader session is planned.

The change adds semantics without changing search behavior, layout, or stored
data. No unresolved implementation decisions or additional dependencies.

## Implementation results, 2026-10-22

All three implementation steps are complete. The nonempty overview emits one
search landmark named “Gesetzesvorhaben finden”; the empty overview omits the
controls. The regression assertions cover both cases.

Review validation passed on the implemented code:

- Full Python 3.13 suite: 1,371 tests, 1 skipped.
- Existing browser checks: desktop and mobile overview, detail, and protocol
  checks, plus recipe-copy checks.
- Compilation of the changed Python files and `git diff --check`.

No dedicated screen-reader session was run. The engineering review below records
the earlier planning state and is preserved as historical evidence.

## Engineering review, 2026-10-22 (before implementation)

Target and report destination: `docs/plans/bill-search-accessible-role.md`.
Reviewed at `8015662`; implementation remains pending. The original proposal above
is preserved. Review evidence is static source inspection plus the existing bill
unit suite, not verification of the future role attribute.

### Scope Challenge

Scope accepted as-is. Three proposed changed files, zero new classes/services
[measured: implementation steps above]. No complexity selector is needed.
No issues found. Dispositions: no remedies proposed or scope changes accepted.

Premise table:

| Premise | Claim | Receipt | Verdict |
| --- | --- | --- | --- |
| Current markup | Controls have a label but no role | `scripts/build_dip_pulse_site.py:6796` | verified |
| Conditional output | Controls exist only when rows exist | `scripts/build_dip_pulse_site.py:6793` | verified |
| Shared generation | Production and fixtures use this renderer | `scripts/build_dip_pulse_site.py:7077`, `tests/test_bills.py:89` | verified |
| Existing tests | Both named tests and parser exist | `tests/test_bills.py:155`, `:418`, `:441` | verified |
| Deferred work | TODO bundles all three independent concerns | `TODOS.md:443` | verified |
| Browser command | Runner accepts Python as its first argument; CI runs it | `tests/run_bills_browser_check.mjs:75`, `.github/workflows/ci.yml:38` | verified |

REALITY: premise-table pass unverified=0; six factual premises checked docs/plans/bill-search-accessible-role.md:60
REALITY: already-done pass fetched origin/main; its renderer still lacks role scripts/build_dip_pulse_site.py:6796
REALITY: surface-check pass named renderer, parser, tests and CLI argument exist tests/run_bills_browser_check.mjs:75
REALITY: binding-decisions pass branch decision search returned no entries; original scope retained docs/plans/bill-search-accessible-role.md:8
REALITY: numbers pass three proposed files, zero classes; no timing or scale claims docs/plans/bill-search-accessible-role.md:25
REALITY: deferred-asks pass no linked issue; both remaining TODO requests explicitly deferred docs/plans/bill-search-accessible-role.md:14
REALITY: pr-count pass one PR assumed under default policy; no split or additional gate docs/plans/bill-search-accessible-role.md:23

No new architecture, infrastructure, concurrency, dependency, database or
search-algorithm pattern is proposed. Tier 2 reality rows do not apply. This is
an accessibility semantics change, not a search-recall change.

### 1. Architecture review

No issues found. Dispositions: none required.

[Layer 1] Reuse the renderer and its existing controls container. W3C APG supports
`role="search"` for a search landmark, with an accessible label. The native
`search` element is another supported mechanism; changing the element is
unnecessary for this fixed role contract.
Source: https://www.w3.org/WAI/ARIA/apg/patterns/landmarks/examples/search/

The production writer and fixture writer receive the same markup. No new
input, network, authorization, storage or publication boundary is introduced.
Existing static-site generation and CI distribute the attribute without new
artifacts or deployment configuration.

### 2. Code Quality review

No issues found. Dispositions: none required.

Keep the existing div, class, label, child controls and JavaScript selectors.
Use class-token matching in the current parser assertions. No helper extraction
or new dependency earns its cost for one attribute and two test extensions.
No existing flow diagram needs a behavior change.

### 3. Test review

Framework: Python standard-library unittest, per `AGENTS.md:3`. Source and named
tests were read together before constructing this diagram.

```text
CODE PATHS                                      USER FLOWS
write_bill_pages() / fixture writer              Open /bills/index.html
  -> render_bills_index(bills)                     |
       |                                          +-- nonempty publication
       +-- rows exist                                 -> find named search landmark
       |    -> existing .bill-controls div                [GAP, PLANNED ASSERTION]
       |    -> role=search + unchanged name
       |       [GAP, PLANNED ASSERTION]             +-- empty publication
       |    -> existing controls + readable rows       -> session recovery link
       |       [★★★ TESTED: test_bills.py:418]          -> no search controls/landmark
       |                                                 [GAP, PLANNED ASSERTION]
       +-- no rows
            -> empty-publication message/link
            -> no controls or bill scripts
               [★★ TESTED: test_bills.py:441]

Unchanged search interactions:
  initialize -> query/year/sort -> reset/page/history
  [★★★ EXISTING BROWSER ASSERTIONS: bills_browser_check.js:140-208]
```

Legend: ★★★ behavior plus edge/error assertions; ★★ behavior assertion.
New role-contract assertions: currently 0/2 branch contracts protected, proposed
2/2 after the existing tests are extended. Code and journey rows describe the
same two contracts, not four independent gaps. No unplanned gaps identified.
No additional E2E suite or LLM eval is needed for this attribute-only change.

The existing tests protect readable rows, metadata, individual disabled controls
and empty-state recovery. They do not yet protect the new container role/name or
its absence on an empty publication. Both missing assertions are already in
implementation step 2; no additional remedy or test policy is proposed.

Planned proof, extending `tests/test_bills.py` only:

- Nonempty: select by class token, assert exactly one container, exact search role
  and German name. This catches removal, duplication or mislabeling of the landmark.
  Value: protects=one named search landmark; fails_when=role/name removed or container duplicated; why_new=current test checks individual controls only; seam=none; no_claim=screen-reader announcement behavior
- Empty: assert no controls container. This catches an ineffective landmark being
  emitted around the existing empty-state recovery view.
  Value: protects=no empty search landmark; fails_when=container emitted without bills; why_new=current empty test checks child hooks only; seam=none; no_claim=screen-reader application behavior

Existing search/focus/reset/history browser checks remain the regression guard
specified by the original validation plan. Rapid input, stale URLs and multiple
tabs gain no new behavior from a static attribute. No asynchronous path, loading
state, retry, network error or data transformation changes.

Tests made obsolete: none. No tests or acceptance suite were built during review.
Evidence: `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p test_bills.py`
passed 29 tests on the unchanged implementation at `8015662`. The full suite,
browser runner and future role assertions remain implementation-time validation.
Dispositions: original proof plan retained; no new test decisions.

### 4. Performance review

No issues found. Dispositions: none required.
One constant attribute adds no queries, loops, cache, memory growth or blocking
work. Existing renderer cost and search behavior remain unchanged. No benchmark
or performance estimate is claimed.

### Outside Voice

Claude Code was attempted with read-only access and no tools, using the plan and
bounded source context. It returned `status=unavailable`, `code=authentication`:
"Claude Code authentication failed. Run claude interactively in this execution
context to authenticate." Repair: `claude auth login`.

No reviewer response completed. Native fallback cannot satisfy the skill's
required Plan agent type, TaskStop and background timer combination on this host;
no fallback was launched. Outside coverage is unavailable, not a clean review.
No cross-model agreement is claimed.

### NOT in scope

- Same-day event ranking and diacritic/ß folding remain in the existing polish
  TODO because neither is required to expose a named search landmark.
- A dedicated screen-reader session remains excluded by the original plan;
  markup assertions cannot prove announcement behavior in every screen reader.
- No generated site artifacts, redesign, new dependencies or production edits
  are part of this review.

### What already exists

- `scripts/build_dip_pulse_site.py:6763`: one shared overview renderer; reuse it.
- `scripts/build_dip_pulse_site.py:7077` and `tests/test_bills.py:89`: production
  and fixture callers already consume that renderer.
- `tests/test_bills.py:155`: HTML parser; reuse its attributes and class tokens.
- `tests/test_bills.py:418` and `:441`: extend the existing owning tests.
- `CONTRIBUTING.md:13` and `.github/workflows/ci.yml:38`: existing browser runner
  and distribution validation; preserve their commands.

### Failure modes

| Path | Realistic regression | Proof and user effect |
| --- | --- | --- |
| Nonempty | Attribute or name omitted/wrong | Planned exact role/name assertions catch a silent loss of landmark navigation; visible search still works |
| Empty | Controls container emitted unconditionally | Planned absence assertion catches a misleading empty landmark; existing recovery link stays available |

Zero critical gaps: each changed branch has planned regression proof. Runtime
error handling is unnecessary for adding a constant attribute. Future tests are
not claimed as executed.

### Decision ledger

Original proposal retained; no engineering remedies, scope changes, extractions,
new verification policies or TODO additions were proposed or accepted.
The existing TODO split is original implementation step 3, not a review addition.
Approval readiness: PASS; checked IDs: none; no remedy approvals required.

### Worktree parallelization strategy

Sequential implementation, no parallelization opportunity.

## Implementation Tasks

Synthesized from this review's findings. No new tasks from Scope Challenge,
Architecture, Code Quality, Test review or Performance. Execute the original
three implementation steps above; review found no additional task to add.

## Completion summary

- Step 0: Scope Challenge: scope accepted as-is.
- Reality rows: 7/7 applicable rows emitted; unverified premises: 0.
- Architecture Review: 0 issues found.
- Code Quality Review: 0 issues found.
- Test Review: diagram produced; 0 additional gaps, 2 already-planned branch assertions.
- Performance Review: 0 issues found.
- NOT in scope and What already exists: written.
- TODOS.md updates: 0 new items proposed; original bookkeeping retained.
- Failure modes: 0 critical gaps flagged.
- Unresolved decisions: 0 in this review.
- Outside voice: Claude Code unavailable, authentication failure; no native fallback.
- Parallelization: 1 lane, 0 parallel / 1 sequential.
- Lake Score: N/A; no scored decisions.
- No durable learnings this session.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| CEO Review | /plan-ceo-review | Scope & strategy | 0 | NOT RUN | No target-specific record |
| Outside Review | Claude Code, codex-plan-review | Independent 2nd opinion | 1 | UNAVAILABLE | Authentication failure; host=codex, outside_provider=claude-code, outside_status=unavailable, phase=plan-review |
| Eng Review | /plan-eng-review | Architecture & tests (required) | 1 | CLEAR (PLAN) | 0 new issues, 0 critical gaps; implementation pending |
| Design Review | /plan-design-review | UI/UX gaps | 0 | NOT RUN | No target-specific record; related feature design used as context |
| DX Review | /plan-devex-review | Developer experience gaps | 0 | NOT RUN | No developer-facing change |

**OUTSIDE COVERAGE:** Claude Code, plan-review phase: unavailable because authentication failed. No independent report completed.

**VERDICT:** ENG CLEARED; original plan ready to implement. This is plan readiness, not implementation validation.

NO UNRESOLVED DECISIONS
