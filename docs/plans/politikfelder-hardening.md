# Politikfelder: Vorgang fetch and repersist guard hardening

Planning snapshot: 2026-10-19, based on `cfcd249` (`v0.20.0.0`), branch
`plan/politikfelder-fetch-repersist`. Implements the six findings in
`TODOS.md`, “Politikfelder: harden the Vorgang fetch and the repersist guard”.
Updated after the adversarial review on 2026-10-19 to include its four P2
findings and three acceptance-test clarifications. Implementation completed
2026-10-19; the planning and review records below retain their historical context.

## Implementation verification (2026-10-19)

All six original findings and the incorporated adversarial requirements are
implemented. Fetches retain valid peers without certifying partial membership;
validation errors stay outside outage breakers. Replay compares persisted
identities in persistence order and refuses unreadable or incomplete stores.
Cache loads refuse incompatible versions and read errors, corruption backups
are unique, and each atomic-save staging attempt includes the final rename.
Both filter selectors have 44px coarse-pointer targets. README and TODOS updated.

- Python 3.13 focused suites: 88 Politikfelder tests and 42 replay tests passed.
- Full Python 3.13 suite: 1,362 tests passed, one skipped; script compilation passed.
- Demo build and publication validation passed; capabilities/config output
  succeeded; development-marked demo correctly failed publication validation.
- Chrome DevTools on tagged fixture pages: coarse-pointer emulation at 320px
  and 390px, 44px computed chip heights, wrapping with multiple Politikfelder,
  no horizontal overflow, working radar/Politikfeld/Fraktion filters, and visible
  2px keyboard focus outlines. Desktop at 1280px retained 30px chips. No console
  warnings/errors on either page. Screenshots inspected.
- No live DIP requests, live cache/store rewrites, physical-device tests, or
  Python 3.11/3.12 runs (those interpreters are unavailable locally). The build's
  existing best-effort acquisition and online replay limitations remain as scoped.

## Scope and intended behavior

Keep valid DIP records when another record is malformed, distinguish invalid
data from an outage, and refuse an offline replay that would lose a previously
known TOP's or vote's fetched state. Preserve cache files on failures and make
the existing filter chips usable with a coarse pointer.

Reuse the current deterministic tagging rules, cache format, staged SQLite
rebuild, and renderers. No schema migration, dependency, CLI option, tagging-rule
change, live cache rewrite, or neighboring TODO is needed.

| Files | Work |
| --- | --- |
| `scripts/validate_dip_protocol.py` | Explicit response/record shape checks; isolate malformed records in `fetch_vorgaenge` |
| `scripts/build_dip_pulse_site.py` | Fetch accounting and breaker handling; number-lookup isolation; identity-based replay guard; cache-load error reporting; coarse-pointer chip CSS |
| `scripts/politikfelder.py` | Cache version policy, refusal on read errors, null normalization, unique corruption backups, complete atomic-save fallback |
| `tests/test_politikfelder.py` | Extend existing fetch, cache, guard, and rendered-page regressions |
| `tests/test_repersist.py` | Verify command failure and unchanged store for the new guard/cache-load failures |
| `README.md` | Replace the aggregate-count explanation in the repersist instructions; document unsupported/unreadable-cache recovery |
| `TODOS.md` | Mark this item completed only after the six original findings and incorporated adversarial requirements are implemented and verified |

`persist_dip_pulse_store.py`, `stable_ids.py`, and `derive.py` supply the existing
identity and persistence rules; they should not need behavioral changes.
No fixture files, exports, feature configuration, or release-version changes
are expected.

## 1. Validate explicitly and keep good fetch results

In `ApiClient.list_all`, require an explicit `documents` list: missing/null,
`false`, `""`, `{}`, and other non-lists are shape failures. Only an actual
empty list can certify an empty page. This supersedes the draft's
missing/null-as-empty policy. This shared method also serves protocol,
position, activity, and person acquisition: retain the `DipError` contract
and check those callers for the stricter response validation.

Separate response-container validity from row validity and lookup completeness.
A non-object row must not discard its valid object peers. Preserve valid
objects from every readable page, continue pagination when its envelope is
usable, and mark membership incomplete if any row is non-object or a later
page's envelope is unusable. Do not return a filtered list as a complete answer.

In `vorgang_cache_record`, normalize only missing/null `sachgebiet` to `[]`.
Require every other value to be a list of strings. Do not turn falsy malformed
values into a successful empty record. Keep descriptors and other metadata's
existing behavior.

Use a small `DipError` subclass for these shape failures, so callers can handle
them without matching error-message text and existing `DipError` handlers still
work. At the list boundary, it must carry the valid objects collected so far
and indicate incomplete membership. The two Vorgang acquisition paths may
salvage those objects; other callers retain their existing failure behavior.
Do not add a second result wrapper or change `fetch_vorgaenge`'s dictionary
return type. Keep transport failures and unreadable/non-JSON responses on the
existing outage path, including the bot-challenge breaker behavior.

In `fetch_vorgaenge`, validate each returned object's ID before indexing it:
missing, blank, or malformed IDs must not become stringified cache keys.
Catch record-shape failures around each record conversion: warn with the
Vorgang ID where available, omit only that malformed record, and retain good
records, including those salvaged from a list-boundary shape failure.
A requested ID genuinely absent from a complete, identifiable response still
gets the existing fetched-empty record. If any row has an unusable ID or the
list boundary reports incomplete membership, leave unmatched requested IDs
uncached; the malformed row could be one of them. A bad Sachgebiet on an
identifiable record leaves that ID uncached without obscuring other IDs.

Update `refresh_vorgang_cache` to count returned records rather than the size of
the requested batch. Retain the existing success/failure keys, add a clearly
named shape-error count, and distinguish validation warnings from outage
warnings. Shape errors must not increment the consecutive-outage breaker;
receipt of a well-formed response, even with bad records, resets that streak.
A malformed envelope also stays outside outage accounting. Preserve pacing,
periodic/final saves, and the existing five-consecutive-outage stop rule.

