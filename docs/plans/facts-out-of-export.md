# Plan: the `facts` tables leave the release export

Review target: this plan (`/plan-eng-review`, 2026-11-27). Review record below the plan.

TODOS.md, "Owner decisions of 2026-11-23" (work before the release). Decision: Q5 owner, `docs/plans/v1-scope-review.md` (2026-11-06): Fakt der Woche off the v1 site and its `facts` tables out of the release; the engine stays.

## Scope

Export only. `fact_metrics`, `facts` and `fact_sources` leave the distribution copy and everything derived from it. The build store keeps them, `scripts/facts.py` computes them as before, and the Fakt pages keep rendering from the store. Taking Fakt der Woche off the site is "Apply the v1 surface list" and not part of this.

Checked on main c1b6b94:

- `_run_export` copies the whole store with `sqlite3.Connection.backup`, so the three tables ship today.
- `write_facts_pages` reads the store (`facts.open_readonly`, `facts.load_facts`). `compare_store_values.py` and `validate_store_gate.py` read the three tables from the build store too. `compare_store_values` opens the distribution copy only to run recipe r3.
- No recipe reads a facts table. The only foreign keys into them come from each other (`facts` → `fact_metrics`, `fact_sources` → `facts`).

Export-only therefore holds.

## Change

`scripts/build_dip_pulse_site.py`:

