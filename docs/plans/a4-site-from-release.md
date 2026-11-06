# A4: Split the dataset from the site, so the site builds from a release alone

## Context

This is roadmap item A4: TODOS.md "Split the dataset from the site: the site builds from a release alone" (effort L, P2). A1–A3 are done (v0.27.0.0, 4705fb3). The TODO's done criterion is: an offline build from a downloaded release SQLite, with no report JSON present, produces the same site as today's build. The dev-view API dumps are exempt.

**Status (2026-11-06):** the v1 scope review (`docs/plans/v1-scope-review.md`) requires slices 2 to 11 before the public site and none for the data release. D8: no AI summaries in v1, so slice 5 adds no `summaries` table. D9: as recommended. D10: both dumps dropped; slice 7 first checks no needed field exists only in the dump. Fakt der Woche is off the v1 site, so slice 3 drops its gap notes rather than moving them.

**Status (2026-11-04):** a re-scope to a static site generator was reviewed and **held by the owner** (ledger R17, part "A4 re-scope for a new frontend" near the end of this file): design pass, chart prototype and a go/no-go come first (TODOS.md "Decide the frontend stack"). Slice 1 has since shipped in Python (#133, v0.32.0.0). **The go/no-go ended in no-go on 2026-11-04 (`docs/plans/frontend-go-no-go.md`), so R10 to R16 are not applied and A4 continues in Python.**

**Status (2026-11-03):** slices 0 and 1 built (slice 1's reference-store oracle owed, see "Slice 1 result"). **Status (2026-11-01):** passed /plan-eng-review (see the review part at the end of this file). Ledger entries R1–R9 are settled; do not reopen them without new evidence. Owner decisions D8–D10 stay open until their slices. Slices 0 and 1 are planned down to individual tasks and land as two PRs; later slices are headlines only, because slice 1 will change what they need.

### What the code does today (census, 2026-11-01, at 4705fb3)

Line refs: `B` = `scripts/build_dip_pulse_site.py`, `R` = `scripts/render_dip_pulse_html.py`.

| Page / output | Reads |
| --- | --- |
| Dossiers `protocols/*.html` (`write_report_files` B:1088 → `render_html` R:2978) | report JSON; also `vorgang_cache`, `person_corrections.json`, and `mp_lookup` from the store |
| `puls.html` (`render_front_page` B:6575), the landing page (B:5254), the votes card (B:5421) | report JSON plus `vorgang_cache` |
| `votes/index.html` (`collect_votes_archive` B:5510, `render_votes_archive_index` B:5565) | report JSON plus `vorgang_cache` |
| Bills pages and `data/bills.json` (`collect_bill_pages` B:7254) | report JSON. The public "Erfasste Quelldaten" raw dump is at B:8324. |
| `overview.html`, `api-sitzungen.html`, `sources.html` | report JSON plus the catalog file. The public "API-Felder" raw dump is at B:10802. |
| `data/features.json` (`build_publication_manifest` B:11833) | report JSON (`acquisition.*`, `llm_summary`, aw urls) |
| `abgeordnete/*` | store. `publication_domains` comes from the JSON-derived manifest. |
| `fakt/*` | store, plus `entries` for gap notes (`completeness_from_entries`, B:10264) |
| `database.html`, `data/exports/**` | store, plus render artifacts: `mp_lookup` → `has_page`, `readiness`, `catalog_count`, `dossier_count`, `excluded_sittings` |

These inputs are outside the store and outside the release, and the renderers read them:
- `data/plenarprotokoll-*.json`
- `data/plenarprotokoll-catalog.json`, which holds every sitting, including those without a dossier
- `dip-vorgang-cache.json` and the Antrag cache
- `person_corrections.json`, applied at render time through `registry.corrected_speaker`
- `coverage-exclusions.json`

Data the site shows that the store does not hold, or holds lossily:
- **AI summaries and their receipts:** no table.
- **Acquisition states:** no table. This is the planned `protocol_acquisition`.
- **Validation `warnings` and `aktivitaet_count`:** not stored.
- **Speech paragraph boundaries:** `speeches.text` is whitespace-collapsed, and `paragraphs_json` was dropped.
- **Per-speech role text:** not stored.
- **Per-item Drucksache order and source label:** not stored. The page applies "XML url wins over DIP url" per item, but the store keeps one merged url.
- **Proceeding positions:** `proceeding_positions` upserts overwrite `agenda_item_id` when two TOPs share a position.
- **Vote details:** `vote_heading`, fraction order and raw member `faction` spelling are not stored.
- **Untagged vs not fetched:** Politikfeld `untagged` and `not_fetched` collapse into one stored row.

**Can the site build from a release today? No.**
- The release is gzipped, and the build has no gunzip step.
- `run_facts_engine` refuses a distribution copy (`require_build_store`).
- Every page except `abgeordnete/*`, `fakt/*` and the Daten page needs `entries`.

**Store measurements** (`~/agent-runs/a3/full`, the A3 full build; it predates the post-merge rebuild, see D3):

| Measurement | Value |
| --- | --- |
| Protocols / report JSON files | 716 / 717 |
| Votes / vote_members | 556 / 382,441 |
| Votes with a `vote_politikfelder` row | 556. By source: drucksache 545, top 8, untagged 3. |
| Votes with no `agenda_item_votes` row (sitting-level) | 0 |
| Votes with no `vote_documents` row | 4 |
| Free disk | 43 GB |

## Decisions

These are the plan's own decisions D1–D10. The eng review of 2026-11-01 settled or replaced several of them; its ledger entries R1–R9 (below, under "/plan-eng-review") are authoritative where they differ. The review asked its own questions D1–D10 as well; ledger entries name which one answered each.

### D1: Equivalence target (replaced by R4 + R8)

Each slice renders its page type at the base commit and at the branch tip from two clones of one store (D3), and compares them with a strict `diff -ru`. The only allowed diff is **(a) the store is more correct**, with old and new values recorded. A **(b) store is lossy** diff is fixed in persist and compared again. No order or whitespace exemption: fraction order is stored (R8). For fields that both the archive and a still-JSON page show, the two pages must agree (R3).

### D2: What renders when there is no persistent store (replaced by R1)

The site always renders from a store. `--no-persist` is removed with all its `not no_persist` branches; a preview runs in a scratch output dir (README "Try a fetch or a backfill in a scratch directory"). Tests and `build_demo_site.py` build a temporary store through the production rebuild path. The pre-rebuild dossier write at B:2860 goes away in slice 4 (T0.3 moved there).

Caveats kept: the temporary store costs a rebuild per test that renders (T0.2 measures it), and the temp store must go through `rebuild_database_from_entries` rather than bare `persist_report` if their person links differ (T0.2 checks).

### D3: Oracle baseline

- Make two APFS clones of `~/agent-runs/a3/full`:
  - clone A: run `--offline --repersist` and render at the slice's base commit (a separate worktree at that commit);
  - clone B: the same at the branch tip;
  - then `diff -ru A/<pages> B/<pages>`.
- One shared directory can't work: once a slice bumps the schema, the branch's `require_current_schema` refuses the base-commit store, and the other way round.
- T1.1 runs before any code changes, so it can use one repersisted clone.
- Do not diff against the A3 store as it is. The A3 post-merge rebuild and gate are still owed, so it may not match main.
- Cost: one repersist of 716 protocols is estimated at about 10 minutes [estimated from about 245 s per 284 protocols; T0.6 measures it]. A clone costs almost no disk until written; a written store is about 0.85 GB.

### D4: Oracle permanence

The old-vs-new diff is a **one-off check per slice**, recorded in this file (page counts, every (a) diff with old and new values). No compare script until slice 10, where the full-site check needs the dev-view exemption (Scope record). After the old path is deleted, the permanent tests are **store-seeded fixture tests** built through the production rebuild path. A permanent golden-HTML test was rejected: it would break on every copy change and duplicate the structured assertions.

### D5: Render-side read layer (replaced by the Scope record)

No `scripts/site_store.py` in slices 0–1. The archive's store reads live in `scripts/features/votes.py`, next to the archive code, and go through an adapter that feeds the existing rule functions (R5). The store opens through `facts.open_readonly` + `pulse_store.require_current_schema`. A shared reader is extracted when slice 2 brings the second page type. Still true for later slices: Reden counts go through the planned "One module that counts Reden and Beiträge", and persons and links through `collect_abgeordnete` / `mp_lookup` until "One Persons module" lands.

### D6: Feature-selection axis in slice 1

Slice 1 removes only the votes-archive piece of "Delete the feature-selection axis":
- the `collect_votes_archive` and `write_votes_archive_page` ctx callables (B:12305-12306);
- `VotesComponent.write_pages`.

`render_site` then calls the archive writer directly with an open store. The rest of that TODO stays open.

### D7: Schema and export versioning

One schema bump per slice that changes the store, batched inside the slice. Slice 1 takes `SCHEMA_VERSION` from 8 to 9 and `EXPORT_FORMAT` from 11 to 12. Each bump updates DATA.md, the codebook, `docs/data-changelog.md`, `compare_store_values.py` and `validate_store_gate.py` where they name the changed tables. Review checklist class 11 applies to every changed sentence. Holding the format bump until slices 1–3 land was proposed (outside voice O10) and rejected: CLAUDE.md's pre-release rule says no reader depends on any export format.

### D8 (owner, before slice 4): AI summaries and receipts in the release

To show summaries on a release-built site, they have to be in the release. They are generated text, so they need their own licence layer under ADR 0003 and a "generated, not editorially checked" flag on every row. The alternative is a separate site-only file next to the release, which weakens the done criterion.

Recommendation: put them in the release as their own table, with model, prompt version and receipts. **Open.**

### D9 (owner, before slice 5): DIP Vorgang records and abgeordnetenwatch fields

The Vorgang cache feeds the Politikfelder, "Worum es geht" and the Antrag passages. The persisted results already sit in `vote_proceedings`, `proceedings.abstract`, `vote_passages` and `documents.forderung`. The renderers must read those instead of the cache.

Recommendation: no new third-party data enters the release. Renderers read only what is already persisted, under the existing layers. **Open.**

### D10 (owner, at the bills and catalog slices): the two public raw dumps

These are the bill page's "Erfasste Quelldaten" (B:8324) and the catalog page's "API-Felder" (B:10802). They dump raw records that the release does not hold.

Recommendation: **drop both.** Their content is in the release in structured form, and a raw dump on a citizen page breaks principle 3. The alternative is to move them into the exempt dev view. **Open.**

## Slice map

Sibling TODOs that a slice needs are listed under **Needs**. A slice may not start before its needs land. Slices 0 and 1 are separate PRs (R7).

| # | Slice | Needs | Store additions |
| --- | --- | --- | --- |
| 0 | Harness, PR 1, behaviour-neutral for pages: `--no-persist` removed (R1), temporary-store fixture for tests (the demo moved to slice 1, see "Slice 0 result"), coverage refusal (R2), missing-store refusal (F7) | none | none |
| 1 | Votes archive (`votes/index.html`), PR 2 | 0; a demo fixture under the current speech rule (see "Slice 0 result"). The member-row loss is already fixed (#107, v0.21.0.0): 0 of 3,866 groups short on the repersisted A3 clone, 2026-11-01 | Politikfeld state, `agenda_item_documents.url`, `vote_documents.rank`, `vote_fractions.rank`, missing vote totals as NULL (T1.2) |
| 2 | Catalog table: catalog page, overview, landing, facts' `SittingCatalog`, export `catalog_count`/`dossier_count`, coverage exclusions; extract the shared store reader | 0 | `sittings` (the DIP catalog incl. sittings without a dossier), `coverage_exclusions` |
| 3 | Acquisition state: dossier vote-panel status copy, profile notice, facts gap notes (drop `completeness_from_entries`), publication manifest and `readiness` | TODOS "Typed completeness gaps", then "Persist per-sitting acquisition state (`protocol_acquisition`)", which this slice implements | `protocol_acquisition`, validation counts and warnings |
| 4 | Dossier vote panels and the puls votes card; the single online dossier write (T0.3) | 1, 3 | `vote_heading`, member faction as printed |
| 5 | Dossiers (rest): speeches, Beiträge, Drucksachen, positions, AI summaries | TODOS "One module that counts Reden and Beiträge", D8 | paragraphs, role text, per-item document order, position-to-item links, `summaries` + receipts |
| 6 | `puls.html` (radar, week comparison, topic rows) | 5 (Reden module, summaries) | probably none |
| 7 | Bills pages and `data/bills.json` | 5, D10 | none expected |
| 8 | `sources.html`, the remaining manifest inputs | 2, 3 | none expected |
| 9 | Export as its own module `export(store, out_dir) -> manifest`; `has_page` from the store | TODOS "One Persons module", plus the Reden module | `has_page` computed from the registry |
| 10 | Release-only build: `--from-release <file.sqlite[.gz]>` (a proposed flag) | 1–9 | none |
| 11 | File split: the renderers leave `build_dip_pulse_site.py` | 10 | none |

**Slice 10 in detail:**
- gunzip into the private staging dir;
- open read-only and accept a distribution copy on the render path only;
- run no persist, no facts engine and no export;
- build the Daten manifest from the release's `datenstand` table and its own files;
- no `data/plenarprotokoll-*.json`, no catalog file, no caches, no `person_corrections.json` on disk.

Done check: render once from the release and once with today's normal build of the same data, then compare all pages with a compare script that exempts the dev view (written in this slice). Every input listed under "What the code does today" must be persisted by then, or this check fails.

**Overlapping TODOs that A4 closes or absorbs**, to be marked in TODOS.md when each lands:
- `protocol_acquisition` (slice 3);
- the archive part of "Delete the feature-selection axis" (slice 1);
- the B:1146 export inputs (slice 9);
- "Stale derived data" notes in the persisted Politikfeld and context tables, which renderers will now read instead of re-deriving.

## Slice 0: harness (PR 1)

PR 1 changes no page. Its own check: render the full site from one repersisted clone before and after PR 1 and `diff -ru` it; the result must be empty.

**T0.1 Store open and missing-store refusal (F7)**
- Store-reading renders open the store through `facts.open_readonly` + `pulse_store.require_current_schema`; they never call `require_build_store`, which guards writes.
- A render with no store file exits 1 with a message naming `--offline --repersist` (or an online run), never a sqlite "unable to open database file" traceback (checklist class 9).
- Tests: a missing store file; a read-only open leaves the store byte-identical.

**T0.2 Temporary store for tests and the demo (R1)**
- `tests/_site_store_fixture.py` and `build_demo_site.py` build a temporary store from their entries through the production rebuild path and render from it.
- **Path check:** persist the same fixtures once through bare `persist_report` and once through `rebuild_database_from_entries` with carry-forward off, then compare `collect_abgeordnete`'s `mp_lookup`. Use the rebuild function if they differ.
- **Measure:** the full suite time before and after; record both here (budget kept as measure-only, outside voice O5).
- Checklist class 10: if the process stops at any point, no temp store is left outside the private dir; the private-dir sweep removes it.

**T0.3** moved to slice 4: the single online dossier write. Remove the pre-rebuild page write at B:2860 and keep the JSON write. A run whose rebuild fails would then leave no page for the sittings it fetched; say so in the CHANGELOG when it lands.

**T0.4 Remove `--no-persist` (R1)**
- Delete the flag from `parse_args` (B:13056) and every `not no_persist` / `no_persist=` branch (facts pages B:10250, MP pages B:13658, export, `render_site`).
- Re-point the 9 test files that pass `no_persist=True` or `--no-persist` to the T0.2 fixture.
- Docs: `docs/project-documentation.md:145-175, 271, 428, 497`, README:288 and :449 point previews to the scratch output dir recipe.
- Test: argparse rejects `--no-persist`.

**T0.5 Coverage refusal (R2)**
- Before every store-reading render (offline, and online after the rebuild): the cached entries minus recorded exclusions and the store's `protocols` must name the same sittings in both directions; otherwise exit 1 naming up to 5 sittings and the `--offline --repersist` repair.
- Tests: one report not in the store; one store sitting with no report; a normal online `--detail-limit` run and a `--document-number` run pass (outside voice O4: `merge_detail_entries` B:1326 merges every cached entry, and the store is rebuilt from the same list).

**T0.6 Baseline recipe (D3)**
- Write the exact commands into "Verification": the two clones, the repersist of A at the base commit and of B at the branch tip, and the `diff -ru`. Measure one repersist and replace D3's estimate.
- Reuse the README "Validate a data correction" layout under `.context/`, or `~/agent-runs/a4/` if `.context` is short of space.

## Slice 0 result (2026-11-01)

Built on `claude/a4-todo-plan-3119e1` on top of 40fa3bc.

**What landed**
- **T0.4:** `--no-persist` is gone, with every `not no_persist` branch: `parse_args`, `run_data_pipeline`, `render_site`, `write_facts_pages`, `FactsComponent`, `main`. Also gone: `facts.compute_and_store(no_persist=)`, which had no caller left.
  - An online run now always persists. Online `main()` tests patch `refresh_vorgang_cache`, so they never reach DIP, and run the real staged rebuild.
  - The shared test builder `SittingWeekComparisonTests._entry` now carries a protocol id and `speech_kinds_version`, so a build can persist it.
  - Docs: `docs/project-documentation.md` and the README, with the one-sitting preview pointing to the scratch-directory recipe.
  - `database.html`'s fallback copy no longer names the flag. In a build, that fallback is now reached only through `DataExportUnavailable`.
- **T0.1 / F7:** an `--offline` render with no store exits 1 with `error: no store at …; the offline render reads it`, naming `--offline --repersist`, before any page is written. The check runs after the read-only cached-report load and the `--week` check, so those refusals keep their order.
  - Tests: a missing store; an offline render that leaves the store byte-identical.
- **T0.5 / R2:** `store_coverage_gap` compares the cached entries (minus recorded exclusions) with the store's `protocols`.
  - It matches on the protocol id, through `pulse_store.clean`, the key persist and the rebuild's missing-evidence check use.
  - It runs offline before any page is written, and online after the staged rebuild.
  - It names up to 5 sittings in each of three cases, each with its repair:
    - a cached report the store does not hold: repersist;
    - a stored sitting without a report: restore the report, or exclude the sitting;
    - a sitting recorded as excluded that the store still holds: repersist. This is the case where `update_coverage_exclusions` ran and the online rebuild then failed.
  - Tests: all three cases end to end, unit tests for the label limit and id matching, and a plain offline render with a pre-rule report, which warns and then refuses.
  - The existing `--detail-limit 1` (`test_online_main_accepts_a_week_held_only_by_preserved_dossiers`) and `--document-number` (`test_backfill` `RetainedScopeTests`) main tests run the real rebuild and the real check, and pass (outside voice O4).
- **T0.2:** `tests/_site_store_fixture.py` builds a store through `rebuild_database_from_entries`. It refuses an OUTPUT that is the temporary directory itself, so `.OUTPUT.private` cannot leak into `$TMPDIR`.
  - **Path check:** the same 4 reports gave different results on the two paths, because bare persist does not reconcile persons.

    | Path | `mp_lookup` keys | MPs |
    | --- | --- | --- |
    | bare `persist_report` | 18 | 6 |
    | `rebuild_database_from_entries` | 28 | 3 |

    The fixture therefore uses the rebuild path.
  - Direct `render_site` tests stay store-less until T1.6. `render_site` does not open the store in slice 0, and with no store file they render exactly as `no_persist=True` did.

**Deviation from R1 (owner to confirm): the demo is not yet built from a store.**
- `tests/fixtures/demo-report-21-84.json` predates speech rule 6: no `speech_kinds_version`, no per-speech kinds. The rebuild refuses it, correctly.
- Re-reading it from the real 21/84 XML fails ("agenda item set changed"), because the fixture holds a trimmed subset of TOPs.
- Stamping the version onto it would publish old-rule counts as current.
- So `build_demo_site.py` still renders store-less in PR 1, and a demo fixture rebuilt under the current rule is now a **Need** of slice 1. A store-reading archive breaks a store-less demo.
- **Resolved for slice 1 (2026-11-03).** The fixture was regenerated from the real 21/84 XML (sha256 `3fd2ef65…6c7790`) by `scripts/extract_demo_fixture.py`, which now takes `validation_summary` from `contribution_summary` over the one extracted TOP, as a real report does. Its agenda item came out byte-identical to the committed one: the old fixture already held today's parse (14 Reden; 1 Kurzintervention, 1 Erwiderung, 1 Zwischenfrage), it only lacked the rule stamp and summary keys. The re-read path stays unusable for it (the trimmed TOP set), so the extractor, not `--fetch-xml`, is how it follows a rule change. `build_demo_site.py` now persists it through `rebuild_database_from_entries` into `OUTPUT/data/bundestag-pulse.sqlite`, reads the Abgeordnete back with `collect_abgeordnete`, and renders with that store; a fixture without the current rule stops it with exit 1.

**Measurements**

| Measure | Value |
| --- | --- |
| Full suite at 40fa3bc (unloaded) | 151 s |
| Full suite at the tip (unloaded) | 126 s, 1914 tests |
| Suite on Python 3.13.12 (uv) | 1914 tests OK |
| `--offline --repersist` with render and export, clone A (base) | 2,570 s |
| The same, clone B (tip) | 1,600 s |

Both timings cover repersist, render and export. B's 1,600 s matches the README's recorded 1,650 s for the same steps; A shared the machine with a test run and another session's repersist. They replace D3's 10-minute estimate: a repersist with render and export of the 716-sitting store takes about 27 minutes.

**PR 1 oracle (D3):** two `cp -cR` clones of `~/agent-runs/a3/full`, A repersisted and rendered by 40fa3bc, B by the tip.
- B passed the R2 check on the real data (716 protocols, the real exclusion record).
- `diff -rq` shows 5 pages and 2 JSON files differing, plus the export generation directory. After the volatile tokens are normalised, every page and `data/features.json` is identical, except `database.html`'s sha256 and size lines for the export files. Those have the same cause as `datenstand.json` below. The tokens:
  - the generation name `g-…`;
  - wall-clock timestamps and the "Stand … MEZ" line;
  - the build revision, which both sides resolve from this worktree's git, so it names no code.
- All 37 export files have equal content once timestamps are normalised, except the hashes and byte sizes computed over the timestamped store and CSVs: `datenstand.json`, `DATA.md`'s file inventory, `datenstand-local.csv`.
- `compare_store_values.py A B`: nothing moved. 0 protocols changed, 0 of 1,908 Fakt values moved, page counts equal.
- Result: no page changed.

**Recipe** (T0.6), from the repository root:

```bash
cp -cR ~/agent-runs/a3/full .context/a4/A && cp -cR ~/agent-runs/a3/full .context/a4/B
mkdir -p .context/a4/src-base .context/a4/src-tip
git archive <base> | tar -x -C .context/a4/src-base     # the tip: archive HEAD into src-tip, then apply `git diff`
SOURCE_DATE_EPOCH=1793491200 python3 .context/a4/src-base/scripts/build_dip_pulse_site.py --offline --repersist --output-dir .context/a4/A
SOURCE_DATE_EPOCH=1793491200 python3 .context/a4/src-tip/scripts/build_dip_pulse_site.py --offline --repersist --output-dir .context/a4/B
diff -rq .context/a4/A .context/a4/B -x '*.sqlite' -x '*.sqlite.gz' -x '*.lock'
python3 scripts/compare_store_values.py .context/a4/A .context/a4/B
```

Normalise `g-[0-9a-f]{12}`, ISO timestamps, the "Stand dd.mm.yyyy, hh:mm MEZ" line and the build revision on copies before the content diff. Compare the export CSVs gunzipped, with timestamps normalised. Slice 1 needs the same normalisation: wall-clock values differ between any two builds.

**Review checklist** (`docs/agents/review-checklist.md`, full pass; the diff is over 200 lines):

| Class | Answer |
| --- | --- |
| 1 Sibling path | F7 and R2 run on every path that renders from `main`. `--offline` runs both before any page write (B:`main`, after `reject_unknown_week`). `--offline --repersist` builds the store first, then runs the same checks. The online path runs R2 after `rebuild_database_from_entries`; F7 cannot fire there, because the rebuild creates the store. `--fetch-xml` and `--validate-publication` return before rendering. Direct `render_site` calls and `build_demo_site.py` stay store-less by design until slice 1. `scripts/preview_dip_pulse_site.sh` calls `main` and inherits both. |
| 4 One key | `store_coverage_gap` keys on `pulse_store.clean(protocol.id)`, which `replace_protocol` writes as `protocols.id`. The rebuild's missing-evidence check uses the same key. Exclusions match on `normalized_document_number`, as `without_recorded_exclusions` and the rebuild do. |
| 5 Absent vs zero | Empty store against no reports passes (unit test). A report with no id is keyed `""`, never matches a stored id, and is named by its document number. |
| 9 Input shape | A malformed `coverage-exclusions.json` raises an uncaught `RuntimeError`. That predates this diff (`without_recorded_exclusions`, `repersist_cached_reports`, the online `listed` set) and is recorded in TODOS.md. |
| 10 Interrupted run | No new writes. The fixture's staged stores live under a test's temporary directory. The fixture refuses an OUTPUT that is the temporary directory itself. |
| 11 Claims | The README rows for both refusals cite `store_coverage_gap` and the F7 block, and say "no page is written" (the tests assert no `puls.html` and an empty `protocols/`). The `docs/project-documentation.md` store row matches `main`. The `database.html` fallback copy matches its only reachable cases. |
| 13 Last commit | Owed at commit time. |
| 2, 3, 6, 7, 8, 12 | Not touched: no merge, carry-forward, matcher, scanner, derived column or per-row loop. The coverage check is two set operations over 716 rows. |

**CHANGELOG line for /gstack-ship:** "Removed `--no-persist`: every page renders from the SQLite store. To preview without touching the site you serve, build into a clone copy of the output directory (README 'Try a fetch or a backfill in a scratch directory'). An `--offline` render now refuses when there is no store, or when the store and the cached reports cover different sittings, and names the repair (`--offline --repersist`, or restoring a report). No page changed: the full-site diff against 40fa3bc is empty apart from timestamps."

## Slice 1: votes archive from the store (PR 2)

Needs PR 1 and a demo fixture under the current speech rule (Slice 0 result). The lost member-row fix is already in (#107); T1.1's count of short groups is expected to be 0. `votes/index.html` reads no members except for the Abweichler count, no acquisition state, no committee and no lead.

**T1.1 Measure first** (one repersisted clone, before any code; record the numbers here):
- Archive rows whose Politikfelder differ between `politikfelder.report_politikfelder(report, vorgang_cache)` and the stored `vote_politikfelder`.
- Per-link urls: for every vote link, whether `documents.url` equals the per-item winner of `document_source_links` (R6 makes this moot for the page; the count goes in the data changelog).
- Which agenda item supplies a vote's links: the collector keeps the first seen (B:5536-5537); confirm that equals the lowest `item_index` in `agenda_item_votes`, and that `votes.id` equals `pulse_html.vote_key` for every vote (outside voice O3).
- The 4 votes with no `vote_documents`: does the JSON path show links for them? If yes, they are a (b) gap (outside voice O9).
- Votes whose member groups don't cover their fraction counts on the store (expected 11 before the member-row fix, 0 after).

**T1.2 Persist what the archive needs** (schema 9, D7):
- **Politikfeld state:** keep `not_fetched` apart from `untagged` (a `vote_politikfelder.source` value or a `votes.politikfeld_state` column), so the store can tell "Ohne Politikfeld" from "not fetched".
- **Per-link url (R6):** add `agenda_item_documents.url`, the url that source printed for that item.
- **Link order:** add `vote_documents.rank`, the order of `vote.document_numbers`.
- **Fraction order (R8):** add `vote_fractions.rank`, the first-seen order of `merge_fractions`.
- **Missing totals:** `persist_vote` writes `int(total.get("yes") or 0)` (persist:1342-1345); store a missing count as NULL so `vote_groups_cover_total` can't pass on an invented 0 (checklist class 5).
- Rejected: persisting `votes.abweichler_count` from the report; the release's own `vote_members` rows could not reproduce it.
- Update DATA.md, the codebook, `docs/data-changelog.md` and `EXPORT_FORMAT` for every added column.

**T1.3 Store-to-vote adapter in `features/votes.py` (R5)**
- Build vote and item dicts from store rows: fractions `ORDER BY rank`, members, `document_numbers` by `rank`, the supplying item's `api.linked_drucksachen` / `xml_drucksachen` from `agenda_item_documents` with their urls, Politikfeld tags with their state. The supplying item is the lowest `item_index` (T1.1).
- Run the existing functions unchanged: `derive.merge_fractions`, `_fraction_position`, `derive.vote_abweichler_count`, `_vote_procedure_type`, `politikfelder.shown`, `votes_feature.document_source_links` / `document_source_chambers`, `votes_feature.vote_anchor_id`.
- **href:** `../protocols/<slug>.html` from `protocols.document_number` through the same slug function the dossier writer uses (checklist class 4).
- **Order:** date, then `_vote_id_sort_key`, descending, as today.
- **Reads (F8):** set-based, one query per table grouped by `vote_id`, never per vote inside the loop (382,441 `vote_members` rows, 556 votes [measured on the A3 store]); record the archive's render time on the full store (checklist class 12).

**T1.4 Rewire and delete**
- `render_site` opens the store and calls the archive writer with the adapter's rows (D6).
- Delete `collect_votes_archive`, the ctx callables and `VotesComponent.write_pages`.
- `politikfelder.report_politikfelder` stays as long as other pages use it.

**T1.5 Footer copy**
- The archive footer says "Die Liste umfasst die Dossiers, die in diesem Build mit --detail-limit erzeugt wurden". After this change the list covers the votes in the store. Reword it, and cite the code line that makes the new sentence true (checklist class 11). Keep the disclosure that "Say when a count covers only Sitzungen mit Dossier" relies on.

**T1.6 Tests (R4)**
- Port the archive suites to store-seeded fixtures (`tests/_site_store_fixture.py`), keeping every assertion: `tests/test_build_dip_pulse_site.py:2789-3250`, `tests/test_b1_consumers.py:76-125`, `tests/test_mehrheitsvotum.py:102-109`, `tests/test_politikfelder.py:1416-1442`, `tests/test_vote_interpretation.py:625-645`.
- Rewrite `tests/test_politikfelder.py:1445`: the Vorgang cache takes effect at persist; an offline render without repersist keeps the persisted tags.
- New cases: `not_fetched` vs `untagged`; link order and the xml-over-dip url and label from per-item rows; fraction order from `rank`; incomplete Abweichler stays absent; a missing vote total stored as NULL; a sitting-level vote (no `agenda_item_votes`); a vote with no `vote_documents`; a vote under two TOPs takes the lowest `item_index`.

**T1.7 Oracle run (R4, R8, R3)**
- With the two D3 clones, `diff -ru A/votes B/votes` must show only (a) diffs, each recorded with old and new values; loop on (b).
- Cross-page agreement (R3): for every vote, the archive row and the dossier panel show the same result badge, Drucksache links and Abweichler figure. A disagreement is fixed in persist or the JSON path, or slice 1 waits.

## Slice 1 result (2026-11-03)

Built on `claude/peaceful-heisenberg-tr9f0f` on top of 940ed88. The reference store (`~/agent-runs/a3/full`) was not on the build machine, so T1.1's measurements and the T1.7 oracle are **owed** (recipe below). Everything else landed.

**What landed**
- **Schema 10 / export format 14** (not 9/12 as planned: C1 took schema 9 and format 13 first). `require_current_schema` refuses a schema 9 store (no `vote_fractions.rank`) with the upgrade command.
  - `vote_fractions.rank`: first-seen order of `derive.merge_fractions` (R8); `_repoint_party` keeps the smaller rank when it merges two rows.
  - `vote_documents.rank`: place of the number's first occurrence in `vote.document_numbers`.
  - `agenda_item_documents.url` (R6) and **`agenda_item_documents.rank`**. The rank is an addition to the plan: `_vote_procedure_type` reads the TOP's DIP links in their order, and a table without an order column has none (checklist class 3). The url follows `document_source_links`: an XML reference listed twice under one TOP ends on its last url, a DIP link on its first.
  - `votes.yes_count` / `no_count` / `abstain_count` / `absent_count`: nullable; persist writes NULL for a count the report does not give (`_total_count`), never 0.
  - **Politikfeld state needed no column.** `vote_politikfelder.source` already stores `not_fetched` apart from `untagged`, and the adapter hands `politikfelder.shown` the stored `(tags, source)`.
  - Data dictionary, README, CONTEXT.md, `docs/stable-ids.md`, `docs/project-documentation.md` updated. `scripts/compare_store_values.py` gains a "vote totals" section (votes with a NULL count; every shared vote whose total moved, old and new). `scripts/validate_store_gate.py` records `votes_without_total` in the receipt.
  - **Recipe r4** now leaves out a vote with a NULL Ja or Nein total. Before, such a vote was stored as 0:0, so it ranked first with Differenz 0; with NULL it would still sort first (SQLite puts NULL first in `ASC`). The method text says so.
- **T1.3 adapter:** `features.votes.stored_votes(conn)` reads seven queries (fractions, members, document numbers, Politikfelder, supplying TOPs, TOP links, votes), groups them by vote id, and returns `StoredVote`s in the report shapes. `build_dip_pulse_site.votes_archive_rows(database_path)` then runs the unchanged rules (`merge_fractions`, `_fraction_position`, `vote_abweichler_count`, `_vote_procedure_type`, `politikfelder.shown`, `document_source_links`/`_chambers`, `vote_anchor_id`).
  - The supplying TOP is the lowest `item_index` among the vote's TOPs in its own sitting.
  - A member's identity is its `mps` id (one `vote_members` row per vote and MP).
  - href: `report_paths(…, protocols.document_number)`, the dossier writer's slug.
  - No store file: an empty archive, as the Fakten pages behave; `main` refuses that case first (F7).
- **T1.4:** `render_site` calls `write_votes_archive_page(output_dir, votes_archive_rows(database_path), features)`. Gone: `collect_votes_archive`, `VotesComponent.write_pages`, and the two ctx callables.
- **T1.5 copy:** header "Jede namentliche Abstimmung der erfassten Sitzungen, neueste zuerst."; footer "Die Liste umfasst die namentlichen Abstimmungen der Sitzungen in der Datenbank dieses Builds, also nur Sitzungen mit Dossier; sie enthält nicht jede Sitzung des Katalogs." True because the store holds exactly the cached reports minus the recorded exclusions (`store_coverage_gap`, checked by every render from `main`), and every cached report is written as a dossier.
- **T1.6 tests:**
  - `tests/_site_store_fixture.py` gains `persistable` (it fills in a protocol id and the current speech-rule version, nothing else) and `archive_rows(entries, vorgang_cache)`, a rebuilt store read by `votes_archive_rows`. Every ported archive assertion now runs through the production rebuild path.
  - Ported: `test_build_dip_pulse_site.VotesArchiveTests`, `test_b1_consumers`, `test_mehrheitsvotum`, `test_politikfelder`, `test_vote_interpretation`, and `tests/votes_archive_browser_fixture.py`.
  - Dropped: `test_write_page_is_skipped_when_the_votes_feature_is_off`, because the switch is gone.
  - Rewritten:
    - `test_collect_leaves_href_none_when_page_path_is_missing` becomes `test_href_names_the_dossier_of_the_votes_sitting_by_its_protocol_number`.
    - `test_politikfelder.py:1445` becomes `test_the_archive_shows_the_persisted_tags_and_the_front_page_the_render_time_cache`: the cache takes effect at persist, and an offline render without a repersist keeps the persisted tags.
  - New: link order with the per-item xml-over-dip url (an XML reference listed twice, a DIP link listed twice, another sitting printing another url); fraction order from `rank`; a missing total leaves the Abweichler count absent; a vote under two TOPs takes the lowest `item_index`; a vote without Drucksachen; no store file. Also persist `ArchiveColumnsTests`, a schema 9 refusal and upgrade test (`test_repersist`), and the compare-script section.
  - Hand-seeded stores in 9 test files now write the `rank` columns.
  - Item (g) of "A4 slice 0 review: deferred findings" is done: `store_people` now has a caller (the demo test), and the unused `today`/`catalog` parameters are gone.
- **TODOS.md:** (g) struck through; the Vorgang-cache staleness guard (R9) is now live for the archive; the archive part of "Delete the feature-selection axis" is noted as done; the footer quote is updated.

**Substitute for the oracle, on fixtures (before the old path was deleted).** `collect_votes_archive` was wrapped so every call in the five archive suites also built a store from the same entries and rendered both rows with `render_votes_archive_index`.

| Result | Calls |
| --- | --- |
| HTML identical | 28 |
| Differs only in the href slug | 2 |
| Could not persist | 4 |
| **Total** | **34** |

- The 2 href diffs: the test's `page_path` was `plenarprotokoll-x.html` while the protocol number was 20/999. A real build writes the page under the number's slug, so these are not page diffs.
- The 4 that could not persist: their reports had no protocol number. The ported tests now give one.

The browser check (`tests/votes_archive_browser_check.js` over the store-built fixture page) passes, and the fixture page has 0 px horizontal overflow at 375 px in light and dark.

**Differences the oracle must classify.** Each is a kind of (a) diff the store path can produce and the fixtures do not exercise. Each needs a count on the reference store, plus old and new values where a page changes:
1. Drucksache numbers print canonical ("21/06561" → "21/6561"), and links match on the canonical number on both sides.
2. The Drucksachetyp column reads `documents.document_type`, one value per Drucksache, instead of the type on that TOP's DIP link.
3. Titles and topics have their whitespace collapsed (`clean`).
4. The Abweichler count dedupes members on the reconciled `mps` id, not on `derive.vote_member_identity`. If the registry folds two Einzelstimmen of one vote into one MP, that vote can turn partial.
5. A vote id stored for two sittings links to the sitting persist wrote last (`votes.protocol_id`). The JSON path took the newest entry.
6. A vote number that `upsert_document` refuses is dropped, where the JSON path showed a muted span.
7. The supplying TOP is the lowest `item_index` (T1.1 confirms it equals first-seen).
8. Politikfelder come from the cache at persist time (intended, R4).

**Measurements:** a synthetic store at the reference size (556 votes, 382,528 `vote_members`, 140 sittings × 20 TOPs × 16 links) builds the rows in 2.5 s and renders the page in 0.02 s. The time on the real store is owed (checklist class 12).

**Owed on the reference store (T1.1, T1.7, R3).** Use the slice 0 recipe, with A = 940ed88 and B = the slice 1 tip; both need `--offline --repersist`, because the tip refuses a schema 9 store.

```bash
cp -cR ~/agent-runs/a3/full .context/a4/A1 && cp -cR ~/agent-runs/a3/full .context/a4/B1
git archive 940ed88 | tar -x -C .context/a4/src-base1 ; git archive <tip> | tar -x -C .context/a4/src-tip1
SOURCE_DATE_EPOCH=1793491200 python3 .context/a4/src-base1/scripts/build_dip_pulse_site.py --offline --repersist --output-dir .context/a4/A1
SOURCE_DATE_EPOCH=1793491200 python3 .context/a4/src-tip1/scripts/build_dip_pulse_site.py --offline --repersist --output-dir .context/a4/B1
diff -u .context/a4/A1/votes/index.html .context/a4/B1/votes/index.html   # after the slice 0 normalisation
python3 scripts/compare_store_values.py .context/a4/A1 .context/a4/B1     # expect only "vote totals" to move
sqlite3 .context/a4/B1/data/bundestag-pulse.sqlite "SELECT COUNT(*) FROM votes WHERE yes_count IS NULL OR no_count IS NULL"
```

- **T1.1** on B1:
  - Votes with a NULL count, and the 0 → NULL list from `compare_store_values`.
  - Votes whose stored `documents.url` differs from their supplying TOP's winning link. Count it in Python with `stored_votes` and `document_source_links`, and record it in the data changelog.
  - The lowest `item_index` against `iter_report_votes`' first TOP over the cached reports, and `votes.id` against `pulse_html.vote_key`.
  - The 4 votes with no `vote_documents`.
  - The short-group count, expected 0.
  - The render time of `votes_archive_rows`.
- **T1.7:**
  - The `votes/` diff must show only the kinds listed above, each counted with old and new values. Loop on anything else.
  - **R3:** for every archive row, follow the href to the dossier panel id and compare the result badge (`vote-result…` span), the Drucksache links (`doc-link` anchors) and the Abweichler figure. Slice 1 is not done until these agree on every vote. Kinds 1, 4 and 6 can make them disagree. If one does, fix it in persist or the JSON path.
- **Fresh vs incremental:** a from-scratch build and an `--offline --repersist` give identical CSVs and `votes/index.html`.

### Slice 1 sample oracle (2026-11-03)

The owed checks, run on a real-data sample built for the purpose, not on the reference store. **The sample passes all of them.** It cannot stand in for the reference-store run, because it holds none of the source shapes that make the expected diff kinds (see "Still owed" below).

**Sample.** Built online by 940ed88 (`git archive` into a src-base dir), into `.context/a4-sample/base`:
- 42 WP 21 sittings, 21/62–21/103 (2026-03-05 to 2026-10-16). The command was `--limit 45 --detail-limit 0 --protocol-wahlperiode 21 --vote-scan-pages 90 --sleep 1`; 21/104–106 have no XML yet.
- 8 WP 20 sittings, 20/207–20/214 (2024-12-19 to 2025-03-18), with `--document-number`. They bring in Gruppe BSW, Gruppe Die Linke and fraktionslos.
- **Store:** 50 sittings; 55 votes in 21 of them (49 under a TOP, 6 sitting-level); 35,881 `vote_members`; 354 `vote_fractions`; 106 `vote_documents`; 3,172 `agenda_item_documents`; 9 parties.
- **Sources:** 50 XML downloads in two runs (42 between 11:08 and 12:00 UTC, 8 between 12:02 and 12:19). DIP was asked at 1 s spacing. No timeout, no slow answer, no failed person lookup or Politikfeld lookup.
- **Run times:**
  - online builds: 3,132 s (42 sittings) and 1,035 s (8 sittings);
  - `--offline --repersist` with render and export: A (940ed88) 59 s, B (8bb194a) 73 s;
  - `votes_archive_rows`: 0.21 s for 55 rows; the page render: 0.003 s.

  A and B are `cp -a` clones of the sample. Both runs used `SOURCE_DATE_EPOCH=1793491200` and the slice 0 normalisation.

**T1.1 on B** (`stored_votes` and the tip's rule functions against the 50 cached reports):

| Measure | Sample |
| --- | --- |
| Politikfelder differ, `report_politikfelder` against stored `vote_politikfelder` (both through `shown`) | 0 of 55 (all 55 `drucksache`) |
| Vote links whose `documents.url` differs from the supplying TOP's winning link | 0 of 94; the other 12 links belong to the 6 sitting-level votes, which have no TOP link on either path |
| Lowest `item_index` ≠ `iter_report_votes`' first TOP | 0 of 55 (no vote sits under two TOPs) |
| `votes.id` ≠ `pulse_html.vote_key` | 0 (55 ids on each side) |
| Votes with no `vote_documents` | 0 |
| Short groups (member rows do not cover the fraction counts) | 0; Abweichler count None: 0 |
| Votes with a NULL count | 0 |

**T1.7 diff, A against B:**
- `diff -rq` before normalisation: `votes/index.html`, the export generation directory, `datenstand.json` and `data/features.json`. Also `database.html`, `index.html`, `overview.html` and `sources.html`. All 50 dossiers, `puls.html`, `bills/`, `abgeordnete/` and `fakt/` are byte-identical.
- After normalisation, **`votes/index.html` differs in 2 lines, both the T1.5 copy:**
  - header: "aus den erzeugten Plenarprotokoll-Dossiers" → "der erfassten Sitzungen";
  - footer: the `--detail-limit` sentence → "Die Liste umfasst die namentlichen Abstimmungen der Sitzungen in der Datenbank dieses Builds, …".
- **All 55 rows are byte-identical**, including the `data-fraktion-positions` key order (R8) and the Drucksachetyp text. 0 (a) data diffs, 0 (o), 0 (b).
- Of the eight kinds listed above, the sample has none of the source shapes:
  - 0 zero-padded Drucksache numbers (kind 1);
  - 0 titles with extra whitespace (kind 3);
  - 0 member identities folded by the registry: 35,881 report identities against 35,881 `vote_members` (kind 4);
  - 0 vote ids in two sittings (kind 5);
  - 0 refused numbers (kind 6);
  - 0 votes under two TOPs (kind 7).
  - Kinds 2 and 8 change no row.
- `index.html`, `overview.html` and `sources.html` are equal after normalisation: wall-clock only.
- **Export:** `agenda_item_documents` gains `url` and `rank`, both set on all 3,172 rows. `vote_documents.rank` is set on all 106 rows, `vote_fractions.rank` on all 354. Every pre-existing column is equal in value and in row order, and `votes` is unchanged.
- `datenstand.json`, DATA.md, `datenstand-local.csv` and `database.html` change only in these:
  - format 13 → 14 and schema 9 → 10;
  - the codebook rows for the new columns;
  - the r4 `WHERE`;
  - sizes and sha256 over timestamped files, as in slice 0.
- `data/features.json` is equal after normalisation.

**`compare_store_values.py A B`:** nothing moved.
- 50 shared protocols;
- 0 changed vote totals; votes with a NULL count 0 → 0, so there is no 0 → NULL on this sample;
- 0 of 288 Fakt values moved;
- row counts, parties, `leading_vote`, Redeanteil and r3 are equal.

**R3 agreement on B:** a scratch script followed each of the 55 archive hrefs to its `vote-…` panel. The anchor exists exactly once each time. It compared:
- the result badge (span HTML);
- the Drucksache links (label and href, in order, from the vote head only, not the committee line);
- the Abweichler figure: `data-abweichler` against the panel's "(N):" labels, "Niemand stimmt anders …" (0), or the gap note (none).

**0 disagreements.** That covers 55 badges, 106 links (94 linked, 12 muted) and Abweichler figures of 0 on 31 votes and above 0 on 24 (145 in total). A negative control, a copy with one badge and one count altered, reported both.

**Store-less repersist (part of "fresh vs incremental"):** the tip ran `--offline --repersist` into a third clone with the store and export deleted (C, 66 s). B and C agree on:
- every CSV;
- `votes/index.html` and every page;
- every `compare_store_values` figure.

They differ only in hashes and sizes over timestamped files. So repersisting over a schema 9 store carries nothing into B that a store-less repersist would not produce. The online from-scratch half is not run.

**Defects:** none found, nothing fixed.

**Still owed on the reference store** (the recipe above):
- The counts and old/new values of kinds 1–8. The sample has no source shape for any of them; on the reference store, kinds 1, 4, 5 and 6 are the ones that can make the archive and the panel disagree.
- The 0 → NULL vote totals (0 here) and the 4 votes with no `vote_documents` (none here).
- The short-group count on 556 votes, and the `documents.url` against per-item winner count for the data changelog (0 of 94 here).
- R3 on all 556 votes.
- WP 18/19 sittings (none here).
- The render time at 382k `vote_members` (0.21 s at 35,881 here, 2.5 s synthetic).
- An online from-scratch build against `--offline --repersist`.
- The browser check of the filter chips at 375 px and in dark mode, not re-run here.

**Demo:** merged with the store-backed demo (see "Resolved for slice 1" under Slice 0 result): `build_demo_site.py` builds its own store and the archive reads it. The 21/84 fixture holds no votes, so the demo archive shows the empty state with the new footer copy; no figure changes.

**Review checklist** (full pass):

| Class | Answer |
| --- | --- |
| 1 Sibling path | Every page build reaches the archive through `render_site` → `votes_archive_rows(database_path)`: online after the staged rebuild (`main` runs `require_current_schema` and `store_coverage_gap` first), `--offline` and `--offline --repersist` after the F7 and R2 checks. Direct `render_site` calls and the demo without a store get an empty archive. The export, facts and the release script do not read the archive. The schema 9 refusal is in `require_current_schema`, which the rebuild, the export and every render path call. |
| 2 Stale beats fresh | The archive's tags no longer follow a cache refreshed after persist (R9 TODO, now live). Nothing is carried forward: all four new columns are written fresh on every persist. |
| 3 Order | Fraction, link and TOP-link order all come from stored ranks. Ties in `ORDER BY` fall back to the party name, but none can occur, because ranks are unique per vote or per (TOP, source). The supplying TOP is the lowest `item_index`, independent of row order. |
| 4 One key | Vote identity is `votes.id`, written via `derive.vote_identity`. The href comes from `report_paths` on `protocols.document_number`. Document numbers are canonical on both sides of the link lookup. |
| 5 Absent vs zero | Missing totals are NULL, and `vote_groups_cover_total` rejects them (test). Recipe r4 excludes NULL. The facts query `yes+no > 0` already excludes NULL. `_fact_vote_citation` only resolves votes the facts query chose. A vote without fractions, members, documents or Politikfeld rows gets empty lists or `_NO_TAGGING` (tests). |
| 6 Derived columns | `_repoint_party` merges ranks with `MIN`. `leading_vote` is unchanged. |
| 7, 8 | Not touched. |
| 9 Input shape | A blank or non-numeric count in a report: `_total_count` returns NULL for `None`/`""`. A non-numeric string raises in `int()` as before (persist already did `int(… or 0)`). |
| 10 Interrupted run | No new writes outside the staged rebuild. The archive page is written as before. |
| 11 Claims | The footer cites `store_coverage_gap`. The data dictionary says NULL means "keine Gesamtzahl" (`_total_count`), the XML-last and DIP-first url rule (`persist_agenda_documents`), and the ranks. The r4 method follows its new WHERE. README, stable-ids, CONTEXT and project-documentation name schema 10 / format 14. |
| 12 Loop cost | Seven set-based queries; synthetic full size 2.5 s; reference store 3.14 s for 619 votes (2026-11-04). |
| 13 Last commit | Owed at commit time. |

**CHANGELOG line for /gstack-ship:** "`votes/index.html` now renders from the SQLite store, not the cached report JSON: the archive runs the same vote rules as the dossier panel on stored rows. Schema 10 / export format 14 store what that needs: the order of a vote's Drucksachen and Fraktionen (`vote_documents.rank`, `vote_fractions.rank`) and each agenda item's own Drucksache url and order (`agenda_item_documents.url`, `.rank`). A vote total the source did not give is now NULL, not 0, so an Abweichler count can no longer rest on an invented zero, and recipe r4 leaves such votes out instead of ranking them as the closest vote. Old stores need `--offline --repersist`. The archive's Politikfelder now come from the store, so a refreshed Vorgang cache reaches them only with a repersist."

**Scripts for the full run** (committed in `docs/plans/a4-slice1-oracle/`): `t11_measure.py <tip scripts dir> <output dir>` (T1.1), `r3_agreement.py <output dir>` (R3, archive vs dossier panel), `normalise.py <source> <destination>` (volatile tokens; rename the `g-…` export directories to one name before the `diff`).

### Slice 1 reference-store oracle (2026-11-04)

Run by the owner on the A3 reference store (`~/agent-runs/a3/full`, 716 sittings), on two clones. A was repersisted and rendered by `origin/main` c04dcc4 (v0.31.0.0 plus #132). B was repersisted and rendered by this branch at 2108295. The recipe is the one above, with `SOURCE_DATE_EPOCH=1793491200`.

**T1.1 on B** (`t11_measure.py`):

| Measure | Value |
| --- | --- |
| Store | 619 votes, 425,322 `vote_members`, 716 protocols; report votes 619, all ids distinct |
| `votes.id` vs `vote_key` | 0 store-only, 0 report-only |
| Politikfelder, report path vs stored | 0 differ. Stored sources: 563 drucksache, 30 not_fetched, 18 untagged, 8 top |
| Vote links | 1,551. `documents.url` equals the per-item winner on 1,338, differs on 1, and 212 have no per-item link (sitting-level votes) |
| Lowest `item_index` vs first TOP | 0 mismatches. 13 votes sit under 2+ TOPs of one sitting; 63 are sitting-level |
| Votes with no `vote_documents` | 19, and their reports name no document either, so none is a (b) gap |
| Short groups, missing Abweichler, groups not covering the total | 0, 0, 0 |
| Votes with a NULL count | 0: no vote total moves from 0 to NULL on the reference store |
| `votes_archive_rows` | 3.14 s for 619 rows; render 0.03 s |

The one differing link is vote 493, Drucksache 19/19. `documents.url` holds the Bundesrat PDF `brd/2019/0019-19.pdf`; the per-item winner is the Bundestag PDF `btd/19/000/1900019.pdf`. Under R6 the archive and the panel both print the per-item url, so no page shows the wrong link. The stored `documents.url` predates slice 1 and is recorded in TODOS.md.

**T1.7.** `diff -ru` of the normalised `votes/` shows only the two T1.5 copy lines (the header lead and the footer). All 619 rows are identical. That gives 0 (a) data diffs and 0 (b) diffs; none of the eight expected kinds occurred. `compare_store_values.py A B`: every table has the same row count, 0 vote totals changed, 0 NULL counts, and 0 of 1,908 Fakt values moved.

**R3** (`r3_agreement.py`): on all 619 votes, the archive and the dossier panel agree on the result badge, the Drucksache links and the Abweichler figure (287 at 0, 332 above 0). 0 disagreements.

**Both clones (not slice 1).** A and B print the same 45 "facts: changed winner" lines against the clone's earlier facts tables. These come from code merged since `~/agent-runs/a3/full` was last built, not from this branch. The stores agree with each other afterwards ("changed winners: none").

**Full site** (`diff -rq` of the normalised clones, export generation directories and stores aside): only `database.html` and `votes/index.html` differ. `database.html` differs by export format 13 → 14, schema 9 → 10, the new codebook rows, the r4 `WHERE`, and the hashes and sizes of the export files.

**Drucksachen card from #132** (measured on B's reports): it moves on 572 of 716 dossiers, from a total of 5,198 to 29,353 (e.g. 18/100 0 → 72, 18/130 0 → 86). Recorded in the TODOS.md Completed note.

**Browser check (2026-11-04, ship):** `tests/run_bills_browser_check.mjs` passes the votes archive filter and `?politikfeld` preload at desktop and mobile; at 375 px in dark mode the fixture page has 0 px overflow and the Verkehr chip filters 4 rows to 2.

**Ship review fix (2026-11-04):** the review found that NULL totals could not arise from fresh parser output: `vote_counts_from_csv` padded a listing without `data-chart-values` with four zeros. The listing parser now keeps a missing count as `None` (no chart values: no total), and persist stores a four-zero total as NULL (`_stored_total`), which also covers cached reports. **Owed on the reference store:** the 0 → NULL list from `compare_store_values.py A B` and r4's old and new first rows; facts cannot move (`yes + no > 0`). `derive.vote_groups_cover_total` also reads four zeros as no total, so the archive and the dossier panel keep agreeing: beside four-zero Fraktion rows the panel would otherwise say "Niemand stimmt anders" (0) where the store path gives no figure. Such a vote's Abweichler figure moves from 0 to absent on both pages; its count on the reference store is owed with the replay.

## Verification (each slice)

- Run the full suite on local Python, and also `uv run --python 3.13.12 python -m unittest discover -s tests` (review checklist).
- Run the D3 oracle; only recorded (a) diffs may remain. For PR 1, the full-site diff must be empty.
- Run `compare_store_values.py` baseline vs after. Slice 1 should move no stored figure except missing vote totals becoming NULL; report any that moves with old and new values.
- Fresh vs incremental: a from-scratch build and an `--offline --repersist` give identical CSVs and archive pages.
- Open `votes/index.html` in the browser at 375px and in dark mode. Check that the Fraktion and Politikfeld filter chips still work, since they read only `data-*` attributes.
- Export: the new columns appear in the CSVs and the release SQLite, and DATA.md matches.

## Critical files

- `scripts/build_dip_pulse_site.py`: archive B:5456-5810, `render_site` B:12201, `parse_args` `--no-persist` B:13056, `main` B:13485, export B:2886-4510.
- `scripts/features/votes.py`: `write_pages` :606; shared badge and link helpers :33-80; the new adapter.
- `scripts/persist_dip_pulse_store.py`: schema :274-424, `persist_vote` :1276, `persist_politikfelder` :1470, `require_current_speech_rules` :72.
- `scripts/derive.py`: `merge_fractions` :143, `vote_abweichler*` :637-696, `vote_identity` :466.
- `scripts/facts.py`: `open_readonly` :2678.
- `scripts/politikfelder.py`: `report_politikfelder`, `shown`.
- `scripts/build_demo_site.py`.
- New: `tests/_site_store_fixture.py`.

## NOT in scope (for slices 0–1)

- Dossier vote panels: they need acquisition state and `vote_heading`, so they belong to slice 4.
- A shared store-reader module: extracted in slice 2 when a second page type exists.
- A page-compare script: written in slice 10, where the dev view must be exempted.
- Holding export format 12 until slices 1–3: rejected under the pre-release rule.
- A guard for a Vorgang cache newer than the store: recorded in TODOS.md (R9), no current path reaches it.
- WP 1–17, a second site, any change to what counts as a Rede, the file split (slice 11).

# /plan-eng-review: A4 plan (target: this file)

Review started 2026-11-01 on branch `claude/a4-todo-plan-3119e1` (base 4705fb3). The target is this plan as drafted above. Design-doc lookup returned `docs/designs/puls-wochenradar.md` and a CEO plan from branch `expand-database` (fix-wrong-values); both are unrelated to A4 and were not used.

## Reality rows

**Premise table** (claims the plan rests on; static reads at 4705fb3):

| Premise | Claim | Receipt | Verdict |
| --- | --- | --- | --- |
| P1 | A missing vote total is stored as 0 | `persist_dip_pulse_store.py:1342-1345` `int(total.get("yes") or 0)` | true |
| P2 | Politikfeld `untagged` and `not_fetched` collapse into one stored row | `persist_dip_pulse_store.py:1476-1477` "``untagged`` and ``not_fetched`` are stored as an explicit ``untagged`` row" | true |
| P3 | `vote_documents` keeps no order and no url source | `persist_dip_pulse_store.py:400-404` (vote_id, document_id, PK only) | true |
| P4 | `require_build_store` guards the rebuild and the facts engine | `build_dip_pulse_site.py:1543`, `:13360`; `persist_dip_pulse_store.py:145` | true |
| P5 | The archive is wired through ctx callables | `build_dip_pulse_site.py:12305-12306` | true |
| P6 | The archive's Drucksachetyp falls back to the sitting-wide map, by `vote.document_numbers` order | `build_dip_pulse_site.py:5465-5481` | true |
| P7 | Online runs write dossier HTML before the rebuild | `build_dip_pulse_site.py:2860` `return write_report_files(report, output_dir, mp_lookup, ...` | true |
| P8 | The lost member-row defect is open | `TODOS.md:62-77` (no "done" marker, P2) | true |
| P9 | A `no_persist` `render_site` test reads the archive | `tests/test_politikfelder.py:1445` | true |
| P10 | A read-only store opener already exists | `facts.py:2678-2681` `open_readonly` (`?mode=ro`, `Row`) | true |
| P11 | `--no-persist` has a documented user use: preview one sitting without touching the store | `docs/project-documentation.md:497` `--document-number 21/87 --no-persist` | true |

unverified=0

REALITY: premise-table pass 11 premises, unverified=0 scripts/persist_dip_pulse_store.py:1342
REALITY: already-done pass no commit on local origin/main touches A4 (fetch blocked by sandbox; local origin/main = 4705fb3) TODOS.md:1130
REALITY: surface-check finding `--from-release` (slice 10) is a proposed flag, not existing; `--no-persist` exists (`build_dip_pulse_site.py:13056`) scripts/build_dip_pulse_site.py:13056
REALITY: binding-decisions pass no binding decisions recorded for this branch; PRODUCT.md principle 6 and CLAUDE.md pre-release rule are honoured PRODUCT.md:91
REALITY: numbers pass store figures tagged measured (sqlite3 on ~/agent-runs/a3/full); repersist time tagged estimated scripts/persist_dip_pulse_store.py:35
REALITY: deferred-asks pass no linked GitHub issue; the TODO's own asks (store-first renderers, release-only build, slice comparison) are all in the slice map TODOS.md:1130
REALITY: pr-count finding no .gstack/ship-policy.json, so default one PR per wave; the plan implies at least two PRs before slice 1 can finish (member-rows fix, slice 0+1) TODOS.md:62

## Scope record

feature answers: no feature cuts proposed (slice 0 no-store rendering, slice 1 archive, schema 9 kept); structure: A) Smaller arrangement, D1, auto-decided by the plan-tune adjudicator 2026-11-01 ("a reader with one caller is premature; `diff -ru` covers the oracle until the full-site check needs the dev-view exemption"); accepted scope: slices 0–1 as planned, except no `scripts/site_store.py` and no `scripts/compare_site_render.py` — the archive store query lives in `scripts/features/votes.py`, the store opens through `facts.open_readonly` + `pulse_store.require_current_schema`, the oracle is `diff -ru A B`, and the only new file is `tests/_site_store_fixture.py`; a shared reader is extracted when slice 2 brings the second page type, and a compare script with the dev-view exemption is written at slice 10; pending remedies: none.

## Decision ledger

### R1: what `--no-persist` becomes once pages render from a store
Finding: F1, P1, confidence 8/10, plan D2/T0.2, reviewer: Claude (scope challenge)
Plan baseline: original proposal D2: `--no-persist` persists the run's entries into a temporary SQLite and renders from it (unapproved)
Runtime evidence: `--no-persist` = "Skip writing the SQLite graph store" (`build_dip_pulse_site.py:13056-13058`); documented preview use `docs/project-documentation.md:497`; online runs merge all cached entries (`merge_detail_entries`, B:1337), so a temp store holds every cached report; full repersist of 716 protocols ~10 min [estimated from ~245 s per 284 protocols]; `not no_persist` guards in `write_facts_pages` (B:10250), MP pages (B:13658), export
Comparison grid:
| Choice | Current | A | B | C |
|---|---|---|---|---|
| R1 `--no-persist` flag | exists; skips store, pages from JSON | removed; previews use a scratch output dir (README "Try a fetch or a backfill in a scratch directory") | kept: normal staged rebuild into the private dir, render, discard instead of swap | kept: pages fall back to JSON when no store |
| Tests and demo | render from entries | temp store through the production rebuild path (`tests/_site_store_fixture.py`, `build_demo_site.py`) | same as A | unchanged |
| Cost of a preview run | no persist | same as a normal run, into a scratch copy | full rebuild (~10 min est.) then discard | no persist |
| `not no_persist` branches | many | deleted | kept, meaning changes | kept |
| Principle 6 (one computation) | broken for JSON pages | holds | holds | broken until slice 10 |
| R2–R5 | pending | pending | pending | pending |
Question D2:
D2 — What should `--no-persist` become?
Project/branch/task: A4 plan on claude/a4-todo-plan-3119e1, pages move from report JSON to the store.
ELI10: Today `--no-persist` builds pages from the JSON and never touches the database. Once pages come from the database, a run without a database has nothing to render from. A temporary database would mean rebuilding every cached sitting (~10 min, estimated), so the "quick preview of one sitting" use is gone either way. The question is whether to keep the flag with a new, slow meaning, drop it in favour of a scratch copy of the output folder, or keep a JSON fallback.
Stakes if we pick wrong: a flag that silently became slow and confusing, or a second computation of every figure that A4 exists to remove.
Recommendation: A because it deletes the `not no_persist` branches A4 would otherwise carry, and a scratch copy (cheap clone on APFS) already gives "don't touch my store" with the same output as a real run.
Completeness: A=9/10, B=8/10, C=4/10
Pros / cons:
A) Remove the flag (recommended)
  ✅ Every page always reads a store; the `read_store = not no_persist and ...` branches in facts, MP pages and export disappear
  ✅ A preview in a scratch copy gives exactly the pages a real run would, store included
  ❌ Breaks the documented one-sitting preview command; docs must point to the scratch-dir recipe instead
B) Keep it as rebuild-and-discard
  ✅ Users keep the flag and its promise that the real store stays untouched
  ✅ Same output as a real run, since it goes through the normal staged rebuild
  ❌ A flag named "skip the store" now costs a full rebuild, and every guard branch stays in the code
C) Keep a JSON fallback
  ✅ Previews stay fast and the flag keeps its current behaviour
  ✅ No test or demo needs a store
  ❌ Two computations of every page figure until slice 10, which PRODUCT.md principle 6 and the pre-release rule both reject
Net: you trade a documented convenience flag for one render path with no store-less special case.
Header: No-persist
Options:
A) Remove the flag (recommended)
Delete --no-persist and its guard branches as each slice lands; docs point previews to a scratch output dir; tests and the demo build a temporary store through the production rebuild path. Human ~1 day / CC ~30 min across slices.
B) Keep as rebuild-and-discard
Keep --no-persist; it runs the normal staged rebuild into the private dir, renders from it, then discards instead of swapping. Costs a full rebuild per run (~10 min est.). Tests and demo as in A.
C) Keep a JSON fallback
Keep --no-persist as today; pages that move to the store fall back to the JSON path when no store exists. No deletion of the JSON path until slice 10.