Apply the same per-record isolation to `resolve_numbers`: keep valid returned
records. Cache the number's membership only when pagination completed and
every returned row had a usable ID. In that case retain every returned ID,
including IDs whose Sachgebiet failed validation; those missing records are
retried by the existing `fetch_targets` ID pass. If any row lacks a usable ID,
is non-object, or the envelope is malformed, leave the number unresolved even
when some valid records were salvaged. Do not cache a partial response as an
empty or complete subset of membership. The next update must request the
number again. Keep record validation separate from the number-request outage
streak as well.

Checks using `FetchTests.FakeClient`, `raw`, and `run_refresh`:

- One malformed record among 100 retains the other 99, reports accurate counts,
  leaves the bad ID retryable, and does not prevent the next batch or number pass.
- Repeated shape failures beyond the breaker threshold do not trigger the outage
  breaker; genuine consecutive outages still do. A valid response containing a
  bad record breaks a prior outage streak.
- A mixed Drucksache lookup keeps good records and complete ID membership;
  `fetch_targets` requests the malformed record on the next update.
- A valid record plus a missing/blank/malformed-ID object retains the valid
  record but leaves the number unresolved and unmatched requested IDs uncached.
  `fetch_targets` retries both the unresolved number and required missing IDs.
- A non-object row among 100 retains the 99 valid records without certifying
  absent IDs or complete number membership. Cover valid earlier pages followed
  by a malformed row/page, and retain pagination/pause behavior.
- Boundary subtests reject missing/null/falsy malformed `documents`, accept
  actual empty lists, and preserve genuine missing-ID behavior only for complete
  responses. Missing/null Sachgebiet still normalizes to `[]`.

## 2. Refuse unreadable stores and compare identities

Keep the guard before the staged rebuild in `repersist_cached_reports`.
Only an absent database or the expected missing Politikfeld tables of a legacy
store may bypass it. Establish that legacy condition explicitly: exactly one
missing tag table is an incomplete store and must refuse, even when its name
matches an expected legacy table. Catch only the specific expected missing-table
condition; convert every other SQLite failure, including locks and corruption, into
`DatabaseRebuildError` with the database path and an actionable diagnostic.
Always close the connection. Do not silently return for arbitrary SQLite errors.

Replace aggregate counts and the global `from_cache` shortcut with separate
sets of stored, known TOP and vote identities (`source != 'not_fetched'`).
Derive prospective `not_fetched` identities from the same tagging functions used
by persistence. Refuse when either prospective set intersects its corresponding
stored-known set. Thus recovering one entity cannot compensate for losing
another, and newly introduced entities with no previous known state do not
cause a false refusal. Already-`not_fetched` entities can stay missing or recover.

Use persistence's exact keys:

- TOP: `stable_key('agenda', pulse_store.clean(protocol.id), source_index(item.index))`.
- Vote: `pulse_store.clean(vote.id)`; skip IDs that clean to nothing and
  deduplicate normalized IDs. Use `politikfelder.vote_key` only to retrieve the
  derivation result, not as the stored vote ID.

For raw vote IDs that normalize to one persisted ID, mirror persistence's
iteration/overwrite order when building the prospective state, including
`sorted(entries, key=entry_sort_key, reverse=True)` across reports and
`derive.iter_report_votes` within each report. Build the final state per cleaned
vote ID before selecting `not_fetched` identities; an earlier occurrence must
not override the eventual persisted result. Keep TOP and vote sets separate.
Known includes fetched-but-untagged entities, since losing
that fetched state is also a regression; an Einzelplan still derives without
the cache and therefore passes naturally. This guard protects loss to
`not_fetched`, not arbitrary changes between known Politikfelder.

Report counts of newly regressed TOPs and votes, with a bounded example of their
IDs and the existing online-update/restore-cache instructions. Update the
README's count-based explanation accordingly.

Checks:

- Equal-total swaps between known and missing identities refuse, separately for
  TOPs and votes; also cover a net improvement that masks another entity's loss.
- Unchanged degraded state and genuine recovery pass. New missing entities do
  not offset or invent losses; normalized string TOP indexes match persistence.
- Missing/blank/whitespace-only vote IDs do not count; normalized duplicates
  follow persistence. Include duplicate persisted vote IDs across reports with
  conflicting sources, input order different from persistence order, and both
  possible final states (known and `not_fetched`). Einzelplan-only replay and
  pre-schema-5 upgrades still pass.
- Locked/corrupt stores and unrelated SQLite errors refuse. Unexpected missing
  columns/tables must not be mistaken for the expected legacy tables. Explicitly
  test each case with exactly one tag table missing while the other retains data.
- Reuse `RepersistGuardTests.store`, replacing synthetic `t1` IDs with real
  stable TOP IDs and adding protocol IDs to reports. Update aggregate-message
  assertions. Use `RepersistTests` and `sha` to verify refused replay exits 1,
  has no traceback, and leaves the existing SQLite bytes unchanged.

## 3. Preserve cache compatibility and failure evidence

In `load_cache`, accept integer version 1 and treat an absent version as the
existing legacy version 1. Reject every explicitly unsupported or malformed
version (including boolean values) with a clear error, leaving the original file
untouched. Do not quarantine a newer format as corruption or rewrite it as v1.
Inspect the version immediately after decoding the top-level object, before
accessing v1-specific fields such as `vorgaenge` or `dokumentnummern`; a future
layout must not reach the corruption/quarantine handler through a `KeyError`.
Catch that error at `main`'s cache-load call and exit 1 before fetch, persistence,
or rendering; explain that the user must use compatible code or restore a v1
cache. This keeps every path from overwriting an unsupported cache.

Only `FileNotFoundError` permits the absent-cache fallback. For other read
`OSError`s, leave the existing file untouched and raise a clear cache-load
error. Catch it at the same `main` boundary and exit 1 before refresh, saving,
rebuild, or rendering; name the path and explain how to restore read access or
the cache. Returning `empty_cache()` is unsafe here: a writable parent directory
can permit replacement of an unreadable file. Keep the preserved-corrupt-content
recovery path separate from a failure to read the file at all.