1. `_run_export`: right after the backup, before the foreign-key check and the schema hash, `DROP TABLE IF EXISTS` for `reversed(facts.FACTS_TABLES)` (child first; `IF EXISTS` because a direct export can run on a store the engine never touched). The following `VACUUM INTO` rewrites the file, so no dropped page ships. CSV files, `manifest.tables`, `relationships`, `total_rows`, `schema_hash`, DATA.md's table section and the Daten page's schema cards all read the snapshot and follow without further code.
2. `EXPORT_FORMAT` 28 → 29.
3. Remove the three `DATABASE_TABLE_DESCRIPTIONS` entries, `| set(facts.FACTS_TABLES)` in `_TABLE_SOURCE_DERIVED`, and the facts exemption in `_load_data_dictionary`'s stale check. After this the dictionary is a second guard in both directions: a facts table back in the export fails as "data dictionary missing", a facts entry back in the dictionary fails as "describes tables no export has".
4. Comments that say the export holds them (above `run_data_pipeline`'s engine call, and the Daten section header). The engine still has to run before the export: the export hashes and copies the store file the engine writes.

Rejected: filtering the tables out of the CSV list and manifest only (the SQLite file would still ship the rows). An allowlist of exported tables (the dictionary check already is one: an undescribed table stops the export).

## Text that would become false

- `scripts/data_dictionary.json`: drop the three table entries. `withheld_units.meaning` ends with "Nicht zu verwechseln mit facts.withheld (…)", a column no export has: drop that sentence.
- `DATABASE_TABLE_DESCRIPTIONS["withheld_units"]` and `_codebook_withheld` (DATA.md) carry the same sentence with `facts.withheld`: drop it. The sentences that say how a withheld or cut sitting affects the site's Fakten stay, because they are still true of the build and name no table; they go when Fakt der Woche leaves the site.
- `LICENSE-DATA.md` (embedded in DATA.md): take the three tables out of the `derived` row; the "What we changed" bullet says the build store's Fakt der Woche tables are not part of the export, without naming the table identifiers, so no shipped file names a table it does not hold (X1).
- `docs/stable-ids.md` (format number; the two key-dictionary rows are marked build store only), `README.md` and `docs/project-documentation.md` (format 29; the export leaves the three out), `CONTEXT.md` (the stale "schema 16 / export format 27" line), a dated note in ADR 0003 whose licence table names them, `CHANGELOG.md`.
- `docs/data-changelog.md` describes the release changelog format and names no table and no format number: no change.
- `manifest.transformation` stays as it is. It never listed every difference (`mp_canonical`, `datenstand`); LICENSE-DATA.md is where the change is stated.

## Tests (test first)

Seam: `export_distribution_data`, the public function a release goes through.

1. New, red first: after `run_facts_engine`, the export's SQLite file has no facts table, the generation holds no `facts-`, `fact_metrics-` or `fact_sources-` file, the manifest lists none, and the build store still holds all three with their rows.
2. `schema_hash` is the same whether or not the engine ran on the store (the facts DDL is no part of it).
3. No shipped text names them: DATA.md and the generation's `LICENSE-DATA.md` hold no `fact_metrics`, `fact_sources` or `facts.`; no description on the Daten schema cards does either.
4. Changed: the CSV count test (36 → 33, no facts names), the literal `export_format` 28 → 29. Removed, because their subject is gone: the two facts-caption tests (`test_daten_export.py`, `test_facts.py`) and the codebook assertions on `fact_metrics` and `facts` columns.

## Verification

- Clone the reference store twice under `/private/tmp/claude-501/todo-stores/facts-out/`. Baseline: main c1b6b94, `--offline --repersist --today 2026-11-27`. After: a clone of the baseline, this branch, same `--today`.
- Inspect the new export: `sqlite_master`, the file list, `schema_hash` old → new, table, relationship and row counts old → new (each difference must be exactly the three tables).
- Diff every rendered page. Normalise what depends on the run, not on this change: the generation id `g-<hash>` in download URLs (`overview.html`, `sources.html` and others link to it), export timestamps (`generated_at` and its German display) and the build revision (X2). Expected after that: `database.html` only (format number, schema hash, table list, row, table and relationship counts, file sizes and checksums, the one caption). Report every other difference.
- `compare_store_values.py base after`: no figure moves. Compare the three facts tables row by row.
- Exported tables other than the three: same rows in both copies (apart from `datenstand`).
- Review checklist, `/verify`.

### Results (2026-11-27)

- Export: format 28 → 29, store schema 17 and key version 1 unchanged. Schema hash `0c6b0488194c84b15292609688ccbb7a1688e060bd9c3ea4f81c065541e34f59` → `a53316825dd4fbcb1d9139d68b0052a19cca28c0a72f2bc458eaf0564ff82d0c`. Tables 37 → 34, files 45 → 42 (the three CSVs), rows 1,372,489 → 1,367,645, relationships 52 → 50, SQLite gzip 303,678,673 → 302,834,660 bytes.
- The new file has no schema object on a facts table, no free page, and no byte match for the table names or a facts row id (the old file has them). The other 34 tables hold the same rows and columns; `datenstand` differs in format and schema hash.
- Build store: byte-identical (same `source_sha256`); the three tables hold 8, 1,944 and 2,892 rows.
- Pages: 10,296 files before and after. `data/features.json`, `index.html`, `overview.html` and `sources.html` differ only in build time and generation id. `database.html` differs: format, the three schema cards, downloads and relationships, counts, size and checksum, and the `withheld_units` caption. Its note on the `-dirty-` suffix comes from building the uncommitted tree (build:5869).
- `compare_store_values.py`: exit 0, 238 publishable weeks and 46 months, no changed winner, 0 of 1,944 Fakt values moved.

---

# Review record

## Scope record

feature answers: none asked (no cut proposed); structure: A, original arrangement (D1, 2026-11-27, the owner's delegated AskUserQuestion adjudicator); accepted scope: export-only removal as in "Change", with every file listed in this plan (about 13 [estimated], 0 new classes or services); pending remedies: none.

## Scope Challenge

- Reuse: `_run_export` already reshapes the copy (`ALTER TABLE speeches DROP COLUMN paragraphs_json`, `scripts/build_dip_pulse_site.py:5385`). Three `DROP TABLE` statements there are the same pattern, SQLite built-ins only [Layer 1]. No new pattern, so no web search.
- TODOS: "Apply the v1 surface list" (TODOS.md:560) also lists "its `facts` tables out of the release"; that half is done by this plan. Only this session's own TODOS entry is edited; the report names the other.
- Distribution: no new artifact.

Finding SC1 [INFORMATIONAL] (confidence 9/10, reviewer: the AskUserQuestion adjudicator, checked here) `docs/designs/fakt-der-woche.md:34`: "a downloadable `facts` table is what lets other people build on it." (also :273). Factual correction, no behaviour change: extend that file's existing "Superseded in part" line. The other hits under `docs/plans/`, `docs/research/` and `docs/prompts/` are dated records and stay.

REALITY: premise-table pass 6 premises read in code, unverified=0 (copy: build:5369; site reads the store: build:11629; no recipe reads facts: RECIPES build:3929-4191; FKs only among the three: scripts/facts.py:1965; compare and gate read the build store: scripts/compare_store_values.py:358, scripts/validate_store_gate.py:296; dictionary check refuses an undescribed table: build:4600) scripts/build_dip_pulse_site.py:5369
REALITY: already-done pass origin/main is c1b6b94 after a fetch on 2026-11-27; no commit drops the tables scripts/build_dip_pulse_site.py:5333
REALITY: surface-check pass --offline, --repersist, --today, --output-dir exist; --today read at parse_args scripts/build_dip_pulse_site.py:14606
REALITY: binding-decisions pass Q5 owner decision; gstack decision search for this branch returns nothing docs/plans/v1-scope-review.md:192
REALITY: numbers pass CSV count 36 [measured: tests/test_daten_export.py:1368] to 33 [estimated: minus three]; export format [measured: scripts/build_dip_pulse_site.py:3800] is 28 and becomes 29 [estimated: plus one]; store figures are re-measured in Verification scripts/build_dip_pulse_site.py:3800
REALITY: deferred-asks pass no linked issue; the task's out-of-scope item (Fakt der Woche off the site) is named in Scope TODOS.md:560
REALITY: pr-count pass this session opens no PR TODOS.md:67

## 1. Architecture review

No issues found.

```
build store (facts engine writes) ──backup()──> dist copy
                                                  │ DROP fact_sources, facts, fact_metrics   [new]
                                                  │ DROP speeches.paragraphs_json, add mp_canonical, datenstand
                                                  ▼ VACUUM INTO (rewrites the file: no dropped page survives)
                                               snapshot ──> .sqlite.gz, CSVs, manifest, schema_hash, DATA.md
build store ──facts.open_readonly──> fakt/*.html, puls.html   (unchanged)
build store ──> compare_store_values.py, validate_store_gate.py   (unchanged)
```

- Two shapes: not run, no new module or boundary.
- Hand-synced list: `facts.FACTS_TABLES` repeats the names in `FACTS_SCHEMA` (existing). A fourth engine table left out of the tuple would stop the export ("data dictionary missing"), so the build fails rather than ships it.
- Failure modes: a store the engine never wrote has no tables (`IF EXISTS`); a failing `DROP` raises `sqlite3.Error`, which `export_distribution_data` already turns into "export: distribution copy failed" and leaves the previous publication in place.
- The manifest's `source_sha256` still covers the store with its facts, so a facts-only engine change still names a new generation. Unchanged behaviour.
- Later: A4 would render the site from the release. Fakt pages cannot be rendered from an export without these tables; Q5 takes them off the v1 site first (surface list, step 0).

## 2. Code quality review

CQ1 [INFORMATIONAL] (confidence 9/10) `scripts/build_dip_pulse_site.py:4977`: "**zurückgehaltenen Fakt** (`facts.withheld`)" (same at :164 and in `data_dictionary.json` `withheld_units.meaning`) names a column the export will not have. Part of the approved removal; fix is in "Text that would become false".

`manifest.transformation` (build:5613, shown on the Daten page) was considered and stays: it describes a removed column and claims no complete list.

Dispositions: CQ1 accepted (needed for the task's "no `facts` table in the export"; no separate choice).

## 3. Test review

Framework: `unittest` (CI: `python -m unittest discover -s tests`); lanes in `.gstack/pregate.json`.

```
CODE PATHS (_run_export and what reads the snapshot)
  ├── DROP TABLE IF EXISTS x3                                   [new]
  │     ├── [GAP T1]        store with facts: gone from sqlite, CSVs, manifest; store keeps them
  │     └── [★★ TESTED]     store without facts: every export test that skips the engine
  ├── schema_hash        [GAP T2] same with and without an engine run
  ├── _load_data_dictionary
  │     ├── [★★★ TESTED]    table missing / stale table or column refused (test_daten_export.py:560-570)
  │     └── [GAP T3]        a facts entry is refused too: one row in that table
  └── DATA.md, LICENSE-DATA.md, schema cards   [GAP T3] no facts table named
USER FLOWS
  ├── researcher downloads the release          [GAP T1]
  └── reader opens fakt/ and puls.html          [★★★ TESTED] tests/test_facts.py PageTests; clone page diff
COVERAGE: 3/7 today; 7/7 with T1-T3  |  GAPS: 4 (all in the plan's approved contract)
```

Regression at risk: the store keeps the three tables and the Fakt pages render. T1 asserts the store side after an export; `PageTests` covers the pages.

T1 value card: Value: protects=the release holds no facts table or file and the build store keeps them; fails_when=the drop is removed or runs on the store; why_new=tests pin the opposite; seam=none; no_claim=real-store size
T2 value card: Value: protects=schema_hash describes the exported schema only; fails_when=the drop moves after the hash; why_new=no test relates the hash to the tables; seam=none; no_claim=none beyond protects
T3 value card: Value: protects=no shipped text or dictionary entry names a dropped table; fails_when=a caption, DATA.md line or entry returns; why_new=no test scans them; seam=none; no_claim=prose naming Fakten

Tests to retire: `test_facts_tables_get_real_captions_not_the_fallback`, `test_fact_sources_description_names_agenda_items`, and the `fact_metrics`/`facts` codebook assertions (their subject leaves).

## 4. Performance review

No issues found. Three drops of about 5,000 rows on a copy; the export gets smaller.

## Decision ledger

No remedy needed its own choice. D1 (structure) is the scope record above. SC1, CQ1, the four test gaps, X1 and X2 are factual corrections or required proof of the task's contract (export holds no facts table or file; store and site unchanged).

Approval readiness: PASS (D1: adjudicator, 2026-11-27; no open ids)

## NOT in scope

- Fakt der Woche off the site: "Apply the v1 surface list".
- Sentences that explain how a withheld or cut sitting affects the site's Fakten (DATA.md, dictionary): still true, name no table; they leave with the pages.
- The gstack upgrade offered at skill start: sibling sessions share the install.

## What already exists

`_run_export`'s reshaping of the copy, the dictionary completeness check (used here as the guard in both directions), the manifest inventory check in `validate_manifest`.

## Failure modes

| Path | Failure | Covered by | User sees |
|---|---|---|---|
| drop | removed or moved after the hash | T1, T2, dictionary check | export stops with the table's name |
| dropped rows | survive in free pages of the file | VACUUM INTO; byte search in Verification | n/a |
| build store | drop runs on the store | T1 | n/a (source opened read-only) |

0 critical gaps.

## Outside voice

Codex (`gpt-6.1-sol`, read-only, completed), 2 findings, both Medium, both factual corrections to this plan's own checks, so no decision was needed:

- X1 accepted: test 3 forbade the table names in LICENSE-DATA.md and DATA.md while the licence bullet was to name them. The bullet now describes the tables without their identifiers; test 3 stays strict.
- X2 accepted (checked at build:13851 and :13966): the generation id changes with the format and appears on pages besides `database.html`. Verification now normalises run-dependent values first.

## Parallelization

Sequential implementation, no parallelization opportunity.

## Implementation Tasks

- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — tests — failing export tests (T1–T3), update the count and format literals, retire the two caption tests
  - Surfaced by: Test review
  - Files: tests/test_daten_export.py, tests/test_facts.py
  - Verify: the new tests fail on main, pass after T2
- [ ] **T2 (P1, human: ~30min / CC: ~10min)** — export — drop the three tables, format 29, remove entries and the exemption (CQ1 sentence included)
  - Surfaced by: Code quality CQ1 and the plan's "Change"
  - Files: scripts/build_dip_pulse_site.py, scripts/data_dictionary.json
  - Verify: tests/test_daten_export.py
- [ ] **T3 (P2, human: ~1h / CC: ~10min)** — docs — correct every text that names the tables or format 28
  - Surfaced by: Scope Challenge SC1 and the plan's "Text that would become false"
  - Files: LICENSE-DATA.md, README.md, docs/stable-ids.md, docs/project-documentation.md, docs/designs/fakt-der-woche.md, docs/adr/0003-licences-and-impressum.md, CONTEXT.md, CHANGELOG.md, TODOS.md
  - Verify: repo search for the table names

## Completion summary

- Step 0: Scope Challenge: scope accepted as-is (1 factual finding, SC1)
- Reality rows: 7/7 applicable rows emitted (`PLAN_REALITY ... verdict=complete`), 0 unverified premises
- Architecture Review: 0 issues found
- Code Quality Review: 1 issue found (CQ1)
- Test Review: diagram produced, 4 gaps identified (all within the approved contract)
- Performance Review: 0 issues found
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 0 items proposed
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 0 in this review
- Outside voice: Codex, completed (2 findings, both accepted)
- Parallelization: 1 lane, sequential
- Lake Score: N/A (the one question differed in kind)

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Review | Codex via `/plan-eng-review` | Independent 2nd opinion | 1 | completed | 2 findings, both accepted |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN | 5 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:** Codex (`gpt-6.1-sol`), plan review, completed: 2 Medium factual corrections to the plan's checks.
- **CROSS-MODEL:** no overlap: the native sections found the dangling `facts.withheld` text; Codex found two checks that could not pass.
- **VERDICT:** no open decision; the 5 issues are mapped to T1–T3 in this plan. Ready to implement.

NO UNRESOLVED DECISIONS