State: approved
Actual answer: A) Remove the flag, D2, auto-decided by the plan-tune adjudicator 2026-11-01 (pre-release rule; README scratch-dir recipe at README:184 and 227-236 covers the preview use)
Accepted scope: delete `--no-persist` and its `not no_persist` guard branches; docs that name it (`docs/project-documentation.md:145-175, 271, 428, 497`, README:288, 449) point previews to the scratch output dir recipe; tests and `build_demo_site.py` build a temporary store through the production rebuild path (`tests/_site_store_fixture.py`), with the D2 path check and cost measurement from T0.2. Replaces plan D2's temp store for `--no-persist`.
History: none

### R2: offline render when the store and the cached reports cover different sittings
Finding: F2, P1, confidence 8/10, `persist_dip_pulse_store.py:77-80`, reviewer: Claude (Section 1)
Plan baseline: original proposal: no coverage check; offline pre-checks are `require_current_schema`, `require_current_speech_rules`, `require_applied_partitions` (B:13566-13601)
Runtime evidence: `require_current_speech_rules` joins `protocols LEFT JOIN speech_rule_inputs`, so it only sees protocols already in the store; an online run writes report JSON at B:2860 before the staged rebuild, so a failed rebuild leaves JSON with no store row; recorded exclusions are removed from entries and store alike (`without_recorded_exclusions`, B:681)
Comparison grid:
| Choice | Current | A | B | C |
|---|---|---|---|---|
| R2 coverage check before rendering | none | refuse: cached entries (minus recorded exclusions) and store `protocols` must name the same sittings, both directions; message names up to 5 sittings and the `--offline --repersist` repair | warn with the same list, then render | none; rely on the per-slice oracle |
| Where it runs | n/a | every render that reads the store (offline and online, after the rebuild) | same as A | n/a |
| R1 | approved A (flag removed) | unchanged | unchanged | unchanged |
| R3–R5 | pending | pending | pending | pending |
Question D3:
D3 — Should a render refuse when the store and the cached reports cover different sittings?
Project/branch/task: A4 plan on claude/a4-todo-plan-3119e1, slice 0 render pre-checks.
ELI10: After slice 1 the votes archive comes from the database while dossier pages still come from the cached JSON files. If an online run saved new JSON but its database rebuild failed, the next offline build would show a dossier for a sitting whose votes are missing from the archive, with no warning. The existing checks only look at sittings already in the database, so they miss this.
Stakes if we pick wrong: a published archive silently missing a sitting's votes (principle 2, "show gaps honestly"), or a build that refuses for a reason the user can fix with one command.
Recommendation: A because the repo already refuses stale stores the same way (speech rules, Antrag passages) and the repair command is known.
Completeness: A=9/10, B=6/10, C=3/10
Pros / cons:
A) Refuse on mismatch (recommended)
  ✅ No page set can mix sittings that are in the store with sittings that are not; the failure names the sittings and the fix
  ✅ Same shape as the existing `require_current_speech_rules` refusal, so users already know the repair
  ❌ An offline render after a failed rebuild stops until `--offline --repersist` runs, about 10 minutes (est.)