Normalize a record's missing/null Sachgebiet to `[]` while retaining its other
metadata. Continue dropping genuinely malformed records as cache misses.
Use the standard library's unique temporary-file naming to reserve corruption
backup destinations; preserve each corrupt input independently and name its
actual location in the warning. Retain private-directory preference and the
existing fallback if private preservation fails. Do not overwrite earlier
`.corrupt` evidence.

In `save_cache`, make each candidate staging attempt include creation, writing,
flush/fsync, and final replacement. If the private attempt raises `OSError`,
clean up its temporary file and retry the complete atomic write beside the cache,
even when the failure occurred during rename. If both attempts fail, preserve
the previous cache and propagate the final error for the existing caller warning.
Do not retry interruption exceptions; preserve cleanup, mode, cross-filesystem
checks, stale-temp sweeping, and the existing documented public-staging fallback.

Checks using `CacheFileTests` temporary directories and existing path mocks:

- v1 and versionless caches load; unsupported/malformed versions refuse without
  changing the file. Include `{"version": 2, "records": {}}`, which has no v1
  fields, and assert no quarantine or rewrite. A CLI case proves exit 1 before
  fetch/rebuild/render.
- A non-absence read error (including `PermissionError`) produces an actionable
  error and exits 1 before fetch/save/rebuild/render. Exercise the main/online
  path with an unreadable cache and writable parent, using a read-error mock if
  needed, and assert the original bytes remain unchanged. A genuinely missing
  cache still permits first-build acquisition.
- Null Sachgebiet survives as `[]`; malformed falsy values are still dropped.
- Two corrupt inputs produce two intact backups and useful diagnostics.
- A failed private final rename succeeds via local staging. If both replacements
  fail, the old cache is byte-identical and temporary files are removed. Existing
  interrupted-save, mode, fallback, and stale-temp tests remain green.

## 4. Restore coarse-pointer chip targets

Extend the existing `@media (pointer:coarse)` rule for the radar with
`.radar-filter .chip { min-height:44px; }`. Add the equivalent coarse-pointer rule
for the votes archive's filter `.chip` buttons. Both Fraktion and Politikfeld
controls use these selectors. Retain existing colors, focus styles, filtering,
and desktop sizing.

Check generated CSS in the existing page tests, then inspect both rendered pages
with coarse-pointer emulation at mobile width: computed targets are at least
44px high, rows wrap without horizontal overflow, both filter groups work, and
keyboard focus remains visible. Discover Chrome DevTools MCP first for this
verification; use another driver only if unavailable and state that limitation.
Do not claim emulation verifies a physical touch device.

## Implementation order and completion checks

Implement boundary validation and fetch isolation first, the replay guard
second, cache durability third, and the two CSS changes last. Add each focused
regression with its fix; use existing local fixtures and no live DIP requests.
Update README/TODOS after the behavior is verified.

From the repository root, use this machine's Python 3.13:

```sh
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p 'test_politikfelder.py'
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p 'test_repersist.py'
/opt/miniconda3/bin/python3.13 -m py_compile scripts/*.py
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests
/opt/miniconda3/bin/python3.13 scripts/build_demo_site.py --output-dir /tmp/poliwatch-politikfelder-demo
/opt/miniconda3/bin/python3.13 scripts/build_dip_pulse_site.py --validate-publication /tmp/poliwatch-politikfelder-demo
```

Use the generated demo only for publication smoke validation. It renders without
a Vorgang cache and currently produces zero Politikfeld filter buttons on both
pages. For chip inspection, render the existing `RenderTests.report()` fixture
with its speech and `cache_of({'v1': vorgang('Verkehr')})`, using the existing
`render_site` setup in `test_render_site_threads_the_cache_into_the_front_page_and_the_votes_archive`.
Write those pages only to a scratch directory, assert that the radar and archive
filter buttons exist, and then perform the coarse-pointer/desktop checks above.
Use the fixture's existing fraction data to exercise the archive's Fraktion
filters alongside Politikfeld filters. No demo-builder change or new production
test seam is needed. CI additionally covers Python
3.11/3.12, capabilities/config output, and rejection of development-marked
publication artifacts; reproduce those existing checks before landing.

Review the final diff for the wider `list_all` caller impact, preservation of
retry/breaker behavior, and identical identity normalization to persistence.
The live cache and store are not required to reproduce these failures and must
not be modified for tests. A sustained DIP shape change will still require an
upstream compatibility fix: this work warns and preserves good records while
continuing the build's existing best-effort acquisition policy.

## Engineering review record

Target and report file: `docs/plans/politikfelder-hardening.md`.
Review started 2026-10-19 on `cfcd249`; evidence is static source/test inspection
and bounded checks of existing commands, not proposed implementation execution.
The scope answers, source receipts, initial contract map, and external-provider
attempt below are historical records of that initial review. The subsequent
adversarial findings and the user's authorization to incorporate them are
recorded separately; the completion summary and terminal report reflect both.

### Scope record

- Feature answers: original six-item TODO scope retained; no cuts proposed.
- Structure: D1 B, user's exact answer `B` after the arrangement question.
- Accepted scope: seven implementation files, one exception subclass, no new
  service. Put fetch/API boundary regressions in `tests/test_politikfelder.py`
  and replay integration regressions in `tests/test_repersist.py`. The full
  suite still exercises other API consumers.
- History: the original eight-file draft optionally proposed edits to
  `tests/test_validate_dip_protocol.py`; B removes that optional edit and its
  separate targeted command, retaining every planned assertion.
- Pending remedies: none at the structure gate; this answer grants no
  implementation permission or approval of later engineering remedies.
- Scope Challenge: scope accepted as-is. Structure was simplified without
  reducing features. No new scope findings; dispositions: none required.

### Scope evidence

| Premise | Receipt | Evidence |
| --- | --- | --- |
| A malformed record aborts the batch conversion | `scripts/validate_dip_protocol.py:318` | static |
| SQLite errors all bypass the current guard | `scripts/build_dip_pulse_site.py:1683` | static |
| Guard compares aggregate missing totals | `scripts/build_dip_pulse_site.py:1694` | static |
| Falsy Sachgebiet defaults to an empty list | `scripts/validate_dip_protocol.py:289` | static |
| Cache version, backup name and final rename need hardening | `scripts/politikfelder.py:170` | static |
| Archive/radar filter chips declare 30px minimum | `scripts/build_dip_pulse_site.py:4417` | static |
| Existing ApiClient test mock supports boundary cases | `tests/test_politikfelder.py:719` | static |
| Batch size 100, outage threshold five | `scripts/validate_dip_protocol.py:282`, `scripts/build_dip_pulse_site.py:1515` | static |

