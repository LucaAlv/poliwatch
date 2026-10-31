# D: Release codebook and recipe result CSVs

Status: implemented and locally verified, 2026-10-29; see Implementation result below. R1/D1-A and R2/D2-A are implemented. The original review record is retained; outside coverage was unavailable because the authorized Claude attempt exhausted usage credits.
Target: TODOS.md, “Codebook (`DATA.md`) and recipe result CSVs in the release” (lines 136–147).
Baseline: branch `codebook`, HEAD `d766825`, export format 8. Product code is unchanged by this planning session.

## Outcome and boundary

A researcher can keep one exported generation, read its German `DATA.md` without the website, understand every exported table/column and counting rule, and reproduce each of the six published recipe result CSVs against that generation's SQLite file. Definitions, results and checksums describe the same snapshot.

This is one implementation PR. Extend the existing exporter, rather than building another release pipeline. The separate immutable-release script must later upload every manifest-listed artifact and `datenstand.json`, preserving the generation-relative links. This work prepares the assets; it does not upload or publish a release.

## What already exists

- `scripts/build_dip_pulse_site.py:2451` `iter_tables()` discovers the distribution schema, types, keys, foreign keys and row counts.
- `:2498–2558` provenance tags and `column_source()` distinguish DIP, bundestag.de, abgeordnetenwatch and derived data, but not all upstream/derived field semantics or API versus XML.
- `:2592–2759` six `RECIPES` define SQL, ordered output columns, hidden link IDs and caveats. Preserve the current SQL, limits and result order.
- `:3019` `export_distribution_data()` owns locking, caching and generation publication; `:3149` `_run_export()` owns snapshot creation and serialization.
- `:3334–3359` queries already execute once against the distribution snapshot; `datenstand.json` already carries their rows and SQL.
- `:3502` downloads and `:3575` recipe rendering use the manifest, with local/remote base-URL support. `:11219` validates operator-supplied manifests.
- `tests/test_daten_export.py` and `tests/_daten_fixture.py` cover exports, recipe semantics, NULLs, text fidelity, cache reuse, failure preservation and locks.
- `CONTEXT.md`, ADR 0001/0002, `docs/stable-ids.md` and ADR 0003 own the domain, identity and licence decisions. `docs/data-license.md` contains the existing layered notice. The aw-column source fix is already complete; do not reimplement it.

## Proposed artifact and manifest contract

Keep all new bytes inside the existing generation directory:

```text
data/exports/
  datenstand.json                 published last
  g-<inputs-hash>/
    bundestag-pulse-<tag>.sqlite.gz
    <table>-<tag>.csv.gz          existing table extracts
    DATA.md                      this snapshot's generated codebook
    recipe-<recipe-id>-<tag>.csv   one result per existing recipe
```

Propose plain UTF-8 recipe CSVs because results are small and directly usable. Include all selected columns in SQL result order, including IDs hidden only for HTML presentation. Per D2/A, derive both the new-format manifest `recipes[].columns` and CSV headers from the SQL cursor, even for zero rows; select each cell by header name. This intentionally reorders r5's new-format machine metadata to `proceeding_id, title, typ, reden, sitzungen, erste_drucksache`; retain the existing HTML display order and legacy-manifest behavior. Keep SQL LIMITs; these are the published recipe results, not unrestricted analytical exports. Zero rows still produce a header, with the existing empty reason in manifest/codebook. SQLite remains authoritative for NULL versus empty-string distinction. Preserve text verbatim using the existing CSV conventions; document spreadsheet import as text rather than altering cells.

Add typed entries to the existing `files` inventory (`sqlite`, `table_csv`, `recipe_csv`, `codebook`), keeping SQLite first. Each new file has basename, bytes and SHA-256; CSVs also have row count. Each recipe references its corresponding file by name. Render table downloads by kind, a codebook link in the download panel, and a CSV link beside each recipe. Avoid a second untracked artifact inventory. Per D1/A, preserve existing pre-change manifest behavior, but require the complete typed inventory in the new format: exactly one codebook and a correctly typed CSV reference for each recipe, alongside the existing SQLite/table files. A new-format manifest missing those entries fails with a named error; missing metadata must not classify it as legacy. Validate new fields and references at the existing manifest boundary, including plain basenames, supported kinds and duplicate/dangling references. This verifies manifest structure, not the availability of remote asset bytes.

Bump export format from 8 to 9 if still current at implementation time; do not change the build-store schema or identity version. No new CLI option or dependency.

## Proposed codebook inputs and content

Use two authored inputs, composed by a small renderer in the current export module:

- `scripts/data_dictionary.json` (new): one explicit table entry and one entry per exported column, containing German meaning, unit/representation, source detail and applicable existing licence layer. Sources distinguish DIP API, protocol XML, bundestag.de, abgeordnetenwatch, generated bookkeeping and derived/mixed values. Units distinguish IDs, counts, characters, dates/timezones, booleans, ratios/percentages and structured JSON. Mixed/fallback sources must be described honestly, not collapsed into a false single-origin assertion.
- `docs/data-methods.md` (new): a release-oriented German snapshot of counting rules, transformations, known limitations and citation instructions. Quote the relevant definitions from CONTEXT.md/ADRs with their repository paths, rather than silently redefining Rede, Beitrag, written submission, Sitzung mit Dossier, Sprechrolle or completeness. Record the source revision in generated output. No runtime fetch of today's documentation.

At export time, validate that every actual distribution table/column has authored metadata; fail with a named missing entry rather than filling gaps with generic text. Inspect persistence/derivation writers while authoring meanings. Include distribution-only `mp_canonical` and `datenstand`, registry/history tables and facts. Do not document removed `speeches.paragraphs_json` as exported. Reuse schema facts from `iter_tables()` instead of duplicating types and relationships in JSON. If finer source descriptions expose a wrong existing manifest source tag, surface that discrepancy during review rather than silently changing licence claims.

Generated `DATA.md` includes:

1. Release tag (or explicitly local), build revision, export/store/key versions, generation identity, data dates and file guide. An unknown revision stays unknown.
2. Every table/column with meaning, unit, SQLite type, nullable/key/FK information, source detail and licence layer; row counts and stable-key/alias usage.
3. Counting rules and transformations, including Reden versus other Beiträge, Sprechrolle attribution, identity consolidation, characters versus time, Abweichler rules, and the scope and denominators of every recipe.
4. Coverage per Wahlperiode: observed stored sittings/dates and relevant recorded counts, all derived from this distribution snapshot. Separate stored coverage from catalog/dossier build counts and acquisition/period completeness. Do not claim WP18–present is already acquired, or infer completeness from absence of votes. Missing per-WP expected counts or acquisition evidence are explicitly unknown. Empty stores get an explicit empty-coverage section.
5. Known gaps grounded in the existing source/ADRs/TODOs: missing acquisition state in the download, partial historical coverage, ceremony acquisition limitations, roll-call reconciliation and redistribution questions where still open. Distinguish dataset-wide known issues from findings proven in this snapshot.
6. Exact recipe SQL, ordered output definitions, caveats, limits and empty reasons; CSV filenames and checksums. Explain hidden IDs and NULL representation.
7. Existing layered attribution/terms and transformation notices from `docs/data-license.md`/ADR 0003. State unresolved roll-call redistribution status; generation does not grant publication permission or invent a new licence.
8. Citation instructions using this release's actual tag/revision and immutable download reference when available. Local exports say they are local and lack a version DOI. DOI minting, a product-name decision and `CITATION.cff` stay with their own TODO. Do not invent them.

The codebook does not contain its own checksum, which would be circular. The manifest inventories its checksum. Keep the useful on-page explanations in this PR; moving/deleting prose is a separate editorial decision and is unnecessary for release-local documentation.

## Execution flow and failure behavior

```text
finalized build store + authored dictionary/methods/licence + existing recipes
  -> export lock + existing source fingerprint
  -> inputs hash includes content hashes of every codebook input
       unchanged + all listed assets present/sized -> reuse whole generation
       otherwise -> private staged distribution snapshot
         -> schema introspection + complete metadata validation
         -> existing table CSVs and SQLite gzip
         -> execute recipes once -> manifest rows + result CSVs
         -> snapshot coverage + generated DATA.md
         -> manifest with all file hashes
         -> rename complete generation -> replace datenstand.json last
  -> manifest-driven Daten page or future release uploader
```

Read authored inputs once per export attempt and use the same bytes for hashing and rendering. Cache invalidation must cover dictionary, methods, licence notice, recipe output metadata/caveats and any other text that changes DATA.md, even with unchanged SQLite and SQL. Renderer changes follow the export-format bump convention. Missing/truncated new assets invalidate reuse through `files` as today. Keep existing failure/lock/cleanup behavior: dictionary/CSV/codebook failures before publication leave the previously published generation and manifest intact, with a useful error. No fetch is needed and the build store stays read-only.

