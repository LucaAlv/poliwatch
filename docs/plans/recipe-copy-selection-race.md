# Recipe-copy selection race

Planning snapshot: 2026-10-21, based on `1d1ba2c`, branch
`plan/recipe-copy-selection-race`. Status at that snapshot: planned, not
implemented. The implementation receipt below records the completed work.
Source: `TODOS.md`, “Recipe copy: compare the selection by range, not by text”.

## Implementation receipt (2026-10-21)

The runtime now snapshots every selected range's endpoint nodes and offsets at
click time. After the latest-copy guard, rejection compares all current ranges
against those saved values. Labels, timers, success handling and immediate
clipboard-unavailable fallback retain their existing behavior.

The focused fixture in `tests/test_daten_page.py` emits the actual production
runtime beside two equal SQL blocks. The existing browser runner now executes
16 deterministic scenarios from `tests/recipe_copy_browser_check.js`, using fresh
frames and controlled clipboard promises. The two-range cases use real mutable
Ranges through a restored test-only Selection substitute.

Verification:

- Before the runtime edit, the browser command failed with
  `equal text in another recipe: rejected write replaced the reader selection`.
- After the edit, all 16 recipe scenarios and all existing desktop/mobile bill,
  detail and protocol browser checks passed.
- Focused Python 3.13 Daten suite: 34 tests passed.
- Python compilation and Node syntax checks passed for changed code.
- Full Python 3.13 suite: 1,363 tests ran in 97.192 seconds; passed with one skipped.

Browser execution used the existing CDP runner and a temporary Chrome profile;
localhost serving required sandbox escalation. Native clipboard permission
dialogs and other engines were not tested. The review sections below remain a
historical planning record, including their original verification limits.

## Problem and acceptance criteria

`recipe_copy_runtime_script()` snapshots `String(window.getSelection())` before
the clipboard promise settles. Its rejection handler compares that string with
the current selection. If the reader selects equal text in another recipe,
the comparison passes and the fallback replaces the reader's selection.
The existing page-wide `latestCopy` counter prevents older copy clicks from
winning, but does not distinguish these selections.

A rejected write may select its own SQL only if it is still the latest copy
attempt and the current selection has the same range endpoints as at click
time. Equal text at different DOM positions must remain selected; the failed
button should show the existing “Nicht kopiert” feedback. An unchanged selection
(including no selected range) must still permit the manual-copy fallback.

## Smallest complete implementation

1. In `scripts/build_dip_pulse_site.py`, replace the text snapshot in
   `recipe_copy_runtime_script()` with saved start/end containers and offsets
   for each selected range. Save the values at click time, not a live `Selection`
   or `Range` object: those can change while the promise is pending.
2. In the rejection handler, retain `if (copy !== latestCopy) return;` before
   any selection or feedback action. Compare the current range count and each
   range's four endpoint values with the snapshot. Treat a missing selection
   as zero ranges and handle zero ranges without calling `getRangeAt(0)`.
   Capture every range so a multi-range selection is not reduced to its first
   range. Compare node references directly, not text, HTML, or serialized IDs.
3. Retain `selectFallback()` and the current labels/timers. Preserve the secure
   clipboard success path and the immediate fallback when clipboard access is
   unavailable. No selection-change listener or additional request counter is
   needed. Returning to the exact original endpoints permits fallback; tracking
   intermediate selection history is outside this TODO's endpoint contract.

## Scope and checks

| Location | Planned change |
| --- | --- |
| `scripts/build_dip_pulse_site.py` | Selection snapshot and comparison inside the existing runtime script; its sole page integration is `render_database_page()` |
| `tests/test_daten_page.py` | Update the test that currently requires text equality; retain latest-copy ordering checks and add a small fixture entry point for the browser check |
| `tests/recipe_copy_browser_check.js` (new) | Deterministic behavioral checks against the generated script and real DOM selections |
| `tests/run_bills_browser_check.mjs` | Generate and load the recipe fixture and run its checks using the existing temporary server, Chrome process, and DevTools connection |
| `TODOS.md` | Mark the item complete only after implementation and verification |