No unverified current-behavior premises. `git fetch origin main` succeeded;
current source/history still contain the six findings. Both build scripts'
`--help` commands exited 0, and all six named build flags were present.
Branch decision search returned no additional decisions. Relevant prior
learnings applied: `single-test-file-unittest-invocation` and
`macos-python-default-below-floor`, confidence 10, dated 2026-10-08/2026-09-29.
The unrelated bills design and cross-branch CEO plan are not adopted here.
Aside was unavailable; no new architecture/concurrency pattern requires web
research. Brain cache lookup could not write its metadata under the sandbox;
source, prior learnings and the ship checkpoint provided project context.

REALITY: premise-table pass eight current-behavior premises checked; unverified=0 scripts/validate_dip_protocol.py:318
REALITY: already-done pass fetched origin/main; these six fixes remain outstanding TODOS.md:909
REALITY: surface-check pass build/demo help exit 0; named flags present docs/plans/politikfelder-hardening.md:192
REALITY: binding-decisions pass D1 B retained; no implementation authorized docs/plans/politikfelder-hardening.md:6
REALITY: numbers pass batch=100 and outage-stop=5 from constants; seven-file arrangement approved scripts/validate_dip_protocol.py:282
REALITY: deferred-asks pass all six TODO requests retained; no linked issue TODOS.md:912
REALITY: pr-count pass default one PR; no split proposed docs/plans/politikfelder-hardening.md:17
REALITY: transaction-semantics pass guard remains read-only before existing staged rebuild scripts/build_dip_pulse_site.py:1718

PLAN_REALITY: phase=eng rows=8/8 missing=none unverified=0 verdict=complete

### 1. Architecture review

The initial review found no architecture issues. The adversarial pass then
identified incomplete-result handling and the unreadable-cache overwrite path
(A1-A4 below). Their remedies are now incorporated into sections 1 and 3 and
remain within acquisition, cache storage, replay validation, and generated CSS.
The proposed data flow is:

```text
main
 +-- load_cache(output)
 |    +-- absent -> note + empty_cache
 |    +-- read OSError other than absence [proposed] -> error + stop, file intact
 |    +-- corrupt content -> preserve evidence + warn + empty_cache
 |    +-- unsupported version [proposed] -> error + stop before acquisition/replay
 |    `-- supported -> normalize records/numbers -> cache
 +-- online -> refresh_vorgang_cache
 |    +-- fetch_targets -> ID batches -> list_all -> vorgang_cache_record
 |    |    +-- valid ID -> cached record
 |    |    +-- absent ID in complete response -> fetched-empty record
 |    |    +-- malformed record [proposed] -> warn + retain other records
 |    |    +-- incomplete rows/envelope [proposed] -> salvage, no negative entry
 |    |    `-- outage -> existing consecutive-failure stop
 |    +-- if not down -> number lookups -> valid records + only complete membership
 |    `-- periodic/final save_cache -> private staging -> atomic replace
 |         `-- private OSError [proposed] -> local staging -> replace or warning
 `-- offline --repersist -> load/reparse/validate reports -> merge entries
      -> require_vorgang_cache_for_tags [proposed identity comparison]
         +-- no prior store/legacy tables -> existing upgrade/rebuild
         +-- read error or known entity becomes not_fetched -> refuse
         `-- no regression -> existing locked, staged rebuild -> swap
              -> render_site -> puls.html + votes/index.html + export
```

No credentials, cache schema, store schema, provenance, or distribution format
changes. Expected failures at each new boundary are visible warnings or build
errors. Replay refusal occurs before the existing rebuild. The guard protects
loss to `not_fetched`; it does not prove unchanged policy-area labels.
Cache concurrency, adding an online-path replay guard, and cross-process store
locking changes remain separate existing TODO scope.

### 2. Code quality review

The initial review found no code-quality issues. A1-A4 add explicit read-error,
row-identity, and completeness requirements; do not retain the original
missing/null-as-empty policy for `documents`. Reuse
`vorgang_cache_record` at both existing conversion sites
(`validate_dip_protocol.py:318`, `build_dip_pulse_site.py:1579`), and the existing
`pulse_store.clean`, `source_index`, `stable_key`, and report tagging functions.
An exception subclass preserves `DipError` compatibility without text matching.
No shared conversion wrapper is justified: ID batching creates fetched-empty
records, while number lookup must retain complete membership. Their failure
bookkeeping differs; the shared validator is the appropriate common boundary.
No additional extraction or line-savings claim is proposed.

Cache shape checks should remain explicit rather than truthiness-based. On a
version refusal, distinguish an unsupported cache from corrupt JSON and keep
the file intact. Attempt cleanup must not hide the original save error. These
are implementation requirements of the existing preservation contract, not
additional features or a request to refactor unrelated persistence code.

### 3. Test review

Framework: standard-library unittest, from `AGENTS.md:3`; use the named Python
3.13 executable and discovery form. Dedicated source/test reads preceded this
diagram. Evidence labels distinguish existing tests from proposed assertions:

```text
CODE PATHS                                         USER FLOWS
ApiClient.list_all                                 Online update
 C01 [***] pages/cursor/pause                        U01 [PLANNED] malformed peer
 C02 [PLANNED] reject falsy malformed envelope           keeps good tags + warning
vorgang_cache_record                               Offline replay [->E2E]
 C03 [***] valid labels                              U02 [PLANNED] equal-total loss
 C04 [***] null -> []                                    exits 1; old store identical
 C05 [PLANNED] false/empty-string/object reject      Unsupported cache [->E2E]
fetch_vorgaenge + refresh_vorgang_cache               U03 [PLANNED] exits 1, file
 C06 [PLANNED] mixed 100-record batch isolation          intact; no fetch/render
 C07 [***] absent requested ID -> fetched-empty     Reader filters
 C08 [PLANNED] shape envelope outside outage count   U04 [PLANNED] coarse pointer
 C09 [***] five outages stop calls                       both groups >=44px, wrap
 C10 [PLANNED] bad-record response resets streak      U05 [PLANNED] desktop/filter/
 C11 [***] down ID pass skips numbers                    keyboard behavior retained
 C12 [PLANNED] partial number keeps complete IDs     No cache
 C13 [***] failed save warns; interruption saves      U06 [***] no false tag/chip
require_vorgang_cache_for_tags -> staged rebuild
 C14 [***] absent legacy tables permit upgrade
 C15 [***] known cache-derived tag loss refuses
 C16 [PLANNED] swaps/net improvement check identities
 C17 [PLANNED] clean blank/duplicate vote identities
 C18 [PLANNED] locked/corrupt/unrelated SQL refuses
 C19 [***] fresh store/unchanged missing state passes
load_cache -> main
 C20 [***] version-1/versionless legacy input
 C21 [PLANNED] unknown/bool version refuses intact
 C22 [PLANNED] null Sachgebiet survives normalization
 C23 [***] corruption warns + first backup
 C24 [PLANNED] repeated corruptions keep both backups
save_cache
 C25 [***] private unavailable/cross-device -> local
 C26 [PLANNED] rename fallback + double failure intact
 C27 [***] interruption cleanup/private staging/mode
 C28 [***] stale sweep retains young/unrelated files
render_site -> radar/archive
 C29 [***] cache reaches both pages; tagged chips
 C30 [PLANNED] coarse-pointer CSS beats 30px defaults

Legend: *** existing behavior+edge/error contract tests;
PLANNED = assertions to add with the implementation, not passing evidence.
->E2E = real local CLI/SQLite integration; no external DIP service needed.
Initial mapping: 16/30 code contracts + 1/6 user flows = 17/36 (47.2%).
This historical map predates A1-A4. The additional mandatory acceptance cases
are listed in sections 1-3 and the adversarial review record below; the initial
36-contract map must not be treated as complete coverage of the revised plan.
This is a manually counted contract map, not instrumented code coverage.
```

Existing test receipts (all `test_politikfelder.py` unless specified):
C01 `:721`; C03 `:579`; C04 `:729`; C07 `:617`; C09 `:632`;
C11 `:668`; C13 `:679`; C14 `test_repersist.py:789`;
C15 `test_repersist.py:819`; C19 `test_repersist.py:819`;
C20 `:399,:520`; C23 `:399`; C25 `:449,:508`; C27 `:415,:425`;
C28 `:478`; C29/U06 `:950`.
The success-reset test at `:650` remains required, but does not independently
cover C10's newly isolated malformed-record response. Reuse/extend its fixture.

One gap in the draft's verification recipe:

1. [P2] (confidence: 10/10) `docs/plans/politikfelder-hardening.md:206`:
   original line `Use the generated demo for the chip inspection.` cannot
   verify the intended controls. `scripts/build_demo_site.py:101-113` calls
   `render_site` without `vorgang_cache` and with `no_persist=True`.
   Bounded current-code probe generated both pages with zero matching filter
   buttons. The existing test at `test_politikfelder.py:950-979` already proves
   cached rendering creates the buttons and uncached rendering omits them.
   Disposition: factual validation-recipe correction, no runtime behavior
   change and no separate remedy approval required. Use that existing fixture
   setup for browser inspection, retaining demo publication smoke validation.

The other 18 missing contract checks in the initial map were already proposed
in the original plan. A1-A4 and the three acceptance clarifications add further
required regressions. No LLM/prompt files are touched, so no eval suite applies.
Retire no tests. Update the aggregate guard assertion and number-membership assertion in
place to reflect the intended fixes; keep their independent original contracts.
Browser checks use generated fixtures with no external service or new testing
framework. Both a nonzero button count and the computed CSS are required, so an
empty fixture cannot give a false pass.

Executed evidence on runtime source `cfcd249`: existing Politikfelder unittest
file passed, 74 tests in 7.175s. Current demo build exited 0 at
`/private/tmp/poliwatch-eng-review-demo`; `puls.html` and `votes/index.html` each
had zero Politikfeld filter buttons. These checks do not validate proposed fixes.

### 4. Performance review

No issues found. Dispositions: no new remedy decision required. Identity sets
require O(K) memory for K stored entities and at most one set-producing query
per tag table; reports are already loaded for replay. Derivation remains one
pass over the reports as in the current guard. Use distinct entity IDs rather
than carrying duplicate rows for multiple labels. No per-TOP SQL query or new
index is needed. Fetch batching, cursor pacing, and the existing cache reuse
rules remain unchanged. Save fallback makes at most two staging attempts.
No new cache, background worker, profiling suite, or timing target is justified.
Actual added runtime and peak memory are unmeasured; no speedup is claimed.

### QA and task artifacts

The QA checklist was saved and read back at
`/Users/Luca/.gstack/projects/LucaAlv-poliwatch/Luca-plan-politikfelder-fetch-repersist-eng-review-test-plan-20261019-200610.md`.
It maps the original regressions and retained contracts, with 15 value cards;
it is proposed verification work, not evidence that the fixes ran.
The review task JSONL was saved and read back at
`/Users/Luca/.gstack/projects/LucaAlv-poliwatch/tasks-eng-review-20261019-200610.jsonl`.
These external artifacts describe the initial review and have not been updated
by this plan-only amendment. The revised requirements and tasks in this file
take precedence for implementation.

### Outside voice status

Claude Code preflight reported ready. Automatic approval initially rejected
launching the external review because plan/source export was not explicitly
authorized. D2 A subsequently authorized the prepared 52,647-byte prompt, and
`bash /private/tmp/poliwatch-outside-review.sh` launched the read-only invocation.
It exited 1: `You're out of usage credits. Switch to another model, or manage
usage credits at https://claude.ai/settings/usage?from=cc_cli_limit_message, to continue.`
No outside reviewer response was returned. This is missing coverage, not a pass.
Provider: Claude Code; host: Codex; phase: plan-review; status: unavailable.
Selection requested `claude-fable-5-1` from the frontier catalog; actual inference
model identity is unverified because no review completed. No provider switch or
model downgrade was attempted. Re-run the independent review after restoring
Claude account availability. The prompt contained no environment/credential-file
reads, and the prepared private prompt was removed after the failed attempt.
The required Plan-agent/TaskStop/background-task native fallback is not offered
by this host; no general-purpose replacement was launched.