## Implementation sequence and affected surface

Estimated seven implementation files; no new classes/services. The plan document itself is a planning artifact, outside that estimate.

1. Author `scripts/data_dictionary.json` and `docs/data-methods.md` against the actual distribution schema and existing writers. Resolve any ambiguous source/unit claim before treating it as fact.
2. Extend `scripts/build_dip_pulse_site.py`: metadata loading/validation, content fingerprint, recipe CSV serialization from already computed rows, snapshot coverage, codebook generation, typed manifest inventory, format bump, validation and download links. Update nearby export layout diagram.
3. Extend `tests/test_daten_export.py` and the existing dedicated `tests/test_daten_page.py` at public export/validation/render boundaries. This corrects the original test-location estimate; `tests/test_build_dip_pulse_site.py` and `tests/test_data_pipeline_cli.py` remain validation inputs, without a planned edit. Reuse the fixture; add fixture data inline only where an independent contract requires it.
4. Update `docs/project-documentation.md` with assets, manifest fields and consumer/upload obligations. Update the existing `TODOS.md` entry only when implementation is verified; keep upload/legal/DOI/changelog/hosting TODOs open. No CI configuration changes expected: existing unittest discovery runs the new cases.

Sequential implementation, no parallelization opportunity: the new inputs and export/manifest/rendering contract are one coupled workstream. Content authoring can be delegated narrowly after the format is settled; merge and verify through the same exporter.

## Planned validation and acceptance

Use standard-library unittest per AGENTS.md. During implementation run focused modules, then `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests` from the repository root. This planning draft has not run that suite.

- Export fixture -> decompress the emitted distribution SQLite -> independently execute every declared recipe SQL -> compare ordered header/rows with its CSV and manifest. Per D2/A, compare all six SQL cursor headers to CSV and new-manifest columns, including an explicit r5 `7, 2, 20/100` field-order assertion and zero-row headers. Preserve SQL text, LIMITs, result row order and named values; HTML display and legacy rendering stay unchanged. Includes hidden stable IDs and text/NULL formatting; protects current recipe results rather than adding new queries.
- Extend empty-recipe coverage: header-only file, zero rows, manifest/codebook empty reason and valid checksum. Include quotes, commas, line breaks and Unicode in a focused serialization case; preserve leading formula-like text just as current table CSVs do.
- Validate all real exported columns have meaningful authored entries, including newly added distribution tables; deliberately missing metadata fails with a table/column name and preserves the previous published output.
- Validate coverage for multiple Wahlperioden and no rows; counts equal the snapshot and unknown completeness remains labelled unknown.
- Read generated DATA.md: actual tag/revision/versions, table/column descriptions, source/licence layers, selected counting-rule quotations, known-gap caveats and all recipe SQL/results filenames. No generic placeholders, false DOI or fabricated release URL.
- Extend hash/cache cases: unchanged export reuses; change each authored input or recipe caveat -> regenerate; missing or truncated codebook/recipe asset -> regenerate. Inject a codebook/CSV write failure and reuse existing publication-preservation assertion.
- Render local/remote current manifests: codebook and each recipe CSV point into the named generation; table CSV count stays accurate. Per D1/A, render a legacy fixture with existing behavior; accept a complete new-format manifest; reject missing/mistyped codebook or recipe entries and malformed references with clear errors. Preserve existing recipe SQL/copy behavior and text escaping. These checks do not establish remote asset availability.
- Proportionate offline smoke run from existing demo/fixture exports, checking that every manifest reference resolves. No proposed test/benchmark implementation during engineering review.

## NOT in scope

- Immutable GitHub release uploader and scheduled workflow: separate D release TODO; document the complete inventory contract now.
- Legal/Impressum work or a redistribution-source decision: separate D launch blockers; use existing decisions without declaring them settled.
- DOI/CITATION.cff, public data changelog, product naming and hosting: their existing roadmap items.
- Remote-manifest SQL authenticity/pinning: existing separate P2 TODO. This work validates new artifact metadata; it does not execute remote SQL or claim that copied SQL is trusted.
- A3 backfill, new acquisition tables, count/identity changes, extra recipes, query unlimiting or site redesign: unrelated to packaging the current dataset honestly.

## Review topics and dispositions

- Plain recipe CSVs containing all SQL result columns and the exact existing LIMITs remain the baseline; R2/D2-A explicitly fixes SQL cursor order and regression proof.
- One typed inventory and backwards-compatible old-manifest rendering remain the baseline; R1/D1-A requires complete new-format artifact metadata.
- Static authored definitions plus generated schema/coverage fit the existing exporter. Required input hash, metadata completeness, source/licence and coverage checks are specified below; semantic authoring still requires writer inspection.
- Legacy-manifest and recipe-output regression contracts are resolved by R1/D1-A and R2/D2-A. This review grants no product implementation permission.

## Engineering review

Fixed target and report destination: `docs/plans/d-codebook-recipe-csvs.md`. Review session `98480-1793169711-773d09a3`, started 2026-10-28. The original proposal above is retained; the source locator for `iter_tables` was corrected from 2456 to 2451 as a factual correction.

### Startup and evidence

- Skill startup: interactive, collaborative repo, question tuning off, telemetry off. The update check crashed with unknown update status; the workflow lease was unavailable. No upgrade attempted.
- Context recovery read recent project decisions and the newest checkpoint. No branch-scoped binding decisions were returned. Prior learnings about export format checks and fixture limitations inform later validation; they are not approvals for this plan.
- Brain product/recent-decision cache reads failed because their helper attempted to write a cache metadata file outside the sandbox. No digest exists in the readable cache; PRODUCT.md, CONTEXT.md and the explicit roadmap supply the project context instead.
- The design helper selected unrelated `docs/designs/puls-wochenradar.md`; it is not used as this feature's design authority. The directly relevant existing `docs/designs/daten-page.md` was read for its snapshot/recipe/download constraints. A CEO plan from another branch was discovered but not used or imported.
- Aside is unavailable (`NEEDS_ASIDE: Darwin`). No new architecture/infrastructure/concurrency pattern is proposed: this is an extension of the existing generation exporter [Layer 1] using standard-library CSV [Layer 1]. No web research or legal re-verification is claimed.
- `git fetch origin main` succeeded after an initial sandbox-denied FETCH_HEAD write. Refreshed main is `71ade83`; this worktree's product baseline is `d766825`. History searches over the named paths and codebook/recipe-CSV terms found roadmap/licence/recipe work, not an implemented codebook. Future input files are not available and have no history to inspect.
- Existing behavior evidence: `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p test_daten_export.py` passed 51 tests in 7.546s on `d766825` with only this planning file added. Fixture/unit evidence, not a live release check. No proposed tests or benchmarks were built.

### Scope Challenge A/B

Minimum work: extend the existing generation builder, schema introspection, recipe execution and manifest-driven rendering. No extraction, new service, CLI option or infrastructure. The initial proposal estimates seven changed/new implementation files and zero new classes/services (implementation sequence above), so the complexity selector is not triggered. One PR; sequential implementation. Upload tooling, legal publication, DOI, changelog, backfill and hosting remain their separate roadmap items, rather than being silently treated as shipped here.

Distribution: new Markdown/CSV payloads follow the existing platform-neutral Python exporter and current unittest CI. Build-store schema/key policy and current recipe SQL/limits are retained in the baseline proposal. Publishing immutable downloads is not implemented today; upload inventory/layout remains an explicit handoff to the release-script TODO.

| Premise | Claim | Receipt | Verdict |
|---|---|---|---|
| P1 | Existing exporter can stage additional generation files before manifest publication | scripts/build_dip_pulse_site.py:3109–3126 | verified, static read |
| P2 | Six recipe SQL results already exist in the distribution manifest | scripts/build_dip_pulse_site.py:3334–3359 | verified, static read and fixture suite |
| P3 | Column source tags exist, but a semantic codebook is not generated | scripts/build_dip_pulse_site.py:3305–3332 | verified, static read |
| P4 | Release script/DOI/legal settlement are separate unfinished work | TODOS.md:698–724 | verified as roadmap status, no legal verification claimed |
| P5 | Proposed change reaches seven implementation files, no new services | docs/plans/d-codebook-recipe-csvs.md:88 | estimated from enumerated implementation sequence |
| P6 | Current manifest loader has no version-specific artifact requirements | scripts/build_dip_pulse_site.py:11219–11264 | verified, static read |