B) Warn and render
  ✅ The build still produces pages, and the gap is printed on the console
  ✅ Cheapest to implement, a few lines next to the existing checks
  ❌ The published pages still disagree; a console line is easy to miss in a long build log
C) No check
  ✅ No new code and no new refusal path
  ✅ The per-slice oracle would show a gap on the reference data
  ❌ The oracle runs once per slice; a real failed rebuild later goes unnoticed on the live site
Net: you trade one extra refusal path for never publishing a page set built from two different sets of sittings.
Header: Coverage check
Options:
A) Refuse on mismatch (recommended)
Add a pre-render check: the cached entries (minus recorded exclusions) and store protocols must name the same sittings in both directions; otherwise exit 1 naming up to 5 sittings and the --offline --repersist repair. Runs before every store-reading render. Test: one report not in the store, one store sitting with no report. Human ~2 h / CC ~10 min.
B) Warn and render
Same comparison, but print a warning listing the sittings and continue rendering. Same tests, asserting the warning.
C) No check
Leave the pre-checks as they are; rely on the per-slice oracle to show gaps on the reference data.

State: approved
Actual answer: A) Refuse on mismatch, D3, auto-decided by the plan-tune adjudicator 2026-11-01 (same shape as the existing stale-store refusals; a warning is easy to miss)
Accepted scope: slice 0 adds a pre-render check before every store-reading render: the cached entries (minus recorded exclusions) and store `protocols` must name the same sittings in both directions; otherwise exit 1 naming up to 5 sittings and the `--offline --repersist` repair. Tests: one report not in the store, one store sitting with no report.
History: none