Keep the fixture beside the Daten tests: two minimal recipe blocks containing
equal SQL text, with the actual `recipe_copy_runtime_script()` output appended.
The existing page-rendering tests already cover its production integration;
this focused fixture needs no SQLite/export setup. Stub clipboard writes before
clicking; retain explicit resolve/reject callbacks instead of relying on
permission prompts or timing delays. Select text in the first recipe, click
its button, then select matching text in the second recipe while the write is
pending. Assert that the click-time and current selections have equal text but
different endpoints before settling the promise. Starting with no selection
would not reproduce this bug because the old string comparison would differ.
Use fresh page state between scenarios and assert endpoints after settlement,
not just the selected string or button label.

Approved in engineering review D2 A: retain every regression case below and
extend the same emitted-runtime browser checks with a test-only
`window.getSelection()` substitute returning multiple real DOM `Range` objects.
Verify unchanged two-range selection permits fallback, while a mutation confined
to the second range preserves the current selection and reports “Nicht kopiert”.
Assert the substitute actually reports two ranges before settling the promise.
Also verify null selection is treated as zero ranges without calling
`getRangeAt(0)`, and leaving then returning to the exact original endpoints
permits fallback. Restore selection overrides between cases and retain real DOM
selections for the original regression scenarios. Add no production export,
injection hook or browser dependency. These substitute-based checks prove the
comparison logic, not native Firefox multi-range behavior.

The existing browser command already runs in CI's Python 3.13 lane and through
`tests/run_pregate.py`; extend that command without adding a driver, dependency,
workflow, or separate CI job. No production markup, CSS, fixtures containing
real data, manifest contract, exports, schema, or feature configuration changes
are needed. The neighboring remote-manifest validation TODO remains separate.

## Verification and completion

First make the browser regression fail against the current runtime, then apply
the endpoint comparison and verify these cases:

- A pending rejection after moving to equal text in another recipe preserves
  that selection and reports “Nicht kopiert”.
- Equal text at different offsets in the same text node is also preserved.
- A different-text selection, a changed range count, or a moved collapsed caret
  is preserved; an unchanged range or unchanged empty selection permits fallback.
- A newer copy click suppresses the older attempt's late failure and success
  feedback. A successful latest attempt still reports “Kopiert”.
- An unavailable clipboard still selects the clicked recipe immediately.

Run from the repository root after implementation:

```bash
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p 'test_daten_page.py'
node tests/run_bills_browser_check.mjs /opt/miniconda3/bin/python3.13
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests
```

Confirm the negative regression fails with the old text comparison, and that
the fixture executes the actual emitted runtime. Browser automation proves DOM
selection and promise ordering in Chrome/Chromium; it does not certify native
clipboard permission dialogs or other browser engines. If interactive page
diagnostics are needed, use the Chrome DevTools MCP per project instructions.

At initial preparation, this plan did not alter runtime behavior and the race
remained open. The implementation receipt above supersedes that planning status;
the review sections below retain their historical scope and verification state.

## Engineering review

Target and report destination: `docs/plans/recipe-copy-selection-race.md`.
Review date: 2026-10-21. Evidence revision: `1d1ba2c`.
D1: user chose B, continue standard review without office-hours.
The older Gesetzesvorhaben design and cross-branch CEO plan are unrelated and
are not used as requirements. Brain-cache loading failed with EPERM; local
source, project instructions, history and learnings supply the evidence instead.

### Scope Challenge

No issues found. Scope accepted as-is: five proposed changed files, including
one new test file; zero new classes/services. The complexity gate does not apply.
The runtime already owns selection fallback, promise ordering and label timers.
Reuse it and the existing browser runner; do not extract a shared abstraction.
`tests/test_bills.py:682` supplies the fixture-CLI pattern. No new distributed
artifact or release channel is involved. No new TODO is proposed.

Premise table:

| Premise | Claim | Receipt | Verdict |
| --- | --- | --- | --- |
| Current race | Rejection compares selected text | `scripts/build_dip_pulse_site.py:3644`, `:3651` | verified, static read |
| Copy ordering | Page-wide counter guards success and rejection | `scripts/build_dip_pulse_site.py:3639`, `:3647`, `:3650` | verified, static read |
| Integration | Database page emits runtime | `scripts/build_dip_pulse_site.py:4008` | verified, static read |
| Browser infrastructure | Existing Chrome/CDP runner can load another fixture | `tests/run_bills_browser_check.mjs:74`, `:96` | verified interface, extension not implemented |
| CI/pregate | Existing command is invoked by both | `.github/workflows/ci.yml:38`, `tests/run_pregate.py:23` | verified, static read |
| Snapshot semantics | Selection ranges are retained by reference | https://www.w3.org/TR/selection-api/ | verified, specification |
| Fix already landed | Refreshed origin/main still contains text comparison | `scripts/build_dip_pulse_site.py:3651` on origin/main after successful fetch | false; work remains |

REALITY: premise-table pass unverified=0; future behavior remains a proposal docs/plans/recipe-copy-selection-race.md:24
REALITY: already-done pass fetched origin/main; text comparison remains; no newer matching path commits scripts/build_dip_pulse_site.py:3651
REALITY: surface-check pass Python discover command ran; runner accepts Python positional argument tests/run_bills_browser_check.mjs:74
REALITY: binding-decisions pass no branch decisions returned; D1 selects standard review docs/plans/recipe-copy-selection-race.md:118
REALITY: numbers pass five proposed files and zero services counted from scope table docs/plans/recipe-copy-selection-race.md:42
REALITY: deferred-asks pass source TODO endpoint contract covered; no linked issue; manifest TODO stays separate TODOS.md:152
REALITY: pr-count pass one PR intended; no ship-policy override or split proposed docs/plans/recipe-copy-selection-race.md:40
REALITY: falsification-box pass controlled rejection must clobber equal text on old runtime; otherwise reject reproduction before changing runtime; existing runner bounds apply docs/plans/recipe-copy-selection-race.md:84
REALITY: stop-reasons pass existing stale-copy early return has proposed late-success and late-failure checks; no new stop code docs/plans/recipe-copy-selection-race.md:92
REALITY: reporter-environment pass historical report has no exact browser version; Chrome evidence will not claim other-engine or native-permission proof docs/plans/recipe-copy-selection-race.md:104

### 1. Architecture review

No issues found. Endpoint values and node references belong in the existing
click closure. The counter remains page-wide, and comparison happens only after
the stale-attempt guard. No network, database, auth, distribution or schema
boundary changes. Realistic failure: a denied write settles after another
selection; the proposed comparison preserves that selection and reports
“Nicht kopiert”. No listener, additional counter or new service is needed.
Dispositions: none.

### 2. Code quality review

No issues found. The emitted runtime has one authored production caller,
`render_database_page()` at `scripts/build_dip_pulse_site.py:4008`; extraction
has no second caller or reliability benefit. Snapshot plain endpoint values,
retain all existing guards, fallback, labels and timer behavior. The plan has
no stale ASCII diagram. Dispositions: none.

### 3. Test review

References to original plan:74-81 in the decision record identify the
pre-review snapshot; those same cases now appear under Verification and
completion. Reproduction uses the existing runner's bounded fixture generation
and CDP calls; it must show the old runtime's incorrect selection before changing
that runtime. A failure to reproduce is evidence to investigate, not a pass.

Framework: standard-library unittest, per AGENTS.md. Existing bounded check:
`/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p test_daten_page.py`
passed all 34 tests on `1d1ba2c`. This is unit/render evidence, not browser proof.
No acceptance suite, feature or benchmark was built during review.