REALITY: premise-table pass unverified=0; future behavior remains a proposal docs/plans/d-codebook-recipe-csvs.md:9
REALITY: already-done pass refreshed origin/main history has no implemented codebook; source-export artifacts remain SQLite and table CSVs scripts/build_dip_pulse_site.py:3283
REALITY: surface-check pass named export/render/validation functions exist and existing unittest command completed AGENTS.md:5
REALITY: binding-decisions pass roadmap and accepted ADRs retained; no branch decision overrides found docs/plans/d-codebook-recipe-csvs.md:22
REALITY: numbers pass implementation estimate enumerates seven files and no classes; recipe count follows authored definitions docs/plans/d-codebook-recipe-csvs.md:88
REALITY: deferred-asks pass no linked issue; both requested artifact types retained and separate release TODOs explicit TODOS.md:136
REALITY: pr-count pass one proposed PR, no extra queue gates docs/plans/d-codebook-recipe-csvs.md:11
REALITY: transaction-semantics pass existing snapshot/lock/publication sequence retained; fixture failure preservation test is green tests/test_daten_export.py:489

### Scope Challenge C

1. [P2] (confidence: 8/10) docs/plans/d-codebook-recipe-csvs.md:40, primary reviewer: the compatibility rule identifies legacy manifests by missing artifact metadata, without saying whether a new-format manifest missing that metadata is malformed. Motivating plan text: “Legacy manifests with no artifact-kind metadata retain their existing page behavior and expose no invented links.” Current `validate_manifest` only checks field types at `scripts/build_dip_pulse_site.py:11223–11227` and returns success at `:11264`; there is no version-specific artifact requirement. Without settling this contract, a partial new release could be silently presented as a legacy export. Proposed risk, not an observed failure of code that has not been written.

Dispositions: finding 1 accepted through D1/A (user reply “A” on 2026-10-28). Complete new-format artifact validation and its legacy/new regression checks are incorporated above. Scope Challenge result: scope accepted as-is; no scope reduction. No pending Scope Challenge answer remains; continue to Sections 1–4.

### Review continuation, 2026-10-28

Review run `98480-1793227652-cd18d040`. Target/report remains this file. Retain the earlier D1/A approval as recorded in R1; no product implementation is authorized by this review. Continuous decision numbering resumes at D2.

Startup repeated: interactive, collaborative, question tuning off, telemetry off. Update check failed, and no workflow lease was acquired; update status is unknown. Context recovery and branch decision search found no new binding architecture decision. Brain-cache reads failed with `EPERM` on their metadata writes; PRODUCT.md and the repository domain/licence/design documents supply context instead. Aside readiness returned `NEEDS_ASIDE: Darwin`. No new architecture, infrastructure or concurrency pattern is proposed, so no web research is needed or claimed. The design helper again returned the unrelated Wochenradar document; `docs/designs/daten-page.md` is the relevant existing design context. The cross-branch CEO plan was not imported. No extra prerequisite review is needed to resume the recorded review.

Fresh evidence at HEAD `d766825` (product files unchanged; this plan is untracked):

- `git fetch origin main` succeeded after the sandbox denied the initial FETCH_HEAD write. Refreshed `origin/main` is `18d3ddf`. History searches over proposed existing paths and codebook/recipe-CSV terms found no implemented codebook or recipe CSV exporter. Future dictionary/methods files remain unavailable.
- `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p test_daten_export.py`: 51 tests passed in 6.709s. Existing fixture/unit evidence only; the complete suite and proposed tests were not run or built.
- Bounded fixture probe: execute the existing r5 SQL against `_daten_fixture.seed_store` and inspect `cursor.description`. SQL order is `proceeding_id, title, typ, reden, sitzungen, erste_drucksache`; existing manifest metadata order is `proceeding_id, title, typ, erste_drucksache, reden, sitzungen`. Actual fixture values are `vg-1, Gesetzentwurf zur Testbarkeit, Gesetzgebung, 7, 2, 20/100`. This verifies an existing schema-order mismatch, not a failure of the proposed CSV implementation.
- A narrowly delegated source/domain check found no blocker in the proposed licence layering or unknown-completeness disclosure. Primary review checked `docs/data-license.md:15–22,28–38`, the export-only tables at `scripts/build_dip_pulse_site.py:3195–3221`, and the plan's explicit unknown-completeness rule at line 58. Not an independent outside review or a full per-column audit.

Scope Challenge continuation: no new scope finding. The proposed seven implementation files and zero new classes/services remain an estimate, not a measured diff; the complexity gate remains below its threshold. One PR and sequential implementation remain proposed. R1 is resolved as recorded; scope accepted as-is. The test-location detail will be reconciled with the existing dedicated Daten-page tests during Test review.

REALITY: premise-table pass unverified=0; original factual premises rechecked, future implementation remains proposed docs/plans/d-codebook-recipe-csvs.md:144
REALITY: already-done pass refreshed origin/main has no implemented codebook/result CSV exporter scripts/build_dip_pulse_site.py:3283
REALITY: surface-check pass current exporter/manifest entry points read; documented Python command ran AGENTS.md:5
REALITY: binding-decisions pass R1/D1-A retained and no conflicting branch decision found docs/plans/d-codebook-recipe-csvs.md:40
REALITY: numbers pass seven implementation files estimated; six recipes counted from RECIPES scripts/build_dip_pulse_site.py:2592
REALITY: deferred-asks pass no linked issue; upload/legal/DOI/backfill exclusions remain explicit docs/plans/d-codebook-recipe-csvs.md:109
REALITY: pr-count pass one implementation PR; no PR split proposed docs/plans/d-codebook-recipe-csvs.md:11
REALITY: transaction-semantics pass no driver/pool/protocol change; existing snapshot and failure-preservation path retained scripts/build_dip_pulse_site.py:3090

### 1. Architecture review

No issues found. Reuse the existing exporter, private staging directory, snapshot connection, schema introspection, manifest boundary and renderer [Layer 1]. Standard-library CSV remains sufficient [Layer 1]. No extraction, new dependency, new service, CLI option or additional publisher is justified.

The proposed flow on lines 68–80 covers the principal boundaries: read-only build store -> private SQLite snapshot -> staged assets -> complete generation -> manifest last -> local/remote rendering. Dictionary or serialization failures must fail before publication, with the old generation retained. The existing failure preservation test (`tests/test_daten_export.py:489`) verifies current publication behavior, not yet failures in future codebook/recipe writers. R1 already requires new-format structural completeness at the operator-manifest boundary. Remote asset existence and remote SQL authenticity remain explicitly outside that validation claim.

Distribution stays with existing Python 3.11–3.13 CI and platform-neutral Markdown/CSV assets; the separate release uploader must retain generation-relative paths. The codebook must separate stored per-WP observations from unknown acquisition completeness and preserve the documented layered licence. Neither packaging nor this review authorizes public redistribution.

Dispositions: no new architecture remedy; R1/D1-A retained. Source revision and every rendered input must enter the generation fingerprint under the existing line-83 contract; the current `_inputs_hash` does not include `commit`, so implementation must extend that input coverage rather than copy its current field list unchanged.

### 2. Code quality review

2. [P2] (confidence: 9/10) `docs/plans/d-codebook-recipe-csvs.md:38,100`, primary reviewer: the CSV/manifest column-order contract needs an explicit r5 decision. Motivating plan text: "Include all selected columns in SQL result order" and "compare ordered header/rows with its CSV and manifest." Existing SQL at `scripts/build_dip_pulse_site.py:2708–2710` selects `"SELECT pr.id AS proceeding_id, pr.title, pr.proceeding_type AS typ,\n"`, then `"       COUNT(DISTINCT s.id) AS reden, COUNT(DISTINCT ai.protocol_id) AS sitzungen,\n"`, then `"       MIN(p.document_number) AS erste_drucksache\n"`. The authored display columns instead put `{"name": "erste_drucksache", "align": "text"}` before `reden` and `sitzungen` at lines 2724–2726. `_run_export` writes `"columns": [column["name"] for column in recipe["columns"]]` at line 3355. The fixture probe above confirms the difference. Reusing that manifest array for the CSV violates the draft's SQL-order promise; serializing row values by insertion order beneath that array's header would mislabel cells. No new CSV corruption is claimed before implementation.

Keep HTML display metadata separate from machine output ordering, with no shared-code extraction. The renderer intentionally uses local `RECIPES_BY_ID` metadata (`scripts/build_dip_pulse_site.py:3584–3586`); changing a new manifest's machine column order need not reorder the HTML. A cursor-derived header also works for zero rows, unlike inferring keys from the first result.

Dispositions: finding 2 accepted through R2/D2-A, user reply "A" on 2026-10-29. The new-format machine header follows SQL; existing HTML display order, legacy behavior, SQL, limits, row order and named values stay fixed. R1/D1-A is unchanged. Continue to Test review.