### R3: archive and dossier panel disagree during the migration
Finding: F3, P2, confidence 7/10, plan D1 and slice map rows 1/4, reviewer: Claude (Section 1)
Plan baseline: original proposal D1: identical HTML except listed "store is more correct" diffs; nothing about the dossier panel, which stays on JSON until slice 4
Runtime evidence: both pages render the same vote's result badge (`votes_feature.render_result_badge`, features/votes.py:33), Drucksache links (`render_document_links`, `document_source_links` features/votes.py:59) and Abweichler figure (`derive.vote_abweichler_count`, derive.py:696; the panel lists names via `derive.vote_abweichler`); Politikfelder, the Drucksachetyp column and Fraktion positions are archive-only
Comparison grid:
| Choice | Current | A | B |
|---|---|---|---|
| R3 cross-page agreement in slice 1 | not addressed | slice 1 is done only when the shared fields (badge, Drucksache links, Abweichler) agree between archive and panel on every vote of the D3 baseline; a "store is more correct" diff on a shared field is fixed in persist or the JSON path so both pages agree, or the slice waits | list shared-field disagreements in this file and in a TODO, accepted until slice 4 moves the panel |
| Archive-only fields (Politikfelder, Drucksachetyp, positions) | n/a | D1 rule as planned | D1 rule as planned |
| R1, R2 | approved A, A | unchanged | unchanged |
| R4, R5 | pending | pending | pending |
Question D4:
D4 — Must the archive and the dossier vote panel agree on shared fields after slice 1?
Project/branch/task: A4 plan on claude/a4-todo-plan-3119e1, slice 1 acceptance.
ELI10: After slice 1 a vote appears twice on the site: in the archive, built from the database, and on its sitting's dossier page, still built from the JSON until slice 4. Both show the result badge, the Drucksache links and the dissenter figure. If the database version is "more correct" somewhere, the two pages show different facts about the same vote. The question is whether slice 1 may ship with such disagreements listed, or must make both pages agree first.
Stakes if we pick wrong: a reader clicks from the archive to the dossier and sees a different result or dissenter count for the same vote, which is exactly the drift A4 exists to end.
Recommendation: A because the overlap is three fields on 556 votes, and the 22-group member fix already removes the known Abweichler cause.
Completeness: A=9/10, B=6/10
Pros / cons:
A) Require agreement (recommended)
  ✅ No vote shows two different badges or dissenter counts on two pages, even mid-migration
  ✅ The check is one more comparison in the slice-1 oracle over 556 votes, no new tooling
  ❌ A store-side correction on a shared field can hold slice 1 until the JSON path or persist is fixed too
B) List and accept until slice 4
  ✅ Slice 1 is not blocked by panel code that slice 4 will rewrite anyway
  ✅ Every disagreement is still written down, with old and new values
  ❌ The live site can show two different facts for one vote for as long as slices 2–4 take
Net: you trade a possible hold on slice 1 for never showing two answers to the same question.
Header: Cross-page
Options:
A) Require agreement (recommended)
Slice 1 is done only when badge, Drucksache links and Abweichler agree between archive and dossier panel for every vote of the D3 baseline. A shared-field diff is fixed in persist or the JSON path, or slice 1 waits. Adds one comparison to T1.7. Human ~half day / CC ~20 min if diffs appear.
B) List and accept until slice 4
Record shared-field disagreements in this file and in a TODO; they stay until slice 4 moves the panel to the store.

State: approved
Actual answer: A) Require agreement, D4, auto-decided by the plan-tune adjudicator 2026-11-01 (pre-release accuracy rule; one extra oracle comparison)
Accepted scope: slice 1 is done only when the result badge, Drucksache links and Abweichler figure agree between the archive and the dossier panel for every vote of the D3 baseline; a shared-field diff is fixed in persist or the JSON path, or slice 1 waits; T1.7 adds this comparison. Archive-only fields keep the D1 rule.
History: none

### R4: regression contract for the votes archive
Finding: F5 + IRON RULE, P1, confidence 9/10, `build_dip_pulse_site.py:5600` (`json.dumps(row["fraction_positions"], ...)` in first-seen order) and plan D1/T1.6, reviewer: Claude (Section 3)
Plan baseline: original proposal D1 (identical HTML except listed "store is more correct" diffs) and T1.6 (port every archive suite, keep each assertion); unapproved
Runtime evidence: about 30 archive tests build input from report dicts (`tests/test_build_dip_pulse_site.py:2789-3250`, `test_b1_consumers.py:76-125`, `test_mehrheitsvotum.py:102-109`, `test_politikfelder.py:1416-1445`, `test_vote_interpretation.py:625-645`); no golden HTML exists; `test_politikfelder.py:1445` asserts that the render-time Vorgang cache changes archive chips; store `vote_fractions` has no order column (`persist_dip_pulse_store.py:406`)
Comparison grid:
| Choice | Current | A | B | C |
|---|---|---|---|---|
| R4 page equivalence | none | `diff -ru` identical except listed diffs of exactly two kinds: (a) store more correct, old/new values recorded; (o) key order inside `data-fraktion-positions` JSON only, counted | normalized comparison (whitespace, attribute and key order ignored) plus the (a) list | no page oracle; substring tests only |
| Existing archive assertions | ~30, from report dicts | all kept, input built through the production rebuild path | same as A | same as A |
| `test_politikfelder.py:1445` | render-time cache moves chips | rewritten: the cache takes effect at persist; an offline render without repersist keeps persisted tags | same as A | same as A |
| New cases (T1.6 list + R2 refusals + F7) | n/a | required | required | required |
| R1–R3 | approved A, A, A | unchanged | unchanged | unchanged |
| R5 | pending | pending | pending | pending |
Question D5:
D5 — What counts as "the archive still behaves the same" in slice 1?
Project/branch/task: A4 plan on claude/a4-todo-plan-3119e1, slice 1 regression contract.
ELI10: Slice 1 rewires every existing archive test and replaces the code that builds the page. There is no saved copy of today's page to compare against, so we need an agreed rule for which differences are allowed. One difference is harmless but shows up on every row: the database does not remember the order of the Fraktionen, so a hidden JSON attribute lists them in a different order. One test also checks something that changes on purpose: the Vorgang cache will now take effect when the database is written, not when pages are drawn.
Stakes if we pick wrong: either a real change hides in 556 noisy rows, or a comparison so loose that it misses a reordered list a reader would see.
Recommendation: A because it allows exactly one named harmless difference and keeps every visible order strict, which a normalized diff would not.
Completeness: A=10/10, B=7/10, C=4/10
Pros / cons:
A) Strict diff, two listed kinds (recommended)
  ✅ Every visible change is either a recorded correction with old and new values or a counted key-order change in one hidden attribute
  ✅ All ~30 existing assertions survive, and the one test whose meaning changes is rewritten on purpose
  ❌ The order-only kind must be checked by a small script so it doesn't hide another change in the same attribute
B) Normalized diff
  ✅ Less noise; no special rule for the positions attribute
  ✅ Same assertion porting as A
  ❌ Ignoring attribute and key order also hides a changed order of Drucksache links, which readers see
C) Substring tests only
  ✅ No oracle run; the ported tests are the only check
  ✅ Fastest to finish slice 1
  ❌ Fixtures cover a handful of votes; differences on the 556 real votes would go unseen
Net: you trade one small order-check script for a comparison that misses nothing a reader can see.
Header: Regression
Options:
A) Strict diff, two listed kinds (recommended)
diff -ru identical except (a) store-more-correct diffs with old/new values recorded and (o) key-order-only changes inside data-fraktion-positions, counted and checked by parsing the JSON. All ~30 archive assertions kept through store-seeded fixtures; test_politikfelder.py:1445 rewritten so the cache takes effect at persist; T1.6 new cases, R2 refusals and the F7 missing-store refusal added. Human ~1 day / CC ~40 min.
B) Normalized diff
Compare pages ignoring whitespace, attribute and key order, plus the (a) list. Same assertion porting and new cases as A.
C) Substring tests only
No page oracle; port the existing assertions and add the new cases only.

State: approved
Actual answer: A) Strict diff, two listed kinds, D5, auto-decided by the plan-tune adjudicator 2026-11-01 (keeps every visible order strict; one named harmless difference)
Accepted scope: `diff -ru` of the two D3 clones is identical except (a) store-more-correct diffs with old/new values recorded and (o) key-order-only changes inside `data-fraktion-positions`, counted and checked by parsing the JSON; all ~30 archive assertions kept through store-seeded fixtures built by the production rebuild path; `test_politikfelder.py:1445` rewritten so the Vorgang cache takes effect at persist; T1.6 new cases, the R2 refusals and the F7 missing-store refusal added. Replaces plan D1.
History: none

### R5: how the store-side archive applies the vote rules (outside voice O1)
Finding: O1, High, confidence 8/10, plan T1.2/T1.3 vs `build_dip_pulse_site.py:5536-5545`, reviewer: outside voice (Claude Plan subagent), confirmed by Claude
Plan baseline: original proposal T1.2/T1.3: Abweichler counted in SQL from `vote_fractions` + `vote_members`; Drucksachetyp via a `documents.document_type` join reproducing the rule; Politikfelder "shown" rule applied to store rows; fraction positions through `derive.fraction_position`
Runtime evidence: today's collector calls `derive.vote_abweichler_count`, `_vote_procedure_type`, `politikfelder.shown`, `derive.merge_fractions`/`_fraction_position`, `votes_feature.document_source_links`/`document_source_chambers` on report dicts (B:5536-5545); the dossier panel (still JSON until slice 4) calls the same functions, and R3 requires both pages to agree
Comparison grid:
| Choice | Current | A | B | C | D |
|---|---|---|---|---|---|
| R5 rule application on the store path | plan: rules re-expressed in SQL/joins | store-to-vote adapter in `features/votes.py`: build vote and item dicts (fractions, members, document_numbers, linked/xml Drucksachen, Politikfeld tags and source) from store rows, then call the existing rule functions unchanged | keep plan T1.2/T1.3 (SQL count, join rule) | investigate: prototype both on 20 real votes, report diffs and code size, no implementation choice | defer: leave T1.2/T1.3 as written, decide at slice 4 |
| R1–R4 | approved A, A, A, A | unchanged | unchanged | unchanged | unchanged |
| R6–R8 | pending | pending | pending | pending | pending |
Question D6:
D6 — Should the store-built archive reuse today's vote rules through an adapter?
Project/branch/task: A4 plan on claude/a4-todo-plan-3119e1, slice 1 archive read path.
ELI10: The plan rewrites three of the archive's rules as database queries: the dissenter count, the Drucksachetyp column and which Politikfelder show. The same rules already exist in Python and the dossier panel keeps using them until slice 4. Two copies of each rule is exactly the drift A4 exists to end. The outside reviewer proposes loading the database rows into the same shapes the current code reads and running the existing functions unchanged. Then any difference between old and new pages can only come from what the database stores.
Stakes if we pick wrong: two implementations of the dissenter count and the Drucksachetyp rule that must be kept in step for four slices, and a disagreement between archive and panel that R3 forbids.
Recommendation: A because it keeps one computation per figure and turns every oracle diff into a persist bug that is easy to find.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Apply the adapter (recommended)
  ✅ One rule per figure: `derive.vote_abweichler_count`, `_vote_procedure_type` and `politikfelder.shown` stay the only implementations
  ✅ Archive and dossier panel run identical code on identical shapes, so R3 holds unless persist loses data
  ❌ The adapter rebuilds report-shaped dicts, a shape A4 later retires; slice 4 may reshape it
B) Keep SQL and joins
  ✅ Store-native reads that the release's own SQL recipes can mirror
  ✅ No report-shaped intermediate
  ❌ Second implementation of three rules until slice 4, against principle 6 and R3
C) Investigate first
  ✅ Measures both approaches on real votes before committing
  ✅ No code shape is chosen yet
  ❌ Delays slice 1 for a question whose answer follows from principle 6
D) Defer to slice 4
  ✅ Slice 1 proceeds exactly as written
  ✅ Slice 4 can settle the rule home with panels in view
  ❌ Ships the duplicate rules this review identified
Net: you trade a temporary report-shaped adapter for one computation of every archive figure.
Header: Rule reuse
Options:
A) Apply the adapter
features/votes.py builds vote and item dicts from store rows (fractions in stored order, members, document_numbers, per-item Drucksache links, Politikfeld tags with their state) and calls the existing derive, politikfelder and votes_feature functions unchanged. T1.2 keeps only the persisted additions the adapter needs; T1.3's SQL count and join rule are dropped. Human ~1 day / CC ~30 min.
B) Keep this row's current value
Keep T1.2/T1.3 as written: Abweichler counted in SQL, Drucksachetyp via a join reproducing the rule, the shown rule applied to store rows.
C) Investigate before choosing
Prototype both on 20 real votes from the D3 baseline; report diffs and code size; no implementation is approved, T1.2/T1.3 stay pending.
D) Defer this proposed change only
Leave T1.2/T1.3 as written for now; the rule home is decided at slice 4. Other choices unchanged.

State: approved
Actual answer: A) Apply the adapter, D6, auto-decided by the plan-tune adjudicator 2026-11-01 (one implementation per rule; oracle diffs point at persist)
Accepted scope: `features/votes.py` builds vote and item dicts from store rows (fractions in stored order, members, document_numbers, per-item Drucksache links, Politikfeld tags with their state) and calls the existing `derive`, `politikfelder` and `votes_feature` functions unchanged; T1.2 keeps only the persisted additions the adapter needs; T1.3's SQL Abweichler count and Drucksachetyp join rule are dropped.
History: none

### R6: where the per-link Drucksache url lives (outside voice O2)
Finding: O2, High, confidence 9/10, `persist_dip_pulse_store.py:274-281` and :400-404 vs `features/votes.py:59-77`, reviewer: outside voice, confirmed by Claude
Plan baseline: original proposal T1.2: add `vote_documents.rank` and `vote_documents.url_source`; url read from `documents.url`
Runtime evidence: `documents.url` is one url per document, chosen by `_document_url_rank`; `agenda_item_documents` already has one row per (item, document, source) with `source` xml/api but no url; `document_source_links` takes the DIP url per item, then lets the XML url override it
Comparison grid:
| Choice | Current | A | B | C | D |
|---|---|---|---|---|---|
| R6 per-link url | not stored | add `url` to `agenda_item_documents` (the url that source printed for that item); the R5 adapter rebuilds each item's `api.linked_drucksachen` / `xml_drucksachen` from these rows, and `document_source_links` picks the winner unchanged | store the chosen url beside `url_source` on `vote_documents` (persist runs the xml-over-dip choice) | investigate: measure on the D3 baseline whether `documents.url` always equals the per-item winner; no schema change approved | keep `url_source` only (plan baseline) |
| `vote_documents.rank` (order of `vote.document_numbers`) | not stored | added (needed by the R5 adapter for `_vote_procedure_type` and link order) | added | pending | added |
| R1–R5 | approved A, A, A, A, A | unchanged | unchanged | unchanged | unchanged |
| R7, R8 | pending | pending | pending | pending | pending |
Question D7:
D7 — Where should the store keep each Drucksache link's own url?
Project/branch/task: A4 plan on claude/a4-todo-plan-3119e1, slice 1 schema 9.
ELI10: The archive links each Drucksache either to the XML protocol's url or to the DIP url, and labels which one it used. Today the code picks per agenda item: XML wins when both exist. The database keeps only one url per Drucksache across all sittings, so it can't tell which url a given agenda item printed. Without a fix, a page could show a DIP url with an "XML" label. The question is where to store the per-link url.
Stakes if we pick wrong: wrong source labels or urls on citizen pages, or a second copy of the xml-over-dip rule in persist.
Recommendation: A because the per-item rows already exist with their source, and storing each source's url lets the existing `document_source_links` keep making the choice (R5).
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Url per agenda-item link (recommended)
  ✅ One column on rows that already exist; the xml-over-dip rule stays in `document_source_links` only
  ✅ Also serves slice 5 (dossier Drucksachen), which needs the same per-item urls
  ❌ Stores both urls where both sources link a Drucksache, a little redundancy in the release
B) Chosen url on vote_documents
  ✅ The archive reads one ready url per vote link
  ✅ Fewer rows to join than A
  ❌ Persist runs the xml-over-dip choice, a second implementation beside `document_source_links`
C) Investigate first
  ✅ Might show no schema change is needed at all
  ✅ Cheap: one query on the baseline
  ❌ A "no difference today" result proves nothing for the next sitting