Provider attempt metadata (reported, not inferred):

```json
{"status":"error","provider":"claude-code","result":"","error":{"code":"exit","message":"Claude Code exited with code 1. You're out of usage credits. Switch to another model, or manage usage credits at https://claude.ai/settings/usage?from=cc_cli_limit_message, to continue."},"session_id":"e47be6ca-8617-444f-887a-4493ef4394db","usage":{"output_tokens_details":{"thinking_tokens":0},"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","fallback_credit":null},"modelUsage":{},"exit_code":1,"selection":{"role":"plan-review","tier":"frontier","status":"selected","requested_model":"claude-fable-5-1","source":"gstack catalog frontier/anthropic (verified 2026-10-07)"}}
```

## Adversarial review record (2026-10-19)

Four additional P2 findings were confirmed against the existing implementation:

- **A1 — Unreadable cache can be overwritten.** `load_cache` returns an empty
  cache on a read `OSError`, leaving the original file in place; a later save
  replaces it when the parent directory is writable. A bounded probe injected
  `PermissionError` during reading, then saved the returned cache and confirmed
  the old bytes changed. Remedy: section 3 now refuses non-absence read errors
  before any acquisition or save, with an end-to-end preservation assertion.
- **A2 — Unidentifiable rows leave permanent partial membership.** A number
  response containing one valid record and an ID-less object cached only the
  valid ID; `fetch_targets` then returned no requests and derivation used that
  subset. Remedy: section 1 keeps good records but certifies number membership
  and missing requested IDs only when all rows are identifiable and pagination
  is complete. Test both number and ID acquisition paths.
- **A3 — Missing/null `documents` certifies false absence.** Both `{}` and
  `{"documents": null}` produced fetched-empty records for a requested ID in
  bounded probes. Remedy: section 1 supersedes the draft's compatibility policy;
  only an explicit list is accepted, and only a complete response can certify
  that requested IDs are absent.
- **A4 — One non-object row still discards valid peers.** A valid object plus
  `null` raised from `list_all`; the draft retained that whole-response rejection.
  Remedy: the shared shape exception preserves valid objects and signals
  incompleteness. Vorgang callers salvage those records without certifying
  absence or complete membership; other API consumers still receive `DipError`.

Three acceptance requirements are also now explicit: reject a future cache
layout before accessing v1 fields; refuse each one-tag-table-missing store;
and match cross-report vote overwrite order even when input order differs
from the rebuild's sort order. These clarify existing preservation and identity
requirements without adding schema changes, dependencies, or production files.

Baseline evidence: `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`
passed 1,345 tests in 88.426s, with one skipped. Separate Politikfelder and
repersist runs passed 74 and 39 tests respectively. Probes used temporary
directories and mocks; no live cache/store was modified. These results concern
the current implementation, not the proposed fixes. No live DIP, browser/device,
or additional external-provider review was performed in the adversarial pass.

Disposition: all four remedies and the three acceptance clarifications are
incorporated as planned work at the user's request. Their implementation and
verification remain outstanding; no clean implementation review is claimed.

## Decision ledger

### R1: External plan/source export consent

Finding: operational approval gate, confidence 10/10, Outside Voice; automatic
approval reviewer rejected the external invocation before execution.
Plan baseline: the invoked skill proposes an automatic outside review, but no
explicit data-export approval has been given. D1 B fixes only file arrangement.
Runtime evidence: preflight ready; external execution rejected, no report.

| Choice | Current | A: Send to Claude | B: Keep review local |
| --- | --- | --- | --- |
| External export | not authorized, nothing sent | authorize sending this prepared plan/source prompt to Claude Code | send nothing; finish with unavailable outside coverage |
| Existing source access | parent reads local repo | Claude gets supplied excerpts, `--access none` | no external source access |
| Six TODO fixes | retained proposals | unchanged | unchanged |
| File arrangement | seven files, D1 B | unchanged | unchanged |
| Implementation permission | none | none | none |
| New outside findings | unknown | review and disposition separately if returned | unknown; no outside-review credit |
| Native evidence | 74 existing tests pass; factual recipe corrected | unchanged | unchanged |

Question D2:

**D2 — Allow the independent review to receive the plan and code?**

Reply **A** to authorize sending, or **B** to keep the review local.

On `plan/politikfelder-fetch-repersist`, the native review found one validation
recipe error and corrected it. The independent check would send the prepared
plan and selected source excerpts, about 53 KB, to Claude Code's provider.
Once sent, that disclosure cannot be undone. It would be a read-only review.

Recommendation: **A**, because the independent check may catch assumptions the
native review missed.

Note: options differ in kind, not coverage; no completeness score.

**A) Send to Claude (recommended).** Authorize this plan and the prepared source
excerpts to be sent for the independent check. The reviewer gets enough context
to challenge the native conclusions and has no repository tools. The tradeoff
is disclosing these materials to an external provider. Estimated effort:
human ~1 minute / CC ~1–5 minutes.

**B) Keep review local.** Finish using the native review and its recorded
evidence. This avoids exporting the materials and keeps all six planned fixes
and the seven-file arrangement. Independent outside coverage remains missing.
Estimated extra external-review effort: human 0 / CC 0 minutes.

Net: independent scrutiny versus keeping the plan and code local.

Header: External consent
Options:
A) Send to Claude (recommended)
Authorize this plan and the prepared source excerpts to be sent for the
independent check. The reviewer gets enough context to challenge the native
conclusions and has no repository tools. The tradeoff is disclosing these
materials to an external provider. Estimated effort: human ~1 minute / CC
~1–5 minutes.
B) Keep review local
Finish using the native review and its recorded evidence. This avoids exporting
the materials and keeps all six planned fixes and the seven-file arrangement.
Independent outside coverage remains missing. Estimated extra external-review
effort: human 0 / CC 0 minutes.