### 3. Test review

Framework: Python standard-library unittest, authoritative command from AGENTS.md. Source and concrete export/page/pipeline tests were read in dedicated calls before this trace. New writers/metadata/coverage renderers remain proposals, with no existing tests credited for their future branches. The diagram groups related assertions into 16 review scenarios; its fraction is a review inventory, not measured line or branch coverage.

```text
CODE PATHS                                             USER FLOWS
export_distribution_data()                             Daten reader
  +-- [*** TESTED] existing guard/lock/staging            +-- [GAP G7] [->E2E] local links -> named files
  |     old SQLite/schema/rule mismatch -> error         +-- [GAP G7] remote base -> generation URLs
  |     live lock -> refuse, dead lock -> retry          +-- [GAP G2] downloaded DATA.md -> offline citation
  |     lock holder alone sweeps private work            +-- [GAP G1] [->E2E] six SQL queries -> same CSV rows
  |     source changes during backup -> refuse          +-- [GAP G6] old manifest -> old page behavior
  |     SQLite/write failure -> cleanup, preserve        +-- [GAP G5] operator failure -> old files retained
  |       tests/test_daten_export.py:489,571,698
  +-- [*** TESTED] existing cache inputs/reuse
  |     _read_previous_manifest: absent/bad/readable
  |     _source_sha256: stat match -> cached / else hash
  |     _recipes_hash + _inputs_hash -> generation
  |     _manifest_reusable: format/hash/generation/files
  |       mismatch/missing/wrong size -> rebuild
  |       equal + !force -> return previous
  |       force -> rebuild same generation safely
  |       tests/test_daten_export.py:327,450-475,533,540,646
  +-- [GAP G4] same-read input bytes + new content hashes
  |     dictionary/methods/licence/recipe metadata/revision
  |       equal -> reuse / any rendered input differs -> rebuild
  +-- _run_export() -> read-only source backup -> private copy
  |     optional paragraphs_json -> drop only in copy
  |     mp_canonical from copy -> integrity guard
  |     schema hash + datenstand -> VACUUM -> snapshot
  |     iter_tables -> names/types/keys/relationships/counts
  |     _write_csv -> PK/rowid order, NULL/text, gzip
  |     SQLite gzip + _hash_file -> existing inventory
  +-- [GAP G2] authored dictionary + methods -> DATA.md
  |     malformed/unreadable/missing table/column -> named error
  |     complete -> schema + German meanings/units/source/licence
  |     no revision/tag/immutable URL -> honest local/unknown text
  |     source/ADR quotations + limitations + hashes -> documentation
  +-- [GAP G1] each existing recipe executes once
  |     SQL error -> named recipe failure
  |     cursor.description -> manifest columns + CSV header [D2/A]
  |     zero rows -> header only + unavailable/generic reason
  |     rows -> values by header name, hidden IDs included
  |       NULL -> empty cell; quotes/newlines/Unicode -> CSV quoting
  |       leading formula text -> unchanged; SQLite authoritative
  |     rows -> manifest; bytes/rows/hash -> recipe_csv entry
  +-- [GAP G3] per-WP snapshot coverage
  |     no protocols -> empty section
  |     several WPs -> isolated counts/date ranges
  |     missing acquisition/catalog evidence -> unknown completeness
  +-- [GAP G5] new input/CSV/codebook failure
  |     before publication -> error, cleanup, old tree unchanged
  |     success -> rename complete generation -> manifest last
  |       same generation exists -> set aside/restore on rename failure
  |       publish succeeds -> remove old generations
  +-- validate_manifest(operator input)
  |   [GAP G6] existing shape checks + new-format contract [D1/A]
  |     not dict/missing/wrong types -> named error
  |     legacy version -> existing validation/rendering
  |     new version -> typed SQLite/table/codebook/recipe inventory
  |       missing/mistyped/duplicate/dangling/unsafe reference -> reject
  |       complete -> accept, no claim remote bytes exist
  +-- render_database_page -> downloads + recipes
        [** TESTED] existing recipe presentation
          rows/empty; hidden columns; NULL/numeric/text; truncation
          known/unknown entity -> link/plain text; SQL/copy escaping
            tests/test_daten_page.py:86-124,151
        [GAP G7] new links + typed table count + legacy fixture
          local/remote base -> same generation-relative suffix
          codebook download + each recipe CSV; page order unchanged

COVERAGE: 3/16 scenario groups have existing **/*** evidence.
Code scenarios: 3/10. User-flow scenarios: 0/6 for the new artifacts.
QUALITY: ***:2, **:1; seven distinct future requirement gaps G1-G7.
Legend: *** behavior/edge/error; ** behavior; * smoke (not coverage).
[->E2E] = offline integration at real export/SQLite/file/HTML boundaries.
```

The existing download size/SQL-title smoke checks (`tests/test_daten_page.py:72–84,146–149`) do not establish new file availability or exact SQL parity. Retain valuable existing tests; extend them at the real owning boundary. Remote transport timeout, bad JSON and size cap remain covered by mocked transport tests at `tests/test_data_pipeline_cli.py:131–169`; no new transport is proposed.

Test findings (future requirements, not observed regressions):

3. [P2] (confidence: 9/10) `docs/plans/d-codebook-recipe-csvs.md:100–101`, G1: "compare ordered header/rows with its CSV and manifest" needs the approved D2/A replay, explicit r5 order and zero-row cases. Current recipes have no CSV output. Extend `tests/test_daten_export.py`; replay each SQL from the emitted SQLite, compare ordered cursor headers and named rows to CSV/manifest, assert exact current LIMITs and row order, then exercise quotes, commas, LF, Unicode, NULL/empty and formula-like text. Existing r1/r2/r3 semantic tests remain independent checks against self-consistent mistakes. **CRITICAL regression contract:** D2/A fixes preserved semantics and the intentional format-9 r5 header change; no new approval needed for its proof.

4. [P2] (confidence: 9/10) `docs/plans/d-codebook-recipe-csvs.md:102,104`, G2: "every actual distribution table/column has authored metadata" and "No generic placeholders" need schema-wide checks, not a handful of heading assertions. Extend `tests/test_daten_export.py` against ordinary and facts-populated fixture exports, including export-only and registry tables. Missing table/column, malformed input or unusable required meaning/unit/source/licence must fail with a useful named input/entry error. Check representative real definitions, domain quotations, versions, local/unknown provenance, all six SQL blocks, file hashes and layered notice; verify no removed paragraphs column or invented DOI/URL. Human authoring still requires reading every relevant writer; green tests cannot establish semantic truth for all German descriptions.

5. [P2] (confidence: 9/10) `docs/plans/d-codebook-recipe-csvs.md:103`, G3: "counts equal the snapshot and unknown completeness remains labelled unknown" needs a multi-WP fixture and empty snapshot case in `tests/test_daten_export.py`. Counts/date ranges must be checked independently per WP; missing acquisition/catalog evidence stays unknown, including zero votes. Existing global protocol/count tests cannot establish that separation.

6. [P2] (confidence: 9/10) `docs/plans/d-codebook-recipe-csvs.md:83,105`, G4: "any other text that changes DATA.md" requires extending the existing input-change table at `tests/test_daten_export.py:646`. Vary each authored input, recipe title/columns/caveat and supplied revision independently; keep SQLite/SQL unchanged. Assert regeneration and matching output text, then unchanged-input reuse and rebuild for missing/truncated new files. Verify hash/render use the same bytes if an input changes after its initial read. The existing hash includes only recipe id/SQL at `scripts/build_dip_pulse_site.py:2788` and has no commit field at `:2807–2822`; copying it unchanged does not implement the draft. This is required proof of the existing line-83 input-identity contract, not a new freshness policy.

7. [P2] (confidence: 9/10) `docs/plans/d-codebook-recipe-csvs.md:83,105`, G5: "leave the previously published generation and manifest intact" must extend the tree-preservation assertion at `tests/test_daten_export.py:489` to failed dictionary validation, recipe CSV output and codebook output. Exercise new and forced/same-generation attempts, cleanup, named error and byte-for-byte old publication preservation. Existing table-writer injection cannot prove that future writers stay inside staging. This preserves the draft's existing publication guarantee; no new lifecycle contract is proposed.

8. [P2] (confidence: 9/10) `docs/plans/d-codebook-recipe-csvs.md:40,106`, G6: "missing metadata must not classify it as legacy" requires the exact approved D1/A matrix. In `tests/test_daten_page.py`, call the public validator with a pre-change manifest fixture, a complete new manifest, missing/mistyped codebook/recipe entries, unsafe basenames, unsupported kinds and duplicate/dangling references. Check error names. Keep SQLite first and validate bytes/rows/hash metadata for the new entries. Existing generic shape rejection at `tests/test_data_pipeline_cli.py:360–374` does not test these future cases. **CRITICAL regression contract:** legacy behavior plus complete new-format inventory is already approved by D1/A.