D) Keep url_source only
  ✅ Smallest schema change
  ✅ Matches the original plan
  ❌ Cannot reproduce the url a link actually shows, the defect this finding names
Net: you trade one redundant url column for keeping the link rule in one place.
Header: Link url
Options:
A) Url per agenda-item link
Schema 9 adds agenda_item_documents.url (the url that source printed for that item) and vote_documents.rank; the R5 adapter rebuilds item links from these rows and document_source_links picks the winner unchanged. vote_documents.url_source is dropped from the plan. Human ~2 h / CC ~15 min.
B) Keep this row's current value
Keep plan T1.2 as written: vote_documents.rank and vote_documents.url_source, url from documents.url.
C) Investigate before choosing
Measure on the D3 baseline whether documents.url always equals the per-item winner; no schema change approved; T1.2's link columns stay pending.
D) Defer this proposed change only
Leave T1.2's link columns as written; revisit after the slice-1 oracle. Other choices unchanged.

State: approved
Actual answer: A) Url per agenda-item link, D7, auto-decided by the plan-tune adjudicator 2026-11-01 (keeps the xml-over-dip rule in `document_source_links`, per D6)
Accepted scope: schema 9 adds `agenda_item_documents.url` (the url that source printed for that item) and `vote_documents.rank`; the R5 adapter rebuilds item links from these rows and `document_source_links` picks the winner unchanged; `vote_documents.url_source` is dropped from the plan.
History: none

### R7: one PR or two for slices 0 and 1 (outside voice O5)
Finding: O5, Medium, confidence 7/10, R1 accepted scope (flag removal) + plan slices 0–1, reviewer: outside voice, confirmed by Claude
Plan baseline: original proposal: slices 0 and 1 land together (plan "NOT in scope" lists only slice 2+); the lost member-row fix is already its own PR (plan T1.2)
Runtime evidence: removing `--no-persist` touches 18 sites in `build_dip_pulse_site.py`, 24 `no_persist=True` tests in 8 files (outside-voice count; Claude's grep found 9 test files naming `no_persist=True` or `--no-persist`) and six doc locations; slice 1 adds schema 9 and the archive rewrite
Comparison grid:
| Choice | Current | A | B | C | D |
|---|---|---|---|---|---|
| R7 PR boundaries | one PR for slices 0+1 | PR 1: slice 0 (flag removal, temp-store fixture through the rebuild path, R2 coverage refusal, F7 missing-store refusal, suite-time measurement); PR 2: slice 1 (schema 9, adapter, archive, oracle); member-row fix stays its own PR before PR 2's oracle | one PR for slices 0+1 | investigate: size both after T0.2; decide then | defer: decide at implementation time |
| R1–R6 | approved | unchanged | unchanged | unchanged | unchanged |
| R8 | pending | pending | pending | pending | pending |
Question D8:
D8 — Should slice 0 and slice 1 land as separate PRs?
Project/branch/task: A4 plan on claude/a4-todo-plan-3119e1, PR boundaries.
ELI10: Removing `--no-persist` and switching tests to a temporary database touches about 18 places in the build script, 9 test files and six docs. Slice 1 then changes the schema and rebuilds the votes archive. In one PR, the harness churn and the archive change sit in one diff, and the archive's page comparison can't be read apart from test-setup changes. Two PRs let the harness land, behaviour-neutral, before the archive moves.
Stakes if we pick wrong: a review that misses an archive bug inside a large harness diff, or one extra ship cycle.
Recommendation: A because slice 0 changes no page and can be checked on its own, and the project's ship reviews find more on smaller diffs.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Two PRs (recommended)
  ✅ Slice 0's diff proves "no page changed" on its own, so slice 1's diff shows only archive changes
  ✅ The test-harness churn reviews once, without the schema change beside it
  ❌ One more /gstack-ship run, roughly 1–2 hours of review cycles
B) One PR
  ✅ One ship run and one version bump
  ✅ The harness is exercised by the archive change it exists for
  ❌ A diff of several hundred lines across two concerns, where ship has found late bugs before
C) Investigate first
  ✅ Decide with T0.2's real diff size in hand
  ✅ No commitment now
  ❌ Leaves the PR plan open for the implementer
D) Defer
  ✅ Implementation can choose freely
  ✅ No change to the plan text
  ❌ Same as C, with no measurement promised
Net: you trade one extra ship run for two diffs that each review cleanly.
Header: PR split
Options:
A) Two PRs
PR 1 = slice 0 (flag removal, temp-store fixture, R2 and F7 refusals, suite-time measurement), behaviour-neutral for pages; PR 2 = slice 1 (schema 9, adapter, archive, oracle). The member-row fix lands as its own PR before PR 2's oracle run.
B) Keep this row's current value
Slices 0 and 1 land in one PR, as the plan implies.
C) Investigate before choosing
Measure the slice-0 diff after T0.2, then decide; PR boundaries stay pending.
D) Defer this proposed change only
Leave PR boundaries to implementation time. Other choices unchanged.

State: approved
Actual answer: A) Two PRs, D8, auto-decided by the plan-tune adjudicator 2026-11-01 (slice 0 is behaviour-neutral; smaller diffs lower the ship cap risk)
Accepted scope: PR 1 = slice 0 (flag removal, temp-store fixture through the rebuild path, R2 and F7 refusals, suite-time measurement), behaviour-neutral for pages; PR 2 = slice 1 (schema 9, R5 adapter, archive, oracle); the lost member-row fix lands as its own PR before PR 2's oracle run.
History: none

### R8: store the fraction order instead of exempting key order (outside voice O8; reopens R4)
Finding: O8, Medium, confidence 8/10, R4 accepted scope ("(o) key-order-only changes ... checked by parsing the JSON") vs Scope record ("no compare script"), reviewer: outside voice, confirmed by Claude
Plan baseline: R4 approved A (D5): strict `diff -ru` except (a) store-more-correct and (o) key order inside `data-fraktion-positions`, checked by parsing the JSON
Runtime evidence: `vote_fractions` has PK (vote_id, party_id) and no order column (`persist_dip_pulse_store.py:406`); `derive.merge_fractions` returns rows "in first-seen order" (derive.py:149) and persist already iterates them in that order; the R5 adapter (approved) feeds `merge_fractions` "fractions in stored order", which is undefined without a rank; slice 4 needs fraction rank for the panel (slice map row 4)
Reason for reopening: concrete new evidence — the (o) exemption needs a parsing checker, which contradicts the approved Scope record's "`diff -ru`, no compare script", and R5 now needs a defined fraction order anyway
Comparison grid:
| Choice | Current | A | B | C | D |
|---|---|---|---|---|---|
| R8 fraction order | R4: not stored; (o) exemption with JSON-parsing check | schema 9 adds `vote_fractions.rank` (first-seen order of `merge_fractions`); R4's (o) exemption is removed, so the oracle is strict `diff -ru` with only (a) diffs; slice 4 reuses the rank | keep R4 as approved: (o) exemption plus a parsing check | investigate: count rows whose key order differs on the D3 baseline; R4 stays as approved meanwhile | defer: keep R4 as approved; add rank at slice 4 |
| R4 other parts (assertion porting, test 1445 rewrite, new cases, (a) list) | approved | unchanged | unchanged | unchanged | unchanged |
| R1–R3, R5–R7 | approved | unchanged | unchanged | unchanged | unchanged |
Question D9:
D9 — Store the Fraktion order now so the page comparison needs no exception?
Project/branch/task: A4 plan on claude/a4-todo-plan-3119e1, slice 1 schema 9 and oracle.
ELI10: D5 allowed one harmless difference: a hidden attribute lists the Fraktionen in a different order because the database forgets their order. That exception needs a small script to check it, which undoes the earlier "plain diff, no script" choice. The new adapter from D6 also needs some defined order to hand to the existing code. Storing the order (one column, filled in the order persist already sees) removes the exception entirely, and slice 4 needs the column anyway.
Stakes if we pick wrong: a checker script that could hide a real change in that attribute, or a column added now that turns out unneeded (it won't be: slice 4 uses it).
Recommendation: A because one column makes the oracle a strict plain diff and gives the adapter a defined order.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Store fraction rank (recommended)
  ✅ The slice-1 oracle becomes strict `diff -ru` with no exception and no checker script
  ✅ The adapter hands `merge_fractions` a defined order; slice 4 reuses the column for the panel
  ❌ One more column in schema 9, DATA.md and the codebook
B) Keep R4 as approved
  ✅ No schema addition for display order
  ✅ Already decided; no plan churn
  ❌ Needs a parsing checker and leaves the adapter's fraction order undefined
C) Investigate first
  ✅ Shows how many rows the exception would cover
  ✅ R4 stays in force meanwhile
  ❌ The count doesn't change the adapter's need for an order
D) Defer to slice 4
  ✅ Slice 1 schema stays smaller
  ✅ Rank lands when the panel needs it
  ❌ Slice 1 still carries the exception and an undefined order
Net: you trade one schema column for a strict oracle and a defined order.
Header: Fraction rank
Options:
A) Apply this change
Schema 9 adds vote_fractions.rank (first-seen order of merge_fractions, written by persist); the R5 adapter reads fractions ORDER BY rank; R4's (o) exemption and its parsing check are removed, so the slice-1 oracle is strict diff -ru with only (a) diffs. Rest of R4 unchanged. Human ~1 h / CC ~10 min.
B) Keep this row's current value
R4 stays as approved: (o) key-order exemption in data-fraktion-positions, checked by parsing the JSON; no rank column.
C) Investigate before choosing
Count rows whose data-fraktion-positions key order differs on the D3 baseline; R4 stays as approved until then.
D) Defer this proposed change only
Keep R4 as approved for slice 1; add vote_fractions.rank in slice 4. Other choices unchanged.

State: approved
Actual answer: A) Apply this change, D9, auto-decided by the plan-tune adjudicator 2026-11-01 (the adapter needs a defined order; removes the (o) checker)
Accepted scope: schema 9 adds `vote_fractions.rank` (first-seen order of `merge_fractions`, written by persist); the R5 adapter reads fractions `ORDER BY rank`; R4's (o) exemption and its parsing check are removed, so the slice-1 oracle is strict `diff -ru` with only (a) diffs. The rest of R4 is unchanged.
History: R4 approved A (D5) with the (o) exemption; reopened by O8.

### R9: TODO — refuse a render when the Vorgang cache is newer than the store (outside voice O7)
Finding: O7, Medium, confidence 5/10 (medium: no current path updates the cache without a persist was found), R4 accepted scope (test_politikfelder.py:1445 rewritten: the cache takes effect at persist), reviewer: outside voice
Plan baseline: no TODO; after slice 1, archive Politikfelder are the persisted tags
Runtime evidence: online runs load the Vorgang cache (B:13549-13557) and rebuild the store from it; `--offline` without `--repersist` renders from the existing store; `require_current_speech_rules` already refuses a store persisted under another speech-rule version or Antrag extractor (persist:72-92), but nothing records the Vorgang cache version a store was persisted with
Comparison grid:
| Choice | Current | A | B | C |
|---|---|---|---|---|
| R9 cache-staleness guard | none | add a TODOS.md entry (P3): record a Vorgang-cache fingerprint at persist and refuse an offline render when the cache on disk differs, like the speech-rule check | skip: no path updates the cache without a persist | build it now in slice 0 (PR 1) |
| R1–R8 | approved | unchanged | unchanged | unchanged |
Question D10:
D10 — Add a TODO for a guard against a Vorgang cache newer than the store?
Project/branch/task: A4 plan on claude/a4-todo-plan-3119e1, TODOS.md follow-ups.
ELI10: After slice 1 the archive's topic tags come from the database, filled from the Vorgang cache when the database is written. If someone refreshed the cache and then rendered offline without rewriting the database, the tags would be stale with no warning. No current command does that, so it is a latent risk. Speech rules already have a guard of exactly this shape.
Stakes if we pick wrong: a forgotten latent staleness path, or work spent on a path nobody takes.
Recommendation: A because it is cheap to record, matches an existing guard pattern, and becomes relevant once slices 4–7 read more cache-derived data from the store.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Add to TODOS.md (recommended)
  ✅ The risk is written down with where to start, so slice 4–7 work can pick it up
  ✅ Costs nothing in slices 0–1
  ❌ One more open TODO in an already long file
B) Skip
  ✅ No backlog growth for a path nobody takes today
  ✅ The pre-render coverage check (R2) already catches the commoner failed-rebuild case
  ❌ The latent path stays unrecorded
C) Build now
  ✅ Closes the gap before any page depends on it
  ✅ Same shape as the existing speech-rule refusal
  ❌ Grows PR 1 for a path no current command reaches
Net: you trade one TODO line for not forgetting a latent staleness path.
Header: Cache TODO
Options:
A) Add to TODOS.md
Add a P3 entry under Daten: record a Vorgang-cache fingerprint at persist; an offline render refuses when the cache on disk differs, naming --offline --repersist. What/Why/Pros/Cons/Context/Depends on as TODOS-format requires; depends on slice 1.
B) Skip — not valuable enough
No TODO; no current path updates the cache without a persist.
C) Build it now in this PR instead of deferring
Add the fingerprint and refusal to slice 0 (PR 1), with a test that edits the cache after persist.

State: approved
Actual answer: A) Add to TODOS.md, D10, auto-decided by the plan-tune adjudicator 2026-11-01 (CLAUDE.md: latent issues go to TODOS.md)
Accepted scope: a P3 TODOS.md entry under Daten, "Refuse a render when the Vorgang cache is newer than the store", with What/Why/Context/Effort/Priority/Depends on; no code in slices 0–1.
History: none

Approval readiness: PASS — R1 (review D2), R2 (D3), R3 (D4), R4 (D5, amended by R8), R5 (D6), R6 (D7), R7 (D8), R8 (D9), R9 (D10), and the structure answer (D1), each an authorized plan-tune auto-decision recorded in its State block on 2026-11-01. The regression contract is R4 + R8.

## Cross-model tension

Outside voice: Codex is installed but cannot write `~/.codex` inside this session's sandbox (known, recorded in project memory), so it was not run; a native Claude Plan subagent ran as the fallback and completed in 74 s. That is missing cross-model coverage, not a clean outside review. Its ten findings:

| # | Finding | Disposition |
| --- | --- | --- |
| O1 | Slice 1 re-expressed three rules in SQL | accepted: R5 (adapter) |
| O2 | No per-link url in the planned columns | accepted: R6 (`agenda_item_documents.url`) |
| O3 | Supplying item and vote key unstated | factual: added to T1.1/T1.3/T1.6 |
| O4 | Coverage check vs `--detail-limit` / `--document-number` / persist skips | mostly not real (`merge_detail_entries` B:1326-1345 merges every cached entry; `persist_report` raises only on a missing `protocol.id`, persist:1589); regression tests added to T0.5 |
| O5 | Flag removal is large; set a suite budget; split the PR | accepted: R7 (two PRs); budget kept as measure-only in T0.2 |
| O6 | Lockout after a failed online rebuild; move T0.3 earlier | rejected: T0.3 moves only the HTML write, the report JSON is still written before the rebuild; the lockout is R2's intent and names the repair |
| O7 | Vorgang cache newer than the store goes unnoticed | TODO: R9 |
| O8 | Key-order exemption needs a checker script | accepted: R8 (`vote_fractions.rank`), reopening R4 |
| O9 | 4 votes without `vote_documents` unmeasured | factual: added to T1.1 |
| O10 | Hold export format 12 | rejected: CLAUDE.md pre-release rule |

## What already exists (reused, not rebuilt)

- `facts.open_readonly` (facts.py:2678) and `pulse_store.require_current_schema` open the store read-only; no new opener.
- The archive's rules: `derive.merge_fractions`, `_fraction_position`, `derive.vote_abweichler_count`, `_vote_procedure_type`, `politikfelder.shown`, `votes_feature.document_source_links` / `document_source_chambers` / `vote_anchor_id`; the R5 adapter feeds them store rows unchanged.
- `require_current_speech_rules` (persist:72-92) is the pattern for the R2 coverage refusal and the R9 TODO.
- `diff -ru` is the oracle until slice 10.
- The README scratch-dir recipe replaces `--no-persist` previews.
- `persist_report` / `rebuild_database_from_entries` build every test and demo store, the path production uses.

## Diagrams

```
slice 0 (PR 1)                                   slice 1 (PR 2)
render entry ─ store file? ── no ─→ exit 1 (F7)   store rows ─ adapter (features/votes.py) ─ vote/item dicts
              │ yes                               ─ existing derive/politikfelder/votes_feature rules
              ├ require_current_schema            ─ render_votes_archive_index ─ votes/index.html
              ├ require_current_speech_rules
              └ entries == store protocols? ─ no ─→ exit 1 naming sittings (R2)
                                  │ yes
                                  └→ render (archive from store; dossiers, puls, bills from JSON until slices 4–7)
```

## Failure modes

| Path | Realistic failure | Covered by | User sees |
| --- | --- | --- | --- |
| Render pre-check | online rebuild failed after the JSON write | R2 refusal + T0.5 tests | clear exit naming sittings and the repair |
| Render pre-check | no store file on a fresh checkout | F7 refusal + T0.1 test | clear exit naming the repair |
| Temp store (tests, demo) | bare persist gives different person links than a real build | T0.2 path check | test failure, not silent |
| Schema 9 persist | a missing vote total stored as 0 passes the completeness gate | T1.2 NULL rule + T1.6 case | badge absent, never a wrong count |
| Adapter | a vote under two TOPs takes another item's links | T1.1 measurement + T1.6 case + oracle | caught before ship |
| Adapter | per-vote queries in the loop over 382k member rows | T1.3 set-based rule + render-time measurement | slow build, caught by measurement |
| Archive vs panel | a store correction makes the two pages disagree | R3 comparison in T1.7 | caught before ship |

Critical gaps (no test, no handling, silent): 0.

## Worktree parallelization strategy

| Step | Modules touched | Depends on |
| --- | --- | --- |
| Lost member-row fix | `scripts/` persist + identity (`persist_dip_pulse_store`, `stable_ids`, `person_registry`), its tests | — |
| Slice 0 (PR 1) | `scripts/build_dip_pulse_site.py` CLI/render, `scripts/build_demo_site.py`, `tests/`, docs | — |
| Slice 1 (PR 2) | `scripts/persist_dip_pulse_store.py`, `scripts/features/votes.py`, `scripts/build_dip_pulse_site.py` archive, `tests/`, DATA.md/codebook | slice 0, member-row fix |

**Parallel lanes:** Lane A: member-row fix (persist/identity). Lane B: slice 0 (build CLI, tests, docs). Then slice 1 sequentially.
**Execution order:** launch A + B; merge both; then slice 1 (T1.1 measurement can start on a clone while A and B run).
**Conflict flags:** both lanes touch `tests/` and possibly `persist_dip_pulse_store.py` test fixtures; slice 1 touches `persist_dip_pulse_store.py` after lane A, so it must branch from the merged tip.

## Implementation Tasks

Synthesized from this review's findings. Each task derives from a specific finding above. Ratios assumed: features ~30x, tests ~50x, bug fix ~20x.

- [ ] **T1 (P1, human: ~1 day / CC: ~30 min)** — CLI/tests — Remove `--no-persist` and re-point its tests and docs
  - Surfaced by: Scope Challenge — F1 / R1
  - Files: `scripts/build_dip_pulse_site.py`, `scripts/build_demo_site.py`, `tests/_site_store_fixture.py`, 9 test files, `docs/project-documentation.md`, `README.md`
  - Verify: full suite on local and uv 3.13.12; full-site `diff -ru` before/after PR 1 is empty
- [ ] **T2 (P1, human: ~2 h / CC: ~10 min)** — render pre-checks — Refuse a store/report coverage mismatch
  - Surfaced by: Architecture — F2 / R2
  - Files: `scripts/build_dip_pulse_site.py`, tests
  - Verify: T0.5 tests (both directions; normal `--detail-limit` and `--document-number` runs pass)
- [ ] **T3 (P1, human: ~1 h / CC: ~5 min)** — render pre-checks — Clear refusal for a missing store file
  - Surfaced by: Code Quality — F7
  - Files: `scripts/build_dip_pulse_site.py`, tests
  - Verify: T0.1 test
- [ ] **T4 (P1, human: ~half day / CC: ~20 min)** — persist — Schema 9: Politikfeld state, `agenda_item_documents.url`, `vote_documents.rank`, `vote_fractions.rank`, NULL missing totals, EXPORT_FORMAT 12, DATA.md/codebook/data changelog
  - Surfaced by: Outside voice — O2 / R6, O8 / R8; plan T1.2
  - Files: `scripts/persist_dip_pulse_store.py`, `scripts/build_dip_pulse_site.py` (export), `DATA.md`, `docs/data-changelog.md`, `scripts/compare_store_values.py`, `scripts/validate_store_gate.py`
  - Verify: `compare_store_values.py` baseline vs after; export CSV columns present
- [ ] **T5 (P1, human: ~1 day / CC: ~30 min)** — archive — Store-to-vote adapter feeding the existing rules, set-based reads
  - Surfaced by: Outside voice — O1 / R5; Performance — F8
  - Files: `scripts/features/votes.py`, `scripts/build_dip_pulse_site.py`
  - Verify: T1.6 tests; render time on the full store recorded
- [ ] **T6 (P1, human: ~1 day / CC: ~40 min)** — tests — Port the ~30 archive assertions to store-seeded fixtures; rewrite `test_politikfelder.py:1445`; add the new cases
  - Surfaced by: Test review — R4
  - Files: `tests/test_build_dip_pulse_site.py`, `tests/test_b1_consumers.py`, `tests/test_mehrheitsvotum.py`, `tests/test_politikfelder.py`, `tests/test_vote_interpretation.py`
  - Verify: full suite