```text
CODE PATHS                                 USER FLOWS / PROPOSED PROOF
recipe_copy_runtime_script()
 |-- no buttons -> return                  existing static guard test
 |-- button missing code -> skip           existing static guard test
 `-- valid button -> wire, then reveal     existing render/guard tests
     `-- click -> increment latestCopy
         |-- clipboard unavailable
         |   `-- selectFallback()          [GAP] immediate manual copy
         |       |-- selection exists -> replace ranges
         |       `-- null -> label only    existing guard; no behavioral proof
         `-- clipboard available -> snapshot endpoint values -> writeText
             |-- resolve
             |   |-- latest -> flash       [GAP] latest success
             |   `-- stale -> no action    [GAP] old success after newer click
             `-- reject
                 |-- stale -> return       [GAP] old failure after newer click
                 `-- latest -> compare count + every endpoint
                     |-- changed -> flash  [GAP] equal text in other recipe
                     |                     [GAP] equal text at other offsets
                     |                     [GAP] different text / moved caret
                     |                     [GAP] changed range count
                     |                     [GAP] only second range changes
                     `-- unchanged
                         `-- fallback      [GAP] range / empty / null selection
                                           [GAP] leave and return to endpoints
flash(label)
 |-- pending timer -> clear                existing static timer test
 `-- schedule reset -> default label       existing static reset test