9. [P2] (confidence: 9/10) `docs/plans/d-codebook-recipe-csvs.md:106–107`, G7: "codebook and each recipe CSV point into the named generation; table CSV count stays accurate" needs extending the existing `tests/test_daten_page.py` exporter/render fixture. Inspect actual hrefs, resolve local paths to files, check remote URL suffixes without a network request, exclude new artifacts from table counts, and render a frozen pre-change manifest without invented links. Retain HTML visible column order, exact escaped SQL/copy text and entity links under D1/A and D2/A. The existing SQL-prefix assertion is too weak for exact copy preservation; extend the emitted `<pre><code>` assertion rather than duplicating the clipboard runtime tests.

Dispositions: G1 and G6 carry D2/A and D1/A respectively. G2–G5 and G7 retain the draft's existing acceptance requirements; they are required proof for that baseline, not newly selected product policies. No new or reopened decision is needed. Seven future test gaps remain implementation work; none is claimed tested by this review. Tests to retire: none. No LLM/prompt/tool-definition change, so no eval scope. No production-only testing seam, new framework, browser benchmark or paid eval is justified. Double-click, navigation-away and two-tab interactions add no new application state for ordinary static downloads; existing clipboard interaction code is retained and its existing browser checks remain part of implementation CI.

### 4. Performance review

No issues found in the proposed approach. The existing table CSV path streams rows (`scripts/build_dip_pulse_site.py:2983`); preserve that. Each of six current recipes returns at most five rows, so result serialization adds at most 30 rows per generation [measured bound from the six existing LIMIT 5 clauses]. Reuse those already computed rows instead of rerunning SQL for Markdown or CSV. The dictionary is proportional to schema size; read its source bytes once and avoid loading table data to produce descriptions. Per-WP coverage belongs in grouped SQL aggregates from the same snapshot, with separate aggregates for different entities to avoid multiplying rows through joins. No additional index, cache service, parallel export, new dependency or benchmark is justified.

The unchanged path should retain the existing size/stat checks after hashing the small authored inputs. Rehashing every large generated file on every cache hit is not part of this plan. Missing/truncated assets are covered; same-size external tampering is not detected by the existing reuse policy. Distribution size/time and per-WP aggregate cost on the real store are unknown; the prior design's historical timings are not a current measurement or a new performance promise.

Dispositions: no new performance remedy. Existing recipe SQL/LIMITs and the input-identity contract remain fixed. No performance benchmark was run or proposed for this review.

Test Plan Artifact: saved and read back at `/Users/Luca/.gstack/projects/LucaAlv-poliwatch/Luca-codebook-eng-review-test-plan-20261029-124413.md`. It contains the baseline QA requirements, R1/D1-A and R2/D2-A; no new test implementation was written. Existing page/pipeline verification on unchanged product HEAD d766825: `PYTHONPATH=tests:scripts /opt/miniconda3/bin/python3.13 -m unittest test_daten_page test_data_pipeline_cli`, 64 tests passed in 10.085s on 2026-10-29 (captured output `/private/tmp/codebook-eng-page-cli-tests.log`). The earlier 51-test export result remains valid for the same unchanged source; no full-suite or live-release credit is claimed.

### Outside Voice

Provider: Claude Code. The two initial host approval rejections are retained in R3's history and the outside log. R3/D3-A (actual user reply A on 2026-10-29) then authorized sending the exact prepared prompt. Its fingerprint was verified before execution, and no global provider/config setting was changed.

The authorized process exited 1 with an empty reviewer result. Verbatim diagnostic: "You're out of usage credits. Switch to another model, or manage usage credits at https://claude.ai/settings/usage?from=cc_cli_limit_message, to continue." The result validator classified the execution unavailable; no recommendation or reviewer report exists. Fix: restore Claude account usage credits before a later outside review. No alternative external provider was substituted.

Outside voice unavailable: Claude usage credits exhausted; required native Plan agent type, TaskStop and background timer interfaces are also unavailable in this host. Continuing to planning decisions and Approval readiness. (OUTSIDE_VOICE_UNAVAILABLE)

Coverage attribution: `source=none`, `outside_status=unavailable`, host `codex`, phase `plan-review`. Requested model selection was `claude-fable-5-1` from the installed gstack catalog; no model execution or distinct-model agreement is established. Returned `modelUsage` was `{}`; input/output/thinking token counts were all zero, and no web searches/fetches were reported. Full returned usage/selection/session metadata is retained in `/private/tmp/codebook-outside-result.json` and the local outside-review log; outside session id `adbaeb9f-338f-4aef-a6e8-1004d3718fba`.

Dispositions: no outside findings, no clean-review credit, no Cross-model tension step. R3 consent is resolved; missing independent coverage remains a concern and does not invalidate the native review or its test evidence. The prompt is discarded after consuming this failed outcome, as required by the skill.

## Decision ledger

### R1: Missing artifacts in a new-format manifest

Finding: 1, P2, confidence 8/10, docs/plans/d-codebook-recipe-csvs.md:40, primary reviewer.
Plan baseline: original proposal generates a complete codebook and six recipe CSVs, adds typed inventory metadata, and preserves old manifests with no such metadata. No user approval of the missing-new-metadata policy yet.
Runtime evidence: current loader checks types and generic file structure only, scripts/build_dip_pulse_site.py:11219–11264. Existing fixture export suite passed 51 tests. New-format manifest behavior is not implemented.

| Choice/contract | Current baseline | A | B | Approval |
|---|---|---|---|---|
| R1: new-format manifest missing required artifact metadata | unspecified, pending | reject with named error | accept; hide absent downloads | none |
| Existing pre-change manifests | retained by original draft | same supported legacy behavior | same supported legacy behavior | original proposal, not a new remedy |
| Newly generated local payloads | complete DATA.md and one CSV per recipe | unchanged | unchanged | original proposal |
| Other new artifact validation | plain names, supported kinds, no duplicate/dangling references when present | unchanged | unchanged | original proposal |
| SQL, limits, hidden-column export proposal, file naming, licence policy, upload scope | original draft; no new approvals here | unchanged | unchanged | original proposal |
| Necessary proof for R1 | pending | old manifest accepted; complete new one accepted; missing/mistyped codebook/recipe inventory rejected | old and complete new accepted; partial new accepted without fabricated links; malformed present metadata rejected | pending D1 |

Question D1:
D1 — Should a new-format release require all its documentation files?
Project/branch/task: Codebook, branch `codebook`; the draft adds DATA.md and recipe CSVs to export format 9.
ELI10: A manifest is the file list the website reads. Old exports never had a codebook or recipe CSVs, so they still need to work. A new export can promise those files and accidentally leave them out; we need to decide whether that is an error or a page with fewer downloads.
Stakes if we pick wrong: an incomplete new release could look valid, or an older release could stop rendering.
Recommendation: A because the new format should make a complete release checkable while keeping older exports usable.
Completeness: A=10/10, B=7/10.
Pros / cons:
A) Require new-format artifacts (recommended)
Preserve the existing behavior for legacy manifests. Require the complete typed codebook/recipe inventory in the new format, and reject missing entries with a clear error; regression tests cover legacy acceptance, new-format completeness and malformed references. This catches partial new releases before readers see them and keeps versioned definitions dependable. It adds a small version-specific validation branch to maintain (human: ~45 min / CC: ~5 min; estimate for validation and tests).
B) Allow partial new manifests
Preserve the existing behavior for legacy manifests. Accept a new-format manifest without some documentation/download entries, hide those links, and still validate every entry that is present; regression tests cover that fallback. This tolerates partially uploaded or hand-authored manifests and keeps rendering permissive. It cannot guarantee that a valid new-format manifest describes all the promised release artifacts (human: ~30 min / CC: ~4 min; estimate for validation and tests).
Net: A makes the new format a completeness contract; B favours displaying partial exports.

Header: New format
Options:
A) Require new-format artifacts (recommended)
Preserve the existing behavior for legacy manifests. Require the complete typed codebook/recipe inventory in the new format, and reject missing entries with a clear error; regression tests cover legacy acceptance, new-format completeness and malformed references. This catches partial new releases before readers see them and keeps versioned definitions dependable. It adds a small version-specific validation branch to maintain (human: ~45 min / CC: ~5 min; estimate for validation and tests).
B) Allow partial new manifests
Preserve the existing behavior for legacy manifests. Accept a new-format manifest without some documentation/download entries, hide those links, and still validate every entry that is present; regression tests cover that fallback. This tolerates partially uploaded or hand-authored manifests and keeps rendering permissive. It cannot guarantee that a valid new-format manifest describes all the promised release artifacts (human: ~30 min / CC: ~4 min; estimate for validation and tests).