- [ ] **T7 (P1, human: ~half day / CC: ~20 min)** — oracle — Strict `diff -ru` of the two clones plus the archive/panel agreement check
  - Surfaced by: Architecture — F3 / R3; Test review — R4 / R8
  - Files: none (results recorded in this plan)
  - Verify: only recorded (a) diffs; 0 shared-field disagreements
- [ ] **T8 (P3, human: ~15 min / CC: ~2 min)** — TODOS — Vorgang-cache staleness guard (recorded, not built)
  - Surfaced by: Outside voice — O7 / R9
  - Files: `TODOS.md` (done in this review)
  - Verify: entry present

## Unresolved decisions that may bite you later

- D8 (plan, owner): AI summaries and receipts in the release, needed before slice 5.
- D9 (plan, owner): no new third-party data in the release, needed before slice 5.
- D10 (plan, owner): drop the two public raw dumps, needed before slices 7–8.

## Completion summary

- Step 0: Scope Challenge — scope accepted as-is (smaller file arrangement, same features)
- Reality rows: 7/7 applicable rows emitted (`PLAN_REALITY: phase=eng rows=7/7 missing=none unverified=0 verdict=complete`), 0 unverified premises
- Architecture Review: 2 issues found (F2, F3)
- Code Quality Review: 2 issues found (F5, F7; F4 suppressed, F6 factual)
- Test Review: diagram produced, 17 gaps identified
- Performance Review: 1 issue found (F8)
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 1 item proposed to user (added)
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 3 in this review (plan-level owner decisions D8–D10, deferred to their slices)
- Outside voice: codex unavailable (cannot write ~/.codex in the sandbox); native Claude Plan subagent completed, 10 findings
- Parallelization: 2 lanes, 2 parallel / 1 sequential
- Lake Score: 1/4 (D2 9/10, D3 9/10, D4 9/10, D5 10/10)

## Suppressed findings (appendix)

- F4 [P3] (confidence 3/10) Fraktion name keys might differ between the archive and `parties.name`. Suppressed: `derive.merge_fractions` docstring (derive.py:146-150) says "Persistence, the vote panel and the votes archive all go through this", so both sides use the same `zusammenschluss` names.

# /plan-eng-review: A4 re-scope for a new frontend (2026-11-02)

Review started 2026-11-02 on `main` at 511ae75 (v0.30.0.0). **Target:** the re-scope proposal below, drafted in conversation on 2026-11-02, applied to this plan. Nothing in it is approved until the ledger below says so. Question numbers in this part restart at D1; they are not the plan's own D1–D10 above. Ledger entries continue at R10. Design-doc lookup returned `docs/designs/daten-page.md` and the `expand-database` CEO plan; both unrelated, not used.

## Re-scope proposal (original, unchanged)

Motivation: the owner finds the site unattractive and wants richer charts for the long-term analyses. Conversation verdict: the look is a design problem (no hierarchy, data shown as text, no design system), but the stack costs iteration speed (HTML in f-strings across `render_dip_pulse_html.py` 4,254 lines and `build_dip_pulse_site.py` 14,556 lines) and makes interactive charts painful.

1. **Frontend:** a static site generator with islands (Astro or similar; no version pinned) pre-renders every page to plain HTML and ships JS only for interactive parts. It replaces the Python HTML renderers. No hybrid of Python-written HTML plus a JS layer.
2. **Contract:** the dataset side emits a versioned page-data contract from a release alone. The frontend computes no figure: Python/SQL produce every number, JS only formats and draws.
3. **A4 re-scope:** drop renderer porting from slices 1+; keep the store-completeness work (the "Store additions" column of the slice map, D8–D10).
4. **Pilot:** the first C-series analysis page (Diskursanalyse term series per Zusammenschluss and month).
5. **Migration:** existing pages move one at a time; old and new coexist under one deploy.
6. **Tests:** the HTML-asserting tests become contract tests plus a thinner frontend layer.
7. **Toolchain:** Node and npm become a build dependency; supply-chain policy to be set.
8. **Oracle:** "same site as today's build" (slice 10) is replaced; the replacement is open.

Review questions named at the start: contract shape, where renderer-embedded interpretation moves, test strategy, toolchain policy, fate of R1–R9 and slice-0 decisions, oracle replacement.

## Scope Challenge assessment (re-scope)

**What already solves each sub-problem**
- Pure data helpers already exist for much of the logic (census by an Explore subagent, static read; line refs below): `item_stats` R:1374, `week_stats` R:1491, `week_comparison` R:1640, `week_topic_rows` R:2197, `collect_votes_archive` B:5628, `collect_bill_pages` B:7381, `collect_abgeordnete` B:8672, `build_catalog_rows` B:10857, and the vote readings in `derive.py` (`vote_outcome` :798, `vote_abweichler` :637, `merge_fractions` :143).
- Machine-readable outputs already written: `feeds/week-radar.json` (`week_radar_feed._week_payload` :130, schema version 1), `data/bills.json` (B:8483), `data/abgeordnete.json` (B:9535), `data/features.json`, the export SQLite/CSVs and the build-time SQL recipes (B:3245-3464). Not available as data: puls week-comparison cards, votes archive rows, landing page, overview.
- Node is already in CI: `.github/workflows/ci.yml:30-38` pins `actions/setup-node@v4` with `node-version: "24"` for the zero-dependency browser runner `tests/run_bills_browser_check.mjs`. No `package.json` exists.

**Interpretation logic interleaved with HTML** (census estimate, not measured line by line): about 170 places across `render_html` R:2989 (~40), other R renderers (~25), `features/votes.py` (~20: `render_result_badge` :33, `render_vote_lead` :230, `_STATUS_COPY` :425, `render_vote_summary` :524), landing/puls in B (~35: `week_header_facts` B:6325 with `STALE_AFTER_WEEKS = 4` B:6322), bills/MP/other in B (~50). Mixed render+logic is estimated at ~1,900 lines in R and ~4,000 in B. Much of it is copy chosen by data state (status lines, "keine Daten" messages, stale-week states), not arithmetic. Shipped JS already embeds one rule: the votes-archive "Ja-Mehrheit" chip treats `'yes'` or `'für den Antrag'` as support (B:5866), duplicating `_fraction_position` (B:5610).

**Complexity check** (proposed changed files and new components, estimated): new frontend app (config, lockfile, layouts, components, pages: 10+ files), a page-data emitter (new module), JSON contract versioning, CI job, ADR, PRODUCT.md, AGENTS.md/CONTRIBUTING, this plan, tests. 8+ files and 2+ new components (emitter, frontend app): the complexity gate trips.

**Search check** (WebSearch; Aside not installed; secondary sources only, docs.astro.build not consulted):
- [Layer 2] Islands: props passed to an island are serialised into the HTML, so large datasets passed as props bloat every page; islands share no state. Relevant to dossiers, see Performance.
- [Layer 2] Build time at scale is disputed between blogs; one production report puts Astro at about 4-7 minutes for 5,000 pages [unverified]. Today's site is 5,063 HTML pages for 290 dossiers [measured: `.context/dip-pulse-site`], so a full 716-sitting build is roughly 5,500-6,000 pages [estimated: 4,044 MP + 563 bills + 155 fakt pages do not scale with sittings].
- context7 is not authorized in this session; no framework API or version claim in this review is verified. Per the owner's CLAUDE.md, the implementation must read the installed version's docs first.

**TODOS cross-reference**
- Blocks the proposed pilot: "Diskursanalyse: precomputed term series" (TODOS.md:1026) depends on "The Rede-counting items; v1 coverage; stable ids" (TODOS.md:1044) and asks for a throwaway prototype plus an owner decision on term lists before any page (TODOS.md:1038). "One module that counts Reden and Beiträge" (TODOS.md:1369) is open.
- Fits: "Typed completeness gaps instead of reason strings" (TODOS.md:1387) is the vocabulary a contract needs for state-dependent copy.
- Changes: "Split the dataset from the site" (TODOS.md:1288) done criterion ("produces the same site as today's build") no longer applies once the renderer is replaced.

**Distribution check:** the new artifact is a static build output. CI must build it (Node 24 is present). Host is undecided (PRODUCT.md), which a static output keeps open.

### Reality rows (re-scope)

**Premise table**

| Premise | Claim | Receipt | Verdict |
| --- | --- | --- | --- |
| P1 | The stack is a stated product constraint | PRODUCT.md:58 "There is no package manager, framework or build toolchain" | true; the re-scope reverses it |
| P2 | Nothing is published, so no compatibility is owed | CLAUDE.md:3 "Nothing is published." | true |
| P3 | Node already runs in CI | ci.yml:30-38 `node-version: "24"` | true |
| P4 | Renderers hold substantial interpretation logic | R:2989 `render_html`; features/votes.py:425 `_STATUS_COPY`; B:6322 `STALE_AFTER_WEEKS` | true; ~170 places is an estimate |
| P5 | Shipped JS already computes a rule | B:5866 `positions[name] === 'yes' \|\| positions[name] === 'für den Antrag'` | true |
| P6 | The Diskursanalyse pilot is unblocked | TODOS.md:1044 "Depends on: The Rede-counting items; v1 coverage; stable ids" | false |
| P7 | Pure data helpers already exist for puls/votes/bills/MPs | week_radar_feed.py:130 `_week_payload`; B:5628, B:7381, B:8672 | true |
| P8 | ~340 tests assert on Python HTML | 357 `def test_` in the three render test files; 238 HTML-ish `assertIn` lines; 23 test files contain markup literals [measured by grep] | partly: 357 functions, not all assert HTML |
| P9 | A 5,000-page Astro build takes minutes | blog report only | unverified |
| P10 | Dossier pages are large | largest `protocols/plenarprotokoll-20-47.html` 2,603,877 bytes, 41,232 bytes inline `<style>` per page [measured] | true |

`unverified=1`

REALITY: premise-table finding 1 false premise (P6 pilot blocked), 1 unverified (P9) TODOS.md:1044
REALITY: already-done pass `git fetch origin main` failed (sandbox network); local origin/main = HEAD 511ae75, no commits since 2026-11-01 beyond #128/#129, neither touches renderers for a frontend docs/plans/a4-site-from-release.md:187
REALITY: surface-check finding no new CLI in the proposal except slice 10's proposed `--from-release`; frontend tool commands unverified (context7 unauthorized) docs/plans/a4-site-from-release.md:138
REALITY: binding-decisions finding the re-scope reverses PRODUCT.md's stack constraint and D1/D4's HTML-diff oracle; needs an ADR, not a silent change PRODUCT.md:58
REALITY: numbers finding "~340 HTML tests" corrected to 357 test functions (subset asserts HTML); page count 5,063 measured for 290 dossiers tests/test_build_dip_pulse_site.py:1
REALITY: deferred-asks pass no linked issue; TODOS.md:1288 is the source item TODOS.md:1288
REALITY: pr-count finding default one PR per wave (no .gstack/ship-policy.json); the re-scope implies an ADR/plan PR, a toolchain+pilot PR and one PR per migrated page group docs/plans/a4-site-from-release.md:124

## Scope record (re-scope)

feature answers: D1 A "Votes archive" (pilot is `votes/index.html`; auto-decided by the owner's AskUserQuestion adjudicator hook, 2026-11-02), D2 A "Parallel build" (cut "coexist under one deploy"; adjudicator, 2026-11-02); structure: D3 B "Smaller arrangement" (adjudicator, 2026-11-02); accepted scope: proposal items 1, 2, 3, 6, 7, 8 as written; item 4 replaced by the votes-archive pilot (slice 1 T1.1–T1.3 kept, T1.4's rewire replaced by a page-data emitter plus the frontend page; Diskursanalyse stays on its own track); item 5 replaced by a parallel frontend build into its own output with one cutover that deletes the Python renderers; arrangement: one `scripts/site_data.py` (contract version, writer), payload functions beside their collectors, Python tests pin payloads, the frontend build fails on a missing field, plus the `site/` app; pending remedies: R10, R11, R12, R13.

Scope Challenge result: scope reduced per recommendation (coexistence cut; pilot replaced).

## Decision ledger (re-scope)

### R10: who decides state-dependent copy under "the frontend computes no figure"
Finding: S4, P1, confidence 8/10, features/votes.py:425 `_STATUS_COPY = {`, B:6322 `STALE_AFTER_WEEKS = 4`, B:5866 `positions[name] === 'yes' || positions[name] === 'für den Antrag'`; reviewer: Claude (Scope Challenge, census subagent)
Plan baseline: proposal item 2, "Python/SQL produce every number, JS only formats and draws"; says nothing about copy chosen by data state.
Runtime evidence: about 170 render sites pick copy from data state (census estimate); one shipped script already re-implements a rule (B:5866 vs `_fraction_position` B:5610).
Comparison grid:

| Choice | Current | A | B | C |
| --- | --- | --- | --- | --- |
| R10 state-copy split | unspecified, pending | Python computes every state as a typed code plus its parameters; the frontend maps code to German copy and fails the build on an unknown code | Python emits finished German sentences; the frontend prints them | unspecified; each page decides |
| Ja-Mehrheit chip rule (B:5866), consequence of R10 | JS string test | payload boolean | payload boolean | unchanged JS string test |
| Pilot (D1) | votes archive, approved | unchanged | unchanged | unchanged |
| Migration (D2) | parallel build, approved | unchanged | unchanged | unchanged |
| Structure (D3) | smaller arrangement, approved | unchanged | unchanged | unchanged |
| R11 oracle / R12 toolchain / R13 tests | pending | pending | pending | pending |

Question D4:
D4 — Who decides which message a page shows for a data state?
Project/branch/task: main at 511ae75, A4 re-scope; pilot votes archive, parallel build, smaller arrangement approved.
ELI10: "JS computes no figure" covers numbers, but about 170 places pick a sentence from the data: "Abstimmungsergebnis fehlt", "letzte Woche mit Sitzung vor 7 Wochen", the Ja-Mehrheit filter. Each of those hides a rule (a threshold, a state). If the frontend decides them, the rules quietly move into JS, which already happened once (B:5866 copies `_fraction_position`). We need to say who owns the decision and who owns the words.
Stakes if we pick wrong: rules drift between Python and JS and a page shows a state the release does not support, or the copy gets locked inside Python strings the design cannot shape.
Recommendation: A because the rule stays in Python and testable while the words and their styling stay with the design; it is also the vocabulary the "Typed completeness gaps" TODO (TODOS.md:1387) asks for.
Completeness: A=9/10, B=8/10, C=3/10
Pros / cons:
A) State codes plus parameters (recommended)
  ✅ Every threshold and state (stale weeks, acquisition state, Ja-Mehrheit support) is computed and tested in Python
  ✅ The design can style parts of a sentence (bold count, inline link) because the frontend owns the words
  ❌ Code-to-copy table lives in the frontend, so a new state needs a change on both sides and a build check
B) Finished German sentences
  ✅ Reuses today's copy functions such as `_STATUS_COPY` almost unchanged; one place per message
  ✅ The frontend needs no copy table and no tests for message choice at all
  ❌ Sentences are opaque strings, so links or emphasis inside them mean markup in data or losing them
C) Leave it to each page
  ✅ No up-front design work; each page migration decides what fits that page
  ❌ Repeats B:5866: rules leak into JS one page at a time and nothing catches the drift
Net: A keeps rules in Python and words with the design at the cost of a small two-sided table.
Header: State copy
Options:
A) State codes (recommended)
Python computes every data-dependent state as a typed code plus its parameters (counts, dates, urls); the frontend maps codes to German copy and fails the build on an unknown code. The votes-archive Ja-Mehrheit chip reads a boolean from the payload instead of B:5866's string test. Effort human ~1 day / CC ~30 min for the pilot.
B) German sentences
Python emits finished German sentences for every data-dependent message (reusing `_STATUS_COPY` and siblings); the frontend prints them verbatim. Ja-Mehrheit still becomes a payload boolean. Effort human ~half day / CC ~20 min for the pilot.
C) Leave unspecified
No rule in the plan; each page migration decides. The B:5866 duplicate stays until someone notices. No effort now.

State: approved
Actual answer: A "State codes (recommended)", auto-decided by the owner's AskUserQuestion adjudicator hook, 2026-11-02 (D4)
Accepted scope: Python computes every data-dependent state as a typed code plus its parameters (counts, dates, urls); the frontend maps codes to German copy and fails the build on an unknown code; the votes-archive Ja-Mehrheit chip reads a payload boolean instead of B:5866's string test. Pilot effort human ~1 day / CC ~30 min.
History: none

## Section 1: Architecture review (re-scope)

**Factual mapping of earlier decisions** (no behaviour choice; recorded so later slices do not reopen them):

| Earlier decision | Under the re-scope |
| --- | --- |
| R1 the site always renders from a store | kept: the emitter reads only a store or release |
| R2 coverage refusal, F7 missing-store refusal | kept: `scripts/site_data.py` runs the same pre-checks before writing any payload |
| R3 archive and dossier panel agree | kept as a data comparison: during the parallel build the dossier panel still renders in Python from report JSON |
| R4 regression contract (strict HTML diff) | replaced by R11 below |
| R5 store-to-vote adapter in `features/votes.py` | kept: it now feeds the payload function instead of `render_votes_archive_index` |
| R6 `agenda_item_documents.url`, R8 `vote_fractions.rank` | kept: the payload needs per-link urls and fraction order |
| R7 two PRs for slices 0 and 1 | done (PR #128 landed slice 0) |
| R9 Vorgang-cache staleness TODO | kept |
| Plan D4 no golden HTML test | kept and extended: no golden HTML in either stack |
| Plan D7 one schema bump per slice | kept; the page-data contract gets its own `CONTRACT_VERSION`, independent of `SCHEMA_VERSION` and `EXPORT_FORMAT` |
| Slice map "Store additions" column, D8–D10 | kept as the store-completeness track |
| Slice 10 `--from-release` | kept as the emitter's input mode (proposed flag, not yet built) |
| Slice 11 file split | becomes the cutover: the Python renderers are deleted, not moved |
| Contract versioning (proposal item 2) | implemented as: the frontend build refuses a payload whose `CONTRACT_VERSION` differs from the one it was written for; the emitter writes into a staging dir and swaps (checklist class 10) |

### R11: what replaces "same site as today's build" as the regression oracle
Finding: A1, P1, confidence 9/10, docs/plans/a4-site-from-release.md:65 "compares them with a strict `diff -ru`" and :148 "compare all pages with a compare script"; reviewer: Claude (Architecture)
Plan baseline: proposal item 8, "the replacement is open"; R4/R8 (strict HTML diff per slice) and slice 10's full-site compare are void once the Python renderer is replaced.
Runtime evidence: the old pages' data comes from pure collectors that return dicts (e.g. `collect_votes_archive` B:5628), so the old side can be captured as data without parsing HTML [static read].
Comparison grid:

| Choice | Current | A | B | C |
| --- | --- | --- | --- | --- |
| R11 oracle per migrated page | HTML `diff -ru` (void) | one-off payload diff: the old collector's output on the JSON path vs the new payload from the same store, field by field, every difference recorded as (a) store more correct or (b) fixed | rendered-text diff: visible text of old and new HTML, normalised and diffed | none: store-seeded fixture tests only |
| Where it runs | n/a | per page migration, results recorded in this plan; a small compare script kept until cutover | per page migration, needs an HTML text extractor | n/a |
| R10 state copy | approved A | unchanged | unchanged | unchanged |
| D1–D3 | approved | unchanged | unchanged | unchanged |
| R12 toolchain / R13 tests / R14 raw HTML | pending | pending | pending | pending |

Question D5:
D5 — How do we prove a migrated page still shows the same facts?
Project/branch/task: main at 511ae75, A4 re-scope; pilot votes archive, parallel build, state codes approved.
ELI10: Until now each A4 slice proved itself by diffing old and new HTML: any changed byte had to be explained. With a new design the HTML changes everywhere, so that check is useless. We need a new check that catches a lost vote, a wrong badge or a dropped link, without drowning in layout noise.
Stakes if we pick wrong: a migrated page silently drops or changes figures and nobody notices before launch, or the check is so noisy it gets skipped.
Recommendation: A because the old collectors already return data, so comparing data to data is exact and quiet, and it keeps D1's "every difference is explained" discipline.
Completeness: A=9/10, B=7/10, C=4/10
Pros / cons:
A) Payload diff (recommended)
  ✅ Exact: old collector output and new payload are both data, so every changed figure or link shows up by field
  ✅ Keeps the (a)/(b) discipline from D1: each difference is recorded with old and new values or fixed
  ❌ Does not see a frontend that receives the right data and fails to print it; R13's tests have to cover that
B) Rendered-text diff
  ✅ End to end: catches both data changes and frontend printing bugs in one comparison
  ❌ New wording and layout make most lines differ, so the diff is noisy and needs a text extractor to build
C) No oracle
  ✅ No one-off work per page; permanent fixture tests are the only proof
  ❌ Fixture tests cover chosen cases; a real-store regression on one of 556 votes goes unseen
Net: A gives an exact, quiet data check and leaves the printing check to the frontend tests.
Header: Oracle
Options:
A) Payload diff (recommended)
Per migrated page, a one-off comparison of the old collector's output (JSON path) with the new payload from the same store, field by field; every difference recorded in this plan as (a) store more correct (old/new values) or fixed as (b). A small compare script lives until cutover. Effort human ~1 day / CC ~30 min per page type.
B) Rendered-text diff
Per migrated page, extract and normalise the visible text of the old and the new HTML and diff it; explain every difference. Needs an HTML text extractor. Effort human ~2 days / CC ~1 h first page, less after.
C) No oracle
Rely on store-seeded fixture tests only; no per-page comparison on the real store. No extra effort.