```

Legend: GAP means proposed behavioral coverage does not exist yet. Existing
source-string assertions prove emitted-source contracts, not DOM execution.
All changed-path behavioral proof is currently absent; no browser percentage is
claimed. The browser fixture is appropriate integration coverage of emitted
runtime, DOM selections, clipboard promises and button feedback. No LLM/eval
scope. Navigation away destroys the document and its handlers; no new persistence
or cross-tab coordination contract is proposed.

**F1 [P2] (confidence: 9/10) docs/plans/recipe-copy-selection-race.md:32:**
Multi-range comparison has no executable proof in the proposed Chrome-only
checks. Motivating requirement: “Capture every range so a multi-range selection
is not reduced to its first range.” The runner selects only Chrome/Chromium
(`tests/run_bills_browser_check.mjs:15`). The W3C Selection API specification
describes non-Gecko engines as restricting selections to one range. A real-DOM
test there can pass when implementation compares only the first range.
This is a proposed test gap, not an observed implementation defect.
Source: https://www.w3.org/TR/selection-api/ .

The plan already proposes the other critical regression cases. Preserve their
observable outcomes and exercise the actual emitted runtime. R1 below settles
the additional proof method without changing the endpoint contract.
Disposition: F1 accepted through D2 A. Required proof now includes two unchanged
ranges, a second-range-only mutation, null normalization, and return to original
endpoints; no production seam or additional browser. All original plan:74-81
cases remain required. These are planned tests, not executed proof.

Tests made obsolete: only the source assertions requiring selection-text equality;
retain production integration, stale-attempt ordering, guards and timer checks.

## Decision ledger

### R1: Complete endpoint-contract regression proof

Finding: F1, P2, confidence 9/10, plan:32 and runner:15, primary reviewer.
Plan baseline: original proposal compares every range, normalizes null to zero,
allows fallback after return to original endpoints, and preserves stale-attempt,
success, fallback and timer behavior. No remedy approved yet. D1 approves review
navigation only.
Runtime evidence: current runtime compares text; existing tests assert source;
Chrome runner exists; all 34 Daten tests pass. Multi-range behavior of the proposed
fix is unknown because implementation does not exist.

| Choice | Current | A | B | Approval |
| --- | --- | --- | --- | --- |
| Endpoint behavior | Original proposal | Retain original proposal | Retain original proposal | No new behavior introduced |
| Existing planned regression cases | Original plan:74-81 | Required alongside fix | Retained in plan | Original proposal |
| Multi-range proof | No executable method specified | Test-only getSelection double; two real DOM ranges | Investigate method only; remedy pending | Pending R1 |
| Additional endpoint proof | Null normalization and return-to-endpoints specified, assertions missing | Add assertions in same emitted-runtime checks | Leave proposed assertions pending investigation | Pending R1 |
| Production seams/dependencies | None added | None added | None added | Fixed scope |
| Investigation bound | None | None | At most 15 agent minutes, read-only comparison of test-double and real-browser methods | Pending R1 |
| Implementation authority | Review only | Amend plan only | Findings only, then return to R1 | User request |

Question D2:
D2 — How should the endpoint contract be tested?
Project/branch/task: poliwatch, plan/recipe-copy-selection-race; reviewing the recipe-copy race plan.
ELI10: Chrome cannot create the multiple selected ranges that this plan promises
to compare. A test using only normal Chrome selections could pass even if the fix
silently checks just the first range. The existing success, fallback and stale-copy
behavior also needs to stay protected while changing the comparison.
Stakes if we pick wrong: green checks could miss a rejection overwriting a reader's later range.
Recommendation: A because a test-only selection double exercises the emitted runtime without another driver or production export.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Complete existing harness (recommended)
  ✅ Retains all plan:74-81 regression cases and exact expected feedback/selection outcomes.
  ✅ Adds two-range unchanged and second-range-only mutation checks, null-to-zero and return-to-original-endpoints cases against the emitted runtime; no production seam or dependency.
  ❌ The selection double proves comparison logic, not Firefox's native selection integration; restore it between cases.
  Effort: human ~45 min / agent ~5 min; maintenance is confined to the proposed recipe browser check.
B) Investigate proof method
  ✅ Bounds read-only investigation to 15 agent minutes, comparing a test double with real-browser alternatives.
  ✅ Keeps the original runtime contract and existing planned regression cases unchanged while the additional proof method stays pending.
  ❌ Defers the test decision and adds another review turn; authorizes no runtime, test, driver or plan-remedy implementation.
  Effort: human ~1h / agent at most 15 min; report findings and return to R1 before amending scope.
Net: a small explicit test double now versus investigating native-browser proof before choosing.
Header: Endpoint proof
Options:
A) Complete existing harness (recommended)
Retain plan:74-81; add the emitted-runtime checks listed in D2 A with a test-only
selection double and no production seam. Plan amendment only. Human ~45 min /
agent ~5 min. Restore selection overrides between cases; native Firefox proof
is not claimed.
B) Investigate proof method
At most 15 agent minutes of read-only investigation of test doubles versus
real-browser proof. Keep behavior and planned regressions unchanged; additional
proof pending. No implementation or remedy amendment. Return to R1.

State: approved
Actual answer: A, user's reply immediately following D2: “A”.
Accepted scope: amend this plan to retain all original regression cases and add
emitted-runtime checks for unchanged two-range selection, second-range-only
mutation, null selection, and return to original endpoints, using a restored
test-only getSelection substitute with real DOM ranges. No production seam,
dependency, driver or runtime implementation is authorized by this review.
History: Original pending record was unanswered; resolved by D2 A. D1 B only
selected standard review and approved no remedy.

Approval readiness: PASS. Checked R1 against the user's D2 A answer, selected
option, comparison grid, accepted scope and amended working plan. All original
regression cases remain required; no independent remedy or implementation scope
was added. D1 B is navigation only. No pending decision remains.

### 4. Performance review

No issues found. Snapshot and comparison are O(r) time and O(r) retained
endpoint records per pending promise, where r is selection.rangeCount. A normal
Chrome selection has zero or one range; other-engine multi-range counts are
user-bounded and unmeasured. The fix does not traverse SQL text or the DOM tree,
add listeners, queries, caches or network calls. Node references remain alive
until the existing clipboard promise settles; no global history is retained.
Stalled clipboard promises already retain their click closure. No benchmark,
delay threshold or separate timeout policy is justified by this fix.
Dispositions: none.

## Outside voice

Claude Code was enabled and attempted once using the amended plan, actual
decisions and current runtime/tests, with no filesystem access and a five-minute
deadline. It returned `status=unavailable`, `error.code=authentication`, an empty
result, zero input/output tokens and empty modelUsage. Session:
`9e57a6fa-1129-4fd8-9cc5-cca1b47f02a7`. No reviewer output or agreement exists.
The requested catalog model was `claude-fable-5-1`; no executed model identity
is established. Run `claude auth login` to repair authentication.

Native fallback cannot run because the host offers neither the required Plan
agent type nor TaskStop/background-task controls. No replacement general-purpose
agent was dispatched. Outside coverage is unavailable, non-blocking for this
review, and recorded as such. No outside findings or cross-model consensus are
claimed.

## NOT in scope

- Selection history: the original endpoint-only contract explicitly permits
  fallback after returning to the original endpoints.
- Native clipboard permission dialogs and other browser engines: the original
  plan limits the automated evidence to Chrome and controlled clipboard promises;
  D2 A adds comparison proof without claiming Firefox integration.
- Remote-manifest validation: explicitly separate neighboring TODO.
- Production markup/CSS, schema, exports, feature configuration, new drivers,
  dependencies and CI jobs: the existing runtime and harness suffice.
- Product implementation during review: this invocation changes planning only.

## What already exists

- `scripts/build_dip_pulse_site.py:3595`: the shared runtime owns copy handling,
  page-wide ordering, fallback and label timers. Modify it in place.
- `scripts/build_dip_pulse_site.py:4008`: the sole production integration emits
  the runtime on the Daten page; existing rendering tests protect that boundary.
- `tests/test_daten_page.py:152`: source contracts and page integration checks;
  replace text-equality assertions while retaining unrelated contracts.
- `tests/test_bills.py:682`: reuse the fixture CLI pattern without copying the
  bill database fixture setup into the recipe fixture.
- `tests/run_bills_browser_check.mjs:74`: reuse the temporary server, Chrome
  process, CDP connection, failure propagation and cleanup. Add a recipe fixture
  route and checks without a generic runner refactor.
- `.github/workflows/ci.yml:38`, `tests/run_pregate.py:23`: both already call
  that runner, so the new checks need no separate delivery path.

## Approved test requirements and QA artifact

The diagram names eleven behavioral groups with zero current executable DOM
coverage; existing source assertions are not credited as DOM behavior proof.
All are planned checks, not newly executed tests. Integration coverage is the
right boundary here; no LLM calls, prompts or evals are involved.

| Proposed test location | Required assertions | Type |
| --- | --- | --- |
| `tests/recipe_copy_browser_check.js` | Equal-text race at different nodes/offsets, different text/caret, changed counts, unchanged range/empty, null-as-zero, restored original endpoints | Browser integration against emitted runtime |
| `tests/recipe_copy_browser_check.js` | Unchanged two ranges permit fallback; second-range-only mutation is preserved; assert two-range precondition and restore getSelection override | Comparison proof with real Ranges and test-only Selection substitute |
| `tests/recipe_copy_browser_check.js` | Latest success, older success/failure suppressed, clipboard unavailable fallback, original feedback and timer behavior retained | Browser integration; deterministic clipboard settlement |
| `tests/test_daten_page.py` | Keep production integration, ordering, guards and timer contracts; replace only assumptions requiring text equality; generate focused fixture from actual runtime | unittest/render and fixture entry point |
| `tests/run_bills_browser_check.mjs` | Load generated recipe fixture and propagate check failures through existing command | Existing runner integration |

CRITICAL regression contract: preserve selections and feedback under all
original plan cases plus D2 A, and prove the primary equal-text reproduction
fails on the old runtime before applying the fix. The multi-range substitute
must expose real mutable Range objects so saving live objects instead of
endpoint values is caught. Value cards for every Critical Path and Edge Case
are persisted in the QA artifact:

`/Users/Luca/.gstack/projects/LucaAlv-poliwatch/Luca-plan-recipe-copy-selection-race-eng-review-test-plan-20261021-212356.md`

## Failure modes

| Path | Realistic failure | Planned proof / user outcome |
| --- | --- | --- |
| Latest rejected write | Reader moves to identical SQL elsewhere | Real DOM endpoint assertions preserve selection and show Nicht kopiert |
| Older write settlement | Earlier promise wins after another copy click | Controlled old resolve/reject checks assert no selection or feedback action |
| Unchanged/null/empty snapshot | Comparison throws or blocks manual fallback | Empty/null checks forbid out-of-bounds range access and retain fallback feedback |
| Multi-range comparison | Only first range compared, or snapshot stores live Range | Change only the second real Range through test substitute; assert preservation |
| Clipboard unavailable | Click tries to write or omits selection fallback | Disable availability before runtime initialization; assert immediate fallback |

Zero critical gaps remain without planned proof/error handling. This describes
planned coverage; it does not certify the future implementation.

## Worktree parallelization strategy

Sequential implementation, no parallelization opportunity. One runtime module
and one shared browser runner make parallel work more expensive to coordinate.
First add the reproduction and observe the expected failure, then change the
runtime, complete the matrix and run the plan's verification commands. The
sequence already belongs to the original plan; D2 A does not strengthen it.

## Implementation Tasks

Synthesized from this review's findings. Each task derives from a specific
finding above. Run with Claude Code or Codex; checkbox as you ship.

- [x] **T1 (P2, human: ~45min / agent: ~5min)**: recipe-copy regression checks;
  cover the complete endpoint contract in the emitted-runtime tests.
  - Surfaced by: Test Review F1, accepted in D2 A.
  - Files: `tests/recipe_copy_browser_check.js`, `tests/test_daten_page.py`,
    `tests/run_bills_browser_check.mjs`.
  - Verify: the focused Python command and existing browser command listed in
    Verification and completion; primary regression fails with old runtime and
    passes with endpoint snapshot implementation. Retain all original cases and
    assert multiple-range preconditions. Native Firefox proof remains excluded.
  - Effort assumption: small extension of the already-proposed harness, not its
    initial construction or the whole implementation; estimates are not measured.

No new tasks from Architecture, Code Quality or Performance.
The original implementation steps remain the feature work; T1 is the added
proof requirement, not a replacement for those steps.

Task JSONL artifact:
`/Users/Luca/.gstack/projects/LucaAlv-poliwatch/tasks-eng-review-20261021-212356.jsonl`

## Completion summary

- Step 0: Scope Challenge: scope accepted as-is; FULL_REVIEW.
- Reality rows: 10/10 applicable rows emitted; `PLAN_REALITY: phase=eng rows=10/10 missing=none unverified=0 verdict=complete`.
- Architecture Review: 0 issues found.
- Code Quality Review: 0 issues found.
- Test Review: diagram produced; 1 additional test-plan gap identified and accepted in D2 A. Existing behavioral gaps remain planned implementation work.
- Performance Review: 0 issues found.
- NOT in scope: written.
- What already exists: written.
- TODOS.md updates: 0 items proposed; mark the source TODO complete only after implementation and verification.
- Failure modes: 0 critical gaps without planned proof/error handling.
- Unresolved decisions: 0 in this review.
- Outside voice: provider claude-code, unavailable due authentication; required native fallback capabilities absent.
- Parallelization: 1 lane, 0 parallel / 1 sequential.
- Lake Score: N/A; no coverage-scored answers. D1 and D2 differ in kind.
- Verification: 34 existing Daten tests passed on `1d1ba2c`; no browser check, full suite, new regression test or runtime implementation was run/built.
- Review outcome: DONE_WITH_CONCERNS; plan amended, implementation and independent outside coverage remain outstanding.
- Navigation: no further design or CEO review is needed for this bounded bug fix; implement the approved plan and run /ship when ready. This grants no implementation scope.

## Suppressed findings

None. No speculative findings were promoted or used to expand scope.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| CEO Review | `/plan-ceo-review` | Scope and strategy | 0 | NOT RUN | Not needed for this bounded bug fix |
| Outside Review | Claude Code via `codex-plan-review` | Independent second opinion | 1 | UNAVAILABLE | Authentication failure; source=none, host=codex, outside_provider=claude-code, outside_status=unavailable, phase=plan-review; no completed reviewer |
| Eng Review | `/plan-eng-review` | Architecture and tests | 1 | ISSUES OPEN (PLAN) | 1 test-plan gap mapped to approved T1; 0 critical gaps, 0 unresolved; FULL_REVIEW; implementation remains |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | NOT RUN | Existing interface and feedback retained; no additional review needed |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | NOT RUN | No new developer-facing surface |

**OUTSIDE COVERAGE:** Claude Code, phase=plan-review, unavailable. Authentication
failed before review; native fallback capabilities were not offered. No findings,
clean-review credit or cross-model agreement are claimed.

**VERDICT:** Engineering plan review complete with one approved proof task.
Implementation is still required; Eng Review remains ISSUES OPEN until that
work is verified. No implementation or independent outside review is certified;
eng review required before shipping the resulting diff.

NO UNRESOLVED DECISIONS