State: approved
Actual answer: A, user reply “A” on 2026-10-28 to D1.
Accepted scope: preserve existing legacy-manifest behavior; require the complete typed codebook/recipe inventory in new-format manifests; reject missing entries with clear errors. Regression proof covers legacy acceptance, complete-new acceptance, missing/mistyped required inventory and malformed references. Local generation remains complete under both original options; all other original proposals stay unchanged. This approves a plan amendment, not product implementation during review.
History: the original record was pending/unanswered, with no accepted R1 remedy. D1/A resolves that state; original option text and comparison grid are retained above as the pre-answer record.

### R2: Recipe output column order

Finding: 2, P2, confidence 9/10, docs/plans/d-codebook-recipe-csvs.md:38,100; scripts/build_dip_pulse_site.py:2708–2726,3355; primary reviewer.
Plan baseline: original draft promises all SQL-selected columns in SQL result order and ordered replay comparison with CSV/manifest. R1/D1-A approves new-format inventory completeness and legacy compatibility only; it does not settle this output-order difference.
Runtime evidence: bounded SQLite fixture probe at HEAD d766825 verifies r5 SQL order `proceeding_id,title,typ,reden,sitzungen,erste_drucksache` and existing manifest metadata order `proceeding_id,title,typ,erste_drucksache,reden,sitzungen`. No recipe CSV writer exists yet. HTML takes its visible order from local RECIPES metadata, independently of manifest columns.

| Choice/contract | Current baseline | A | B | Approval |
|---|---|---|---|---|
| R2: machine column order for new-format recipe CSV and manifest columns | draft says SQL order; existing r5 manifest uses display order | SQL cursor projection order for both | authored recipe display order for both | pending D2 |
| Intentional difference from existing manifest output | unspecified for r5 | format-9 r5 columns reordered to SQL order | no r5 manifest columns reorder; amend draft CSV-order promise | pending D2 |
| CSV values and empty results | CSV is proposed, not implemented | select each value by header name; header from cursor even with no rows | select each value by authored header name; header exists even with no rows | necessary proof of selected R2 contract |
| SQL text, LIMITs, result row order and named values | preserve original recipe semantics | unchanged | unchanged | original draft; explicitly protected by either D2 option |
| HTML visible ordering, SQL/copy and legacy manifest rendering | existing behavior retained | unchanged | unchanged | original draft and R1/D1-A legacy approval |
| New-format typed inventory completeness | require complete typed artifacts | unchanged | unchanged | R1/D1-A |
| Recipe-order regression proof | proposed replay; r5 mismatch not explicitly settled | all six cursor headers equal CSV and manifest columns; named rows equal replay; explicit r5 `7,2,20/100` order and empty-header assertion | all six authored headers equal CSV and manifest columns; named rows equal replay after name-based projection; explicit r5 `20/100,7,2` order and empty-header assertion | pending D2; no test implementation authorized during review |
| Other scope, source/licence policy, upload exclusions and seven-file arrangement | existing draft | unchanged | unchanged | no other remedy decided here |

Question D2:
D2 — Which column order should recipe downloads use?
Reply with A or B.

Project/branch/task: `codebook`, reviewing `docs/plans/d-codebook-recipe-csvs.md` before implementation.
ELI10: Recipe 5 currently has two column orders. Its SQL ends with `reden, sitzungen, erste_drucksache`, but its manifest lists `erste_drucksache, reden, sitzungen`. The draft promises SQL-ordered CSVs; we need one explicit order for the new CSV and its manifest header so a reader cannot associate a value with the wrong column.
Stakes if we pick wrong: a download can violate its documented schema, and a positional CSV writer can mislabel counts as a protocol number.
Recommendation: A because it preserves the draft's SQL-order promise and gives SQL, CSV and manifest one machine-readable order.
Note: options differ in kind, not coverage — no completeness score.

A) Use SQL order (recommended)
Set new-format manifest `columns` and CSV headers from the SQL cursor, including empty results; retain HTML display order and legacy behavior. This gives readers matching SQL/CSV/manifest headers, with regression checks for all six recipes and an explicit r5 case. It intentionally reorders r5's metadata in format 9, which must be documented for consumers (human: ~30 min / CC: ~5 min).

B) Use display order
Keep manifest `columns` in the authored display order and use that order for CSV headers, selecting each cell by column name; retain HTML display order and legacy behavior. This preserves r5's existing manifest order, with regression checks for all six recipes and an explicit r5 case. It requires revising the draft's SQL-order promise and keeps CSV column order different from executing r5 directly (human: ~30 min / CC: ~5 min).

Both options preserve SQL text, limits, result row order and named values; the tests protect those invariants and header-only empty results. R1/D1-A's required artifact validation stays fixed. This approves a plan contract and its regression requirements, not implementation during review.
Net: A follows the SQL projection; B follows the page's authored column metadata.

Header: Recipe order
Options:
A) Use SQL order (recommended)
Set new-format manifest `columns` and CSV headers from the SQL cursor, including empty results; retain HTML display order and legacy behavior. This gives readers matching SQL/CSV/manifest headers, with regression checks for all six recipes and an explicit r5 case. It intentionally reorders r5's metadata in format 9, which must be documented for consumers (human: ~30 min / CC: ~5 min).
B) Use display order
Keep manifest `columns` in the authored display order and use that order for CSV headers, selecting each cell by column name; retain HTML display order and legacy behavior. This preserves r5's existing manifest order, with regression checks for all six recipes and an explicit r5 case. It requires revising the draft's SQL-order promise and keeps CSV column order different from executing r5 directly (human: ~30 min / CC: ~5 min).

State: approved
Actual answer: A, user reply "A" on 2026-10-29 to D2.
Accepted scope: derive new-format manifest recipe columns and CSV headers from the SQL cursor, including empty results, and select each cell by header name. Intentionally reorder r5's format-9 machine metadata to SQL projection order and document that difference. Preserve HTML display order, legacy rendering, SQL text, LIMITs, result row order and named values. Regression requirements cover all six cursor/CSV/manifest headers, named row parity with snapshot SQL replay, explicit r5 `7,2,20/100` order and header-only empty output. R1/D1-A remains fixed. Plan amendment only; product implementation and test construction remain outside this review.
History: original State pending; Actual answer unanswered; Accepted scope none. D2/A resolves that state; original question, options and pre-answer grid are retained above.

### R3: Permission to send the prepared outside-review prompt

Finding: provider authorization gate, not an engineering defect. Outside review has no findings or clean-review credit because no process started.
Plan baseline: the invoked skill requests an independent Claude review automatically. The host's automatic approval review rejected that send, then rejected a retry citing the invoked skill; it requires destination-specific user authorization. Stored `codex_reviews` is `unset`, which is the skill's default, not a recorded explicit user consent.
Runtime evidence: preflight returned `CODEX_MODE: ready`. Both execution requests were rejected before process creation. First reason: "the user authorized reviewing the plan, but not exporting potentially sensitive repository contents to that destination." Retry reason: "stored skill consent and the assistant’s claims do not establish the user’s destination-specific authorization for that sensitive egress." No further retry will occur without an answer. Required native fallback interfaces (Plan agent type, TaskStop and background timer) are not offered; no fallback was launched, and a general-purpose agent was not substituted.

Prepared input: `/private/tmp/gstack-plan-prompt.zFysyssu`, 50,697 bytes, SHA-256 `25951b0a1fc111f6aca1226c25959b2ac456333f4ec6ae2f67f577651cf47f1a`. It contains the size-bounded plan body, current D1/A and D2/A decisions, native review summary and selected existing source excerpts. The intended command is `gstack-claude-code --access none --timeout-ms 300000 --role plan-review`; no repository/filesystem tools are granted to that process. Data supplied in the prompt would still leave this machine for Claude.

| Choice/contract | Current | A | B | Approval |
|---|---|---|---|---|
| R3: transmit the prepared prompt to Claude | blocked; no send authorized by host | authorize this prepared prompt to Claude only | do not send; finish with local review | pending D3 |
| Outside coverage | unavailable, no process ran | attempt bounded independent review; success not assumed | remains unavailable; no clean outside credit | pending D3 |
| Product implementation and repository edits by outside reviewer | forbidden | unchanged; tools/access none | unchanged; no outside process | review-only scope |
| R1/D1-A and R2/D2-A engineering contracts | approved as recorded | unchanged | unchanged | actual D1/A and D2/A answers |
| Other scope, test requirements, publisher/legal/DOI exclusions | baseline draft plus accepted amendments | unchanged | unchanged | no new product remedy here |
| Later outside findings | none exist | examine completed findings; new remedies need their own decisions | none | no remedy pre-approved by sending |