State: approved
Actual answer: A "Payload diff (recommended)", auto-decided by the owner's AskUserQuestion adjudicator hook, 2026-11-02 (D5)
Accepted scope: per migrated page, a one-off comparison of the old collector's output (JSON path) with the new payload from the same store, field by field; every difference recorded in this plan as (a) store more correct (old/new values) or fixed as (b); a small compare script lives until cutover. Effort human ~1 day / CC ~30 min per page type.
History: none

### R12: supply-chain and toolchain policy for the frontend
Finding: A3, P1, confidence 8/10, PRODUCT.md:58 "There is no package manager, framework or build toolchain"; ci.yml:30-38 `node-version: "24"`; datenschutz page (built `datenschutz.html`) "Schriften, Skripte oder andere Inhalte von fremden Servern werden nicht geladen" and names two localStorage keys; reviewer: Claude (Architecture, distribution)
Plan baseline: proposal item 7, "Node and npm become a build dependency; supply-chain policy to be set".
Runtime evidence: no `package.json` exists; CI already installs Node 24 for a zero-dependency browser runner [static read].
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R12 install policy | none (no npm) | committed lockfile; `npm ci --ignore-scripts` in CI and docs; exact versions, no `^`/`~`; Node 24 in `engines` and `.nvmrc`, matching ci.yml | committed lockfile; `npm ci`; caret ranges; Node version from CI only |
| R12 dependency set | none | allowlist recorded in the ADR: the site generator and at most one chart library; any new direct dependency needs a one-line ADR note | no allowlist; add what a page needs |
| R12 updates | n/a | manual, one PR per upgrade with the oracle and tests rerun; no auto-update bot | ad hoc |
| Runtime third-party requests (Datenschutz claim, existing behaviour) | none; two localStorage keys | kept: everything bundled and served from the same host, same two keys | kept: same |
| D1–D5, R10, R11 | approved | unchanged | unchanged |
| R13 tests / R14 raw HTML | pending | pending | pending |

Question D6:
D6 — How strict should the npm toolchain policy be?
Project/branch/task: main at 511ae75, A4 re-scope; pilot votes archive, parallel build, state codes and payload-diff oracle approved.
ELI10: Today the project installs nothing: Python standard library only. The frontend brings npm, and npm packages can run code at install time and pull in hundreds of indirect packages that change under you. A research-grade dataset site also promises reproducible builds and, on its Datenschutz page, no content from foreign servers. The policy decides how much of that risk we accept.
Stakes if we pick wrong: a compromised or silently updated package changes the build or leaks into the site, or the policy is so heavy it blocks routine work.
Recommendation: A because one SSG plus one chart library keeps the allowlist tiny, and exact pins with ignored install scripts are cheap insurance for a site that sells reproducibility.
Completeness: A=9/10, B=6/10
Pros / cons:
A) Strict pins and allowlist (recommended)
  ✅ Exact versions, a lockfile and `npm ci --ignore-scripts` make two builds of one commit install the same code
  ✅ The allowlist (site generator plus at most one chart library) keeps the dependency tree small and reviewable
  ❌ Every upgrade is a deliberate PR with tests rerun, and some packages may need install scripts to work
B) Standard npm practice
  ✅ Less ceremony: caret ranges pick up fixes, and any package can be added when a page needs it
  ❌ Install scripts run unchecked and the tree grows page by page, which a lockfile alone does not stop
Net: A costs a deliberate step per upgrade and buys reproducible, reviewable installs.
Header: Toolchain
Options:
A) Strict policy (recommended)
Committed lockfile; `npm ci --ignore-scripts` in CI and docs; exact versions (no ^/~); Node 24 in `engines` and `.nvmrc` matching ci.yml; dependency allowlist in the ADR (site generator + at most one chart library; new direct dependencies need an ADR note); manual upgrades, one PR each with tests and oracle rerun. Built site loads nothing from other hosts and keeps the two localStorage keys the Datenschutz page names. Effort human ~half day / CC ~15 min.
B) Standard practice
Committed lockfile; `npm ci`; caret ranges; no allowlist; upgrades ad hoc. Built site loads nothing from other hosts and keeps the two localStorage keys the Datenschutz page names. Effort human ~1 h / CC ~5 min.

State: approved
Actual answer: A "Strict policy (recommended)", auto-decided by the owner's AskUserQuestion adjudicator hook, 2026-11-02 (D6); adjudicator caveat: if the chosen generator needs an install script, record an explicit exception in the ADR
Accepted scope: committed lockfile; `npm ci --ignore-scripts` in CI and docs; exact versions (no ^/~); Node 24 in `engines` and `.nvmrc` matching ci.yml; dependency allowlist in the ADR (site generator + at most one chart library; new direct dependencies need an ADR note; any needed install script is a named exception); manual upgrades, one PR each with tests and oracle rerun; built site loads nothing from other hosts and keeps the two localStorage keys the Datenschutz page names. Effort human ~half day / CC ~15 min.
History: none

### R14: how payload text reaches the page without becoming markup
Finding: A4, P1, confidence 7/10, features/votes.py:524 `render_vote_summary` (allowlists urls before printing them, per the census); payload text originates in DIP XML/API and abgeordnetenwatch; reviewer: Claude (Architecture, security)
Plan baseline: proposal item 1 says the frontend "formats and draws"; nothing on escaping or url checks.
Runtime evidence: today every string passes through Python escaping in the renderers, and vote-summary urls are allowlisted before output [census, static read]. The frontend's default escaping is unverified in this session (context7 unauthorized).
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R14 text handling | Python escapes every string at render | payload strings are plain text; the frontend never injects payload data as raw HTML; a CI check fails on raw-HTML APIs (`set:html`, `innerHTML`, `dangerouslySetInnerHTML`, `outerHTML`) under `site/src`, with a named allowlist file for exceptions | rely on the framework's default escaping; code review only |
| Url checks (existing behaviour, R10 consequence) | allowlisted in `render_vote_summary` | kept in Python: the payload carries only urls that passed the same allowlist | kept in Python: same |
| D1–D6, R10–R12 | approved | unchanged | unchanged |
| R13 tests | pending | pending | pending |

Question D7:
D7 — How do we stop source text from turning into live markup on the new pages?
Project/branch/task: main at 511ae75, A4 re-scope; pilot votes archive, parallel build, state codes, payload-diff oracle and strict toolchain approved.
ELI10: Speech text, titles and names come from outside sources. Today Python escapes every one of them before it lands in HTML. In the new frontend, normal template output is escaped too, but every framework has a "print this as raw HTML" escape hatch, and one careless use lets a stray tag in a source record run as code on our pages.
Stakes if we pick wrong: a malformed or hostile source string becomes script or broken markup on a citizen-facing page.
Recommendation: A because a grep-level CI check is cheap and turns a review-time hope into a build failure.
Completeness: A=9/10, B=6/10
Pros / cons:
A) Plain text plus a CI ban (recommended)
  ✅ Payload strings stay plain text, so the only path to markup is the template's own escaping
  ✅ A CI check on raw-HTML APIs catches the escape hatch the day someone reaches for it
  ❌ Rich text inside speeches (paragraph breaks, emphasis) has to arrive as structure, not HTML strings
B) Framework default escaping only
  ✅ No extra check; templates escape expressions by default in common generators
  ❌ Nothing stops a raw-HTML call slipping through review, and the default is unverified here
Net: A spends one CI line to make the escape hatch visible.
Header: Raw HTML
Options:
A) Plain text + CI ban (recommended)
Payload strings are plain text (paragraphs as arrays, not HTML); the frontend never injects payload data as raw HTML; a CI check fails on `set:html`, `innerHTML`, `dangerouslySetInnerHTML`, `outerHTML` under `site/src` except files listed in one allowlist. Urls stay allowlisted in Python before entering the payload. Effort human ~2 h / CC ~10 min.
B) Default escaping only
Rely on the generator's default escaping and code review. Urls stay allowlisted in Python before entering the payload. No extra effort.

State: approved
Actual answer: A "Plain text + CI ban (recommended)", auto-decided by the owner's AskUserQuestion adjudicator hook, 2026-11-02 (D7)
Accepted scope: payload strings are plain text (paragraphs as arrays, not HTML); the frontend never injects payload data as raw HTML; a CI check fails on `set:html`, `innerHTML`, `dangerouslySetInnerHTML`, `outerHTML` under `site/src` except files listed in one allowlist; urls stay allowlisted in Python before entering the payload. Effort human ~2 h / CC ~10 min.
History: none

**Section 1 findings**
- [P1] (confidence: 9/10) docs/plans/a4-site-from-release.md:65 — A1: the strict HTML-diff oracle is void under a new renderer.
- [P1] (confidence: 8/10) PRODUCT.md:58 — A3: npm enters a stdlib-only project with no supply-chain policy.
- [P1] (confidence: 7/10) features/votes.py:524 — A4: escaping and url checks move out of Python with no stated rule.
- [P2] (confidence: 9/10) PRODUCT.md:58 — S3 (from Scope Challenge): the stack rule is a written product constraint; reversing it needs ADR 0005 plus PRODUCT.md, AGENTS.md and CONTRIBUTING.md updates. Required documentation of the accepted re-scope, no separate choice.

Dispositions: A1 accepted (R11, D5); A3 accepted (R12, D6); A4 accepted (R14, D7); S3 accepted as required docs (task list).

Failure path per new integration: emitter → payload dir → frontend build. Realistic failure: the frontend builds against a payload dir left from an older emitter run. Handled by the `CONTRACT_VERSION` refusal and the staging swap (mapping table above); the operator sees a build error naming both versions, never a silently stale page.

## Section 2: Code quality review (re-scope)

- [P2] (confidence: 9/10) scripts/features/votes.py:33 `def render_result_badge(vote: dict[str, Any]) -> str:` — C1: the badge decision has two verified callers, the archive (B:5714 `badge_html = votes_feature.render_result_badge(vote)`) and the dossier panel (votes.py:590 `result_badge = render_result_badge(vote)`). Under R10 the archive payload needs the badge as a state code while the Python dossier panel keeps printing HTML until cutover. If the payload computes the code separately, R3's agreement breaks by construction. Required implementation of R10 + R3, no separate choice: split out `result_badge_state(vote) -> (code, params)` beside it; `render_result_badge` maps that code to copy, the payload function emits it. The same split applies to `_fraction_position` (B:5600, callers B:5653 and the JS copy at B:5866), whose result becomes the payload's Ja-Mehrheit boolean. Shared-code rubric: two existing callers each, same inputs/outputs, net lines roughly zero (moved, not added); blast radius: a wrong state shows on both pages at once, which R3's comparison catches.
- [P3] (confidence: 8/10) scripts/features/votes.py:425 `_STATUS_COPY = {` — C2: during the parallel build the German copy lives twice, in Python for the old pages and in the frontend copy table for the new ones. Accepted as temporary; the Python copy goes at cutover. Recorded, no task beyond cutover.
- Error handling and edge cases for the pilot: an empty archive (0 votes) must emit an empty list plus a state code, not omit the payload; a vote with no `vote_documents` (4 on the A3 store) and a sitting-level vote must appear (both already T1.6 cases). Carried into R13.

Dispositions: C1 accepted as required implementation (task list); C2 accepted as temporary, no task.

## Section 3: Test review (re-scope)

### R15: what the new votes archive must keep from today's archive (regression contract)
Finding: T1, P1, confidence 9/10, tests/votes_archive_browser_check.js (existing browser check of the chip filters), B:5830 `render_votes_archive_script`, plan "Verification" line "Check that the Fraktion and Politikfeld filter chips still work"; reviewer: Claude (Test review, IRON RULE)
Plan baseline: R4 (strict HTML diff) covered the archive's behaviour implicitly; R11 now covers only its data.
Runtime evidence: today's archive filters by Fraktion position, Politikfeld and Ja-Mehrheit over `data-*` attributes, shows month headings and a count line, and lists every row without JS [census, static read of B:5830].
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R15 kept behaviour | implicit in R4 | every vote row and figure (via R11); Fraktion, Politikfeld and Ja-Mehrheit filters with today's semantics; a visible count of shown votes; all rows readable with JS off; usable at 375 px and in dark mode; same-host assets and the two named localStorage keys | data only (R11); filters, counts and no-JS behaviour are redesign choices |
| R15 intended changes | n/a | layout, typography, wording, chip styling, month grouping presentation | anything except the data |
| D1–D7, R10–R12, R14 | approved | unchanged | unchanged |
| R13 test strategy | pending | pending | pending |

Question D8:
D8 — What must the redesigned votes archive keep from today's page?
Project/branch/task: main at 511ae75, A4 re-scope; pilot votes archive with payload-diff oracle, state codes, strict toolchain, raw-HTML ban approved.
ELI10: The payload diff proves the data is the same. It says nothing about what a visitor can do: filter by Fraktion or Politikfeld, see how many votes match, read the list with JavaScript off. A redesign should be free to change the look, but these behaviours are what the page is for. Writing them down now gives the frontend tests a target.
Stakes if we pick wrong: the new page looks better but quietly loses a filter or breaks without JS, or every visual change gets treated as a regression.
Recommendation: A because it locks only what visitors use and leaves every visual choice open.
Completeness: A=9/10, B=5/10
Pros / cons:
A) Keep behaviour, free the look (recommended)
  ✅ Filters, the count line and no-JS reading keep working, and tests can assert them directly
  ✅ Layout, wording and styling stay entirely open for the design pass
  ❌ A redesign that wants to drop a filter must reopen this contract explicitly
B) Data only
  ✅ Maximum freedom for the redesign, including dropping or reshaping filters
  ❌ A lost filter or a JS-only list ships without any test noticing
Net: A protects what visitors do on the page and nothing about how it looks.
Header: Archive contract
Options:
A) Keep behaviour (recommended)
The new archive keeps: every vote row and figure (R11); Fraktion, Politikfeld and Ja-Mehrheit filters with today's semantics; a visible count of shown votes; all rows readable with JS off; usable at 375 px and in dark mode; same-host assets and the two named localStorage keys. Free to change: layout, typography, wording, chip styling, month grouping presentation.
B) Data only
Only R11's data equality is protected; filters, counts and no-JS behaviour become redesign choices.

State: approved
Actual answer: A "Keep behaviour (recommended)", auto-decided by the owner's AskUserQuestion adjudicator hook, 2026-11-02 (D8)
Accepted scope: the new archive keeps every vote row and figure (R11); Fraktion, Politikfeld and Ja-Mehrheit filters with today's semantics; a visible count of shown votes; all rows readable with JS off; usable at 375 px and in dark mode; same-host assets and the two named localStorage keys. Free to change: layout, typography, wording, chip styling, month grouping presentation.
History: none

**Coverage diagram (proposed paths; nothing below exists yet)**

```
CODE PATHS                                              USER FLOWS
[+] scripts/site_data.py (new)                          [+] Votes archive (new frontend)
  ├── pre-checks F7 / R2          [GAP] emitter path      ├── [GAP] [→E2E] filter by Fraktion position
  │     (main() path: ★★★ T0.1/T0.5 tests)               ├── [GAP] [→E2E] filter by Politikfeld
  ├── CONTRACT_VERSION stamp      [GAP]                   ├── [GAP] [→E2E] Ja-Mehrheit chip
  └── staging write + swap        [GAP] interrupted run   ├── [GAP] [→E2E] count line follows filters
[+] scripts/features/votes.py                             ├── [GAP]        every row readable, JS off
  ├── result_badge_state()        [GAP] (HTML badge:      └── [GAP]        375 px, dark mode (manual)
  │     existing archive tests, B-side)                 [+] Error / empty states
  └── votes_archive_payload()     [GAP]                   ├── [GAP] 0 votes: empty list + state code
        ├── vote w/o vote_documents  [GAP]                ├── [GAP] build refuses CONTRACT_VERSION mismatch
        ├── sitting-level vote       [GAP]                ├── [GAP] build refuses unknown code / missing field
        ├── not_fetched vs untagged  [GAP]                └── [GAP] no asset from another host
        └── Ja-Mehrheit boolean, inverted vote [GAP]    [+] CI
[+] site/ (new)                                           └── [GAP] raw-HTML API ban (R14)
  └── code → copy table           [GAP] unknown code

COVERAGE: 0/21 proposed paths tested (all are future code) | GAPS: 21 (5 E2E, 0 eval)
LLM integration: none touched (AI summaries are slice 5 / D8, outside the pilot).
```

Test framework: Python `unittest` (AGENTS.md:5); browser checks through the zero-dependency `tests/run_bills_browser_check.mjs` on Node 24 (ci.yml:30-38).

### R13: how the new frontend and the payloads are tested
Finding: T2, P1, confidence 8/10, tests/run_bills_browser_check.mjs (zero-dependency runner), tests/votes_archive_browser_check.js, plan T1.6 (archive suites to port); reviewer: Claude (Test review)
Plan baseline: proposal item 6, "contract tests plus a thinner frontend layer", unspecified.
Runtime evidence: 357 test functions in the three render test files, many asserting HTML (238 HTML-ish `assertIn` lines) [measured by grep]; the archive's filters are checked today by a browser script injected through the Node runner [static read].
Comparison grid:

| Choice | Current | A | B | C |
| --- | --- | --- | --- | --- |
| R13 Python side | HTML assertions on the archive (T1.6 list) | payload tests on store-seeded fixtures: T1.6's assertions ported to payload fields, plus the empty-archive, `result_badge_state` and Ja-Mehrheit cases | same as A | same as A |
| R13 frontend side | none | build from a committed fixture payload; a `node:test` script (built in, no dependency) asserts the R15 behaviours on the built HTML (every row and figure present JS-off, count line, empty state, no foreign-host asset, build refuses bad version / unknown code); `tests/votes_archive_browser_check.js` re-pointed at the new page for filter clicks | a JS test framework (component tests plus a browser driver) added under an R12 allowlist exception | build success only |
| Old archive tests | kept | kept until cutover, deleted with the Python archive | same | same |
| D1–D8, R10–R12, R14, R15 | approved | unchanged | unchanged | unchanged |

Question D9:
D9 — How do we test the new frontend without breaking the dependency allowlist?
Project/branch/task: main at 511ae75, A4 re-scope; pilot votes archive, archive contract (R15) and strict toolchain (R12) approved.
ELI10: Python tests will check that each payload carries the right data. Something also has to check that the built page actually prints it and that filters work: that is the gap the payload diff leaves (R11). We can do that with Node's built-in test runner plus the browser runner the repo already has, or add a JavaScript test framework, which the strict toolchain policy only allows as a named exception.
Stakes if we pick wrong: the page drops data or a filter breaks and nothing fails, or the test stack doubles the dependency tree the policy just capped.
Recommendation: A because it covers every R15 behaviour with tools already in the repo and adds zero packages.
Completeness: A=9/10, B=9/10, C=4/10
Pros / cons:
A) Built-in Node tests plus the existing browser runner (recommended)
  ✅ Every R15 behaviour gets a test, and the dependency allowlist stays at generator plus one chart library
  ✅ Reuses `tests/run_bills_browser_check.mjs`, which CI already runs on Node 24
  ❌ Assertions on built HTML are coarser than component tests and need small hand-written helpers
B) Add a JS test framework
  ✅ Component-level tests with a mature runner and browser driver, convenient as pages multiply
  ❌ Needs an R12 exception and adds the largest dependency trees in the npm ecosystem
C) Build success only
  ✅ No frontend test code at all; payload tests carry the whole load
  ❌ A page that drops rows or breaks a filter still builds, and R11 cannot see it
Net: A and B cover the same behaviours; A does it with zero new packages.
Header: Frontend tests
Options:
A) Node built-ins + runner (recommended)
Python payload tests on store-seeded fixtures (T1.6 assertions ported, plus empty archive, `result_badge_state`, Ja-Mehrheit). Frontend: build from a committed fixture payload; a `node:test` script asserts R15 on the built HTML (rows and figures JS-off, count line, empty state, no foreign-host asset, refusal on bad version or unknown code); `tests/votes_archive_browser_check.js` re-pointed at the new page. Old archive tests stay until cutover. Effort human ~2 days / CC ~1 h.
B) Add JS test framework
Same Python side; frontend component tests and a browser driver from a JS test framework, recorded as an R12 allowlist exception. Old archive tests stay until cutover. Effort human ~2 days / CC ~1 h plus setup.
C) Build success only
Same Python side; the frontend is checked only by a successful build. Old archive tests stay until cutover. Effort human ~1 day / CC ~30 min.

State: approved
Actual answer: A "Node built-ins + runner (recommended)", auto-decided by the owner's AskUserQuestion adjudicator hook, 2026-11-02 (D9)
Accepted scope: Python payload tests on store-seeded fixtures (T1.6 assertions ported, plus empty archive, `result_badge_state`, Ja-Mehrheit); frontend built from a committed fixture payload; a `node:test` script asserts R15 on the built HTML (rows and figures JS-off, count line, empty state, no foreign-host asset, refusal on bad version or unknown code); `tests/votes_archive_browser_check.js` re-pointed at the new page; old archive tests stay until cutover. Effort human ~2 days / CC ~1 h.
History: none

Test Plan Artifact: `~/.gstack/projects/LucaAlv-poliwatch/Luca-main-eng-review-test-plan-20261102-004653.md`.

Tests made obsolete by this plan (proposal only): the archive's HTML-asserting suites listed in T1.6 retire at cutover with the Python archive, not before.

**Section 3 findings**
- [P1] (confidence: 9/10) tests/votes_archive_browser_check.js — T1: the archive's user-facing behaviour had no contract once R4 went. Accepted: R15 (D8).
- [P1] (confidence: 8/10) tests/run_bills_browser_check.mjs — T2: no test strategy for the frontend or payloads. Accepted: R13 (D9).
- 21 proposed paths, 21 gaps, 5 E2E (diagram above), all covered by R13's accepted scope.