State: approved
Actual answer: D2 A, user's exact reply `A` to the external-export consent brief.
Accepted scope: send the prepared 52,647-byte plan/source prompt to Claude Code
for the read-only outside review with `--access none`; this grants no product
implementation permission and accepts no future outside finding automatically.
History: original automatic invocation was rejected before execution. The prior
state was pending, answer unanswered, with no accepted export scope. Explicit
D2 A authorized this send. The invocation then failed for exhausted Claude
usage credits and returned no reviewer response. Native review and saved
QA/task artifacts remain. No outside findings or further remedy choices exist.

Initial review approval readiness: PASS. D1 B is the actual structure answer;
D2 A is the actual external-export answer. At that stage the only native amendment was F1's factual
verification-recipe correction, which changes no runtime behavior. No new
engineering remedy has been silently accepted; original implementation
requirements remain proposed work. There are no pending engineering decisions.

### R2: Incorporate adversarial findings into the plan

Actual answer: the user requested `update the plan to include your findings`.
Accepted scope: incorporate A1-A4 and all three acceptance-test clarifications
into this plan, its failure modes, tasks, and review summary. This authorizes
the document amendment; it does not authorize implementation, publication, or
a new external-provider invocation. No finding is left awaiting disposition.

## NOT in scope

- Cache concurrency/TTL, an online rebuild guard, and adjacent B3 deferred
  findings remain in their existing TODOs. This plan retains the named six
  original findings and incorporates A1-A4 and their acceptance clarifications.
- Dataset/site separation, new tag sources, policy-area mapping changes, and
  schema/export migrations are outside this hardening task.
- Live DIP requests, live-store rewrites, new acceptance suites, performance
  benchmarks, physical-device validation, and implementation were not performed.
- No new TODO was proposed. Existing target completion awaits implementation
  and validation; `TODOS.md` remains unchanged.

## What already exists

- `scripts/validate_dip_protocol.py:201`: paginated `ApiClient.list_all`, pacing,
  and the `DipError` handler contract. Tighten this boundary without replacing it.
- `scripts/validate_dip_protocol.py:285`: common Vorgang record conversion;
  reuse it at both ID and number acquisition sites.
- `scripts/politikfelder.py:170,234,546`: cache load/save and target selection;
  extend their existing compatibility/fallback/retry paths.
- `scripts/persist_dip_pulse_store.py:79,869,1401` and `scripts/stable_ids.py:20,29`:
  existing cleaning and stable identity rules. Reuse these exact values.
- `scripts/build_dip_pulse_site.py:1703`: replay guard before staged rebuilding;
  retain that order and its old-store preservation guarantee.
- `tests/test_politikfelder.py:381,528,835,950`: cache, fake API, guard, and tagged
  rendering fixtures. D1 B keeps these tests together. No extraction is proposed.
- `tests/test_repersist.py:819`: existing byte-identical-store refusal checks;
  extend for identity swaps and read errors.

## Failure modes

| Path | Realistic failure | Handling and required proof | User-visible outcome |
| --- | --- | --- | --- |
| ID batch | One Sachgebiet has an invalid type | Per-record shape warning, preserve valid peers, mixed-batch test | Partial fetch warning; good tags retained |
| Response envelope | `documents` is missing, null, or non-list | Shape exception, salvage earlier valid objects, no fetched-empty entries, boundary tests | Schema warning; unresolved IDs retry next update |
| ID/number rows | One row is non-object or lacks a usable ID | Preserve good peers, withhold absence/completeness claims, multi-page and next-target tests | Warning; incomplete lookup stays retryable |
| Number lookup | Identifiable record has malformed Sachgebiet | Complete membership plus valid records; next-ID-target assertion | Warning; missing record stays retryable |
| Replay | Locked or corrupt store | Narrow SQLite bypass; guard and CLI/byte-hash tests | Error and exit 1; previous store retained |
| Replay | Exactly one tag table is missing | Refuse both partial-table cases instead of treating them as legacy | Error and exit 1; previous store retained |
| Replay | Equal-total missing identity swap | Known-ID intersection; separate TOP/vote and integration cases | Error identifies newly degraded entities |
| Replay | Duplicate vote ID across reports with conflicting states | Final cleaned-ID map in persistence sort/overwrite order; reversed-input test | Guard agrees with eventual persisted state |
| Cache load | Future or malformed explicit version, including a different layout | Validate version before v1 fields; reject intact before fetch/render; local CLI assertion | Actionable compatibility error |
| Cache load | Read error with a writable parent directory | Fail before fetch/save/rebuild/render; byte-identical-file CLI assertion | Actionable read-access error; original cache retained |
| Corruption | Second invalid cache replaces first evidence | Unique reserved destinations; repeated-corruption test | Warning names preserved copy |
| Cache save | Private final rename fails | Retry complete local staging; double-failure preservation test | Cache saved, or explicit save warning |
| Reader filters | Tagged controls are absent from test pages | Nonzero-button precondition, generated CSS, browser checks | Meaningful 44px target verification |

The initial review's zero-gap assessment was superseded by A1-A4. Each now has
explicit proposed handling and regression requirements above; none is yet
implemented or verified as fixed.

## Worktree parallelization strategy

Sequential implementation, no parallelization opportunity. The acquisition and
guard/CSS work share the build module, and cache behavior affects their tests.
One lane, four sequential steps: boundary/fetch isolation -> replay guard ->
cache durability -> CSS and verification. No implementation worktrees launched.

## Implementation Tasks

The original six fixes are specified above. These tasks capture the initial
review's verification correction and the incorporated adversarial requirements.

- [x] **T1 (P2, human: ~30min / CC: ~5min)**: renderer verification: verify touch
  targets using tagged renderer fixtures.
  - Surfaced by: Test review F1, the ordinary demo contains zero Politikfeld
    filter buttons and cannot prove their target size.
  - Files: `tests/test_politikfelder.py`, `docs/plans/politikfelder-hardening.md`.
  - Verify: assert both generated pages contain the expected controls before
    inspecting computed coarse-pointer size, wrapping, keyboard focus and filter
    behavior; retain ordinary demo publication validation separately.
  - Estimate assumes fixture reuse; browser verification limits compression.
    It is an estimate, not an observed implementation duration.