Question D3:
D3 — Allow the outside review to use Claude?
Reply with A or B.

Project/branch/task: `codebook`; the local engineering review of `docs/plans/d-codebook-recipe-csvs.md` is prepared.
ELI10: The remaining second opinion would send a prepared 50 KB prompt containing the plan, review decisions and selected source excerpts to Claude. That process would have no filesystem or tool access, but the supplied text would leave this machine. Automatic approval review requires your explicit approval of that transfer.
Stakes if we pick wrong: repository content leaves this machine without your intended permission, or the report finishes without an independent second opinion.
Recommendation: A because it completes the requested independent check using a bounded, review-only prompt you can inspect first.
Note: options differ in kind, not coverage — no completeness score.

A) Send to Claude (recommended)
Authorize sending only the prepared prompt at `/private/tmp/gstack-plan-prompt.zFysyssu` to Claude for this review, with no filesystem/tools and a five-minute limit. This enables an independent challenge and keeps its exact input reviewable before the send. Repository content will leave this machine; any findings will still need normal review and separate remedy decisions (human: ~1 min / CC: up to ~5 min).

B) Finish with local review
Do not send the prompt; finish the report using the completed local analysis and existing test evidence. This keeps repository content on this machine and gives you the prepared implementation tasks immediately. The report will explicitly retain missing outside coverage and cannot claim an independent check (human: ~1 min / CC: ~2 min).

Net: the independent check requires sending the prepared repository excerpts to Claude.

Header: Outside consent
Options:
A) Send to Claude (recommended)
Authorize sending only the prepared prompt at `/private/tmp/gstack-plan-prompt.zFysyssu` to Claude for this review, with no filesystem/tools and a five-minute limit. This enables an independent challenge and keeps its exact input reviewable before the send. Repository content will leave this machine; any findings will still need normal review and separate remedy decisions (human: ~1 min / CC: up to ~5 min).
B) Finish with local review
Do not send the prompt; finish the report using the completed local analysis and existing test evidence. This keeps repository content on this machine and gives you the prepared implementation tasks immediately. The report will explicitly retain missing outside coverage and cannot claim an independent check (human: ~1 min / CC: ~2 min).

State: approved
Actual answer: A, user reply "A" to D3 on 2026-10-29, after the explicit request to authorize sending the prepared prompt to Claude.
Accepted scope: send only `/private/tmp/gstack-plan-prompt.zFysyssu` (50,697 bytes; SHA-256 `25951b0a1fc111f6aca1226c25959b2ac456333f4ec6ae2f67f577651cf47f1a`) to Claude for this outside review, with no filesystem/tools and a five-minute limit. Examine only a completed reviewer response; new remedies remain subject to their own decisions. R1/D1-A, R2/D2-A, baseline scope and all exclusions stay unchanged. This grants no product implementation permission or global provider/config change.
History: original State pending; Actual answer unanswered; Accepted scope none. Two earlier host approval rejections occurred before any outside process started. Actual D3/A authorizes the destination-specific transfer now; original question, options and pre-answer grid remain above.

Approval readiness: PASS. Checked R1/D1-A (recorded answer 2026-10-28), R2/D2-A (actual answer 2026-10-29) and R3/D3-A (actual destination-specific consent 2026-10-29) against their exact options and accepted scope. Necessary tests/docs are retained, including the explicit legacy and recipe regression contracts. R3 grants only the bounded external review and approves no product remedy. There are no pending engineering or provider-consent decisions. Outside coverage remains unavailable; it supplies no approval or clean-review credit.

## Failure modes

| Path | Realistic failure | Handling/proof required | User impact |
|---|---|---|---|
| Authored inputs -> DATA.md | malformed or incomplete metadata | named error; schema-wide validation and preservation test G2/G5 | operator can fix named entry; previous generation remains usable |
| Input identity -> reused generation | changed revision/caveat/methods omitted from fingerprint | captured-byte hashing and per-input invalidation G4 | corrected text appears in a new generation rather than stale definitions |
| Snapshot -> recipe CSV | r5 display order used as SQL order; empty header missing | D2/A cursor headers, name-based cells, SQL replay and empty cases G1 | counts and protocol numbers retain their correct labels |
| Snapshot -> per-WP coverage | missing acquisition evidence interpreted as complete | independent counts plus explicit unknown completeness G3 | researcher sees limits of what can be claimed |
| New writers -> publication | disk full while writing CSV or Markdown | private staging, error, cleanup, old-tree preservation G5 | readers retain the prior complete generation |
| Operator manifest -> page | new artifacts missing or references malformed | D1/A versioned validation G6 | clear operator error instead of a silently partial new release |
| Page -> downloads | wrong base/generation or table count includes recipes/codebook | local file-resolution and remote URL-suffix checks G7 | download links identify the advertised snapshot |

Critical gaps (no planned test AND no handling AND silent): 0. These are proposed defenses, not evidence that future code is already correct. Same-size external asset tampering, live remote availability and power-loss durability are outside the stated checks; the review adds no such guarantees.

## Implementation Tasks

Synthesized from this review's findings. Tasks describe the baseline proposal with R1/D1-A and R2/D2-A, not authorization to implement during review. Estimates assume one developer and existing fixtures; dictionary/source judgment dominates effort, so it receives less AI compression than mechanical serialization.

- [x] **T1 (P2, human: ~8h / CC: ~90min)** — codebook — Author the complete German dictionary/methods and generate snapshot-local DATA.md.
  - Surfaced by: Test G2/G3, findings 4/5: complete definitions, honest per-WP observations and citation requirements.
  - Files: `scripts/data_dictionary.json`, `docs/data-methods.md`, `scripts/build_dip_pulse_site.py`, `tests/test_daten_export.py`.
  - Verify: schema-wide ordinary/facts/export-only metadata coverage, representative writer-grounded definitions, named missing-entry failure, empty/multi-WP counts and truthful local/unknown citation text.
- [x] **T2 (P2, human: ~2h / CC: ~15min)** — recipe exports — Write recipe CSVs and new-format machine headers in SQL order.
  - Surfaced by: Code Quality finding 2, R2/D2-A; Test G1/finding 3.
  - Files: `scripts/build_dip_pulse_site.py`, `tests/test_daten_export.py`.
  - Verify: independently replay all six SQLs from the emitted SQLite; cursor/CSV/manifest headers and named rows match; explicit r5 order, header-only results, text/NULL cases, existing SQL/LIMITs and row order retained.
- [x] **T3 (P2, human: ~3h / CC: ~25min)** — manifest/Daten page — Validate complete typed inventories and render generation-local downloads.
  - Surfaced by: Scope finding 1, R1/D1-A; Test G6/G7, findings 8/9.
  - Files: `scripts/build_dip_pulse_site.py`, `tests/test_daten_page.py`, `docs/project-documentation.md`.
  - Verify: legacy/complete-new/malformed-new matrix, local file resolution, remote URL suffixes, table-only count, retained visible recipe order and escaped SQL/copy text. Document consumer/uploader obligations and the r5 format-9 metadata difference.
- [x] **T4 (P2, human: ~2h / CC: ~20min)** — export lifecycle — Complete input identity and prove preservation on new-writer failure.
  - Surfaced by: Test G4/G5, findings 6/7.
  - Files: `scripts/build_dip_pulse_site.py`, `tests/test_daten_export.py`, `docs/project-documentation.md`, `TODOS.md`.
  - Verify: vary every rendered input independently; unchanged reuse; missing/truncated new assets rebuild; hash/render share captured bytes; new/forced failures retain the old published tree and clean staging. Update the nearby export diagram. Run focused tests, then `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests` and the existing offline demo/publication checks; mark only this codebook/CSV TODO complete after verified implementation, leaving upload/legal/DOI/hosting/changelog work open.

_No new tasks from Architecture review._
_No new tasks from Performance review._
_No tasks or clean-review credit from Outside Voice: authorized process failed for lack of usage credits and returned no reviewer report._

Task JSONL saved and read back: `/Users/Luca/.gstack/projects/LucaAlv-poliwatch/tasks-eng-review-20261029-124413.jsonl` (4 records, generated with `jq -nc`). No task is marked shipped.

## Worktree parallelization strategy

Sequential implementation, no parallelization opportunity. All four tasks touch the shared export module; T1's source/format work precedes T2/T3 adoption and T4 verification. Implement in one worktree, without parallel edits to the exporter or its shared fixtures. No additional lane or PR is proposed.

## TODOS.md disposition