Dispositions: T1 accepted (R15, D8); T2 accepted (R13, D9).

## Section 4: Performance review (re-scope)

- [P2] (confidence: 8/10) protocols/plenarprotokoll-20-47.html (built site) — P1: dossiers reach 2,603,877 bytes, about 1.1 MB of it text [measured]. The search check found that islands serialise their props into the HTML. If a later dossier island receives speech text or row lists as props, every such page roughly doubles. The pilot archive has 556 votes [measured on the A3 store], small, but it sets the pattern. → R16 below.
- [P3] (confidence: 9/10) the same page carries 41,232 bytes of inline `<style>` [measured]; repeated on each of about 5,000 pages that is roughly 200 MB of duplicated CSS [estimated]. The new frontend serves one cached stylesheet, so this goes away at cutover. No task.
- [P3] (confidence: 5/10) build time: about 5,500–6,000 pages at full coverage [estimated]; one blog puts a 5,000-page build of the leading candidate at 4–7 minutes [unverified]. Today's repersist + render + export already takes about 27 minutes (slice 0 result), so minutes more are tolerable. Measured when the first multi-thousand-page type migrates; recorded in the slice map, no task now.
- Emitter reads keep T1.3's rule: set-based, one query per table grouped by `vote_id`, never per vote (382,441 `vote_members` rows [measured on the A3 store]).

### R16: how much data an interactive island may carry
Finding: P1, P2, confidence 8/10, built `protocols/plenarprotokoll-20-47.html` 2,603,877 bytes; search check (secondary sources) "props are serialised into the HTML"; reviewer: Claude (Performance)
Plan baseline: proposal item 1, "ships JS only for interactive parts"; nothing on what data those parts receive.
Runtime evidence: today's interactive scripts read `data-*` attributes on server-rendered rows (archive B:5830, radar B:6564, MPs B:9022) and carry no data copies [census, static read].
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R16 island data | scripts read `data-*` on server-rendered rows | lists and long text render as static HTML; islands get only small props (ids, filter options, a chart's series) and read row data from `data-*`; the `node:test` script fails if a built page's inline island payload exceeds 50 KB | each page decides what its islands receive |
| D1–D9, R10–R15 | approved | unchanged | unchanged |

Question D10:
D10 — How much data may an interactive part of a page carry?
Project/branch/task: main at 511ae75, A4 re-scope; pilot votes archive; tests via node:test and the browser runner approved.
ELI10: In the new frontend, an interactive part (a filter, a chart) gets its data embedded into the page as JSON. If we hand it the whole list of votes or a dossier's speeches, the page carries that data twice: once as HTML, once as JSON. Dossiers are already up to 2.6 MB. Today's filters avoid this by reading small attributes on rows that are already on the page.
Stakes if we pick wrong: pages double in size on phones, or a rule so strict a chart cannot get its series.
Recommendation: A because it keeps today's proven pattern and makes a size regression fail a test instead of a phone.
Completeness: A=9/10, B=5/10
Pros / cons:
A) Static rows, small props, 50 KB budget (recommended)
  ✅ Keeps today's pattern: filters read `data-*` on rows that are already in the HTML, so no data is shipped twice
  ✅ A size check in the existing node:test script catches a page whose island payload grows past 50 KB
  ❌ A future chart with a large series must aggregate in Python first or justify raising the budget
B) Each page decides
  ✅ No rule to follow; whichever approach is fastest to build for a page is allowed
  ❌ The first dossier island that gets speech text as props doubles a 2.6 MB page and no test notices
Net: A keeps pages lean by default at the cost of an explicit budget.
Header: Island data
Options:
A) Small props + budget (recommended)
Lists and long text render as static HTML; islands receive only small props (ids, filter options, a chart's series) and read row data from `data-*` attributes; the R13 `node:test` script fails when a built page's inline island payload exceeds 50 KB. Effort human ~2 h / CC ~10 min.
B) Page decides
No rule; each page chooses what its islands receive. No effort.

State: approved
Actual answer: A "Small props + budget (recommended)", auto-decided by the owner's AskUserQuestion adjudicator hook, 2026-11-02 (D10)
Accepted scope: lists and long text render as static HTML; islands receive only small props (ids, filter options, a chart's series) and read row data from `data-*` attributes; the R13 `node:test` script fails when a built page's inline island payload exceeds 50 KB. Effort human ~2 h / CC ~10 min.
History: none

**Section 4 findings**: P1 accepted (R16, D10); P2 no task (goes away at cutover); P3 measured at the first multi-thousand-page migration (no task now).

## Outside voice (re-scope)

Codex is installed but failed inside the session sandbox (`failed to initialize in-process app-server client: Operation not permitted`; network to its auth host denied), the known limit from project memory. A native Claude Plan subagent ran as the fallback and returned a complete report within the five-minute timer. That is missing cross-model coverage, not a clean outside review.

| # | Severity | Finding (condensed) | Reviewer's evidence | Disposition |
| --- | --- | --- | --- | --- |
| O1 | Critical | The votes-archive pilot tests neither goal: no chart, and the look is out of scope; it proves only plumbing | proposal motivation; archive filters already work (B:5800-5900) | **pending owner** (reopens D1) |
| O2 | Critical | No person chose to reverse PRODUCT.md:58; D1–D10 were picked by the adjudicator hook, and the adoption of the re-scope itself was never asked | PRODUCT.md:58; ledger answers | **pending owner** |
| O3 | High | A simpler alternative was never compared: one shared stylesheet now (~1 h), a plain-CSS design system, Python-rendered SVG charts with a little hover JS; keeps stdlib, the 357 tests and the HTML oracle | built page: 41,232 bytes inline CSS | **pending owner** |
| O4 | High | R12/R14/R16 assume one generator's model while "which generator" is undecided; pick it and read its installed docs before the ADR | context7 unauthorized, P9 unverified | pending (depends on O2/O3) |
| O5 | High | Porting pages before a design system means redoing them; the pilot must be the design system's first consumer or wait | R15 "layout and wording are free" | pending (depends on O2/O3) |
| O6 | High | Parallel build has no end date and no go/no-go gate after the pilot; dossiers migrate last and are hardest | D2; `render_html` holds ~40 copy-by-state sites | pending (depends on O2/O3) |
| O7 | Medium | New-archive links to `../protocols/…` and the global nav point at pages absent from the frontend's own output during the parallel build | B:5662; D2 | pending |
| O8 | Medium | Copy lives twice; the payload diff compares data, not the code-to-text mapping, so a wrong reason sentence passes | votes.py:40-43 | pending |
| O9 | Medium | The pilot reads the store, not a release; state "the store until slice 10" | slice map row 10 | factual correction: the contract's input is the store until slice 10's `--from-release` |
| O10 | Low | Operator workflow: `preview_dip_pulse_site.sh` needs Node 24 and `npm ci`; no path stated | PRODUCT.md operator role | pending |
| O11 | Low | The 50 KB island budget will block the first long-term chart unless Python aggregates (monthly) first | R16 | pending |

Reviewer's recommendation: hold the re-scope and its ADR until the owner decides explicitly; compare the rewrite against "shared stylesheet + CSS design system + Python-rendered SVG charts"; only if the rewrite wins, choose the generator, pilot a page with a chart that uses the design system, and add a pilot go/no-go gate.

**Cross-model tension.** Parent and outside voice agree on the facts (pilot has no chart, the look is a design problem, the hook decided). They differ on weight: the parent review treated adoption of the re-scope as given by the owner's request for a review; the outside voice holds that a binding product rule needs the owner's own answer. The outside voice is right on that point: the adoption question was never put to the owner. O1 and O3 are new evidence that reopen D1. The review paused and put the adoption question to the owner in chat (not through AskUserQuestion, which the hook answers).

### R17: adopt the frontend re-scope now, or hold it
Finding: O2 + O1 + O3 (outside voice), Critical, PRODUCT.md:58
Plan baseline: the re-scope proposal; adoption never asked.
Comparison grid:

| Choice | Current | A (chosen) | B |
| --- | --- | --- | --- |
| R17 adoption | unasked | hold: design pass first (plain CSS, usable by either stack), then one chart prototype in a candidate generator, then a go/no-go with written criteria | adopt as reviewed, folding in O4–O11 |
| PRODUCT.md:58 stdlib rule | in force | stays in force until the go/no-go; no ADR 0005 yet | reversed by ADR 0005 now |
| D1–D10 (R10–R16, scope record) | auto-decided | kept as the plan to apply if the go/no-go picks the frontend; O4–O11 get resolved then | applied now |
| A4 slice 1 | planned | T1.1–T1.3 (measure, schema-9 columns, store adapter) proceed, useful in either stack; T1.4 rewire waits for the go/no-go | T1.4 becomes the payload emitter |

State: approved
Actual answer: A "Hold, prototype first", typed by the owner in chat, 2026-11-02
Accepted scope: hold the re-scope. Order: (1) design pass producing a plain-CSS design system usable by either stack; (2) one chart prototype in a candidate generator (the Diskursanalyse throwaway prototype in TODOS.md:1038 is the natural vehicle); (3) go/no-go with written criteria comparing the generator against "shared stylesheet + CSS design system + Python-rendered SVG charts". PRODUCT.md:58 stays in force until then. D1–D10 remain the frontend plan if the go/no-go picks it; O4–O11 are resolved at that point. A4 slice 1 T1.1–T1.3 proceed; T1.4 waits.
History: none

**Outside-voice dispositions after R17:** O1, O2, O3 resolved by R17 (hold, owner's answer). O4, O5, O6, O7, O8, O10, O11 deferred to the go/no-go (recorded in the TODOS entry). O9 factual correction recorded.

## TODOS.md proposals (re-scope)

### R18: TODO — frontend go/no-go after a design pass and a chart prototype
Finding: R17 accepted scope; TODOS.md "DESIGN.md, tokens and a typeface decision via /design-consultation" (## Design, P3) already covers step 1
Plan baseline: R17 order (design pass, chart prototype, go/no-go) exists only in this plan.
Comparison grid:

| Choice | Current | A | B | C |
| --- | --- | --- | --- | --- |
| R18 | not in TODOS.md | add "Decide the frontend stack: chart prototype and go/no-go" under ## Design (P2, L), depending on the DESIGN.md item, which rises from P3 to P2; criteria and O4–O11 listed in it | skip; R17 lives only in this plan | build the prototype in this review |

Question D11:
D11 — Add the frontend go/no-go to TODOS.md?
Project/branch/task: main at 511ae75; the owner held the frontend re-scope (R17) pending a design pass, a chart prototype and a go/no-go.
ELI10: The hold decision has three steps. The design pass is already a TODO (P3). The chart prototype and the go/no-go are written only in this plan file, where a future session working from TODOS.md would not find them. One entry that names the steps, the comparison and the open review findings keeps the decision from getting lost.
Stakes if we pick wrong: the stack question resurfaces later with the evidence and review findings forgotten.
Recommendation: A because TODOS.md is where the project tracks follow-ups, and the DESIGN.md item is now on the critical path.
Completeness: A=9/10, B=4/10, C=8/10
Pros / cons:
A) Add to TODOS.md (recommended)
  ✅ The prototype, the comparison against the stdlib option and O4–O11 stay findable for any session
  ✅ Raising the DESIGN.md item to P2 puts step 1 of the hold where it belongs in the queue
  ❌ One more L-sized open item in an already long TODOS.md
B) Skip
  ✅ No TODOS.md churn; the plan file records the hold
  ❌ Sessions that read TODOS.md first never see it
C) Build it now
  ✅ Starts the prototype right away
  ❌ The design pass is step 1 and has not happened; building the chart prototype first skips it
Net: A records the hold where the project looks for work.
Header: Go/no-go TODO
Options:
A) Add to TODOS.md (recommended)
Add "Decide the frontend stack: chart prototype and go/no-go" under ## Design (P2, effort L, depends on the DESIGN.md item); raise "DESIGN.md, tokens and a typeface decision" from P3 to P2. The entry lists the steps, the written go/no-go criteria to set, the stdlib alternative to compare, and O4–O11.
B) Skip
Leave R17 in this plan file only.
C) Build it now
Start the chart prototype in this session instead of deferring.

State: approved
Actual answer: A "Add to TODOS.md (recommended)", auto-decided by the owner's AskUserQuestion adjudicator hook, 2026-11-02 (D11)
Accepted scope: added "Decide the frontend stack: chart prototype and go/no-go" under TODOS.md ## Design (P2, effort L, depends on the DESIGN.md item); raised "DESIGN.md, tokens and a typeface decision" from P3 to P2 with the shared-stylesheet step noted. Done in this review.
History: none

Other TODO candidates considered and folded in rather than proposed separately: the shared stylesheet (41 KB inline CSS per page) went into the DESIGN.md item as part of step 1; the Ja-Mehrheit rule duplicated in JS (B:5866) is resolved by R10 if the frontend goes ahead, and otherwise stays a latent drift with no current wrong output (both copies agree today), below the bar for its own entry.

## Approval readiness (re-scope)

Checked: scope record (D1 A, D2 A, D3 B), R10 (D4), R11 (D5), R12 (D6), R14 (D7), R15 (D8), R13 (D9), R16 (D10), R17 (owner, chat), R18 (D11). Every accepted remedy cites its own answer. R10–R16 and the scope record are conditional on the R17 go/no-go; R17 and R18 are in effect now.

Approval readiness: PASS (scope record, R10–R18; answers D1–D11 by the adjudicator hook, R17 by the owner in chat)

## NOT in scope (re-scope review)

- Building any frontend code: held by R17 until the go/no-go.
- ADR 0005 and the PRODUCT.md/AGENTS.md/CONTRIBUTING.md stack edits: written only if the go/no-go picks the generator.
- Choosing the generator: part of the prototype step; no version or API claim in this review is verified.
- The visual design itself: TODOS.md "DESIGN.md, tokens and a typeface decision" (now P2).
- Migration order for pages after the pilot, the public host, Diskursanalyse term lists.
- Plan-level owner decisions D8–D10 (AI summaries, third-party data, raw dumps): unchanged, still due at their slices.

## What already exists (re-scope review)

- Pure collectors and rules that a page-data layer would reuse: `collect_votes_archive` B:5628, `collect_bill_pages` B:7381, `collect_abgeordnete` B:8672, `build_catalog_rows` B:10857, `item_stats`/`week_stats`/`week_topic_rows` in R, the vote rules in `derive.py`.
- Existing data outputs: `feeds/week-radar.json` (`week_radar_feed._week_payload` :130), `data/bills.json`, `data/abgeordnete.json`, `data/features.json`, the export SQLite/CSVs, the build-time SQL recipes.
- Node 24 in CI and the zero-dependency browser runner `tests/run_bills_browser_check.mjs` with six injected checks.
- The store-seeded test fixture `tests/_site_store_fixture.py` (slice 0).
- C1 (`result_badge_state` split) is reuse of an existing function with two verified callers, not a new helper.

## Diagrams (re-scope review)

```
now (R17 hold)                                     after the go/no-go
DESIGN.md + plain-CSS tokens + one stylesheet ─┐   go:    ADR 0005 → resolve O4–O11 → pilot (R10–R16, scope record)
   (TODOS ## Design, P2)                       │          store ─ site_data.py ─ payload JSON ─ generator ─ dist/
chart prototype in a candidate generator ──────┼─→ no-go: stdlib path: shared stylesheet + CSS design system
   (Diskursanalyse throwaway, uses the CSS)    │          + Python-rendered SVG charts; A4 slices 1–11 as planned
written go/no-go criteria (set first) ─────────┘
A4 slice 1 T1.1–T1.3 (store work) ── runs in parallel, useful on both branches
```

## Failure modes (re-scope review)

| Path | Realistic failure | Covered by | User sees |
| --- | --- | --- | --- |
| Hold (now) | the stack question resurfaces without the review's evidence | TODOS.md entry + R17 in this plan | n/a |
| Frontend (if go) | payload dir from an older emitter run | `CONTRACT_VERSION` refusal + staging swap (mapping table) | build error naming both versions |
| Frontend (if go) | archive links to dossiers absent from the frontend output | O7, deferred to the go/no-go entry | dead link in preview only, never published (parallel build) |
| Frontend (if go) | wrong code-to-text mapping passes the payload diff | O8, deferred to the go/no-go entry | wrong reason sentence, caught by the text check O8 asks for |
| Frontend (if go) | island payload balloons | R16 50 KB check in node:test | test failure |

Critical gaps (no test, no handling, silent): 0. O7 and O8 have no handling yet, but no code exists and both are written into the go/no-go entry as preconditions.

## Worktree parallelization strategy (re-scope review)

| Step | Modules touched | Depends on |
| --- | --- | --- |
| Design pass (DESIGN.md, CSS tokens, shared stylesheet) | `scripts/` render CSS, `docs/` | — |
| A4 slice 1 T1.1–T1.3 | `scripts/persist_dip_pulse_store.py`, `scripts/features/votes.py`, `tests/`, DATA.md | — |
| Chart prototype + go/no-go | throwaway dir outside the site build | design pass; Diskursanalyse term lists |

**Parallel lanes:** Lane A: design pass. Lane B: slice 1 T1.1–T1.3. Then the prototype after lane A.
**Execution order:** launch A + B; the prototype starts when A lands.
**Conflict flags:** both lanes may touch `scripts/build_dip_pulse_site.py` (CSS strings in A, export columns in B); sequence the merges.

## Implementation Tasks (re-scope review)

Synthesized from this review's findings. Ratios assumed: design/architecture ~5x, research ~3x.

- [ ] **T1 (P2, human: ~2 days / CC: ~1 h)** — design — Run `/gstack-design-consultation`: DESIGN.md, plain-CSS tokens and type, one shared stylesheet replacing the per-page inline `<style>`
  - Surfaced by: Outside voice — O3, O5; R17
  - Files: `scripts/render_dip_pulse_html.py`, `scripts/build_dip_pulse_site.py` (CSS strings), new `DESIGN.md`
  - Verify: full suite; browser check at 375 px and dark mode; inline `<style>` per dossier drops from 41,232 bytes
- [ ] **T2 (P2, human: ~3 days / CC: ~2 h)** — decision — Write the go/no-go criteria first, then build one chart prototype in a candidate generator using T1's CSS, and read that generator's installed docs
  - Surfaced by: Outside voice — O1, O4; R17
  - Files: throwaway prototype dir; criteria in TODOS.md "Decide the frontend stack" or a new plan
  - Verify: criteria answered in writing; owner decides go or no-go in chat
- [ ] **T3 (P2, human: ~1 day / CC: ~30 min, only if go)** — docs — ADR 0005 and the stack edits in PRODUCT.md, AGENTS.md, CONTRIBUTING.md; resolve O4–O11 before the pilot
  - Surfaced by: Scope Challenge — S3; Outside voice — O2, O4–O11
  - Files: `docs/adr/0005-*.md`, `PRODUCT.md`, `AGENTS.md`, `CONTRIBUTING.md`, this plan
  - Verify: review checklist class 11 on every changed sentence

_No new tasks from Sections 1–4 beyond the conditional frontend plan (R10–R16), which waits for T2._

## Unresolved decisions that may bite you later (re-scope review)

None in this review. The frontend plan (R10–R16) is decided but conditional on the go/no-go; O4–O11 are deferred into that decision by R17. Plan-level owner decisions D8–D10 are carried from the 2026-11-01 review.

## Completion summary (re-scope review)

- Step 0: Scope Challenge — scope reduced per recommendation (coexistence cut, pilot replaced; then the owner held the whole re-scope, R17)
- Reality rows: 7/7 applicable rows emitted (`PLAN_REALITY: phase=eng rows=7/7 missing=none verdict=complete`), 1 unverified premise (P9 build time)
- Architecture Review: 3 issues found (A1, A3, A4)
- Code Quality Review: 2 issues found (C1, C2)
- Test Review: diagram produced, 21 gaps identified (all proposed paths)
- Performance Review: 3 issues found (P1, P2, P3)
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 1 item proposed to user (added; DESIGN.md item raised to P2)
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 0 in this review
- Outside voice: codex unavailable (app-server init blocked by the sandbox); native Claude Plan subagent completed within the timer, 11 findings (3 resolved by R17, 7 deferred to the go/no-go, 1 factual)
- Parallelization: 2 lanes, 2 parallel / 1 sequential
- Lake Score: 0/8 (D4–D11 each chose a 9/10 option; D1–D3 differed in kind)
- Answer provenance: D1–D11 auto-decided by the owner's AskUserQuestion adjudicator hook; R17 (adoption) typed by the owner in chat

## Suppressed findings (appendix, re-scope review)

None.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Review | native Claude Plan subagent (codex unavailable) via `/plan-eng-review` | Independent 2nd opinion | 1 | unavailable (native fallback completed; not persisted to review log) | 10 findings: 4 accepted (R5–R8), 1 TODO (R9), 3 factual, 2 rejected |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN (not persisted to review log) | 22 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:** codex, plan-review phase: unavailable (sandbox blocks `~/.codex` writes); native Claude Plan subagent fallback completed in 74 s with 10 findings. No cross-model coverage.
- **VERDICT:** no review CLEAR; every finding is mapped to an approved remedy or a recorded disposition, so ISSUES OPEN means mapped work, not open questions. Eng review required; ready to implement slice 0 and the member-row fix.

**UNRESOLVED DECISIONS:**
- D8: AI summaries and receipts in the release (owner, before slice 5)
- D9: no new third-party data in the release (owner, before slice 5)
- D10: drop the two public raw dumps (owner, before slices 7–8)
