# A4: Split the dataset from the site, so the site builds from a release alone

## Context

This is roadmap item A4: TODOS.md "Split the dataset from the site: the site builds from a release alone" (effort L, P2). A1–A3 are done (v0.27.0.0, 4705fb3). The TODO's done criterion is: an offline build from a downloaded release SQLite, with no report JSON present, produces the same site as today's build. The dev-view API dumps are exempt.

**Status (2026-11-01):** passed /plan-eng-review (see the review part at the end of this file). Ledger entries R1–R9 are settled; do not reopen them without new evidence. Owner decisions D8–D10 stay open until their slices. Slices 0 and 1 are planned down to individual tasks and land as two PRs; later slices are headlines only, because slice 1 will change what they need.

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
| 0 | Harness, PR 1, behaviour-neutral for pages: `--no-persist` removed (R1), temporary-store fixture for tests and demo, coverage refusal (R2), missing-store refusal (F7) | none | none |
| 1 | Votes archive (`votes/index.html`), PR 2 | 0, and TODOS "Store loses roll-call member rows in 22 groups of 11 votes" (open, P2) as its own PR before the oracle run | Politikfeld state, `agenda_item_documents.url`, `vote_documents.rank`, `vote_fractions.rank`, missing vote totals as NULL (T1.2) |
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

## Slice 1: votes archive from the store (PR 2)

Needs PR 1 and the lost member-row fix (its own PR, before the oracle run). `votes/index.html` reads no members except for the Abweichler count, no acquisition state, no committee and no lead.

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