No new TODO proposed. Existing release uploader, SQL-authenticity, legal redistribution, DOI/citation, public data changelog, hosting and acquisition items already own the excluded work; their existing dispositions remain intact. The current codebook/CSV entry is updated only after implementation is verified, as the original draft requires. No TODO or product file was edited during review.

## Completion summary

Review status: DONE_WITH_CONCERNS. All local review stages and decision gates are complete; the independent provider step was attempted with explicit R3/D3-A consent but supplied no reviewer response. This is a plan review, not implementation or ship clearance. The required saved-review receipt is logged only after final Read-back verification.

- Step 0: Scope Challenge — scope accepted as-is; recorded R1 remedy retained.
- Reality rows: 8/8 applicable (`PLAN_REALITY: phase=eng rows=8/8 missing=none unverified=0 verdict=complete`); 0 unverified factual premises, future implementation remains proposed.
- Architecture Review: 0 issues found.
- Code Quality Review: 1 issue found; R2/D2-A settles its plan contract.
- Test Review: diagram produced, 7 future requirement gaps identified; none of the proposed tests was built.
- Performance Review: 0 issues found; no benchmark claim.
- NOT in scope: written above and retained.
- What already exists: written above; exporter/snapshot/schema/CSV/renderer reused, no new abstraction or dependency.
- TODOS.md updates: 0 new items proposed.
- Failure modes: 0 critical gaps in the proposed handling/test plan.
- Unresolved decisions: 0 in this review; no prior fresh review has unresolved engineering decisions.
- Outside voice: Claude Code unavailable because the authorized execution ran out of usage credits; no reviewer response or native fallback. Earlier host approval denials remain in history. Missing coverage, not clean.
- Parallelization: 1 sequential lane, 0 parallel / 4 sequential tasks.
- Lake Score: 1/1 scored completeness answers chose 10/10 (recorded D1/A); D2 and D3 differ in kind and are unscored.

## Suppressed findings

None promoted or suppressed as a positive defect claim without evidence. Per-column semantic truth and real-store aggregate cost remain implementation verification limits; no defect or speedup is inferred from those unknowns.

## Next steps

Implement T1–T4 sequentially, preserving the recorded contracts. No separate CEO review is needed for this packaging scope. Adding ordinary download links in the existing panels requires no new layout, motion or interaction design; a separate design review is not needed for the current plan. Run `/ship` after implementation and its specified checks. These navigation notes approve no implementation change and add no task prerequisite.

## Learning review

No new durable operational learnings this session. One project-specific pitfall is worth retaining: r5's authored HTML/display column order differs from its SQL projection; machine CSV headers must not be inferred from display metadata. This was verified by source and the bounded fixture probe, and its treatment is recorded in R2/D2-A.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | NOT RUN | No separate CEO review needed for this packaging scope |
| Outside Review | Claude Code via `/plan-eng-review` | Independent 2nd opinion | 2 recorded outcomes | unavailable | Earlier host denial; authorized provider attempt exhausted usage credits; no reviewer response |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN | 8 issues: 1 code-quality contract + 7 future test gaps, all mapped; 0 critical gaps; no unresolved decisions |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | NOT RUN | Existing-panel download links; no separate design review needed |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | NOT RUN | No new CLI or dependency |

**OUTSIDE COVERAGE:** provider Claude Code, host codex, phase plan-review, unavailable. D3/A authorized the bounded prompt transfer; the process exited 1 for lack of usage credits and returned no reviewer text. No native fallback or clean outside credit. Returned requested-model/usage metadata is retained; actual model execution is not established.

**VERDICT:** Native engineering review completed with mapped implementation work and missing independent coverage. No fresh CLEAR engineering result exists for the proposed implementation; eng review required before shipping.

NO UNRESOLVED DECISIONS


## Implementation result (2026-10-29)

T1–T4 are implemented in the existing exporter, with no new dependency or CLI option. Export format is 10 (9 until main's Antrag passages took that number; merge db4c696); build-store schema and key version are unchanged. The authored dictionary covers all 30 current distribution tables and 246 columns. Generated DATA.md includes snapshot schema/coverage, exact methods quotations, known gaps, attribution, SQL, result filenames/checksums and truthful local/unknown citation information. Recipe CSV and manifest columns follow cursor order, including r5 and empty results; HTML presentation keeps its behavior; legacy manifests are no longer rendered (see Post-review changes). The single typed inventory is validated at the operator boundary and during cache reuse. Captured dictionary/methods/licence bytes, recipe metadata and revision enter cache identity; missing assets and metadata regenerate or fail before publication.

Semantic review corrected source/derived distinctions and representation details against writers, including facts.percentile (0–1), facts.week_n (current candidates), generated timestamps, source IDs and profile URL fallback. Existing manifest source tags remain unchanged. The methods explicitly disclose that these tags are coarse: some generated fields inherit DIP tags, and mps.profile_url may contain a Bundestag biography rather than an abgeordnetenwatch URL. This records the discrepancy without changing the established source-tag/licence contract. Recipe r1's representative affiliation and r2's complete denominator versus limited/joined output are documented without changing SQL.

Validation:

- Python 3.13 full suite: 1,567 tests in 105.179 s, OK (two skipped).
- Focused export/page/pipeline/build modules: 347 tests, OK. Tests replay all six recipes from distribution SQLite, compare ordered headers/rows (including r5 and empty outputs), exercise text/NULL fidelity, check authored completeness and quoted definitions, verify multi-WP/empty coverage, cache invalidation and captured input bytes, inject CSV/codebook write failures, and cover legacy/new malformed-manifest and link contracts.
- All scripts compile; git diff whitespace check passes.
- Existing browser checks pass, including all 16 recipe-copy scenarios and responsive/keyboard checks.
- Offline demo builds and passes publication validation; development-marked demo is correctly rejected.
- Separate fixture export smoke: all 36 artifact references resolve with matching sizes and SHA-256, and each of the six CSVs matches independent SQLite replay.

Post-review changes (2026-10-29, code review of the uncommitted branch): legacy-manifest acceptance is dropped, superseding the legacy half of D1/A under CLAUDE.md's pre-release rule (no compatibility shims); `validate_manifest` now rejects any other `export_format`, and the legacy fixture/test are removed. The r2 caveat no longer claims the visible rows total 100 %, matching `docs/data-methods.md`. Recipe output definitions are written per recipe instead of shared strings naming other recipes. DATA.md renders Bausteine as text rather than a Python dict and adds a per-table alias-resolution line. Dictionary licence text moved to a `licenses` layer map. `_recipes_hash` covers exported recipe metadata only. Recipe CSVs count unencodable characters. A non-list `files` now fails with the named error instead of a `KeyError`. No figure, SQL or row changed.

Only the codebook/CSV roadmap item is marked complete. No release was uploaded, no live-data backfill or real-store performance benchmark was performed, and no independent outside review is claimed. Release uploader, legal redistribution, DOI/CITATION.cff, changelog, hosting and acquisition TODOs remain open.

Second review round (2026-10-29, two-axis code review): DATA.md now has one H1 — the embedded methods and licence documents move one heading level down, and only the part of `docs/data-license.md` from „Short string“ on is embedded, introduced in German as the unchanged English original, so its maintainer status note stays out. The per-recipe notes left `docs/data-methods.md` for a `method` text per recipe (manifest and DATA.md only, in cache identity), removing the duplicate recipe section; Abweichung and Abweichler are quoted from CONTEXT.md. The dictionary check also refuses entries for tables or columns no export has (facts tables excepted), placeholder text and a meaning shared by several columns of one table. A table without a safe CSV name now fails the export instead of being skipped into a manifest the validator rejects. `codebook_inputs` is keyed by repository path; the inputs travel as one `CodebookInputs` value. The citation names „Bundestag-Puls“ as a working title (PRODUCT.md: name not final). "Einzelstimme" became "Stimme" per CONTEXT.md. Coverage takes the Wahlperiode from `facts.wahlperiode` and orders it numerically. The legacy-manifest reversal of D1/A stands under CLAUDE.md's pre-release rule. No figure, SQL or row changed.

Ship review changes (2026-10-30/31, /ship runs 4–6): r3 now groups by `mc.canonical_id, p.name`, so a member who switched Fraktion has one row per Fraktion; replayed on the reference export g-c1944485a5d4 the top five are unchanged (Bayram 30, Dieren 18, Kraft 13, Koeppen 11, Kubicki 9) and 2 of 363 persons gain a second row below the cut. The data dictionary, recipe texts and `docs/data-methods.md` were audited column by column against the writing code (`docs/research/codebook-dictionary-audit-2026-10-31.md`); 20 false statements were corrected, plus review fixes for `created_at` lifetimes, retired person ids in `persons` and chained `person_aliases`. No exported figure other than r3's split rows moved.