- [x] **T2 (P2)**: preserve valid Vorgang peers without certifying partial results.
  - Findings: A2-A4; implement section 1's explicit-list, row-ID, partial-result,
    negative-cache, and complete-number-membership rules within the existing
    `DipError`/dictionary contracts.
  - Files: `scripts/validate_dip_protocol.py`, `scripts/build_dip_pulse_site.py`,
    `tests/test_politikfelder.py`.
  - Verify: mixed valid/non-object/ID-less rows, missing/null envelopes,
    malformed later pages, next-update retries, counts, pacing, breakers, and
    failure behavior of the other `list_all` callers.
- [x] **T3 (P2)**: close cache-load-to-save preservation gaps.
  - Finding: A1 plus the future-layout acceptance clarification; implement
    section 3's early version validation and non-absence read-error refusal.
  - Files: `scripts/politikfelder.py`, `scripts/build_dip_pulse_site.py`,
    `tests/test_politikfelder.py`, `tests/test_repersist.py`, `README.md`.
  - Verify: future-layout and read-error cases exit before fetch/save/rebuild/
    render and preserve original bytes, while genuine absence still works.
- [x] **T4 (P2)**: verify the replay guard against partial stores and actual
  cross-report vote overwrite order.
  - Files: `scripts/build_dip_pulse_site.py`, `tests/test_politikfelder.py`,
    `tests/test_repersist.py`.
  - Verify: each one-tag-table-missing case refuses; duplicate cleaned vote IDs
    match persistence's final state for both known and `not_fetched` outcomes
    when input order differs from sorted persistence order.

No additional performance task was identified. T2 belongs to the first
implementation step, T4 to the second, T3 to the third, and T1 to the last.

## Suppressed findings

None. No speculative issue was promoted, and no outside finding was returned.

## Completion summary

- Status: DONE_WITH_CONCERNS. Native review completed; outside coverage unavailable.
- Step 0: Scope Challenge: scope accepted as-is; D1 B simplifies arrangement.
- Reality rows: 8/8 applicable rows emitted, 0 unverified current-behavior premises.
- Initial engineering review: one validation-recipe finding mapped to T1.
- Adversarial review: four P2 findings A1-A4 incorporated into sections 1 and 3,
  with three acceptance clarifications in sections 1-3. Tasks T2-T4 capture the
  required additions; implementation and regression verification are pending.
- Test Review: the initial 36-contract diagram is historical; its original
  coverage count does not include the adversarial additions. Sections 1-3 and
  the adversarial record list the additional mandatory acceptance cases.
- Performance Review: 0 new issues found; added runtime/memory unmeasured.
- NOT in scope: written. What already exists: written.
- TODOS.md updates: 0 items proposed; no TODO file changes.
- Failure modes: the initial zero-gap assessment is superseded; A1-A4 now have
  explicit proposed handling and tests, with no claim that the runtime is fixed.
- Unresolved engineering decisions: 0; the user requested incorporation of all
  findings into the plan (R2). This amendment changes the plan only.
- Outside voice: Claude Code unavailable, exhausted usage credits after D2 A;
  no reviewer response, no cross-model agreement, no clean-review credit.
- Parallelization: 1 lane, 0 parallel / 4 sequential steps.
- Lake Score: N/A; neither actual answer differed by completeness.
- Validation: the adversarial pass's full Python 3.13 suite passed 1,345 tests
  with one skipped; focused suites passed 74 and 39 tests, and bounded probes
  confirmed the failure paths. The initial demo build and empty-controls probe
  remain evidence for F1. No proposed fixes/tests, live DIP, browser, or
  physical-device checks ran.
- Learning: default demo rendering has no cache-backed Politikfeld filter buttons;
  use tagged renderer fixtures for meaningful filter-control inspection.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| CEO Review | `/plan-ceo-review` | Scope and strategy | 0 for this plan | NOT RUN | Routine hardening; unrelated historical CEO plan not adopted |
| Outside Review | Claude Code via `/plan-eng-review` | Independent second opinion | 1 attempted | UNAVAILABLE | Credit limit; no reviewer response; host=codex, source=none, outside_provider=claude-code, outside_status=unavailable, phase=plan-review |
| Eng Review | `/plan-eng-review` | Architecture and tests | 1 initial | ISSUES OPEN (PLAN) | Initial validation-recipe finding mapped to T1; initial zero-gap assessment superseded by A1-A4; FULL_REVIEW |
| Adversarial Review | User-requested native review | Challenge preservation and completeness assumptions | 1 | ISSUES OPEN (PLAN) | 4 P2 findings A1-A4 and 3 acceptance clarifications incorporated; tasks T2-T4 pending implementation; baseline full suite passed |
| Design Review | `/plan-design-review` | UI and UX gaps | 0 for this plan | NOT RUN | Two CSS target-size corrections; optional design review |
| DX Review | `/plan-devex-review` | Developer experience | 0 for this plan | NOT RUN | No new developer-facing workflow |

**OUTSIDE COVERAGE:** Claude Code, plan-review phase, unavailable after an
authorized attempt; exhausted usage credits, zero returned findings because
there was no reviewer response. Requested model `claude-fable-5-1`; actual
inference model unverified. Required native fallback capabilities absent.

**VERDICT:** The plan now incorporates the initial verification correction,
four adversarial findings, and three acceptance clarifications at the user's
request. Earlier zero-gap conclusions are superseded. The revised requirements
are ready to guide implementation; tasks T1-T4 and their proof remain pending.
Status remains ISSUES OPEN, external-provider coverage remains unavailable,
and implementation review is required before landing.

NO UNRESOLVED DECISIONS

## Implementation status update (2026-10-20)

The implementation and verification are complete. The October 19 verification
above records that day's results; the full Python 3.13 suite now passes 1,363
tests with one skipped, and the focused Politikfelder and replay suites pass 89
and 42 tests. Final native and outside reviews are complete. The documented
Chrome DevTools checks passed at 320px, 390px, and 1280px. No live DIP requests
or live cache/store writes were performed.
