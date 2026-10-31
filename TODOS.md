# TODOS

Reassessed against the code, the live store and the generated site on 2026-09-19 (after PR #59, v0.4.0.0; rebased onto PR #60, v0.5.0.0). Nothing below is done; corrections from that pass are inline. The Daten section was re-checked against the code and the 2026-09-19 store on 2026-09-24 (database state review): five findings, four new open items and a Python version floor now completed; `protocol_acquisition` raised to P2.

## Roadmap to v1 (2026-09-30)

The order of work toward the direction in PRODUCT.md (2026-09-30): a citable dataset for WP 18 to the present, and a site with two equal angles, the daily view and long-term analysis. Items are named by their headings below. Tracks A and B can run in parallel. C waits for A, because every count A changes moves every series C draws. D has to be finished before anything goes public.

**A. Get the counts right and the coverage in, in this order**
1. What counts as a Rede: #68 (Kurzinterventionen) and #70 (Befragung and Fragestunde) are done (PR 1, branch `a1-what-counts-as-rede`, see Completed). A1 follow-ups are implemented in v0.15.0.0 (see Completed): nested Zwischenfragen, written submissions as their own kind, and source-backed historical classification. Final merged A1/A2 validation remains required before A3; ceremony addresses absent from sampled plenary XML remain a separate acquisition gap.
2. "Stable ids for every row a release publishes" (done: A.2, see its Completed note).
3. "v1 coverage: every Sitzung from WP 18 to the present". Running it after 1 and 2 means the backfill is counted once, with ids that last.
4. "Split the dataset from the site: the site builds from a release alone". Start slice by slice alongside 1–3. The votes archive is the first slice.

**B. Abstimmungen (daily view), independent of A**
1. Completed v0.10.0.0 (2026-09-30): "Inverted-vote reading for Beschlussempfehlungen", "Majority rule for derived vote outcomes" and "Match roll-call votes to a TOP when Drucksache numbers fail".
2. Completed (2026-10-04): "Roll-call member rows link to external profiles, never to our own MP pages" (B.2, including vote-member reconciliation).
3. Done (see Completed): "Politikfeld tags on Tagesordnungspunkte and votes". This also feeds C.
4. "Vote reading misses half the inverted votes and never stores it" (P1, found 2026-10-20), then the rest of "Abstimmungen for the daily view: what was decided, by topic, with dissenters". B4 added the DIP abstract, Abweichler, committee citation, factual lead and optional Bundestag report link; the extractive fallback for votes without an abstract remains open, and the AI sentence is deferred. Item 2 (the topic filter) came with B3.
5. "Take namentliche Abstimmungen from the official XLSX instead of the chart markup" can come later. It adds ungültig and Bemerkung but changes no count seen so far.

**C. Analysen (long-term view), after A1–A3**
1. "Fraktion seat counts in the store" (small; the denominator for per-seat figures).
2. "Diskursanalyse: precomputed term series per Zusammenschluss and month".
3. "Politikfelder over time: which Zusammenschluss emphasises what" (after B3).
4. "Zwischenrufe: parse `<kommentar>` and count reactions per Fraktion", which answers "who interrupts most".
5. Then "Muster" and "Präsenz".

**D. Before anything goes public**
- Legal and licence: "Impressum, Datenschutz and licence files before the site goes public", "Settle the roll-call source for redistribution", "Tag the abgeordnetenwatch MP columns with their real source".
- The release: "Write the release script", "Public data changelog per release", "A DOI per release and a citation file". Codebook/recipe-CSV generation is implemented (2026-10-29; see Completed); uploading the artifacts still belongs to the release script.
- Hosting: "Site hosting plan for the 2.5 GB generated site". WP 18 and 19 make it larger.

**Later:** the LLM-content items (Fraktionsblöcke, deterministic validators, Debattenberichte), Fakt der Woche B/C, and the Puls and copy fixes, which stay at their own priorities. WP 1–17, which have no structured XML in the DIP catalog, come after v1.

## Daten

### Take namentliche Abstimmungen from the official XLSX instead of the chart markup

**What:** `parse_roll_call_list_page()` / `parse_fraction_votes()` (`scripts/validate_dip_protocol.py`) read `data-chart-values` from bundestag.de HTML: four numbers (Ja, Nein, Enthaltung, nicht abgegeben) summing to the seat count, and `vote_counts_from_csv` keeps only the first four numbers it finds. The Bundestag also publishes one XLSX per namentliche Abstimmung (list: `/ajax/filterlist/de/parlament/plenum/abstimmung/liste/462112-462112`, e.g. `https://www.bundestag.de/resource/blob/1217428/20260925_3-xls.xlsx`) with columns `Wahlperiode, Sitzungnr, Abstimmnr, Fraktion/Gruppe, Name, Vorname, Titel, ja, nein, Enthaltung, ungültig, nichtabgegeben, Bezeichnung, Bemerkung`. Ingest that instead (or alongside), store ungültig as its own Stimme value and keep Bemerkung.

**Why:** Ungültig is an official Stimme value we cannot represent; if it ever occurs, the chart numbers either hide it or shift it into another category, silently. Bemerkung gives the stated reason for some uncast Stimmen (30 most recent votes, 2026-09-25: "gesetzlicher Mutterschutz" 42×, "Geburt eines Kindes" 1×), which the site could show next to "nicht abgegeben". The XLSX also carries Sitzungnr/Abstimmnr, a sturdier join to the Sitzung than matching by date.

**Context:** Sample of 30 XLSX files (18,895 Stimmen) had zero ungültig, so today's counts are not wrong in practice; this is about not being able to tell. HTML scraping of the filterlist also breaks whenever bundestag.de changes its markup.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Store loses roll-call member rows in 22 groups of 11 votes

**What:** In 22 of 1,498 stored `vote_fractions` groups, across 11 votes, the stored `vote_members` rows do not add up to the fraction counts (21 if nicht abgegeben is ignored). Most are short by exactly one member: Grüne, FDP and AfD on 2022-05-19/20 (votes 773–777), SPD on 2023-05-26 (853, 854) and 2023-06-15 (855–857). On 2024-02-02 (912) the fraktionslos group stores 5 Ja against 40 and AfD one nicht abgegeben short. The report JSON matches 1,498/1,498, so rows are lost or re-attributed at persist. Vote ids: 773, 774, 775, 776, 777, 853, 854, 855, 856, 857, 912 (measured on the reference store 2026-10-20).

**Why:** Every store-side Abweichler figure (`r3-abweichler`, Fakten `meiste-abweichler`) and the Daten `vote_members` CSV inherit it, so the citable dataset is missing Stimmen. The vote panel is not affected: it reads the report.

**Pros:** Fixes a silent loss in the export; B4's Abweichler parity then holds per group on the store too.

**Cons:** Touches identity and stable ids (A.2 territory), possibly a stable-id format change.

**Context:** Found in the B4 eng review (O4, D16). Start from the 11 vote ids. Suspects: namesake collisions of `stable_ids.vote_member_occurrence_id` (built from name and Zusammenschluss), though B.2 measured 0 D3 collisions, and the party attribution of former Linke/BSW MdBs (the fraktionslos group of 912).

**Effort:** M
**Priority:** P2
**Depends on:** none

### Parse the "Entschuldigte Abgeordnete" appendix of each Plenarprotokoll

**What:** Every Plenarprotokoll XML has an `<anlage>` headed "Entschuldigte Abgeordnete" (confirmed in 21/84) listing the MdBs excused for that Sitzung. Parse it into a per-Sitzung, per-MdB table and show "entschuldigt" next to a Stimme "nicht abgegeben" where it applies.

**Why:** It is the only published statement about an MdB's absence (CONTEXT.md: entschuldigt). Without it the site can only say "nicht abgegeben", which readers may still read as skipping the vote.

**Context:** Needs the Person identity merge to map listed names to MdBs (the appendix gives names and Zusammenschluss, check whether it carries redner ids). Never derive "anwesend" from it: not being excused does not mean present.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Persist per-sitting acquisition state in the store (`protocol_acquisition`)

**What:** A `protocol_acquisition(protocol_id, component, state, fetched_at)` table written at persist time from each report's acquisition states (votes: `acquisition_state` as consumed by `render_vote_summary`; XML parsed or not; AI summaries), exported with the Daten CSVs; the facts engine and the Daten page read it instead of re-deriving it.

**Why:** The store cannot tell "no roll-call vote happened" from "votes were not fetched"; the state lives only in the report JSON. The facts engine (A1) gates week completeness from the in-memory `entries` and A0's replay re-derives the same map from the cached JSON, so two derivations of "complete" exist and can drift, and the download keeps a silent gap. Chosen at the eng review 2026-09-19 (D10: gate from entries now, schema later; D17: record).

**Context:** Needs a stable state vocabulary per component (`complete`, `partial`, `failed`, `not_requested` already exist for votes in `scripts/features/votes.py`). Natural B / Daten-pilot item.

**Update 2026-09-24 (v0.6.0.0 ship, adversarial review):** the D10 gap this item exists to close now has a concrete repro. `week_is_complete()` (facts.py) only iterates `week.protocols` - the protocols actually present in the store - so a sitting whose dossier fetch fails (`build_dossiers_with_progress`'s `dip.DipError` -> `continue` path, a real path, not synthetic) is invisible to the completeness check rather than failing it. Repro: seeding 1 of several expected sittings for a period yields `complete=1, publishable=1`. Self-heals once the missing sitting is later acquired (`compute()` recomputes fully every build), but a wrong winner can publish and poison later baselines before that happens. Flagging the repro here in case it changes the priority math — see the database state review update below, which raises this to P2.

**Update 2026-09-24 (database state review):** raised to P2. Since A1 shipped, the facts engine publishes on every build, so this is now a live path to a wrong published card, not a hypothetical. A cheaper first slice than the full table: have `build_dossiers_with_progress` record the protocol ids it skipped on `dip.DipError`, and make `week_is_complete()` fail any week containing one.

**Update 2026-09-29 (fix-votes-completeness):** the repro above is fixed. Facts periods are judged against the DIP catalog (`facts.sitting_gaps`, `period_gaps`), so a sitting whose dossier failed or was never built keeps its period incomplete, and reports without acquisition metadata count as unknown. What remains for this item is the duplicate derivation of "complete" (build entries vs the cached JSON) and the silent gap in the Daten download, so priority drops to P3.

**Effort:** M
**Priority:** P3
**Depends on:** None (A1 works without it)

### Line-by-line audit of the ingestion modules

**What:** Review `scripts/validate_dip_protocol.py` (XML parsing, roll-call scraping, DIP enrichment) and `scripts/abgeordnetenwatch.py` line by line, adding fixture tests for every parse branch that has none. Include the roll-call `fetch_html` path, which has a 60 s timeout but no retry/backoff, unlike `ApiClient.get_json`.

**Why:** `docs/audit-remediation-plan.md` (2026-08-18, "fog of war", Task 8) named these two modules, then at 56% and 40% coverage, as never audited, and they do all the acquisition and identity work. The `SPDSPD` doubled-`<redner>` bug under `parties.name` is the kind of source quirk such an audit finds. No evidence it was done, and it was never mirrored here.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Site hosting plan for the 2.5 GB generated site

**What:** Make the HTML deployable under a capped static host (e.g. GitHub Pages' 1 GB limit). Measured 2026-09-19: 2.5 GB total; `data/` 1.4 GB (`plenarprotokoll-*.json` 607 MB, `bills.json` 386 MB, `exports/` 91 MB); `protocols/` 584 MB for 285 dossiers. **Without `data/` the site is still 1.11 GB**, so a deploy profile that only excludes `data/` does not fit; the dossiers have to shrink too. Pieces: (a) extend `--data-base-url`-style externalisation to the `data/plenarprotokoll-*.json` links on `puls.html`/dossiers and to `bills.json` (the base-URL pattern exists for the two export files); (b) shrink dossiers — see "Move the hidden dev-view API dump" below: ~952 KB of hidden markup per dossier × 285 ≈ 270 MB, so rendering it into a separate on-demand file roughly halves `protocols/`; (c) or pick a host without the cap.

**Why:** The Daten page and `--data-base-url` make the *data* shippable to a public audience; the *site* itself cannot go to a capped host today. Both outside voices in the `/autoplan` review flagged this; the user's go/no-go framing ("ship to a larger audience in a few weeks") depends on the site being public, not only the download.

**Effort:** L
**Priority:** P1
**Depends on:** None (absorbs the former "base URL for report JSON" item)

### Scheduled data-release workflow

**What:** A GitHub Actions workflow on a schedule: online build → export → immutable dated release tag → upload assets → `--offline` rebuild with the release's `--data-base-url` → deploy.

**Why:** The design doc's own constraint is "must stay current automatically"; a manual `scripts/publish_dip_pulse_data.sh` is upkeep a solo maintainer will eventually miss. The user's explicit decision at the Final Gate keeps PR2 manual for now; this is the follow-up once that has been exercised a few times.

**Effort:** M
**Priority:** P2
**Depends on:** **Blocked** — PR2 (`scripts/publish_dip_pulse_data.sh`) is not written yet (2026-09-19: the script does not exist, `.github/workflows/` holds only `ci.yml`, no GitHub release exists); a `GITHUB_TOKEN` with release-upload scope as a repo secret.

### Pilot gate: decide keep/remove for the Daten page

**What:** 8 weeks after the first public data release, decide keep/remove using `gh release view --json assets` download counts, any inbound question or citation, and whether the builder himself used the downloaded file for anything.

**Why:** The user's own go/no-go framing ("if it doesn't work for v1, that is not a deal breaker"); the audience ("developers and researchers") is chosen, not demand-tested, so this is the cheap way to find out without a demand study.

**Effort:** S
**Priority:** P2
**Depends on:** **Blocked** — first public release (PR2); as of 2026-09-19 no release exists, so the 8-week clock has not started.

### Make the build revision reproducible before the release script passes a tag

**What:** `resolve_commit` hashes porcelain `git diff HEAD --binary`, whose bytes depend on the user's git config (`color.ui=always`, `diff.noprefix`, `diff.mnemonicPrefix`, `core.abbrev`, `diff.external`, which also runs that tool) and inherited `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE`; a 30 s timeout gives a constant `-unverified`. The release gate in `export_distribution_data` only looks for `-` in the string, lets untracked or modified `CODEBOOK_INPUT_FILES` through, and no production caller passes a tag yet. Fix: `git diff-index -p --binary --full-index --no-ext-diff --no-textconv --no-color --no-renames HEAD` with `-c core.abbrev=40 -c diff.noprefix=false -c diff.mnemonicPrefix=false` and the `GIT_*` variables removed; a timeout fallback that still moves with edits; gate on `re.fullmatch(r"[0-9a-f]{12}", commit)` and tracked, unmodified authored inputs; a test that a `local` export accepts dirty, unverified and `None` revisions; a real-git temporary-repo test; explain the suffix next to "Commit …" on the Daten page; wire the tag through the release script or a `--data-tag` option. Done when the same edit yields the same revision on any machine and a release export from a tree with an untracked authored input fails.

**Why:** Deferred by the owner during the codebook /ship (2026-10-30, decision D6): every gap bites only when a release tag is passed, which nothing does until the release script exists.

**Effort:** M
**Priority:** P1
**Depends on:** Scheduled data-release workflow

### Export robustness gaps found by the codebook review

**What:** (1) The publish step in `export_distribution_data` is not atomic: if renaming `datenstand.json` fails after `gen_dir.replace(published)`, the `finally` deletes the set-aside previous generation and leaves the old manifest over the new files; undo the generation swap on any failure after it and test the five untested cells (fresh and new-generation rename-in failure; fresh, new-generation and forced manifest-rename failure). (2) `validate_public_output` (`scripts/publication_state.py`) scans only HTML and three presentation JSON files, not `data/exports/**/DATA.md` or `datenstand.json`, so a local path pasted into an authored doc would ship with CI green. (3) Smaller: authored-input and licence-layer errors surface only after the store copy and CSV pass (pre-validate the dictionary shape and the licence doc's `## ` section first); `render_daten_recipes` defaults `data_base_url` (make it a required keyword); `_recipes_hash` raises a raw `KeyError` for an old-shape caller recipe; decide whether recipe CSVs keep formula-leading text unchanged now that they are plain double-clickable `.csv`. (4) Found in /ship runs 4 and 5 (2026-10-30/31), none reachable with today's inputs: export `RuntimeError`s (dictionary drift, recipe failure, copy failure) escape `main()` as a traceback after the store was persisted, so no site renders (pre-existing pattern; run the dictionary check against the source schema before the copy and decide whether `main()` turns them into `data_export_error`); recipe definitions are checked one way only (a definition with no SQL column passes); `_protocol_wahlperiode` accepts Unicode digits; `_demote_headings` treats a fence line with an info string inside an open fence as a close, ignores 1–3-space-indented fences and setext headings, and `_license_notice` has the same edges; `_PLACEHOLDER_RE` rejects legitimate text (`XXX-Straße`, `??`) and `_authored_text`'s bare minimum length 8 rejects short units such as „Anzahl“ (name it or drop it); `_write_recipe_csv` writes `str()` of a BLOB (`b'…'`) or float repr, and a recipe with duplicate output column names collapses in `dict(row)`; `_md_cell` leaves `\r` from a CRLF-edited input in a table cell; DATA.md appends „.“ after the `--data-license` text, so the real short string (ending „LICENSE-DATA.md.“) prints „..“, and the line names only `--data-license` when the text came from `$BUNDESTAG_PULSE_DATA_LICENSE`; `_manifest_reusable` keeps an `export_format` parameter that `validate_manifest` overrides with the global; DATA.md's recipe section hard-codes „LIMIT 5“ instead of reading each recipe's limit (D2); `csv.writer(..., lineterminator="\n")` in `_write_csv` and `_write_recipe_csv` may not quote a bare `\r` on Python 3.11/3.12 (3.13 does), against DATA.md's „Zeilenumbrüche bleiben unverändert“; set the quoting explicitly and test it. Done when each item has a fix and a test, or a recorded decision.

**Why:** Deferred by the owner during the codebook /ship (2026-10-30, decisions D4 and D7). (1) predates the branch and the window is narrow; (2) guards a leak that does not exist today. (4) is latent, cosmetic or naming, deferred under the CLAUDE.md fix-now-or-defer rule (2026-10-31).

**Effort:** M
**Priority:** P2
**Depends on:** None

### Recipe SQL disagrees with the site's own counting rules in edge cases

**What:** (1) r4 and r5 take the "first" sitting by lexicographic `MIN(document_number)` ("21/100" < "21/99"); order numerically (D5). (2) r4 ranks by `ABS(yes_count - no_count)` with no guard, and the vote parser stores a block without `data-chart-values` as 0:0:0:0 (`validate_dip_protocol.py` pads with 0, `persist_dip_pulse_store.py` `int(total.get("yes") or 0)`), so such a vote would rank as the narrowest; `facts.py` already guards with `yes_count + no_count > 0`. 0 such votes in reference export g-c1944485a5d4. (3) r3 excludes only `fraktionslos`; the site's Abweichung rule (`derive.vote_abweichler`) also skips the `Unbekannt` group and groups whose member votes do not match the fraction counts (`partial`). (4) Check whether the shared „Unbekannt“ speaker record (`resolve_speaker` for an unnamed Redner) reaches `mp_canonical` and so r1/r2; 0 such rows in the reference export. (5) r6 groups on the raw `origin_json` urheber, while the vote panels (`derive.vote_committees`) strip and de-duplicate each name, and its `LIKE 'Beschlussempfehlung%'` is case-insensitive where the site's `startswith` is not; neither differs on today's DIP strings. Each change moves published figures: report old and new rows per the CLAUDE.md pre-release rule. Done when each recipe matches the site rule or DATA.md names the difference, with old/new figures recorded.

**Why:** Found by the codebook /ship runs 4 and 5 (2026-10-30/31); deferred because each would move recipe figures and needs its own measurement.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Export cache key: too broad with git, too narrow without

**What:** `EXPORTER_SHA256` hashes the whole 13k-line `build_dip_pulse_site.py` and `commit` carries a hash of the whole tracked diff, so any edit forces a full ~290 MB re-export (D4); rewrite only DATA.md when only the revision or unrelated code moved. In the other direction, with no git (`resolve_commit()` is `None`) edits to `facts.py` (`wahlperiode`, `FACTS_TABLES`) or `persist_dip_pulse_store.SCHEMA_VERSION` do not change the key, and DATA.md quotes CONTEXT.md and ADRs 0001/0002 that are not in `codebook_inputs`, so a reused generation can keep a stale DATA.md. Done when the key covers exactly what DATA.md and the CSVs are built from, with a test per input.

**Why:** D4 deferred by the owner on 2026-10-30; the narrow direction was found by the run-5 adversarial review (2026-10-31).

**Effort:** M
**Priority:** P2
**Depends on:** None

### Codebook follow-ups: licence layers and test hygiene

**What:** (1) The CC BY metadata layers (`eigene-metadaten`, `eigene-metadaten-zuordnung`, `eigene-auswertung-uebernommene-quelldaten`) accept `dip`/`bundestag.de` tags, so whether e.g. `mps.identity_key` (built from DIP/XML names) is own metadata rests on authoring judgment; decide per column. (2) Join tables tagged `bundestag.de` may need their own bundestag.de licence layer instead of a DIP one. (3) The Unbekannt party row is not described under `parties.name`. (4) `test_codebook_describes_all_real_columns_and_snapshot_coverage` packs ~40 assertions with negative string pins; `test_codebook_matches_stored_codes_and_period_units` and `test_authored_definitions_distinguish_sources_units_and_exact_quotations` grep German fragments; derive expectations from the store or code where possible (/test-audit). (5) The embedded short string says „Details in LICENSE-DATA.md“, a file only a published release carries; say so in DATA.md or ship the file with every export. (6) DATA.md links into github.com/LucaAlv/poliwatch (the B4 audit link) and names repo paths; check the repo is public before a release cites them. (7) `person_records.home_person_id` can keep a retired person id within one generation (`person_registry.merge` repoints `person_id` but not `home_person_id`), while DATA.md's alias line speaks only of cross-generation joins; latent today (0 merges in `scripts/person_corrections.json`). (8) The audit's "Could not verify" list (docs/research/codebook-dictionary-audit-2026-10-31.md section 3). Done when each has a decision or a fix.

**Why:** Informational findings from the codebook /ship runs 4 and 5, deferred under the CLAUDE.md fix-now-or-defer rule.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Validate final merged A1/A2 before the A3 backfill

**What:** Finish Claude's paused A2 follow-ups on `right-counts`, review [the A1 identity/schema handoff](docs/plans/a1-a2-contract.md), merge the final A2 changes with `a1-followups`, and repeat combined suite, fresh/incremental grouping, unchanged replay, links and export checks. The current scratch overlay validates an uncommitted A2 snapshot; it is not final merged validation.

**Why:** Claude reached its usage limit on 2026-10-05. The user explicitly requested completing A1 without waiting and recording this gate. A1 preserves schema 3/key version 1 and needs no new registry policy, but later A2 edits may affect grouping and page links.

**Priority:** P1
**Depends on:** A2 completion; must pass before A3 readiness is claimed. [A1 validation receipt](docs/plans/a1-validation.md).

### Cached report 21/50 no longer matches its XML

**What:** On the A1 reference cache (`right-counts-a1/after`), `--offline --repersist` stops at 21/50: "plenarprotokoll-21-50.xml is not the Plenarprotokoll XML of 21/50: agenda item set changed; reacquire the sitting report". Seen on 2026-10-14 with both the 02 tree (`b9e7946`) and the 03 tree, so it is not caused by the A.2 registry changes. Reacquire the sitting, or find which change made the cached agenda items and the XML disagree.

**Why:** A repersist of that cache refuses to run, so the A.2 reference replay had to leave the sitting out (284 reports, `docs/a2-validation.md`).

**Priority:** P2
**Depends on:** None

### Acquire ceremony addresses omitted from sampled plenary XML

**What:** If ceremony addresses are to be ingested, acquire an explicit ceremony source and define its sitting association. The inspected 2016 and 2021 memorial speeches precede their plenary sittings and are absent from the plenary XML; do not synthesize a guest unit or treat all role-less speakers as guests.

**Why:** A1's source-backed guest check corrects the original assumption that those guest addresses inflate delivered Rede counts, but cannot ingest text its source omits.

**Priority:** P2
**Depends on:** Separate source acquisition and evidence-backed association; see [coverage evidence](docs/plans/a1-validation.md).

### Harden the vote acquisition and catalog completeness paths (open review findings)

**What:** Findings from the /ship review rounds of fix-votes-completeness (2026-09-29) that were accepted, not fixed:
(1) `source_stale` (`validate_dip_protocol.enrich_with_api`) holds a genuinely vote-free sitting of the last 14 days partial when the list head is older, delaying its week's and month's vote Fakt by up to two weeks; (2) the judged range starts at the earliest stored sitting, so one old cached dossier turns `--backfill-incomplete` into a job of hundreds of sittings and nothing prints the range; (3) the `numFound` check in `fetch_protocols` hard-stops every build if DIP's count ever includes unretrievable documents, with no override; (4) report JSON, SQLite and the catalog file are written at different points, so a build interrupted between them leaves `--offline` judging completeness from new reports against an old store; (5) a build whose every refresh was skipped exits 0; (6) the build-wide roll-call page cache is a snapshot, and list pagination can shift under a long build (duplicates a boundary entry); (7) `namenslisten_entries()` has no outage cooldown, so an outage costs about 3 minutes per vote; (8) an empty list page after page 1 counts as the end of the list; (9) catalog entries in range with no usable number or date only warn instead of failing closed, and duplicate document numbers keep the last; (10) `api_records.matched_roll_call_votes` and `roll_call_vote_candidates` describe the fresh scan while `agenda_items[].votes` may be cached after a no-scan run; (11) some date checks use the wall clock, not `--today`; (12) a failed vote-detail page stops matching for the rest of that sitting; (13) an uncaught `JSONDecodeError` from the DIP API aborts a build; (14) the offline build trusts the cached catalog with no age check; (15) the in-progress ISO week can be judged complete.

**Why:** Each is a place where a build can publish a slightly stale fact, waste a long backfill, or stop. None was reproduced as a wrong published fact on the reference copy; they were found by reading the code. Codex adversarial and structured reviews of the final tree were unavailable (usage limit), so this list has Claude-only coverage.

**Effort:** M
**Priority:** P2
**Depends on:** None

### v1 coverage: every Sitzung from WP 18 to the present

**What:** Acquire a Dossier for every Sitzung the catalog lists for WP 18, 19, 20 and 21, and keep the store current. Measured on 2026-09-30 against the reference copy (`~/agent-runs/poliwatch/.context/dip-pulse-site/`), counting only Bundestag entries in the cached catalog:

| WP | In the catalog | In the store | Missing |
|---|---|---|---|
| 18 | 245 (2013-10-22 to 2017-09-05) | 0 | all 245 |
| 19 | 239 (2017-10-24 to 2021-09-07) | 0 | all 239 |
| 20 | 214 | 201 | 13, from 2021-10-26 to 2022-01-26 |
| 21 | 87 up to 2026-06-26 | 84 | 3, plus every Sitzung after the catalog snapshot |

The catalog itself is from 2026-08-25, and the store was last updated on 2026-06-22. A newer scratch copy (302 Sitzungen, backfilled 2026-09-29, per the fix-stored-values work) was not found; re-measure against the current reference store before starting. Done when the numbers above read 0 missing on a fresh authoritative catalog, and the README, PRODUCT.md and the Daten page state the covered range.

**Why:** PRODUCT.md (2026-09-30) sets v1 coverage at the Wahlperioden with structured Plenarprotokoll XML, which the DIP catalog lists for WP 18 onward (every WP 18–20 Sitzung has an `xml_url`; no WP 1–17 Sitzung does). Every long-term analysis is only as long as this coverage. A trend that starts in 2022 says little about change over time.

**Context:**
- WP 18 and 19 XML parse with today's code. Test on 2026-09-30 with 18/1, 18/100, 18/200, 18/245, 19/1, 19/100 and 19/239 against `parse_protocol_xml`: every `<rede>` under `<sitzungsverlauf>` is parsed. A1 now ingests the 35 explicitly typed written submissions in 18/100 separately; the 11 annex units in 18/200 and 29 in 19/239 are §31 declarations and remain excluded. See the A1 validation record. Before running the full backfill, check a larger sample of WP 18 and 19, including Sitzungen with Befragung, Fragestunde and Aktuelle Stunde, and the DIP enrichment path (Vorgänge, Drucksachen, roll-call votes), which this test did not touch.
- Speakers from the Bundesregierung have no Fraktion in the XML (45 of 117 Reden in 19/100). Sprechrolle handles this already (ADR 0001).
- WP 18 and 19 roughly triple the Dossier count, so the 2.5 GB site grows accordingly. That makes the P1 site-hosting item harder.
- Budget about half a minute per Sitzung plus votes. `--backfill-incomplete` and `--protocol-wahlperiode` are the tools.
- **B4 extractive descriptions (2026-10-28):** [plan](docs/plans/b4-extractive-antrag.md#a3-coordination). It needs no report field and no re-acquisition: the Antrag text is a third stage of `refresh_vorgang_cache`, keyed by Drucksache number, using A3's DIP pacing. If B4 lands before Phase 3, the Phase 3 Vorgang fill also fills the texts for WP 18–21; otherwise one online build afterwards does. Schema/export bumps: whichever branch merges second takes the next number. Add the text cache to `validate_store_gate.py`'s replay inputs, and the extraction states to the pilot metrics if B4 has merged.

**Effort:** M (mostly running time and checking)
**Priority:** P1
**Depends on:** The Rede-counting items (#68, #70, Zwischenfragen and Gastansprachen) should land first, so the backfill does not have to be recounted.

## Protokoll-Dossier

### Say when a count covers only Sitzungen mit Dossier

**Part 1 completed:** v0.23.4.0 (2026-10-29). Public copy says "Dossier": the Methodik's "Erzeugtes JSON" bullet ("Jedes Dossier verlinkt …", was "Sitzungsseite"), the overview heading "Erzeugte Dossiers" (was "Sitzungsdossiers"), and the internal component label "Dossiers" (was "Protokoll-Dossiers"). A test keeps the avoided names off both pages.

**What is left:** wherever a published count spans a range for which the catalog lists more Sitzungen than have a Dossier, say so, e.g. "in 60 von 94 Sitzungen (nur Sitzungen mit Dossier)". Audit on main at v0.23.1.0 (2026-10-29):
- Already disclosed: the Daten Datenstand ("N von M Protokollen im Katalog als Dossier erfasst", `render_daten_datenstand`), the votes archive footer ("Die Liste umfasst die Dossiers, die in diesem Build mit --detail-limit erzeugt wurden"), and the catalog's "Erzeugte Dossiers" tile and its "Nur mit Dossier" filter.
- Not disclosed: the Abgeordnete list's "Reden" column (`render_abgeordnete_index`), the puls.html header and Wochenvergleich, the Fakten pages and Methodik, and the speech counts on the Gesetzesvorhaben pages.

**Why:** CONTEXT.md "Sitzung mit Dossier": every count covers only Sitzungen mit Dossier, because the store is rebuilt only from Dossier entries (`rebuild_database_from_entries`). A build with `--detail-limit` silently reports a subset as if it were the whole Wahlperiode.

**Context:** Wait for `worktree-a3-plan` to merge: it rewrites `render_abgeordnete_index`, extends `coverage_line` in `render_daten_datenstand`, and adds Fakten coverage text (`facts.coverage_label`, `fill_caveat`). Reuse those rather than adding a second coverage phrase.

**Effort:** S–M
**Priority:** P3
**Depends on:** `worktree-a3-plan` merged

## Puls

The week radar shipped in 0.3.0.0 (#58, 2026-09-18), so the remaining items are no longer blocked by it. The weekday comparison is completed below.

### Textanteil for the r2 Daten recipe, the rest of the ADR 0001 UI half

**What:** The data half is done, and so is puls.html (v0.23.6.0, 2026-10-29): the card is headed "Redeanteil der Fraktionen und Gruppen", lists every row (it cut at eight before, so a WP 21 week's Bundesrat or fraktionslos row could drop and the bars sum to less than 100 %), and sets fraktionslos, Bundesregierung, Bundesrat, weitere Sprechrolle and Unbekannt apart below a rule; its note says "Zuordnung für N von M Reden erfasst". What is left is the recipe: rename r2 "Redeanteil je Fraktion nach Zeichen" to a Textanteil ("Textanteil je Fraktion oder Gruppe") sorted by characters, not by Reden. Done when no share by characters is called Redeanteil.

**Why:** CONTEXT.md (Redeanteil, Textanteil, Redeanteil je Zusammenschluss, 2026-09-25).

**Context:** `worktree-a3-plan` rewrites r2's SELECT, ORDER BY and caveat (per-Wahlperiode shares), exactly the lines this needs, so do it on or after that branch. A changed recipe SQL makes every earlier export's manifest invalid as an override (by design since v0.23.6.0).

**Effort:** S
**Priority:** P3
**Depends on:** `worktree-a3-plan` merged (it rewrites r2)

### "Nächste Sitzungswoche" in the puls.html header

**What:** Show the next planned sitting week from the Bundestag Sitzungskalender when the page is opened during a non-sitting week.

**Why:** The Bundestag sits about 21 weeks a year; most visits land in a non-sitting week and today the page can only say how old the last week is ("vor 13 Wochen · Auswertung vom …").

**Context:** Needs a fetch of the Sitzungskalender and a cache field; the offline rebuild must keep working without it. Header wording and placement are specified in the week-radar design doc (stale-archive state). Start: `scripts/build_dip_pulse_site.py` fetch step + `render_front_page` header.

**Effort:** M
**Priority:** P3
**Depends on:** None

### LLM five-word topic label per Tagesordnungspunkt

**What:** Generate a short neutral topic label (about five words) per TOP once, cached alongside the KI-Zusammenfassung, and use it as the radar row's headline — and as the dossier "Meiste Reden" row title, replacing the deterministic boilerplate-stripped fallback now used there.

**Why:** The DIP Vorgang title is up to 200 characters and, for Antrag-only groups, the lead title is one Fraktion's slogan chosen by DIP ordering. A generated neutral label reads in five seconds and sidesteps the lead-title problem; the Vorgang title stays as the deterministic fallback.

**Context:** The summaries pipeline (`--summary-mode`) already calls an LLM per TOP with receipts; add one more field to its output. Dossier ranking rows now strip boilerplate when they use an XML heading; radar rows still prefer the DIP Vorgang title and otherwise truncate the raw XML heading. The generated label would replace both display paths. Of 459 ranked top-5 rows in the cache, the 61 without a DIP title are Einzelpläne, Regierungserklärungen and "Zur Geschäftsordnung", all already subject-first.

**Effort:** L
**Priority:** P3
**Depends on:** summary data available

### Five-reader comprehension test of the week radar

**What:** Sit five intended readers in front of the week radar and a plain weekly index of the same week; ask what happened, what changed, where they would verify it; measure correct answers and time.

**Why:** The plan verifies rendering and numbers, not whether a citizen understands the week better (Codex CEO-review challenge). The June design doc's "honest test" is the builder's own use.

**Context:** No code. Use a frozen build (`--today`/`--week`) so every reader sees the same page. Record answers per section (header, rows, Außerdem, Wochenvergleich).

**Effort:** M
**Priority:** P3
**Depends on:** None

### Week radar as data: `data/week-radar.json` and an RSS feed

**What:** Emit the radar rows (titles, shares, Fraktion split, trace, links) as JSON and as an RSS item per sitting week.

**Why:** The week's five topics reach readers without a visit; `week_topic_rows()` is already the data product, so this is a second renderer over the same rows.

**Context:** Add to `render_site()` next to the existing `data/` outputs; keep the offline rebuild path. Feed item = one sitting week; GUID = ISO week key.

**Effort:** M
**Priority:** P3
**Depends on:** None

## Fakten

Design doc: `docs/designs/fakt-der-woche.md` (office hours, 2026-09-19). The session chose Approach A (engine + two metrics + one weekly SVG card + Methodik, registry-shaped) as a **test run** of the concept; Approach A (A0 + A1, all eight metrics, weekly and monthly) shipped in v0.6.0.0. The items below are Approach B/C, the full implementation A was the test for. They are deliberately not discarded.

### Fakt der Woche, rasterize and post one card

**What:** Open a published Fakt der Woche card, rasterise it with `qlmanage` (or equivalent), and post it. The one A1 "done when" criterion that isn't code - split out on its own so it doesn't keep a fully-shipped engineering item sitting open.

**Why:** A1's design doc lists this as part of proving the cards are postable; intentionally not gated on the v0.6.0.0 ship (2026-09-24 ship decision D1: manual/promotional action, unrelated to code correctness).

**Effort:** S
**Priority:** P3
**Depends on:** A1 shipped (done)

### Fakt der Woche, publication ledger (`facts_published`)

**What:** A `facts_published` table (or a JSON file under `data/`) appended the first time a week's card is selected, preserved across online rebuilds the way roster rows are (`rebuild_database_from_entries`, `scripts/build_dip_pulse_site.py:716`), never overwritten; the week page shows "veröffentlicht als … / aktuell …" when they differ.

**Why:** A1 only promises "spätere Wochen ändern frühere Karten nicht"; data corrections and metric version bumps can still change an old card, and the changed-winners report only lands in the build log. The ledger makes a posted card reproducible forever and lets the site show its own corrections. Chosen at the eng review (D11: 11A now, ledger recorded) on 2026-09-19.

**Context:** Needs a preservation path through the rebuild (like `preserve_roster`) or a file outside the store, plus two-value rendering on the week page. Not worth building before a card has actually been posted.

**Effort:** M
**Priority:** P3
**Depends on:** A1 shipped and at least one card posted

### One rule for a Tagesordnungspunkt's Thema (lead Vorgang), computed once at persist time

**What:** Compute a Tagesordnungspunkt's Thema/lead Vorgang once, at persist time, with `topic_identity`'s full rule (`derive.agenda_procedures`: `mitberaten` twins, `equal_weight`), and store it. `LEAD_POSITION_CTE` (`scripts/facts.py`) and the `_lead_position_topic` TEMP table in `build_dip_pulse_site._ensure_lead_position_tables` then read the stored value instead of re-implementing a simpler rule in SQL (no twins, no `equal_weight`).

**Why:** Until the rule exists once, the Wochenradar and a Fakt card (`laengste-debatte` and the other metrics that name a topic) can name different Themen for the same TOP. Split from the `meistdiskutierter-vorgang` item (done 2026-10-30, see Completed), whose metric no longer uses a lead Vorgang at all.

**Context:** Adds a stored column to `agenda_items`, so it touches the store schema; do it with or after "The store owns its schema and its rebuild". Any metric that names a topic then needs a version bump.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Fakt der Woche, Approach B: site-wide facts layer (full implementation)

**What:** On top of A1: MP-level metrics via `mp_canonical` (a TEMP table `facts.ensure_canonical` fills from the persisted `mps.person_id`) (first speech in the Bundestag, longest speech of the WP, lone dissent against the own Fraktion; never attendance rankings), proceeding-level metrics (see Approach C), badge hooks in the dossier and MP renderers ("in dieser Woche: knappste Abstimmung der Wahlperiode", "hielt die längste Rede der 21. Wahlperiode") that read from `facts`, and an Open Discourse-compatible export view/CSV variant (their column names for `speeches`, `contributions`, `politicians`, `factions`, `electoral_terms`) so WP20/21 slots into existing notebooks. Done when every badge on a rebuilt site resolves to a `facts` row and the compatibility CSVs load in an Open Discourse notebook unchanged.

**Why:** A0/A1 prove the rule on a side page; B is the distinguishing feature on every page ("every number on this site knows how unusual it is") and the "build on my work" surface. Decided at office hours 2026-09-19: A is the test run, B is the full implementation, not discarded.

**Context:** Adding a metric is a registry entry plus a test once A's shape exists. The badge hooks touch `render_vote_summary` (`scripts/features/votes.py`) and the MP page renderer; keep the fixed Fraktion order and the "kein Redebeitrag" rule from the Plenarwatch-Lücken items. Open Discourse's `contributions` parsing is the reference for the Zwischenrufe item below. feed.json/RSS stay behind the Daten pilot gate.

**Effort:** L
**Priority:** P2
**Depends on:** A1 shipped and A0's pass criteria met

### Fakt der Woche, Approach C: proceeding-trajectory metrics and a timeline page

**What:** A third metric family over the joins (returns of a proceeding to the plenary, speech volume across its debates, final roll-call margin) with a `fakt/<year>-W<ww>.html` card that opens a per-proceeding timeline (debates → speakers → documents → votes). Done when the timeline renders for a proceeding with ≥3 plenary appearances and the card states "seit Beginn unserer Abdeckung (Januar 2022)" wherever a count is censored by the store's start date.

**Why:** Codex's lateral at office hours 2026-09-19: the joins are the asset the corpora lack, and a card that opens a story beats a number. Deferred behind A and B because it needs a bill/timeline page that does not exist and better proceeding titles (see "LLM five-word topic label per Tagesordnungspunkt" under Puls).

**Effort:** L
**Priority:** P3
**Depends on:** Approach B; a bill/timeline page; the LLM topic-label item

## Gesetzesvorhaben


## Abgeordnete

### Store DIP `person_roles` so a Rede without a Zusammenschluss uses the Zugehörigkeit of its Wahlperiode

**What:** ADR 0001 says a Rede whose Plenarprotokoll names no Zusammenschluss counts for the speaker's Zugehörigkeit on the date of the Sitzung. The store keeps no membership history: `mps.person_roles_json` is DIP's `funktion` list, and `compact_person` drops DIP's `person_roles` (fraktion and Wahlperiode per role). The Rede therefore counts for the speaker's party as the store holds it. Keep `person_roles`, and let `derive` pick the role of the Rede's Wahlperiode.

**Why:** Measured 2026-09-29: only 1 Rede (20/109 ID2010905000) has neither a Zusammenschluss nor a Sprechrolle, so the approximation costs almost nothing today; `compare_store_values.py` reports the count so it stays visible.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Fakt cards cut off the caveats of `knappste-abstimmung` and `meiste-abweichler`

**What:** `facts.render_card_svg` keeps two lines of 76 characters of a metric's caveat (`wrap_lines(..., max_lines=2)`). The caveat of `knappste-abstimmung` wraps to 4 lines and that of `meiste-abweichler` to 5 (measured 2026-10-30), so their cards show half a sentence. Shorten the caveats (or give the card room for them) and pin every caveat's line count with a test, as `meistdiskutierter-vorgang` now has.

**Why:** D27: a metric may not be read without its caveat, and a card is read without its page.

**Effort:** S
**Priority:** P2
**Depends on:** None

### List MdBs in a government office as Abgeordnete

**What:** DIP's `funktion` holds only a person's current office, so 48 WP 21 MdBs whose office is Parl. Staatssekretär (27), Bundesminister (8), Staatsminister (7), Vizepräsident(in) (4) or another government one are not in the roster: the Abgeordnete list has 589 of about 630. Their Mandat shows in DIP only as a `person_roles` entry with a `fraktion` for the Wahlperiode, and not even that for some (Merz, Dobrindt, Dorothee Bär, Wadephul: roles end at WP 20 on 2026-10-30), so DIP alone cannot list all of them; the Bundestag's MdB-Stammdaten (MDB_STAMMDATEN XML, with MDBWP_VON/BIS) can, and would also give Mandat end dates.

**Why:** They are MdBs (CONTEXT.md) and the list says it is complete.

**Context:** Tried 2026-10-30 with the `person_roles` rule (637 listed) and backed out: the registry's name guesses match on (name, party), and a Rede given as a member of the Bundesregierung has no party, so 29 of the 48 split into an Abgeordnete row without Reden and a separate Redner page with them (5 such splits before). Needs, first, a registry rule that joins a party-less Sprechrolle record to a roster record of the same name (`person_registry.match_rows`, A.2 territory: guard namesakes), then the roster rule (`derive.is_mdb_funktion` plus the Fraktion role, display name = the name segment of DIP's `titel`, Fraktion from the role when the top-level field is empty).

**Effort:** M
**Priority:** P2
**Depends on:** None

### Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs

**What:** Before 2026-10-30 the roster ingest flagged every DIP person whose `funktion` contained "MdB" as an MdB, which matched "MdBR" and "Stellv. MdBR" (151 Bundesrat members for WP 21). `person_registry.bind` records that as sticky `ever_mdb` evidence (`person_registry.py`, `evidence["ever_mdb"]`, `was_mdb`), so the registry still treats them as former roster persons: they stay page-eligible and `is_stale_roster_partner` can apply to them. Decide whether `ever_mdb` is re-derived from the exact rule (`derive.is_mdb_funktion`) or reset once for records whose only roster evidence is a Bundesrat funktion.

**Why:** No page now calls them Abgeordnete (the Personenseite derives "Mitglied des Bundestages laut Plenarprotokoll" from Reden, not from `ever_mdb`), but the evidence says something false about 151 people and feeds identity decisions.

**Context:** A.2 registry territory: needs a registry reviewer. Measure first how many person records carry `ever_mdb` with only Bundesrat funktion evidence on the reference store.

**Effort:** S
**Priority:** P3
**Depends on:** None

## Design

### DESIGN.md, tokens and a typeface decision via /design-consultation

**What:** Write a DESIGN.md (tokens, type scale, spacing, component vocabulary, focus/visited/selection rules) and decide the site's typeface. Name once the tokens individual pages had to invent, including the Daten page's light `--surface-2`/`--surface-3`.

**Why:** Every page carries its own `:root` token block and the only typeface is Inter / ui-sans-serif / system-ui; every design review re-derives the tokens and flags the default font stack. The Daten page (after the dossier) was the second page to have to invent tokens a shared system would already provide. No `DESIGN.md` exists as of 2026-09-19 (`docs/design/bundestag-pulse-design.md` is the product design doc, not a design system).

**Context:** The week-radar plan writes the radar's tokens into the plan instead. Start with `/gstack-design-consultation`; migrate per-page `:root` blocks to the shared header styles afterwards (the `:visited`/`:focus-visible` item under Daten is the first slice of that migration). Merged from two earlier entries (Daten and Design sections). The puls.html design review of 2026-09-28 also flagged its nested cards (section > panel > tile) for the same pass.

**Effort:** M
**Priority:** P3
**Depends on:** None

## Publication

### Add atomic/versioned publication promotion

**What:** Build a complete static publication in a staging directory, validate it, and atomically promote the validated version with a documented rollback path.

**Why:** The current in-place writer can leave a partial output tree after a late failure. The fixed-public release makes this safe by treating output as disposable and deployable only after exit 0 plus validation, but atomic promotion would prevent readers or deployment tooling from observing a mixed version at all.

**Context:** Start from `scripts/build_dip_pulse_site.py`, which writes many HTML/JSON files directly while SQLite alone uses temporary replacement. Design this together with the real deployment target: staging location, same-filesystem rename requirements, retained versions, cleanup, concurrent-build locking, and rollback semantics. Trigger this work when a deployment pipeline is added, the output directory is served while builds run, or concurrent writers become possible.

**Effort:** L
**Priority:** P3
**Depends on:** A concrete deployment/serving lifecycle

### Global header nav links to a page a build didn't write when its feature is off

**Update 2026-10-03:** superseded if "Delete the feature-selection axis" (Architektur) lands. Without a feature to switch off, there is no dead link to filter.

**What:** `render_global_header` (`scripts/render_dip_pulse_html.py`) accepts a `features: Selection` parameter but never uses it to filter `NAV_ITEMS` — every nav item renders unconditionally. `bills`, `abgeordnete`/`mp-pages`, `fakten`/`facts`, `database`/`store`, and now `votes` all skip writing their page when their feature is deselected (`write_pages`/`write_*_pages` returning early), so a build that deselects any of them still links every page's header to a file that was never written — a sitewide dead link for that nav entry.

**Why:** Found by Claude's adversarial `/ship` review (2026-09-27) while checking the `votes` nav entry this branch adds; the same gap already existed for the other four items before this diff, so this is a pre-existing pattern the branch extended consistently rather than introduced. The real published site always builds with every feature enabled (`publication_selection() = all_selection()`), so this has never actually produced a dead link in production.

**Context:** Fix once for all five items: filter `NAV_ITEMS` by a nav-key → component-id map (`votes`→`votes`, `bills`→`bills`, `abgeordnete`→`mp-pages`, `fakten`→`facts`, `database`→`store`) and call `features.enabled(component_id)` per item before rendering.

**Effort:** S
**Priority:** P3
**Depends on:** None

## Community

### Contribution governance: SECURITY.md, conduct rules, issue forms, contact channels

**What:** Implement ADR 0003 D5:
- `SECURITY.md` with a scope section, and GitHub private vulnerability reporting switched on.
- `/.well-known/security.txt` on the site.
- Short German conduct rules (no party politics in issues, no disparaging statements about people), linked from `CONTRIBUTING.md`.
- `.github/ISSUE_TEMPLATE/` with the „Datenfehler" and „Fehler auf der Seite" forms, auto-applying triage labels, and `config.yml` with `blank_issues_enabled: false` and a contact link to the Impressum e-mail for private matters.
- The site's `issues_url` link pre-fills the page URL in the Datenfehler form.

Done when a new issue can only be opened through one of the two forms and `security.txt` is served by the preview.

**Why:** Data-error reports are the most valuable contribution and need structure. Private requests (GDPR, corrections from the people concerned, press) need a non-public channel. On a political site, the conduct risk is party-political debate, which a generic code of conduct does not address.

**Context:** Decided 2026-09-29 ([ADR 0003](docs/adr/0003-licences-and-impressum.md), D5). E-mail is answered at the owner's discretion and only for matters that cannot be public. `security.txt` needs the final domain and the dedicated e-mail address, both also needed by the Impressum item.

**Effort:** S
**Priority:** P3
**Depends on:** Domain and contact address (Impressum item)

## Plenarwatch-Lücken

Gap list against [plenarwatch.de](https://plenarwatch.de/) (Plenarwatch GbR, München; 169 posts for WP 21 as of 2026-09-19). Their counting rules live on [/methodik/](https://plenarwatch.de/methodik/); read it before touching any item below rather than re-deriving the rule here. Coverage audit of our code on 2026-09-19: their vote tallies, per-sitting summaries, MP pages and bill tracking we already have (`scripts/features/votes.py`, `summaries.py`, `mp-pages`, `bills`); everything else in their nav (Feed, Zwischenrufe, Präsenz, Muster, Bundestag, Methodik) is a gap or partial. Excluded on purpose: Telegram/YouTube/Instagram and the "Unterstützen" page (distribution, not product).

### A tally-less neighboring decision with no document number of its own can still steal the official badge

**What:** `official_vote_result`'s document-number cross-check (this item's own commit) only refuses when the attributed text names a *different*, specific document number. A neighboring, tally-less decision (e.g. a unanimous show-of-hands item, which needs no "Gesamt"/"Ja: N" marker) that names NO number at all is indistinguishable from this vote's own legitimate number-less outcome sentence, and its outcome word can still be adopted as this vote's official result. Done when a fixture or live page demonstrating this shape is found and a fix (e.g. requiring positional/structural confirmation, not just absence-of-mismatch) is verified against it without regressing the fixture or any of the 8 real votes already pinned in the test suite.

**Why:** Found by the /ship red-team review (2026-09-27), same family as the Beschlussempfehlung-inversion badge caveat already shipped in 85411a4 ("acceptable only while the site is not public"). Latent: every real "Beschluss" narration checked so far — the project's own fixture and every live bundestag.de page fetched during this and the prior review round — attaches a document number to every decision it mentions, including tally-less ones, so this specific shape has not been observed on real data. A cheap fix was explored and rejected: requiring a document-number match whenever the lookahead line starts with a proposition keyword (Gesetzentwurf/Beschlussempfehlung/Entschließungsantrag/...) also rejects the fixture's own legitimate "Gesetzentwurf angenommen" case, which has the identical shape.

**Context:** The badge already discloses "(berechnet)" for any non-official result, so a bleed here would show a false-confidence "Laut Beschluss auf bundestag.de" label with the wrong outcome rather than the honest derived caveat — worse than the inversion caveat, which at least states the right raw counts.

**Update (2026-09-28):** narrowed: the outcome is now only read from the line directly under the tally (a blank "<br/><br/>" line ends the block), which closes the blank-line-separated shape. Still open: two decisions with no blank line between them.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Fraktionsblöcke: what each Fraktion argued, per Tagesordnungspunkt

**What:** Under every debated TOP, a block per Fraktion in the fixed order CDU/CSU, AfD, SPD, Bündnis 90/Die Grünen, Die Linke, fraktionslos (plus Bundesregierung when a minister spoke), each with up to three arguments paraphrased in indirect speech, each argument tied to a verbatim protocol quote ≤125 characters with a page anchor; a Fraktion without a speech gets the explicit line "kein Redebeitrag im Protokoll", never an empty block. Done when the order is enforced in code, every quote passes the verbatim check from the validators item, and the block renders on a full-week offline rebuild.

**Why:** Our summary is one neutral 2–3 sentence paragraph per TOP (`generate_top_summary`, `scripts/validate_dip_protocol.py:915-976`) with up to five receipt chunks; it says what was debated, never who stood where. Plenarwatch's "Was gesagt wurde" section is the part readers quote.

**Context:** The receipts pipeline already carries `speaker.fraktion`, `source_page` and 900-char chunks (`summary_source_chunks`, line 794), so the selection is a grouping over existing chunks: first verified mention per speaker, max three per Fraktion, sorted by protocol page; only the paraphrase is an LLM step. Render next to `render_llm_summary` (`scripts/render_dip_pulse_html.py:2241`), gated by `summaries`. The fixed order is a rule, never a prompt instruction.

**Effort:** L
**Priority:** P2
**Depends on:** Deterministic validators

### Deterministic validators that block LLM output before it renders

**What:** Four checks run on every generated summary/Fraktionsblock and fail the build item (falls back to "keine Zusammenfassung") when any fails: (1) vote-sum check, per-fraction `yes+no+abstain+absent == total_count` and fractions sum to the vote totals; (2) verbatim check, every quoted string is a substring of its cited chunk; (3) name check, MP surnames from `mps` appear in generated prose only inside an attributed quote; (4) link check, every generated or derived URL is well-formed and its Drucksache/protocol number matches the vote it sits under. Done when each check has a failing fixture test and the build log counts rejections per check.

**Why:** `parse_summary_response` (`scripts/validate_dip_protocol.py:846-873`) checks JSON shape and that cited chunk ids exist; nothing compares text to source, sums a vote, or looks for names. Plenarwatch lists exactly these as blocking checks on `/methodik/` and it is the basis of their "no interpretation" claim; the Fraktionsblöcke item is unsafe without (2) and (3).

**Context:** Pure functions in `validate_dip_protocol.py` next to `parse_summary_response`; (1) is independent of the LLM and can run at persist time on `vote_fractions`. Plenarwatch also splits writer and validator into two model calls with published prompts; keep that as a follow-up, the deterministic checks come first.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Fraktion seat counts in the store

**What:** A `party_seats` table (`party_id`, `wahlperiode`, `seats`, `valid_from`) filled from the mp-roster enrichment (count of roster rows per Fraktion) with a bundestag.de Sitzverteilung override; exported in the Daten CSVs. Done when `SELECT sum(seats)` for WP 21 equals the roster size and a per-seat column appears in recipe R2.

**Why:** `parties` has `id, name, created_at, updated_at` only (`scripts/persist_dip_pulse_store.py:71-76`); every per-Sitz or share-of-Fraktion number (Zwischenrufe, Präsenz, Redeanteil) needs a denominator, and the `parties.name` duplicate bug under Daten shows why it must be one clean row per Fraktion.

**Context:** Small; the roster count is already computable from `mps.party_id` once the duplicate rows are merged. Fraktionslose count as their own row.

**Effort:** S
**Priority:** P2
**Depends on:** `parties.name` holds Python-list-repr duplicates of the same party

### Zwischenrufe: parse `<kommentar>` and count reactions per Fraktion

**What:** Persist every `<kommentar>` element of the protocol XML (the parenthesised "(Beifall bei der SPD)", "(Lachen bei der AfD)", "(Zuruf des Abg. …)", "(Widerspruch …)", "(Unruhe)") as rows in a `reactions` table: sitting, speech, kind (Beifall / Lachen / Heiterkeit / Zuruf / Widerspruch / Unruhe / other), source Fraktion(en) parsed from the text, page. A `zwischenrufe.html` page then shows per-Fraktion counts with four views: absolut, kumulativ, pro Sitz, gleitender Schnitt over sittings, plus totals since a named cabinet date. Done when the reactions CSV is on the Daten page and the page's totals match a SQL recipe.

**Why:** Speech text no longer includes `<kommentar>` (`speech_text_and_paragraphs`, `scripts/validate_dip_protocol.py`, since the Rede-text fix; 6 of 34,771 stored Reden contain "(Beifall bei", checked 2026-09-30), so the signal is dropped entirely rather than typed and counted. It is the data behind the long-term question "who interrupts the debate most" (PRODUCT.md). Plenarwatch's Zwischenrufe tracker is their most-shared page.

**Context:** Element name per the Bundestag DTD `dbtplenarprotokoll.dtd` (`kommentar` inside `rede`); verify against a live cached protocol before writing the parser, since no XML is cached in `.context/` today. Fraktion attribution is a regex over a small closed vocabulary ("bei der", "bei Abgeordneten der", "des Abg."), keep an `unattributed` bucket rather than guessing. 

**Effort:** L
**Priority:** P2 (raised 2026-09-30: long-term angle, PRODUCT.md)
**Depends on:** Fraktion seat counts in the store

### Präsenz: excused MPs from the protocol Anlage, participation per Fraktion over time

**What:** Parse the "Entschuldigte Abgeordnete" Anlage of each protocol into an `excused` table (sitting, mp, Fraktion), then a `praesenz.html` page with: share of each Fraktion that cast at least one roll-call vote per sitting (rolling average across WP 21), the latest vote split into abgestimmt / entschuldigt / weder noch, and the WP average. Done when every sitting with a roll-call vote has a row per Fraktion and the three buckets sum to the seat count.

**Why:** `parse_protocol_xml` (`scripts/validate_dip_protocol.py:325`) walks `sitzungsverlauf/tagesordnungspunkt` only; `grep -rni entschuldigt` is empty. Absent counts already sit in `vote_fractions`, so the page is the Anlage parser plus one query. Plenarwatch states the limit plainly ("weder noch" cannot separate absent from present-but-not-voting); copy that caveat onto the page.

**Context:** Anlage lives under `<anlagen>` in the same XML; verify the exact markup on a live protocol first (same caveat as Zwischenrufe). Sittings without a roll-call vote produce no data point, by design, say so on the page.

**Effort:** M
**Priority:** P3
**Depends on:** Fraktion seat counts in the store, Vote outcome badge

### Muster: agreement matrix, coalition patterns and Geschlossenheit

**What:** Three aggregates over all roll-call votes of WP 21: (1) Fraktion × Fraktion matrix, share of votes where both majorities voted alike (diagonal 100 %); (2) per-vote coalition pattern, which Fraktionen sided with the outcome, with "Koalition" meaning CDU/CSU + SPD; (3) Geschlossenheit per Fraktion, share of votes with a single vote value across all its members (one deviating member = "geteilt"). Ship first as three SQL recipes on the Daten page, then as `muster.html`. Done when the recipes run in the build and the page numbers equal the recipe output.

**Why:** The only adjacent metric is recipe `r3-abweichler` (`scripts/build_dip_pulse_site.py:1144-1170`), per-MP dissent counts. All three aggregates are queries over `vote_fractions`/`vote_members` that already exist; the page is a renderer.

**Context:** Recipes-first is the tracer bullet: the Daten page already executes SQL at build time and shows the result rows, so the numbers are public and checkable before any chart exists. Fraktionslose are excluded from the matrix and the coalition label, as on plenarwatch.

**Effort:** M
**Priority:** P3
**Depends on:** Vote outcome badge

### Link the vote panel's "namentlich" badge to `bundestag.html`

**What:** The vote panel (`scripts/features/votes.py`) names a namentliche Abstimmung without explaining it. Link its "namentlich" wording to `bundestag.html#abstimmen`, as the week radar's "namentlich abgestimmt" badge already does (depth-aware: the panel renders on dossiers under `protocols/` and on `votes/index.html`).

**Why:** The vote panel is where readers meet the term most. Left out of the explainer change (2026-10-30) because the panel is B-track code.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Impressum, Datenschutz and licence files before the site goes public

**What:** Implement [ADR 0003](docs/adr/0003-licences-and-impressum.md):
- `impressum.html`: Luca Veh as a private person; postal address and e-mail; citing § 5 DDG and § 18 MStV; the same person named as Verantwortlicher under § 18 Abs. 2 MStV.
- `datenschutz.html`.
- Both linked from every footer.
- `LICENSE` (MIT, code only, pointing to `LICENSE-DATA.md` for data).
- The short string from `docs/data-license.md` set as the default `--data-license`.
- The `lizenz` item on `sources.html` (the "Die genaue Lizenzformulierung … steht noch aus" placeholder in `scripts/build_dip_pulse_site.py`) replaced by the layer table.
- The site's machine-generated summaries labelled as such.

Done when `grep -rn "steht noch aus"` over the generated site is empty and every footer links Impressum and Datenschutz.

**Why:** Name and address are required for any non-private Telemedium (§ 18 Abs. 1 MStV). The DIP terms require naming the source and marking changes on redistribution. Hosting can't ship without either.

**Context:**
- Decisions are made (ADR 0003).
- Before launch, the ADR's open questions go to a lawyer, first of all whether a c/o address is enough under § 18 MStV. That answer decides which address goes in `impressum.html`.
- Re-check § 5 DDG and DIP no. 4d if donations are added.
- Blocks the hosting item, not the other way round.

**Effort:** M
**Priority:** P2
**Depends on:** Lawyer answer on the address (ADR 0003, question 1)

### Settle the roll-call source for redistribution

**What:**
- Check whether the Plenarprotokoll's „Endgültiges Ergebnis" also lists non-voters, or only Ja/Nein/Enthalten.
- Ask parlamentsdokumentation@bundestag.de whether the roll-call XLSX lists may be redistributed.
- If the answer is no, or only the XLSX carries the non-voters, source per-member votes from the protocol XML or from abgeordnetenwatch (CC0) instead.

**Why:** bundestag.de's default terms are private use only. The Open Data page calls the XLSX lists open data but names no licence (ADR 0003, open question 5).

**Effort:** S (check and e-mail); M if the source must change
**Priority:** P2
**Depends on:** None

### Debattenberichte: off-agenda topic mentions across a sitting week

**What:** A detector over speech text that, for a configurable term list, counts mentions per speaker, Fraktion and TOP, and emits a Debattenbericht row when a topic clears the threshold (≥10 speakers from ≥3 Fraktionen across ≥2 TOPs) while being on no TOP title; the report shows total / verified / unverified mention counts, first quote per speaker (max three per Fraktion, sorted by page) and the search terms used. Done when a fixture week with a planted off-agenda term produces exactly one report and a week without produces none ("a missing report is also a data point").

**Why:** Nothing counts topic mentions outside their TOP today (audit 2026-09-19). It is plenarwatch's distinctive post type, but a small share of their output (the Sachsen-Anhalt-Wahl report is the headline case), so it comes after the vote and Fraktion work above.

**Context:** Term list is data, not code (`data/debate-terms.json`); verification = the quote passes the verbatim validator. Reuse the Fraktionsblöcke quote-selection rule. Consider it a week-radar row type on `puls.html` rather than a new page.

**Effort:** L
**Priority:** P4
**Depends on:** Fraktionsblöcke, Deterministic validators

## Zitierfähiger Datensatz

PRODUCT.md (2026-09-30) makes the dataset a product in its own right: a source researchers and journalists cite. Citable means a reader can name a version, get exactly those rows back later, and look up what changed since. Stable ids are complete; the release script, release changelog and DOI remain. The licence files and the roll-call redistribution question (both under Plenarwatch-Lücken) block any public release that contains votes.

When the first release goes out, the "Project stage: pre-release" section of CLAUDE.md has to become a stability policy: what may change between releases, and how a change is recorded.

### Stable ids for every row a release publishes

**Completed:** v0.12.0.0 (2026-10-02, A.2). Schema 3 / export format 2 supplies stable text row keys, a durable person/occurrence registry, corrections and resolvable aliases. Explicit offline replay upgrades old stores under a writer lock with staged integrity checks; facts, recipes and person URLs consume persisted assignments. All 997 tests pass (2 skipped); a 285-report reference replay preserves shared-source content, groups records identically for an incremental and a fresh replay, and reuses an unchanged replay. See [key and backup contract](docs/stable-ids.md) and [validation](docs/a2-validation.md).

**Pinned by tests:**
- Two builds, one with one more Sitzung than the other, give the same id to every row they share.
- Correcting a person's name, party or profile URL keeps their person key; a source that names a different Redner-ID or DIP id moves the occurrence instead.
- A person whose abgeordnetenwatch match turns trusted in a later build keeps their person key.
- Merging two persons leaves the merged-away key resolvable as an alias. Only merges that rest on a shared Personenkennung and reviewed corrections are durable; name-based guesses are recomputed, so an incremental and a fresh replay group records identically.

**Why:** A paper that cites "speech 18234" or links to an MP page must still point to the same thing next month. Before A.2 it did not: ids were insertion-order surrogates.

**Effort:** L (the person registry is most of it)
**Priority:** P1
**Depends on:** None

### Write the release script: versioned, immutable data releases

**What:** `scripts/publish_dip_pulse_data.sh`, referenced as "PR2" since the Daten page (#59) but never written. It publishes the export (SQLite, CSVs, manifest, checksums) as an immutable, dated release with a version number, and the site's `--data-base-url` then points at that release. Decide the version scheme: a date, or semver where a schema change bumps the major version.

**Why:** Without a release, "the dataset" is whatever the last local build produced. Nothing can be cited or downloaded twice with the same result. "Scheduled data-release workflow" and the Daten items are blocked on this.

**Effort:** M
**Priority:** P1
**Depends on:** Stable ids; licence files (ADR 0003); settle the roll-call source before releasing votes

### Public data changelog per release

**What:** Each release carries a `CHANGES.md` (in the release and on the Daten page) listing what changed in the data since the previous release: schema changes, coverage added, and every correction that moved a published figure, with old value, new value and reason. That is the old/new report the project already writes into commit messages (CLAUDE.md), made public and tied to a release. Keep a machine-readable twin (`changes.json`) so a researcher can check whether a figure they cited was affected.

**Why:** A researcher who cited version N must be able to see whether a later fix touched their numbers. The Fakt der Woche publication ledger covers cards only, and CHANGELOG.md covers code.

**Effort:** S per release once the format exists
**Priority:** P2
**Depends on:** The release script

### A DOI per release and a citation file

**What:** A `CITATION.cff` in the repo and a DOI for every data release. Zenodo's GitHub integration archives the repository's source zip on each GitHub release, not the release's data assets. So archive the data files through Zenodo's upload API from the release script instead, which gives a concept DOI plus one DOI per version. Show "Zitieren als …" with the version DOI on the Daten page and in the codebook.

**Why:** A DOI is what journals and editors accept as a stable reference, and it survives a change of host or name. The product name is still open, which matters little here: the DOI stays.

**Effort:** S
**Priority:** P2
**Depends on:** The release script; the product name (for the record's title, which can be updated later)

## Analysen

The long-term angle of the site (PRODUCT.md, 2026-09-30). None of it exists yet. Every series here counts Reden, so it waits for the Rede-counting items (#68, #70, Zwischenfragen and Gastansprachen, zu Protokoll gegebene Reden) and the v1 coverage backfill. Each recount moves every point of every series.

### Diskursanalyse: precomputed term series per Zusammenschluss and month

**What:** An `analysen/` page, and a Daten recipe that produces the same numbers. For a published, fixed list of topics, each defined by a term list (`data/terms.json`, reviewed like code): mentions per 10,000 words of Reden, by Zusammenschluss and by month (or quarter), across all covered Wahlperioden. Rules to fix before building:
- **Matching:** German compounds need an explicit rule, for example prefix match on word stems (`klima*` catches Klimaschutz and Klimawandel), plus a list of exclusions. Case-insensitive, on word boundaries. The rule is printed on the page.
- **Unit:** Reden only, per ADR 0001 and 0002. Zwischenrufe, Sitzungsleitung, Kurzinterventionen and Befragung are excluded, or later shown as their own series.
- **Normalisation:** per 10,000 words, because raw counts mostly track how much was debated.
- **Coverage:** only periods whose Sitzungen are complete, or every point labelled as covering Sitzungen mit Dossier only.
- **Reproducibility:** the chart is the recipe's result. The page says plainly that free search over any term is possible with the SQLite download, and links a ready-made query for it.
- **Traceability:** each point links to the Reden it counts.

Done when the chart and the recipe give the same numbers on the same release, and a test pins the matching rule on a handful of compounds.

**Why:** Decided 2026-09-30: precomputed series instead of free search on a static site, with free search delegated to the SQLite download. Term lists instead of a topic model are confirmed only provisionally. The user wants to see a preview before deciding, so the first step is a throwaway prototype: three topics, run over the reference store, drawn as a static chart, shown to the user. Build the page only after that decision. Open Discourse's Diskursanalyse, the named reference, uses 73 LDA topics with yearly granularity from 1949 to 2020. Published term lists are weaker at catching synonyms, but anyone can check and recount them, which fits a neutral, research-grade dataset.

**Context:** Start with a small set of topics (Klimaschutz, Migration, and a few more) and a neutrality review of the term lists before publishing. A term list that uses one side's vocabulary ("Klimakrise" vs. "Klimawandel") frames the result. Also consider filters that Open Discourse offers and the store can support: gender and age group from the abgeordnetenwatch columns.

**Effort:** L
**Priority:** P2
**Depends on:** The Rede-counting items; v1 coverage; stable ids

### Politikfelder over time: which Zusammenschluss emphasises what

**What:** Using the Politikfeld tags, show per Zusammenschluss and per period the share of its Reden (and of its speaking time by characters) that falls under each Politikfeld, and how the share of each Politikfeld in the whole plenary changes over time. Ship as a recipe first, then as a page next to the term series.

**Why:** This answers "which party has which priorities" and "how does attention to a topic change" (PRODUCT.md) from the agenda side, without depending on vocabulary. The term series answers it from the language side. The two complement each other.

**Effort:** M
**Priority:** P2
**Depends on:** Politikfeld tags; the Rede-counting items; v1 coverage

## Abstimmungen

### Abstimmungen for the daily view: what was decided, by topic, with dissenters

**What:** Close the gap to the abgeordnetenwatch.de Abstimmungen (checked 2026-09-30: their vote pages carry a plain-language description of what was decided, topic tags, the committees involved, the source documents and the named dissenters; the list filters by topic and date). For us:
1. A short description of what the vote decided. ~~The DIP abstract.~~ Done in B4: the panel's "Worum es geht" block shows the abstract of each Vorgang the vote's narrow Drucksache numbers resolve to (`politikfelder.vote_vorgang_ids`), and the store keeps it (`proceedings.abstract`, `vote_proceedings`, `votes.context_state`). 64 of 217 votes on the reference store have none (measured 2026-10-20 on a copy, the online refetch of all 86 empty-abstract context Vorgänge filled none, so votes with an abstract stay 153 → 153); those panels say "Keine Beschreibung in DIP". The factual lead and Bundestag report link below are implemented (2026-10-25); the extractive fallback remains open. The labelled AI sentence under the validators item is deferred (decided 2026-10-20).
   - **Done (2026-10-25): lead sentence from stored facts** on every panel, including panels with an abstract: date, recorded subject, interpreted outcome and raw Ja/Nein/Enthaltungen counts, immediately followed by the committee citation. Derived and unavailable outcomes remain labelled. [Implementation plan](docs/plans/b4-vote-lead-and-article.md).
   - **Extractive fallback from the Antrag itself:** quote section II ("Der Deutsche Bundestag fordert die Bundesregierung auf …") verbatim with a source line. A Drucksache is an amtliches Werk (§5 UrhG), so quoting is free. Implemented 2026-10-28 without real-data validation: [plan and status](docs/plans/b4-extractive-antrag.md#implementation-status-2026-10-28). Step 0 on real texts 2026-10-28/29 ([note](docs/research/b4-antrag-extraction.md)): DIP `drucksache-text` keeps list order, so it stays the source (D3); 32 of 37 Fraktion/Gruppe Anträge quoted, none known wrong, 89 % of those with a demands section (gate 90 %). Open items: [B4 extractive fallback: finish validation locally](#b4-extractive-fallback-finish-validation-locally-open-items-from-pr-113) and step 5 (reference-store before/after). Coordinated with A3 so the backfill's Vorgang fill also fetches the Antrag texts.
   - **Done (2026-10-25): “Bericht und Debatte beim Bundestag”** links the whole associated Textarchiv report through the vote’s bounded Debatte association. Repeated copies of one article are allowed; conflicting or missing article IDs omit the link. The nullable scraped `debate_url` survives report replay, schema 7 storage and format 8 export. No editorial body is copied or section-matched; shared articles such as 1005 are valid. Offline replay cannot discover a missing URL; targeted online refresh can.
2. ~~Topic filter on `votes/index.html`, from the Politikfeld tags.~~ Covered by B3 (done).
3. ~~The named Abweichler per Fraktion on the vote panel.~~ Done in B4 (`derive.vote_abweichler`; 632 Abweichler in 95 of 217 votes; archive rows carry the count where every group's Einzelstimmen are complete).
4. ~~The responsible committee, from the Beschlussempfehlung.~~ Done in B4: "Beschlussempfehlung des <Ausschuss> (Drucksache …)" on 190 of 217 panels, recipe `r6-ausschuss`. Mitberatende committees are the follow-up "Mitberatende Ausschüsse on the vote panel".

Done when a vote on the archive can be found by topic and its panel answers "what was decided, who voted how, who broke ranks, where is the source" without leaving the page.

**Why:** PRODUCT.md names this as the votes part of the daily view. The vote panel and archive (v0.7.0.0) already cover tallies, outcome badge and sources. They miss the "what does this mean" layer a citizen needs.

**Context:** Correctness items come first, above all the P1 "Inverted-vote reading for Beschlussempfehlungen". A plain-language description of a rejected Beschlussempfehlung that doesn't handle the inversion would be wrong. The remaining interpretation and replay defects are fixed in v0.22.0.0: see the completed "Vote reading misses half the inverted votes and never stores it" item. Full analysis of the bundestag.de vote pages (2026-10-20): [docs/research/bundestag-vote-pages.md](docs/research/bundestag-vote-pages.md).

**Effort:** M
**Priority:** P2
**Depends on:** Vote reading misses half the inverted votes and never stores it; deterministic validators (only for the deferred AI fallback in 1)

### B4 extractive fallback: finish validation locally (open items from PR #113)

**What:** Validate quoted-Antrag fallback coverage and fidelity, retaining measured failures as separate extractor follow-ups.

**Status: OPEN — validation executed 2026-10-29; acceptance gates fail.** [Plan](docs/plans/b4-extractive-antrag.md#local-validation-outcome-2026-10-29), [Run 3 evidence](docs/research/b4-antrag-extraction.md#run-3-local-reference-and-mid-period-validation-2026-10-29), [91-document audit](docs/research/b4-local-audit-2026-10-29.csv).

**Completed locally:**
1. Preserved the canonical `.context/dip-pulse-site` and a baseline copy (all 4,096 files hash-identical), created separate offline replay control and enriched working copy. No sitting reacquisition or A3 backfill. Artifacts: `.context/b4-local-20261029-163417/`.
2. Verified the renderer's narrow cohort: 217 votes, 153 with an abstract, 64 without. Descriptions **153/217 → 196/217**; 43/64 previously abstract-less votes gain quotes. Across all contexts, **50/71** candidate documents extract (**50/68** with verified demands); all 50 reference quotes are verified after the small v7 elision-hyphen fix. Wholly abstract-less subset: **43/60** candidate documents, **43/59** with demands.
3. Audited 20 mid-period A3-linked WP 18/19 documents (10 each). **16/20** extract (16/16 with demands), but **three passages are incorrect**: `18/2742` loses a hard hyphen, `18/3154` loses nine bullet markers, `19/16794` includes printer-footer text.
4. Counted misses and edge cases before changing extraction: ten interposed-anchor clauses in the reference cohort, one `dazu`, one `möge beschließen`, one demand without an explicit Bundesregierung object, four footnote misses, one direct motion to revoke a regulation, three documents without an applicable demands section. No unsupported inverted Bundesregierung anchor in either local sample. Empty texts **0/91**, so the conditional retry-on-`aktualisiert` fix was not triggered. No broader anchor or footnote rule was added.
5. Compared protected fields by stable IDs in SQLite. Tallies, member rows, tags, abstracts and links are unchanged by enrichment. Every old interpretation difference is reproduced without fallback by the offline replay control (formerly null derived results/scopes/inversion/procedure fields). Checked rendered quotes against stored documents/associations and export CSV/SQLite.
6. Ran compilation, full unittest suite, CI zero-network demo/publication checks and the Node browser runner. Chrome DevTools checked 906, 996, 1005, abstract 846, no_passage 997, and labelled disposable not_fetched/mixed states in light/dark and desktop/mobile. Fixed the missing-cache notice beside an existing quote. `/review` ran with native adversarial review; optional Claude retry was rejected by automatic approval review. Logs and exact check results are in the research note.

**Remaining:** ≥90% extraction coverage and zero incorrect passages are **not satisfied**. The historical cloud result (32/36 demand-bearing candidates, 89%, no known incorrect quotes in that sample) does not override the local results. Do not close this TODO or treat the 196/217 description percentage as the extraction gate.

**Smallest follow-up:** fix source fidelity first with real fixtures for `18/2742`, `18/3154`, `19/16794`, returning `no_passage` where lost source structure cannot be proved. Acceptance: zero incorrect accepted passages on the saved 91-document corpus. Then address measured interposed-anchor clauses and the `dazu` variant while retaining complete sentence openings; re-check cloud inverted cases `20/4666`, `19/30983` before supporting them. Re-audit until ≥90% coverage passes with failures retained in explicitly stated denominators. Substantial extraction work belongs in that separate session.

**Why:** The local audit found actual errors in quoted older-period texts. The reference population has now been read; fidelity beyond that population remains unproven until the failing sample documents are fixed or safely refused.

**Context:** PR #113, branch `claude/charming-lovelace-4a229o`; `EXTRACTOR_VERSION` 7. The Drucksache cache rides in the in-memory Vorgang cache under `antrag_text.CACHE_NAMESPACE`; A3 coordination is on the A3 entry.

**Effort:** M (remaining source fidelity and measured anchor follow-ups)
**Priority:** P2
**Depends on:** Saved local corpus; no new backfill required

### Mitberatende Ausschüsse on the vote panel

**What:** Keep `ueberweisung` (`ausschuss`, `federfuehrung`) from the 1. Beratung positions, which `compact_position` (`scripts/validate_dip_protocol.py`) drops today, and show "mitberatend: …" next to the Beschlussempfehlung line of the vote panel.

**Why:** abgeordnetenwatch lists the committees involved. B4 cites only the committee that issued the Beschlussempfehlung (D14).

**Pros:** Completes the "committees involved" picture; the data is already in the cached raw positions (1,650 `federfuehrung: true` entries).

**Cons:** `ueberweisung` sits on the 1. Beratung, not on the vote's TOP, so it needs a Vorgang-level join, and one more stored table.

**Context:** `api.raw.positions` in the cached reports; B4's `vote_proceedings` gives the vote→Vorgang link (D17).

**Effort:** S
**Priority:** P3
**Depends on:** B4

### B4 review findings: lower-priority edges

**What:** Edges the B4 `/ship` adversarial passes found (2026-10-22, Codex and a Claude subagent) and left open; the four that could lose stored data or stop a build were fixed on the B4 branch the same day:
1. No per-vote cap on "Worum es geht" blocks.
2. `abstract_text` output can differ across Python patch levels (it feeds the content-hashed export).
3. CSV formula injection now reaches free-text DIP columns (`proceedings.abstract`, titles).
4. The teaser can cut after "(Abs.".
5. `derive.vote_identity` uses the raw id while persist cleans it.
6. One member/count mismatch hides a whole group's Abweichler.
7. ~~`derive.vote_abweichler` dedupes member rows by name~~ Done 2026-10-22 (B4 Codex P2 F3): it dedupes on `derive.vote_member_identity`, the key persist hands `upsert_mp`, vote-wide. The 63 occurrences the old Abstimmung-page "profile URL" folded were unfolded by rebuilding the reference store's registry from scratch (2026-10-22, `vote_members` 154,078). Left: merges `registry.bind` makes later are not seen by derive.
8. `derive.member_profile_url` links an abgeordnetenwatch profile whatever its match kind, so a name-guessed aw match can put an external profile beside a named Abweichler (0 cached Einzelstimmen rows carry an aw URL; B4 ship run 2 adversarial review, 2026-10-22).
9. An online Vorgang refetch replaces the cached record whole (`cache["vorgaenge"].update(records)` in `build_dip_pulse_site.py`), so an answer without `titel` or `abstract` drops ones the cache had; the replay guard sees only `not_fetched` transitions.
10. `derive.vote_identity` turns an id of None into `"None"` when `fetch_targets` reads a fresh report before `require_vote_shape`; `features.votes.dip_vorgang_url` puts a non-digit Vorgang id into the DIP path unchecked.

Found by the B4 ship run 3 adversarial passes (2026-10-23, Codex and a Claude subagent) and deferred by the owner; none occurs on the reference data:
11. A Fraktion missing from both the fraction rows and the Einzelstimmen leaves the other groups "complete", so the panel can say "Niemand stimmt anders …" and the archive show 0 while `vote.total` shows the missing Stimmen. Require the groups' totals to equal the vote total before any vote-wide claim (`build_dip_pulse_site.py` `_abweichler_count`, `features/votes.py` `_abweichler_summary_html`). 217 of 217 reference votes have matching totals.
12. Pages and the Fakt `meiste-abweichler` / recipe `r3-abweichler` count Abweichler differently on an incomplete vote: `derive.vote_abweichler` withholds a group whose Einzelstimmen do not match its tally and excludes `Unbekannt`, the SQL (`facts.py`, the r3 recipe) does neither. Decide whether the SQL takes the page's completeness rule. 0 partial groups on the reference data.
13. `derive.report_drucksachen` keeps the first TOP's copy of a Drucksache while persist keeps the fullest, so an empty `urheber` first can make the panel say "Ausschuss nicht ermittelt" while `r6-ausschuss` counts the committee. D15 shows 0 of 217 differ.
14. ~~`derive.person_profile_url` accepts a `..` segment (`/abgeordnete/../apps/na/x` resolves to the Abstimmung page it exists to exclude).~~ Done 2026-10-30: a `.` or `..` path segment, also percent-encoded (`%2E%2e`), makes the URL no profile. No reference row carries one, so no stored value moves.
15. The 10,000-character cut in `dip_text.abstract_text` can leave a cut tag or entity (`<a hr`, `&am`) as visible text; the longest reference abstract has 5,111 characters.
16. html.parser is quadratic on runs like `'<a "'`: 10,000 characters take about 0.9 s per call, paid per persist and per vote panel. Computing the plain text once at cache-write time removes it.
17. Vote ids are not limited to anchor-safe characters, so an id with spaces makes an invalid `id="vote- 7 "` and an archive link that does not scroll (reference ids are numeric).
18. `.vote-context-block:has(…)` hides the teaser with no fallback (a browser without `:has()` shows it twice), and `ul.vote-abweichler-list { display:inline }` drops the list semantics in Safari/VoiceOver.

**Why:** 3 lets a DIP text run as a formula in a spreadsheet that opens the export. 11 is the one item that can make a public statement false.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Stale cached-report error lines: polish

**What:** From the B4 `/ship` review cycle 3 (2026-10-22), on a path no reference report hits (0 of 290). Points 2–4 are done (v0.23.6.0, 2026-10-29): a refusal whose remedy is a re-fetch prints the report's own number (`cached_report_fix`, `--document-number 21/82`), the stale-rule refusal says `--fetch-xml` and names for a re-fetch only the reports without an `xml_url`, an unknown contribution kind keeps its own remedy (`--offline --repersist`), the `[repersist]` remedy comes from the same helper and is asserted in full, `require_vote_shape` names the holder ("TOP 3: …", "sitting_votes: …") with a test for the `sitting_votes` branch, and README.md and the stale-rule refusal no longer promise that a plain update re-fetches a deleted report. Left:
1. The `--backfill-incomplete` stop still prints `CACHED_REPORT_FIX`, which names `--document-number`, a flag `parse_args` refuses next to `--backfill-incomplete`. Give that call site "move it out of data/ and re-run `--backfill-incomplete`" through `cached_report_fix`. Do it on or after `worktree-a3-plan`, which rewrites that block of `main()` and adds `--exclude-document-number` (which may be the better remedy).

**Why:** These lines are the only guide out of a stopped build; each should name a command that works.

**Effort:** S
**Priority:** P3
**Depends on:** `worktree-a3-plan` merged (it rewrites the backfill block of `main()`)

### Politikfelder: findings deferred from the B3 review

**What:** Nine findings of the /ship review (2026-10-09) that B3 does not fix:
1. A missing lead Vorgang or number makes the tags come from the survivors with the wrong lead, and the source says `sachgebiet` or `drucksache`, not that something was missing. Record a partial flag, or count partial results in the build summary.
2. A non-empty Sachgebiet or resolved number is never refreshed, so a changed DIP label never reaches the tags. Use `aktualisiert` (already cached) to refetch Vorgänge DIP has updated.
3. Pages derive the tags from the cache file at render time, the Daten tables hold the snapshot of the last persist. A plain `--offline` build after the cache changed shows different tags than it exports. Since B4 the same holds for the vote panels' DIP abstracts and their Vorgang selection (`proceedings.abstract`, `vote_proceedings`, `votes.context_state`). Put a cache digest into `datenstand`, or render from the store; one fix covers all three.
4. The cache sits in the published `data/` directory and holds DIP `abstract` and `titel` text, which the vote panels now show (B4), so dropping it is no longer an option. Settle with "Site hosting plan" whether `data/` is deployed wholesale; if so, hosting must exclude `data/dip-vorgang-cache.json` or the cache moves out of `data/`.
5. The inline filter scripts on `votes/index.html` and the week radar are checked only by a headless-Chromium probe run by hand (2026-10-09), not by the suite. Add a browser test when the suite has one.
6. A Vorgang DIP does not return, or a number it resolves to nothing, is stored as "fetched, nothing known" and counted as fetched, so an offline repersist stores `untagged`, not `not_fetched`, until the next online build. Empty Sachgebiet records (4,086 of 7,511 cached Vorgänge, most pulled in by numbers with a huge fan-out) and empty lookups are asked again on every online build, about 40 batches and a pause each; bound that with `aktualisiert` or a fetched-at date.
7. A Sachgebiet label the mapping does not know is skipped at tag time, so tagging can fall through to a weaker source; the build summary names the label afterwards. Consider a `not_fetched`-like source for an unmapped label.
8. A TOP that names many specific Drucksachen (a bundled Beratung) is tagged with the three most frequent of up to eight fields, in first-seen order on ties: the plan's cap of 3, not a measure of what the TOP is about (65 of 207 TOPs tagged through their Drucksachen carry more than 3 fields). Decide whether a TOP over some breadth should stay untagged.
9. A Bundesrat Drucksache whose number looks like a Bundestag one is skipped only in `linked_drucksachen` (by its `/brd/` URL), not in a vote's numbers or a heading. `load_cache` leaves a file it could not read in place, but an online build then overwrites it with what it has fetched. A non-empty `dokumentnummern` list is never refreshed, so whether a number is "narrow" depends on when it was fetched.

10. Two online builds on one output directory both fetch before either takes the writer lock: the DIP rate doubles, and the last cache save wins, so the other build's fetches are re-fetched next time (`build_dip_pulse_site.py` `refresh_vorgang_cache` call in `main`, before `rebuild_database_from_entries`). Take the writer lock before the fetch, or merge new keys under a lock before each save.
11. The fetch breaker counts any five failed calls in a row, so five permanently failing numbers in a row (a 4xx, an odd body) stop the number pass on every build and leave the rest `not_fetched`; remember per-number failures with a date, or trip only on challenge-like errors (`refresh_vorgang_cache.resolve_numbers`).
12. A non-JSON 200 is retried three times per call (`validate_dip_protocol.ApiClient.get_json`), about 15 extra requests during a bot challenge before the breaker trips.
13. The online rebuild has no guard against storing more `not_fetched` rows than the previous store (an outage during a first fill); only `--offline --repersist` has one (`require_vorgang_cache_for_tags`).
14. When the radar filter hides the last row, the last visible row keeps its bottom border (`.radar-row:last-child` matches by position).

**Why:** None of them changes a number in the real store today (0 not_fetched, 0 partial, one empty lookup), and each needs a decision beyond B3's plan. Items 10–14 were deferred in the v0.20.0.0 ship review (2026-10-19).

**Effort:** S each
**Priority:** P3
**Depends on:** B3


### Fill the remaining untagged Tagesordnungspunkte

**What:** The 103 TOPs of the real store whose heading names a Gesetz or Antrag but that have no Vorgangsposition and name no Drucksache, and the 31 "other" ones, stay `untagged` after B3. Tag them from the heading with a model, restricted to the closed list, stored with a source of its own (for example `llm`) so a reader can tell it from a DIP-derived tag. Leave Fragestunde, Befragung, Wahlen and Geschäftsordnung untagged: they have no policy area.

**Why:** B3 stays deterministic on purpose, so the Daten export carries no model output (docs/data-license.md). Measure first how many of the 134 a better deterministic rule can still reach, for example matching the heading against `/vorgang` titles.

**Effort:** S
**Priority:** P3
**Depends on:** Deterministic validators; a data-licence decision on model-written tags in the export

## Architektur

### Correct a cached report's XML Drucksache references at the source, not at every reader

**What:** A report cached before `validate_dip_protocol.extract_drucksachen` checked the link host keeps a number read off a quoted URL in `xml_drucksachen` (88/739016 from a syriahr.com link in 20/206), for good: `reparse_report_xml` re-reads Reden and Beiträge from the cached XML but not the Drucksache references. Since v0.23.6.0 every reader filters through `derive.xml_drucksachen` (persist, `item_document_numbers`, the dossier pills, the vote panel's link map), so nothing shows or stores it, but a new reader that reads `item["xml_drucksachen"]` directly brings the bug back. Either refresh `xml_drucksachen` from the cached XML in `--offline --repersist` (then the stored report is right and the filter can go after one replay of every cache), or filter once where reports are loaded (`load_existing_detail_entries`) and drop the per-reader calls.

**Why:** Found by the code review of v0.23.6.0 (2026-10-30). One correction at the source beats a rule every future reader has to remember.

**Context:** Refreshing from XML changes what a repersist writes into the cached reports, and `load_existing_detail_entries` is code `worktree-a3-plan` edits; do it after that branch. Check that `reparse_report_xml` keeps the API's `linked_drucksachen` untouched.

**Effort:** S
**Priority:** P3
**Depends on:** `worktree-a3-plan` merged


### A.2 follow-up ship review: deferred findings

**What:** Findings of the v0.19.0.0 ship review (2026-10-18) deferred by decision, P1 first: (1) **P1** `run_facts_engine` opens the store with `facts.open_readonly` and checks only `require_current_schema`, so the distribution-copy refusal in `pulse_store.connect` (`user_version`/`datenstand`) is skipped: `--offline --database-path` on an exported SQLite writes changed facts into that file before the export fails on `mp_canonical` (build_dip_pulse_site.py `run_facts_engine`, regression of d1a3b0d, reproduced by Codex); apply the build-store guard before computing or staging. Then: (2) `_replace_store` keeps the file mode but not the group, so a group-shared web root can lose read access after a rebuild or facts write (staging moved out of `data/`, whose group the old temp file inherited); (3) the staging sweep `glob(f"{name}.*.tmp*")` also matches a prefix-named sibling store's temp files and a lock of a store literally named `<name>.x.tmp`; restrict it to this store's mkstemp names; (4) `private_dir` treats any store whose directory is named `data` as `OUTPUT/data`, so an explicit `--database-path ~/stores/data/x.sqlite` stages in `~/.stores.private` and `/data/x.sqlite` in `/..private`; derive it from the real OUTPUT or fall back to the store's own directory; (5) the private directory needs a writable OUTPUT parent on the same file system, so OUTPUT as a mount point (container bind mount, CI volume) or under a read-only parent fails every rebuild, facts write and export; add an override or a fallback; (6) the private directory and its `exports/` are not checked for symlink or foreign owner before the sweep deletes their contents (shared `/tmp`); (7) the Daten export reads the store by path (schema check, stat, hash, backup) without the writer lock, so a concurrent rebuild can mislabel `datenstand.json` until the next export; (8) a forced same-name re-export killed between `published.replace(aside)` and `gen_dir.replace(published)` loses the published generation, and the next sweep deletes the set-aside copy; restore `replaced` on sweep; (9) `require_applied_partitions` catches a partition removed from the corrections file but not one added after the build (offline pages apply it, the registry does not); (10) a store from before DIP-id canonicalization holding `dip:07` splits that person on replay (new `dip:7` record, two pages; the real store has no such id); (11) `REPRESENTATIVE_SQL` orders `is_mdb DESC, xml_redner_id IS NULL, identity_key` but `collect_abgeordnete` orders `is_mdb` rows by `identity_key` only, so r1/r3 and the Personenseite can name a person with two MdB rows differently (0 such persons in the real store); (12) persist skips XML Drucksachen off the bundestag-xml host without a count or warning (all 4,699 real ones pass); (13) smaller: `_write_new_file` unlinks then creates, so a person page is briefly missing; an href-less date-like "21/09" folds into Drucksache 21/9; `document_issuer` falls back to BT without herausgeber or URL; a legacy `-journal` sidecar beside the store is not removed before the swap; `canonical_dip_person_id` raises on a >4,300-digit id; a local `document_id` in persist shadows the imported `stable_ids.document_id`; `tests/test_facts.py` computes two goldens with `facts._id_sort_key` (accepted, D25A).

**Why:** (1) can modify a downloaded distribution file; (2)-(6) break deployments other than the default layout; the rest are latent on the reference cache.

**Context:** Deferred in the v0.19.0.0 /ship run after three review passes, a red team per pass, a Claude adversarial pass and Codex adversarial and structured passes (structured gate passed, no P0/P1); Step 9 had used two of its three fix cycles. Verified false positive, not to re-file: a case-differing OUTPUT spelling shares one writer lock on macOS (same inode, second writer refused).

**Effort:** M
**Priority:** P1
**Depends on:** None

### Split the dataset from the site: the site builds from a release alone

**What:** Separate the two halves of the project in the code. On one side: acquisition, the store and the export (the dataset). On the other: the renderers, which read only a store or release. Today `scripts/build_dip_pulse_site.py` (10.7k lines) holds both, and the renderers do not read from the store. Checked 2026-09-30:
- **Read from in-memory report JSON (`entries`):** the Dossiers (`protocols/*.html`), `puls.html`, the bills pages and the votes archive.
- **Read from the store:** only `abgeordnete/*`, `fakt/*` (plus `entries` for completeness) and `database.html`.
- **In the JSON but not the store:** AI summaries and their receipts; acquisition states; validation warnings; per-TOP `xml_drucksachen`, `xml_speakers`, `api.positions` and `api.linked_drucksachen` (the store keeps a subset); raw vote payloads; the DIP API dumps shown in the dev view.
- **The store can't be rebuilt from the JSON alone:** it carries the MP roster over from the previous store.

The real work is therefore to move into the store everything the site shows, then point each renderer at the store. The file split follows from that.

Done when an offline build from a downloaded release SQLite, with no report JSON present, produces the same site as today's build. Dev-view API dumps are exempt.

**Why:** PRODUCT.md principle 6 (one figure, one computation). Today a figure on a Dossier or puls.html comes from the JSON while the release's figure comes from the store, so the two can drift. It also lets the dataset be released on its own schedule, and makes a second site (if one ever happens) a second renderer over the same release.

**Context:** Do it in slices, one page type at a time, behind a comparison test (old output vs. new output). The votes archive is the easiest first slice, because the `votes`, `vote_fractions` and `vote_members` tables already exist. Overlaps with `protocol_acquisition` (Daten), which moves acquisition states into the store.

**Update 2026-10-03 (architecture review):** the Daten export is one slice of this split. It is about 1,600 lines inside `build_dip_pulse_site.py`: export machinery, recipe SQL, and the Daten page HTML and styles. `_run_export` takes 16 keyword arguments, and `export_distribution_data` takes `mp_lookup` and `readiness` from page building. Move it into its own module, `export(store, out_dir) -> manifest`, after "One module that counts Reden and Beiträge" and "One Persons module over the person registry" land. Recipes should call those modules, and nothing in the export should read a render artifact. Moving it earlier would only relocate the code.

**Effort:** L
**Priority:** P2
**Depends on:** None; best started before the Analysen pages, so new pages are store-first from the start

### Vote-member occurrence bindings: cost and use

**What:** `persist_vote` binds every roll-call vote member to a durable occurrence (`vote-member` key), about 154k `person_bindings` rows on top of the 35k speech bindings, each through the full `registry.bind` path. Measure and reduce repeat-bind cost while preserving every occurrence binding: B.2 now uses those keys to link dossier member rows to their Personenseite. Page eligibility still comes from MdB status or speaking contributions. Done 2026-10-16 (handoff 07), every binding row kept: `collect_abgeordnete` puts each binding of a page person into the link lookup (the dossier member rows) and the table is exported, so no row could go. A vote upserts each party once instead of once per member, and a repeat bind reuses the record row it already read and skips the binding write when the binding is unchanged: 12.1 SQL statements per vote member become 8.1 on a repeat replay (10.1 to 8.1 on a fresh build); `persist_vote` takes 55-57 s instead of 79-87 s on a repeat replay of the 284-protocol reference cache (75 to 68 s on one fresh build each), and the store's content is unchanged (equal digests in every table, fresh and repeat). Rejected: a per-build memo of `_fold` for repeated vote-member evidence, worth at most about 6 s (40 µs per bind), because it needs per-connection state that `sqlite3.Connection` cannot hold by weak reference and invalidation around reconcile and merge.

**Why:** Roughly 5x the bind work of speeches on a full replay, and the rows are exported in a public table.

**Context:** Deferred from the A.2 review (2026-10-01). The third A.2 ship round already made a repeat bind cheaper (one statement for the touched mark, no rewrite of an unchanged record) and computes the facts once per rebuild.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Reviewed reassignment of a source record

**What:** Redesign the two corrections that place a source record on another person, occurrence `assignments` and `splits`, which `person_corrections.json` refuses since 2026-10-02. A placed record should be keyed by occurrence and owner (not by the printed speaker's identity, so a roster occurrence seen as `dip:` and as `aw:` lands on one record), contribute only its speeches and votes to the owner's page (never name, party, biography, `is_mdb` or profile), and leave the owner's partition and name guesses untouched (a partition record plus a reviewed record on one person is one owner, not two partitions). A split must refuse a `new_person_id` that is already issued to another person.

**Why:** Seven consecutive review passes of the first design reproduced criticals here: a placed record heading or filling the owner's page, an assignment on the Föhr person splitting its roster record into a second page, a `mps.dip_person_id` UNIQUE abort, a split silently absorbing records into an unrelated person. No shipped correction used either feature, so they were cut instead of patched again.

**Context:** Cut in the third A.2 ship round (decision 2026-10-02). The removed code and its tests are in commit history before the cut (`person_registry.bind`/`reconcile`, `ASSIGNMENT_PREFIX`, `_block_profile`, tests `test_an_owner_page_is_headed_by_its_own_record_not_the_assigned_one` and the split/assignment cases). Start with the invariants: a randomized check that adds assignments and splits must keep incremental == fresh, a fixed point, and owner pages built only from the owner's own records.

**Effort:** L
**Priority:** P2
**Depends on:** A real correction that needs it (none today)

### A.2 registry follow-ups from the third review pass

**What:** Findings of the third A.2 ship review that need a design decision and were not patched (2026-10-02): (1) done 2026-10-02: a stale roster record joins a live speaker as a partner only (`person_registry._stale_roster_partners`); (2) done v0.17.1.0 (2026-10-09): evidence is folded order-independently (`person_registry._fold`): the set of (name, party) pairs and of Redner-IDs per record, a separate deterministic representative for the biography; a record in two qualifying name+party buckets joins neither (see docs/stable-ids.md); (3) done 2026-10-16 (handoff 06): the coverage gaps left after the third ship round's generated tests, each an extension of an existing test: `_guess_merges` partitions from live rows only; the offline CLI with all four registry tables dropped; the `-journal`/`-wal`/`-shm` sidecar sweep and `glob.escape`; the `--repersist` DatabaseRebuildError branch (exit 1, hint); `compare_store_values._zusammenfuehrung` totals; the manifest `stable_keys` exact value; (4) done 2026-10-16 (handoff 08) for `occurrence`: it is required in `bind`/`upsert_mp`, and liveness is the build's touched set alone; the vacated flag stays, because the stale-roster-partner rule needs it (third ship round (5)). (5) the durable home person of a new record is allocated from its first persisted occurrence's own Redner-ID (`bind`, `allocate(conn, preferred)`), so a record holding several Redner-IDs gets a home that depends on persist order; found 2026-10-04 by the ship Red Team: build 1 persists the aw:5 record's occurrences a (Redner-ID 1) and b (Redner-ID 2) as [a,b] or [b,a]; build 2 moves b to Redner-ID 9 and adds an unrelated record with Redner-ID 2, which is pooled into the aw:5 person only for [b,a]. Reference cache: 0 records with more than one Redner-ID, so unreached there. Fix options: key the home on the record's identity (`stable_key('person','record',identity)`), or defer the xml/dip-preferred choice to `reconcile`, where `min(xml_redner_ids)` is known; either changes issued person keys and needs its own continuity decision and a two-build test. (6) findings of the ship review of 2026-10-04..09 that were accepted as follow-ups (none is a persist-order bug): the pass-1 durable union on a shared Redner-ID ignores abgeordnetenwatch conflicts (`match_rows`, pass 1; it is the same at the base for single ids and only newly reachable for records holding several Redner-IDs); pass 3 ignores a conflicting name-found aw profile because it blanks the anchor's profile bucket; a second `dip_person_id` on one record is resolved by string order (`_fold`; contradicting trusted aw ids give no trust since 2026-10-14); "Unbekannt" is a name key and can win the shown party over a lowercase party such as "fraktionslos"; `reconcile(full_build=True)` silently matches nothing when the touched table is missing (done 2026-10-16: a connection without a build is refused); `_touched` treats every `sqlite3.OperationalError` as "untouched" (done 2026-10-15: only the missing temp table); a preserved roster row counts as roster authority for biography values that once came from a cached dossier; a stale roster record with two normalised name+party keys never rejoins its speaker; removing a partition correction is refused, done 2026-10-12 (third ship round (1)); roll-call members keyed `name-party:{name}|{party}` collapse two same-name members of one Fraktion in a vote; a wrong multi-Redner-ID merge never heals because `_hard_id_conflict` ignores aw ids; `bind` is about 60 µs slower per call (fold, one more `_touched` lookup), roughly 12 s per full rebuild, which a short-circuit for evidence already contained in the record would remove; tests: no case for two roster occurrences with different biography values (the `roster_bio` smallest-value rule), no seeded property test for `_fold`, the nine biography field names are spelled in three places, `tests/test_registry_evidence.py` takes about 15 s. Measured on the merged tree (2026-10-09, `docs/a2-validation.md`): 23 roll-call records of party-switching MdBs that `main` attached to their person stay separate, because their Bundestag biography links of two legislative periods (same member number, `biografien/` and `biografien20/`) now share a name+party bucket and trigger the profile-conflict rule; comparing roll-call profile links by member number in pass 3 would attach 619 more roll-call records (2,460 persons) and needs a decision on `main`'s matching design. From the final review pass (also none a persist-order bug): pass 2 vetoes a record in two qualifying name+party buckets but not one that also sits in a bucket with three or more records (it joins the clean bucket; pass 3 vetoes the same shape for roll-call records); pass 3 is all-or-none per anchor, so one conflicting namesake voter in one party bucket of a party-switching anchor also keeps the clean voter of the other bucket split (conservative); a record's `record_id`, `identity_key` and `mps.id` come from the first persisted occurrence (a sampled person `dip:X` against a roster upsert `aw:N` of the same DIP person), so a carried-forward store and a fresh build differ in those ids though groupings and pages agree; `_pair_rank` lets name features (title, length) decide the shown party; `mps.xml_redner_id` holds only the smallest Redner-ID, so `mp_keys` over live `mps` rows never emits the second `xml:` key; the baseline of a record created in the same build is NULL, so `bind` compares against already folded evidence in the rare case that one occurrence id is persisted twice with conflicting hard ids; tests: no case for a party-switching anchor with a voter printed under both of its parties, the five `sorted(...)` calls in pass 3 are for stable iteration only.

**Why:** (1) and (2) change which pages exist or how records group in rare, specific situations; (3) and (4) are hygiene and guards that no test pins.

**Context:** Deferred from the third A.2 ship round by the three-fix-cycle cap; the coverage gate was resolved as "list the gaps" (generation allowance spent).

**Effort:** M
**Priority:** P2
**Depends on:** None

### A.2 second-round review leftovers

**What:** Findings of the second A.2 ship round that were deferred by decision (2026-10-01): (1) done 2026-10-16: r1 and r3 pick each person's row once (`REPRESENTATIVE_SQL`: roster, then speaker, then `identity_key`), and `collect_abgeordnete` orders a person's rows the same way, so the label is the Personenseite's; r1 0.26 s to 0.15 s, r3 stays at 0.12 s because its cost is the vote aggregation (the 1.61 s below did not reproduce on SQLite 3.52, and no available store has roster rows); rows and figures are unchanged, 496 r1 labels lose a DIP ", MdB, ..." title or a roll-call "surname, given name", 16 r1 parties move to the speaker row's, all 16 to an older one (Robert Farle fraktionslos to AfD, Klaus Ernst Gruppe BSW to Die Linke), 25 r3 labels change, one page heading ("Özoguz, Aydan" to "Aydan Özoguz"); open: the speaker record's party is the registry's smallest pair, not its newest (`_representative_pair` has no chronology), so the Personenseite and now r1 show those 16 persons under a former party while their DIP row names the current one; was: the r1/r3 Daten recipes choose each person's representative record with a correlated subquery (`JOIN mps m ON m.id = (SELECT m2.id ... ORDER BY m2.is_mdb DESC, m2.id LIMIT 1)`), about 15x slower than a plain join (r3 1.61 s against 0.11 s on the reference store), run at every export and again in `compare_store_values`; precompute a representative column in `mp_canonical` and join on it (the `m2.id` tie-break is now a hash, so choose by a content key); (2) done 2026-10-16: `_content_digests` sums per-row sha256 values modulo 2**256 with the column names and row count, in storage order; 28 s to 16-17 s per repeat replay (two digests); was: `_content_digests` orders every table by its text primary key, about 3 s more per store and 6-7 s per rebuild than rowid order; fold per-row hashes with a commutative sum instead; (3) advisory simplifications: drop `AbgeordneteComponent.after_persist` and call `collect_abgeordnete` directly, build the `collect_abgeordnete` lookup in one pass, replace the `ensure_canonical` temp copy by a view over `mps(id, person_id)`, drop the `mp_canonical` table if it is not a published contract, one `has_page` predicate instead of three, done 2026-10-15: one `valid_person_key` helper for the key checks; (4) done 2026-10-15: `write_abgeordnete_pages` re-checks every page key, removes whatever sits at the target and creates the file with `O_EXCL|O_NOFOLLOW`, so it never writes through a symlink; (5) a person whose only occurrence moved to another identity loses its page without a redirect (decided: accepted, see docs/stable-ids.md).

**Why:** None changes a published figure; (1) and (2) cost seconds per build, (3) to (5) are readability and defence in depth.

**Context:** The user deferred these to keep the final review on code with mutation-checked tests.

**Effort:** M
**Priority:** P3
**Depends on:** None

### A.2 review leftovers

**What:** Small cleanups the A.2 review found and nobody asked for yet: `person_registry.mp_keys` and `_mp_external_ids` repeat the same three-way id extraction; `_load_corrections` uses an `lru_cache` for one file (kept 2026-10-16: keyed by path, one read per build process, so dropping it would not make reloads more deterministic); `rebuild_database_from_entries` forwards every argument to `_rebuild_database_from_entries` only to take the lock and translate errors (left to "The store owns its schema and its rebuild"); the `built = {"votes"} if ... else set()` expression exists in three places (done 2026-10-16: `facts.built_sources`); the offline path reaches `collect_abgeordnete` through the mp-pages component's `after_persist` while the online path calls it directly (left to "Delete the feature-selection axis"); `tests/test_facts.py` goldens that depend on sha256-ordered ids (done 2026-10-16: the two that changed under a salted `stable_key`, the aktivste-abgeordnete full tie and its receipt order, read the expected order from the stored ids; open: that order is itself a content hash, D25A's "lowest mps.id" tie and the ascending speech-id receipts, not a source order); `person_registry.merge` and `reconcile` write into the `mps` table whose schema lives in `persist_dip_pulse_store`.

**Why:** Less to read, fewer places to drift.

**Context:** Deferred from the A.2 review (2026-10-01); none changes behaviour.

**Effort:** S
**Priority:** P4
**Depends on:** None

### One module that counts Reden and Beiträge

**What:** Give the counting of Reden one module. It should own which XML records count as a Rede and which are Beiträge (ADR 0001, ADR 0002), with attribution to Zusammenschluss, Sprechrolle and Person. It returns counted rows or aggregates per period and grouping. Today `derive.py` owns attribution but nobody owns counting. Five places count on their own:
- `render_dip_pulse_html.item_stats` and `week_stats` use the parser's `xml_speech_count` (falling back to `len(speakers)`).
- `build_dip_pulse_site` counts in three spots: the bills tally in `collect_bill_pages`, `speech_count` in `collect_abgeordnete`, and Daten recipes r1, r2 and r5.
- `facts.py` has six speech queries.
- `compare_store_values.py`.

The "corrected speaker, `rede_id`, `occurrence_id` of a Rede" recipe is copied in render, build and `persist_report`. Done when every page, Kennzahl and recipe reads Reden through this module, and no other module decides what a Rede is.

**Why:** Puls counts from the report JSON (`xml_speech_count`) and Fakten count the rows `persist_report` inserted from `xml_speakers`, so a published Puls figure and a Fakt can disagree. The next change to what counts as a Rede (Zwischenfrage credit, Zu Protokoll gegebene Reden, roadmap A1) has to be made in five places.

**Context:** Found by the architecture review of 2026-10-03 (origin/main 2801f1c). This is the read path that "Split the dataset from the site: the site builds from a release alone" needs: once renderers read the store, they should read Reden through this module rather than writing new SQL. Recipe r2 hard-codes the Sprechrolle labels and the Zusammenschluss COALESCE instead of using `derive.SPRECHROLLE_LABELS` and `ZUSAMMENSCHLUSS_SQL`, and `compare_store_values._redeanteil_group_sql` is a third copy. Tests can then seed store rows and assert counts through one interface, instead of building a report, a store and a page.

**Effort:** L
**Priority:** P2
**Depends on:** Best done with or right after the A1 PRs still open, so the counting rule moves once

### Typed completeness gaps instead of reason strings

**What:** Make a Sitzung's acquisition gaps a typed value with an enum reason and structured detail (scan pages used, date), owned by `publication_state.py`. Today the reasons pass through these steps:
- `validate_dip_protocol` creates them as `failure_reasons` and `roll_call_scan_end`.
- `build_dip_pulse_site.annotate_report_acquisition` rewrites them.
- `facts.completeness_from_reports` flattens them into display text ("votes partial (source_stale)", "scan_budget_exhausted after N pages").
- `build_dip_pulse_site._structural_vote_gap` parses that text back with `text.index("(")` and `_BUDGET_PAGES_RE` to decide whether `--backfill-incomplete` rescans a Sitzung.
- `build_publication_manifest` and `features/votes.py` read the raw dicts again.

Done when the backfill decision, the Completeness basis and the manifest consume the typed gap, and text is produced only for display.

**Why:** Rewording a reason in `facts.py` silently changes which Sitzungen the backfill takes. `publication_state.AcquisitionState` is already typed, but these paths bypass it. The default vote scan budget (`30`) is repeated in `main()` and in the backfill path.

**Context:** Found by the architecture review of 2026-10-03. Overlaps "Persist per-sitting acquisition state in the store (`protocol_acquisition`)". The typed gap is the vocabulary that table would store, so do this first. Several items in "Harden the vote acquisition and catalog completeness paths" ((1), (11), (15)) touch the same code.

**Effort:** M
**Priority:** P2
**Depends on:** None

### One Persons module over the person registry

**What:** Put `person_registry.py` behind one interface that the rest of the code uses for Namensabgleich, Zusammenführung, Personenseite eligibility, page links and the mp-to-Person map. Registry tables become private to it. Today this logic is spread out:
- **Personenkennung keys** (`aw:`, `xml:`, `dip:`) and the trusted-aw rule are built in `persist_dip_pulse_store.mp_identity`, `person_registry.mp_keys`/`_mp_external_ids`, `render_dip_pulse_html.mp_page_href` and `build_dip_pulse_site.speaker_identity`.
- **The mp-to-Person map** is built three times: `facts.ensure_canonical` (a TEMP table), `_run_export`'s `mp_canonical`, and `collect_abgeordnete`.
- **`collect_abgeordnete`** (about 225 lines in the build file) queries `person_records`, `person_bindings` and `person_aliases` directly and parses `evidence_json`.
- **The `mp_lookup` dict** mixes four key namespaces and is threaded through about 50 build call sites.

**Why:** The data export's `mp_canonical.has_page` comes from `mp_lookup`, an HTML link map, so the dataset depends on what the renderer produced. Identity bugs (see the Abgeordnete merge-gap history) have to be fixed in every copy.

**Context:** Found by the architecture review of 2026-10-03. It subsumes the identity items already deferred: "A.2 review leftovers" (`mp_keys`/`_mp_external_ids` duplication, `merge`/`reconcile` writing into `mps`) and "A.2 second-round review leftovers" (3) (one `has_page` predicate instead of three, the `ensure_canonical` temp copy, dropping `mp_canonical` unless it is a published contract). Close those parts there when this lands.

**Effort:** M
**Priority:** P2
**Depends on:** None

### The store owns its schema and its rebuild

**What:** Make `persist_dip_pulse_store.py` the one module that owns the SQLite store, with a small interface: open, rebuild from entries, persist a report. Today:
- **Table definitions live in four modules:** `persist.initialize` and its migrations, `person_registry.initialize`, `facts.py`, and the export tables in `build_dip_pulse_site._run_export`.
- **The rebuild lifecycle lives in the build file:** `rebuild_database_from_entries` stages the store, copies the registry, restores the roster through about 25 keyword arguments to `upsert_mp`, reconciles, computes facts, validates and swaps. `repersist_cached_reports` and `ingest_mdb_roster` are there too.
- **The facts engine runs from three call sites:** the rebuild, `run_facts_engine`, and the fallback in `run_data_pipeline`.
- **Test fixtures are a third writer:** `tests/_facts_fixture.seed_weeks` and `tests/_daten_fixture.seed_store` write rows through `upsert_*` and have to follow every schema change.

**Why:** A schema change touches four files plus the fixtures. Store tests sit in `test_build_dip_pulse_site.py` only because the rebuild lives there.

**Context:** Found by the architecture review of 2026-10-03. Candidates for the same pass: the "`persist_votes` is dead" note in "Stale derived data after `--offline --repersist`", and `rebuild_database_from_entries` forwarding to `_rebuild_database_from_entries` ("A.2 review leftovers"). This is the foundation for the Reden and Persons modules above, and for "Split the dataset from the site". Fixtures should then build stores through `persist(report)`, the path production uses.

**Effort:** L
**Priority:** P3
**Depends on:** None

### Delete the feature-selection axis

**What:** `features.publication_selection()` always returns every component, and `render_site`, `write_report_and_page` and `render_html` overwrite their `features` argument with it. Even so, `features: Selection` is threaded through about 28 build signatures and 2 render signatures, and `if "bills" in features` guards are always true. Remove all of it:
- the Selection parameter;
- `features/loader.py`;
- the pass-through adapters `features/bills.py`, `features/facts.py` and `features/abgeordnete.py`, which call back into build functions through an untyped `ctx` dict;
- the deprecated `--features`, `--enable`, `--disable` and `--list-features` flags with `resolve_from_args` and `warn_deprecated_feature_configuration`.

`render_site` calls its page builders directly. `votes`, `summaries` and `aw_profiles` do real work and stay as plain modules without `ctx`.

**Why:** It is a seam with only one adapter: nothing varies across it, and every signature pays for it. CLAUDE.md's pre-release rule says to drop compatibility shims rather than carry them.

**Context:** Found by the architecture review of 2026-10-03. This makes "Global header nav links to a page a build didn't write when its feature is off" (Publication) moot: there will be no feature to switch off. Close it when this lands. Also check the `AbgeordneteComponent.after_persist` path that "A.2 second-round review leftovers" (3) proposes to drop.

**Effort:** S
**Priority:** P3
**Depends on:** None

### A build pipeline module behind `main()`

**What:** Replace the 480-line `main()` in `build_dip_pulse_site.py` with `build(config, source, clock) -> BuildResult` (pages written, manifest, gaps). DIP access goes behind a source seam with two adapters: HTTP for online builds, and cached reports for `--offline` and tests. Today:
- The offline and online branches repeat the same tail: `run_data_pipeline` returns a 5-tuple that is unpacked into `render_site`'s roughly 20 keyword arguments, in both branches.
- `write_report_and_page` takes 21 parameters, builds a fake `argparse.Namespace` for `dip.build_report`, and returns XML through an out-parameter dict.
- `getattr(args, ...)` appears about 40 times.
- `resolve_today` is called five times while other clocks bypass it, including some in `facts.py`.

**Why:** Orchestration can only be tested by patching module globals: `test_build_dip_pulse_site.py` has about 123 `patch()` calls and 16 full `main()` runs. "Some date checks use the wall clock, not `--today`" (item (11) of "Harden the vote acquisition…") is a symptom.

**Context:** Found by the architecture review of 2026-10-03. Easier after "The store owns its schema and its rebuild" and "Delete the feature-selection axis", which remove most of the parameters threaded through `main()`. `validate_dip_protocol.py` (2.6k lines, imported as `dip`: HTTP client, XML parser, roll-call scraping, three LLM providers, report assembly) is the natural home for the source adapter. `enrich_with_llm_summaries` taking the CLI namespace and the `global _namenslisten_entries` cache should go in the same pass.

**Effort:** L
**Priority:** P3
**Depends on:** Best after the store and feature-axis items above

## Completed

### Audit every `data_dictionary.json` definition against the code that writes the column

**What:** Before the next /ship of the codebook branch, check each of the 246 column definitions (meaning, unit, source, NULL behaviour) and each recipe `method`/`caveat` against its writer in `scripts/persist_dip_pulse_store.py`, `derive.py`, `facts.py`, `registry.py` and the rebuild path (`rebuild_database_from_entries`: every persisting online build stages a fresh store; `--repersist` keeps the old one when content is unchanged), and against NULL and value counts in a real export. For every column: is it ever NULL, and why; is the value as the source gives it or normalised; is the timestamp's lifetime what the text says. Record the result per table in the plan or a short audit file. Done when every definition has been compared with its writer and the measured counts, and the corrections are committed.

**Why:** /ship run 5 (2026-10-31) ran three adversarial rounds; each found new false statements in DATA.md definitions (licence table missing three derived columns; `created_at` called a first-ingest time; `speeches.mp_id` called nullable though it never is; `fraktion` called "as the protocol names it" though normalised; `vote_members.party_id` called nullable). Each fix used a /ship fix cycle and the run stopped at the three-cycle cap. A one-pass audit replaces that loop.

**Effort:** M
**Priority:** P1
**Depends on:** None
**Completed:** v0.25.0.0 (2026-10-31): docs/research/codebook-dictionary-audit-2026-10-31.md found 20 false statements, all corrected; its section 3 lists what could not be verified (see the codebook follow-ups item).

### Codebook (`DATA.md`) and recipe result CSVs in the release

**What:** A codebook (`DATA.md`) in every release: each table and column with its meaning, unit, source (DIP, Plenarprotokoll XML, bundestag.de, abgeordnetenwatch) and licence layer; the counting rules (what counts as a Rede, Sitzung mit Dossier, completeness) quoted from CONTEXT.md and the ADRs; coverage per Wahlperiode; known gaps; how to cite. Also per-recipe result CSVs. Most of the explanatory prose on the Daten page today belongs here, so that it is versioned with the data it describes.

**Why:** A researcher needs the definitions of the release they cite, not of today's site (PRODUCT.md, 2026-09-30). Originally scoped out of PR #59 as an Approach-C follow-up once the data path has real usage. This item used to also cover a "Kopieren" clipboard button on each recipe's SQL block and a "Daten" link in dossier footers; both shipped in v0.6.6.0 (2026-09-26), leaving only the CSV/`DATA.md` half open. The other former part of this item, externalising `data/plenarprotokoll-*.json` links, moved into the site-hosting TODO above.

**Effort:** S–M
**Priority:** P2 (raised 2026-09-30: part of a citable release)
**Depends on:** None

**Completed:** 2026-10-29 (implementation; release upload remains separate). Export format 10 (format 9 on this branch until main's Antrag passages took that number) generates German `DATA.md` from an authored 30-table/246-column dictionary and methods/licence inputs, plus all six recipe result CSVs in SQL column order. The typed manifest inventories every asset with size/checksum and recipe references; the Daten page links the codebook and CSVs while preserving HTML column order; manifests of another export format are rejected. Input hashes invalidate stale generations, and staged failures preserve the previous publication. Full suite after the second review round: 1,572 tests, two skipped. Before that round: 347 focused export/page/pipeline tests, browser checks and offline demo checks passed. Fixture smoke verified 36 artifact links, sizes and checksums and replayed all six CSVs. See [implementation plan](docs/plans/d-codebook-recipe-csvs.md). Uploader, redistribution decisions, DOI/citation, changelog, hosting and acquisition work remain open.

### Call only current MdBs "Abgeordnete" on the Personenseiten

Done 2026-10-30. The roster ingest decided "MdB" with `"mdb" in funktion.lower()`, which matched "MdBR" and "Stellv. MdBR": the Abgeordnete list held 151 Bundesrat members. `derive.is_mdb_funktion` takes "MdB" as an exact value; on DIP WP 21 (built store, sittings 21/87–21/103, 2026-10-30) the list goes from 740 to 589. A store built before the fix keeps its Bundesrat roster rows until the roster is fetched again (`--enrich mp-roster`); no migration path, per the pre-release rule. DIP has no Mandat end dates, so MdBs who left during the Wahlperiode stay listed; the intro says so instead of claiming "aktuell". A Person with Reden or Beiträge but no roster Mandat is a Redner: the eyebrow names the Sprechrollen of their Reden and Beiträge, and "Mitglied des Bundestages laut Plenarprotokoll" when a Rede or Beitrag counts for a Zusammenschluss (ADR 0001) or they cast a namentliche Abstimmung (not "früheres": MdBs in a government office are not in the roster yet, and a build without the roster has none). The Fraktion stays shown when the protocols record a Mandat; the index lists them under "Weitere Rednerinnen und Redner". A page kept only by registry evidence (no Rede, no Beitrag) reads "Keine Reden erfasst" and claims no Redner role. Left open: "List MdBs in a government office as Abgeordnete" and "Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs".

### "So arbeitet der Bundestag" explainer page

Done 2026-10-30. `bundestag.html` (`render_bundestag_page`) is the ninth nav entry and explains, in five sections, who brings in Vorlagen (Art. 76 GG, §§ 75, 76 GOBT), when the Bundestag sits (Art. 39 Abs. 3 GG, §§ 6, 20, 21 GOBT), how it votes (Art. 42 Abs. 2, 79 Abs. 2 GG, §§ 48, 51, 52 GOBT), the freies Mandat (Art. 38 Abs. 1 Satz 2 GG) and the way from Gesetzentwurf to Gesetz (§§ 78–86 GOBT, Art. 77, 78, 82 GG). Every citation was checked against gesetze-im-internet.de and the GOBT on bundestag.de; § 52 is worded as it stands ("bis zum Beginn der Sitzung", five percent of the members present). The sources page's glossaries and the week radar's "namentlich abgestimmt" badge link to it; the vote panel link is its own item (B-track code).

### Fakt der Woche, stop crediting a bundled TOP's Reden to one Vorgang (`meistdiskutierter-vorgang`)

Done 2026-10-30 (metric version 2 → 3). A Tagesordnungspunkt counts for a Vorgang only when it debates exactly that one Vorgang; the Reden of a verbundene Beratung of several Vorgänge count for none (`facts.SINGLE_VORGANG_CTE`, `derive.debated_vorgang`). The Vorgang set is `derive.agenda_procedures`' set, including the `mitberaten` twins (`proceeding_positions.mitberaten_json`); an Entschließungsantrag (DIP „Entschließungsantrag BT“, an unselbständige Vorlage under § 75 Abs. 2 GOBT) counts only when it is the item's only Vorgang. A test pins the SQL to `derive.debated_vorgang` over persisted reports. Measured on WP 21 sittings 21/87–21/103 (2026-10-30): 56 of 121 TOPs with a Vorgang are verbundene Beratungen, and 3 of 4 monthly winners change, from bundled Gesetz debates (Haushaltsgesetz 2027 16 Reden, Tempolimit 17, Infrastruktur-Zukunftsgesetz 16, each debated with other Anträge) to single-Vorgang Anträge (13–14 Reden); October stays (26). Consequence worth a product look: a big Gesetz debate is usually a verbundene Beratung, so the card will rarely name a Gesetz. The receipt resolver (`_fact_proceeding_citation`) reads the same rule; `LEAD_PROCEEDING_CTE` is gone. The card and the Methodik carry the rule as the metric's caveat. Storing one Thema rule at persist time is split out as "One rule for a Tagesordnungspunkt's Thema (lead Vorgang), computed once at persist time".

### The demo fixture predates the A1 Rede rules (16 Reden in the fixture, 14 from today's parser)

Done 2026-10-30. The two speeches that stopped being Reden are the Kurzintervention ID218403400 and its Erwiderung ID218403500 (#68). `scripts/extract_demo_fixture.py` now builds the agenda item from `validate_dip_protocol.xml_top_fields`, the helper real reports use, so the fixture carries `xml_contributions` (the demo dossier lists „1 Kurzintervention, 1 Erwiderung, 1 Zwischenfrage“ as Beiträge) and cannot fall behind the parser's fields again. The guard expects 14 Reden. Demo dossier: 16 → 14 Reden.

### The Bundestag XML gives one Redner-ID to two people (11005304)

**Completed:** v0.12.0.0 (2026-10-02, A.2). Version-controlled source partitions and six reviewed occurrences separate Alexander Föhr's 13 speeches from Dirk-Ulrich Mende's 9 before persistence. Their stable person URLs and speech links are distinct; the shared profile cannot merge them again. See [reference validation](docs/a2-validation.md).

**What:** `<redner id="11005304">` is Alexander Föhr (CDU/CSU) and Dirk-Ulrich Mende (SPD) in 22 Reden of WP 20 (20/91 to 20/190). Where the element is intact the id is the only thing that tells the Reden apart, so all 22 are attributed to one Person (abgeordnetenwatch's Föhr profile, found by ext_id); 6 of them carry a merged element ("SPDCDU/CSU", "Dirk-UlrichAlexander Mende Föhr") that `parse_redner` now repairs from the printed label. Detect an id whose Redner name (or printed label) changes between Reden and split it by name and Zusammenschluss, or report it to the Bundestag.

**Why:** 9 Reden by Mende stand on Föhr's Personenseite. It is the same defect class as the doubled id of Svenja Schulze, but here the id itself is shared, so no derivation from one Rede can spot it.

**Effort:** S
**Priority:** P3
**Depends on:** None

### `2/3-Mehrheit` phrasing can spuriously trip the document-number mismatch check

**Completed:** v0.23.6.0 (2026-10-29). The fix suggested below ("at least 3 digits before the slash") would have rejected every real number ("21/6561"). Instead the vote pages' own pattern (`validate_dip_protocol._DOCUMENT_NUMBER_RE`, no longer an alias of `derive.DOCUMENT_NUMBER_RE`) needs a two-digit Wahlperiode: bundestag.de lists namentliche Abstimmungen from WP 17 and structured XML starts at WP 18. That covers every vote-page site with one rule: the outcome mismatch check, the block identification by documents, the trailing-outcome paragraph, the DIP title evidence, the chair's announcements, and `parse_roll_call_list_page`, where a "2/3" in a teaser would have joined the vote's `document_numbers` and reached `vote_documents`. `derive.DOCUMENT_NUMBER_RE` (headings of every Wahlperiode) is unchanged and still filtered by `plausible_document_number`. No stored vote moves until it is re-acquired: `official_result` is computed at fetch time and a repersist keeps it; no fixture or live page checked so far uses the shape.

**What:** `_DOCUMENT_NUMBER_RE` (`\b\d{1,2}/\d{1,6}\b`) also matches a fractional-majority phrase like "2/3-Mehrheit". If such a phrase appears in the attributed outcome text and doesn't happen to equal one of the vote's own document numbers, `official_vote_result` refuses (falls back to derived) even though the actual outcome word is correct. Require at least 3 digits before the slash for a document number, or exclude common fraction phrases (`1/2`, `2/3`, `3/4`) from the pattern used by this specific check.

**Why:** Found by the /ship red-team review (2026-09-27); not verified against real bundestag.de wording (live pages checked so far spell out "Zweidrittelmehrheit", not "2/3-Mehrheit"). The failure direction is always safe — a spurious refusal falls back to the derived yes>no rule, never produces a wrong official value — so this is a false-negative/coverage gap, not a correctness bug.

**Effort:** S
**Priority:** P3
**Depends on:** None

### A Drucksache reference can be a URL fragment

**Completed:** v0.23.6.0 (2026-10-29). The parser part was already fixed: `extract_drucksachen` skips an anchor off the Bundestag host (`tests/test_validate_dip_protocol.py`), and today's parser finds no 88/739016 in the live `btp/20/20206.xml`. What remained were reports cached before that check: persist and the Politikfelder skipped such a reference, but the dossier still showed it as a muted Drucksache and the vote panel's link map took its URL. `derive.xml_drucksachen(item)` is now the one rule (no link, or a link on the XML host) and every reader uses it: persist, `item_document_numbers`, `render_source_links`, `render_top_documents` (a TOP whose only reference is a fragment gets no empty "Drucksachen" section) and `features/votes.py`. Store figures do not move, since persist already skipped these; only dossier HTML of such stale reports changes.

**What:** The XML parser reads `88/739016` from a syriahr.com URL in 20/206 as a Drucksache (`xml_drucksachen`). Only the link is dropped now (`render_source_links`), and since 2026-10-14 persist skips an `xml_drucksachen` entry whose link is not on a Bundestag host (documents are keyed by number, so it would join the real Drucksache of that number); the reference is still shown as a plain Drucksache number on the dossier, which renders from the report.

**Why:** Found when it aborted the reference store's offline rebuild; the crash is fixed, the false positive is not. Belongs with the other Plenarprotokoll extraction fixes.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Validate remote-manifest recipes before showing their SQL

**Completed:** v0.23.6.0 (2026-10-29). Verify equal, not pin to local: an override manifest must carry exactly this build's recipes, same ids in the same order with byte-equal SQL, rows that are objects, and `empty_reason` text or null; otherwise `validate_manifest` names the recipe ("recipes[0] (r1-meiste-reden) SQL differs from this build's; export the data with this version of the code"). The rows came from the manifest's SQL, so showing local SQL beside them would misstate them as much as tampered SQL would. `render_daten_recipes` takes title and SQL from `RECIPES`; a retitled recipe still validates (titles are not in `recipes_hash`). A manifest exported before a recipe's SQL changed is now refused; re-export it. A missing `empty_reason` no longer raises a KeyError.

**What:** `validate_manifest` checks `recipes[]` only for a string `id` and a list `rows`; `render_daten_recipes` then shows each recipe's `title` and `sql` straight from the manifest (`build_dip_pulse_site.py`, `manifest["recipes"]` loop), and an unknown id silently gets `{}` from `RECIPES_BY_ID`. Reject unknown recipe ids, and either take `title`/`sql` from the local `RECIPES` by id or require the manifest's SQL to match it. Done when a manifest with an unknown id or altered SQL fails validation with a clear error.

**Why:** Found by the adversarial review of the recipe "Kopieren" button (2026-09-26). HTML escaping already stops XSS, but a tampered or mistaken remote `--data-manifest` could present any text as SQL, including sqlite3 dot-commands such as `.shell`, and the copy button makes pasting it one click. The gap predates the button; only reachable through an explicit remote manifest.

**Context:** Choosing between "pin to local" and "verify equal" touches the manifest contract: a newer remote export may legitimately ship newer recipe SQL whose `rows` no longer match the local SQL.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Bill overview polish: same-day step ties

**Completed:** v0.23.5.0 (2026-10-29). `collect_bill_pages` breaks a date tie by `BILL_STEP_RANK` (Plenarprotokoll < Drucksachen < Beschlussempfehlung < Namentliche Abstimmung < Beratung / 1. < 2. < 3. Beratung < Gesetzesbeschluss); a kind not listed ranks by where the event came from (document 10, vote 25, Vorgangsposition 30). Before, insertion order decided: a Drucksache filed on the sitting day beat the Beratung, and Gesetzesbeschluss beat „2. Beratung“ only because documents are appended first.

Measured on the reference cache (`.context/dip-pulse-site`, main vs the branch, 2026-10-29): 8 of 562 bills change `latest_step`:
- „Beschluss“ → „Abstimmung über Vermittlungsvorschlag“: 5
- „Geschäftsordnungsantrag zur Beratung“ → „2. Beratung“: 1
- „2. Beratung“ → „3. Beratung“: 1
- „Unterrichtung“ → „2. Beratung“: 1

„Gesetzesbeschluss“ stays the latest step of 47 bills before and after. No bill moves to a procedurally earlier step. Kinds in the cache not in the table, ranked by origin: „2. Beratung und Schlussabstimmung“, „Abstimmung über Vermittlungsvorschlag“, „Zurückverweisung an die Ausschüsse in 2./3. Beratung“, „Geschäftsordnungsantrag zur Beratung“ (Vorgangspositionen, 30), and „Beschluss“, „Berichtigung“, „Empfehlungen“ (30 or 10 by origin).

**Effort:** S
**Priority:** P3
**Depends on:** None

### Combined Antrag titles render as one four-line bold block on puls.html

**Completed:** v0.23.3.0 (2026-10-29). The cause was the demo fixture, not the renderer: `scripts/extract_demo_fixture.py` copied the joint „a) … b) …“ agenda heading into both Anträge's DIP titles, so `topic_identity` saw one title, the row lost `equal_weight` and the heading became its bold `.radar-title`. The extractor now carries each Antrag's own title (`TITLES`, checked against the Drucksachen 21/6354 = a) and 21/4833 = b) on dserver and against the heading), the fixture's four `titel` fields follow, and the demo row lists both titles like a real build. Real data never had the block: each Vorgang has its own title, and the heading fallback is cut at 120 characters. Splitting titles on „a)“/„b)“ was rejected, since real titles cite „§ 3 Abs. 1 a)“.

**What:** `.radar-title` shows DIP's combined TOP title ("a) Beratung des Antrags … b) Beratung des Antrags …") as one 750-weight wall of text. Split on the `a)`/`b)` markers into the existing `.radar-titles` list, or cap the title with a "mehr" link.

**Why:** It is the heaviest element on the page and pushes the numbers (Reden, Anteil, Wer sprach) off the first screen on mobile. The rest of the page is scannable; this row is not.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Staleness of the "Aktueller Puls" week is only gray meta text

**Completed:** v0.23.2.0 (2026-10-29). Past `STALE_AFTER_WEEKS` (4 ISO weeks) puls.html shows „Nicht aktuell: letzte Woche mit Sitzung vor N Wochen“ right after the h1, outside it, and the facts line no longer repeats the age; up to four weeks the facts line still leads with it. The eyebrow stays „Wochenübersicht“; the docstring and `docs/designs/puls-wochenradar.md` no longer claim it changes. Still open: the homepage's weekly entry shows no age at all (`render_landing_page`), and „Nächste Sitzungswoche“ above.

**What:** When the latest sitting week is more than ~4 weeks old ("vor 16 Wochen" in the demo build), say so next to the h1 instead of in the gray subtitle line.

**Why:** The h1 reads "Was der Bundestag in KW 24/2026 verhandelt hat" as if it were current; the age is only in the muted meta line below it.

**Context:** Same header as "Nächste Sitzungswoche" in the puls.html header above, whose stale-archive state is specified in the week-radar design doc; do both together or this one first, since it needs no Sitzungskalender fetch.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Say "Woche mit Sitzung", not "Sitzungswoche", for the reporting period

**Completed:** v0.23.2.0 (2026-10-29). Every reporting-period use in `scripts/` now says "Woche mit Sitzung" or "Woche", worded per line ("dieser Woche", "je Woche mit Sitzung", "Vergleich: N Wochen mit Sitzung"); the build log counts "Perioden (Wochen und Monate)", and the unused plural in `_PERIOD_NOUN` is gone (`_PERIOD_DEMONSTRATIVE`). A test keeps the longer card footer inside one card line. README and the design docs follow; the source XML fixtures keep the Bundestag's own wording.

**What:** Replace "Sitzungswoche" wherever it names this project's reporting period with "Woche mit Sitzung" or plain "Woche": 32 occurrences on 29 lines in `scripts/`. That includes the Wochenradar notes (among them "ein Vergleichswert folgt mit der nächsten Sitzungswoche"), the Fakt der Woche card footer "Vergleich: N Sitzungswochen" (`baseline_comparison_line()`), the erste-reden card sentence "mehr als in … der Sitzungswochen", the Methodik's "mindestens N Sitzungswochen", and the build log line that also counts months as "Sitzungswochen". No current use means the official Sitzungskalender, which the site does not read at all. Update the 13 test lines that assert these strings. Done when no copy calls a Kalenderwoche a Sitzungswoche.

**Why:** CONTEXT.md (Sitzungswoche, Kalenderwoche, 2026-09-25): a Sitzungswoche is the Ältestenrat's plan, and the site counts Kalenderwochen with at least one Sitzung. A week with only a Sondersitzung counts for us but is sitzungsfrei in the Sitzungskalender, so the current copy overstates it.

**Context:** The card footer and the erste-reden sentence are on the Karten, so this re-renders published Karten; see the footer fix under Fakten.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Bill overview: accent-insensitive search

**Completed:** v0.23.1.0 (2026-10-28). Both build-time `data-search` and the query fold accents and ß, so „fur“ finds „für“ and „strasse“ finds „Straße“. Original titles and query spelling remain visible and survive URL/history restoration. See the [implementation plan and validation](docs/plans/bill-search-accent-insensitive.md). Same-day step ranking followed in v0.23.5.0 (see its entry above).

### Week comparison with no basis still draws every n/a slot

**What:** With a single sitting week, "Noch keine Vergleichswoche" is followed by three N/A metric tiles and six `n/a` chips beside the Redeanteil bars. Collapse the delta column and metric footers when the whole panel has no basis. `test_no_comparison_state_renders_the_current_week_without_deltas` in `tests/test_build_dip_pulse_site.py` asserts the chips today, so it changes with this; the partial-week tests keep their per-row `n/a`.

**Why:** The no-basis marker is honest per row, but repeated nine times it is noise beside a heading that already says there is nothing to compare.

**Effort:** S
**Priority:** P3
**Depends on:** None

**Completed:** v0.22.1.0 (2026-10-26). Implemented [the empty-week comparison plan](docs/plans/empty-week-comparisons.md): missing-week panels retain current totals and fraction shares without metric footers, delta chips or an unused delta column. Partial comparisons and zero-prior values keep their unavailable deltas. Focused tests pass (219); the full Python 3.13 suite passes (1,523 tests, two skipped). Chrome DevTools checks at 1440px, 700px and 375px and a printed PDF confirm the current-only layout.

### Vote reading misses half the inverted votes and never stores it

**What:** Three defects found while analysing the bundestag.de vote pages (2026-10-20, [docs/research/bundestag-vote-pages.md](docs/research/bundestag-vote-pages.md)):
1. **Missed inversions.** Of 28 votes whose Beschluss line reads "Beschlussempfehlung … (Antrag … ablehnen)", `recommendation_inversion` (`scripts/validate_dip_protocol.py`) flags 14 and misses 14: 773, 790, 793, 798, 803, 811, 819, 841, 850, 855, 873, 882, 892, 906. In 9 of them the sponsoring Fraktion voted Nein on its own Antrag, which confirms the inversion. Their WP 20 titles lack the "Ablehnung eines Antrags" wording the regex looks for. The 23 "Beschlussempfehlung annehmen" votes all agree. Detect from the Plenarprotokoll announcement ("Abstimmung über die Beschlussempfehlung … auf Drucksache …", already in the cached XML) or the Beschluss line, not from titles. Careful: "zu Gesetzentwurf X (… ablehnen)" is a vote on the Vorlage and is not inverted.
2. **Nothing persisted.** `inverted` and `result_raw` are empty for all 217 votes in every local store; the replay site shows no inversion note on any of its 108 vote panels, and vote 1005 renders "Kein Ergebnis verfügbar". Not checked against an online build, so first establish whether only offline replays lose them.
3. **Provisional tally blocks the official result.** The bundestag.de Beschluss box prints the tally read out in the sitting; we store the final one from the Plenarprotokoll (correct). For 43 votes they differ by 1–3 (vote 996: 438 Ja vs 439). `_official_vote_text` finds the box line by matching our tally, so these votes fall back to a derived result (inferred from the code, not from a build). Match with a tolerance, or by Drucksache number.

Done when the 14 votes above render the inversion legend, a test pins one WP 20 case (e.g. 906) and one "zu Gesetzentwurf … ablehnen" non-inversion, a replay store has `inverted`/`result_raw` filled, and vote 996 shows the official result.

**Why:** A missed inversion makes the badge read "Angenommen" on a vote whose political meaning is "Antrag abgelehnt", the most misleading state a panel can be in (see the completed "Inverted-vote reading" item). The B4 descriptions build on this flag.

**Result (2026-10-24, [plan](docs/plans/fix-vote-interpretation.md)):** Measured on a disposable copy of the reference site (217 votes).
- **Inversions:** `inverted` was NULL on all 217 stored votes; after the replay 40 are `true` and 177 NULL (none `false`, which the field never holds). All 14 missed IDs are inverted from the chair's announcement in the cached XML (`inversion_source = bundestag-protocol`), and so are four votes the title never flagged (843, 869, 907, 990); 37 protocol inversions in all, plus 1001, 1002 and 983 with title-based evidence. No inversion is lost. Adjacent chair paragraphs are read together; where the combined announcement is not uniquely attributable, the existing unambiguous title fallback remains. Each protocol excerpt names the Antrag of the vote and asks to reject it.
- **Results:** `result_source` NULL on 217 → `derived` 208 and NULL 9 (special-majority votes); `result_scope` NULL on 217 → `proposition` 217; final counts 85496/48366 unchanged. Online builds already stored these fields; only the cached reports of earlier builds lacked them, and `--offline --repersist` now interprets every vote again. A second replay changes nothing. Vote 1005 now renders the legend and `Antrag: Abgelehnt (berechnet)` instead of `Kein Ergebnis verfügbar`.
- **Official results:** the Beschluss block is found by its Drucksachen, with a tolerance of 3 per side only inside such a block, and the outcome may sit in the next paragraph when it names the block's document. Official results 140 → 183 of 217 by the live-page corpus check (43 gained, none changed; 34 stay unresolved, for example 1002, whose page prints several blocks with the same final tally). Vote 996, freshly acquired online (`--document-number 21/67`, including 629 member records): `rejected`, official, scope `application`, inverted, 439/135, and the result survives two replays, with no store replacement on the second.
- **Review fixes:** an announcement now proves an inversion only for a vote on the recommendation (the listing opens with the Beschlussempfehlung, or the chair names its Drucksache among the vote's); a report replayed without its XML keeps its protocol inversion also where its title would invert on its own (the source no longer flips to `bundestag-roll-call`); `build_report` sets the top-level `report["sitting_votes"]` that derive and the store read, so an online build no longer drops the votes no TOP claims (the reference reports hold none, so no figure moves). Adjacent chair passages retain recommendation context, later duplicate copies supply their evidence to every copy, and a foreign current roll-call announcement cannot earn an official result from matching counts. Final revalidation: 290 reports rebuilt; all 217 votes agree across JSON, SQLite, downloadable SQLite and CSV; raw member/fraction counts unchanged. Chrome DevTools confirms 906, 996, 1005 and the direct-vote control. The full suite passes (1,521 unit tests, one skipped, plus browser integration).

**Remaining limits:** Official results missing from a cached report require an online refresh; even then 34 source-page matches remain unresolved. Optional `majorityType`, vote times and the Fundstelle anchor remain open and are outside this completed correctness repair.

**Context:** Smaller extras from the same analysis, worth storing when touching this code: the page's own `<roll-call-votes-component>` JSON carries `majorityType` (only from 2024; 2 of 5 non-simple values look wrong, 926 and 973, so use it only as a cross-check), plus the protocol Fundstelle anchor and vote times.

**Effort:** M
**Priority:** P1
**Depends on:** None

**Completed:** v0.22.0.0 (2026-10-24).

### Test the independently loaded historical parser and classifier

**Completed:** v0.21.1.0 (2026-10-23). A focused CLI regression loads tiny independent parser/classifier stand-ins for the documented rule-4 comparison, without copying historical modules or delegating parsing to the current parser. It checks historical count deltas, rule version and file hashes while current counts stay unchanged across two XML files. Mutation checks detect both historical-to-current and current-to-historical classifier sharing. All four audit CLI tests and the full Python suite pass (1,487 tests, one skipped). No production change was needed.

### Debattenprofil counts Tagesordnungspunkte, and "Wieder auf der Tagesordnung" replaces "Verfahren, die zurückkehren"

**What:** `week_stats` (`scripts/render_dip_pulse_html.py`, `vorgangstyp_counts`) adds 1 per Vorgangsposition. Count each Tagesordnungspunkt once for each distinct Vorgangstyp among its positions instead, and compare against the Wochenvergleich week the same way. On the real store, TOP 7 of Sitzung 21/50 bundles 26 Petition positions with 1 Rede and currently adds 26 to "Petition". 70 TOPs carry 6 or more positions. Change the card note ("Vorgangspositionen nach Art") and the sources.html glossary intro ("zählt die Vorgangspositionen der Sitzungswoche") to say Tagesordnungspunkte and Kalenderwoche. Rename the card heading "Verfahren, die zurückkehren" to "Wieder auf der Tagesordnung" and drop "Verfahren" from its notes. The `returning_vorgaenge` rule itself already matches the glossary. Done when a bundled TOP adds at most 1 per Vorgangstyp and no Puls text says "Verfahren" for a Vorgang.

**Why:** CONTEXT.md (Vorgangstyp, mitberatener Vorgang, Debattenprofil, wiederkehrender Vorgang, 2026-09-26).

**Context:** Only the Puls card and its week view read `vorgangstyp_counts`; facts.py and the Daten page do not (checked 2026-09-26).

**Effort:** S
**Priority:** P2
**Depends on:** None

**Completed:** 2026-10-23. `week_stats` counts each Tagesordnungspunkt once per distinct Vorgangstyp for both weeks. The card and glossary explain TOP counts per Kalenderwoche; the returning card is headed "Wieder auf der Tagesordnung" and its notes use Vorgang/Vorgänge. A regression test covers repeated and mixed types, separate TOPs and the comparison week; all 28 week-comparison tests pass, and the full Python suite passes (1,374 tests, one skipped).

### Document `--protocol-wahlperiode` in the README

**Completed:** v0.20.6.2 (2026-10-22). README's update section now documents the default `21`, filtering only with positive `--limit`, older-Wahlperiode and all-Wahlperioden examples, the separate `--detail-limit`, and explicit/backfill selection. The former TODO's catalog-filter claim was stale: online builds always fetch the whole catalog; the Wahlperiode filter applies only to acquisition. Verified against `parse_args()`, `main()`, `select_acquisition_protocols()` and offline parser/selection checks of the examples.

### Fakt der Woche, copy fixes from the glossary review

**What:** Three copy corrections. (1) `_render_fact_sources` (`scripts/build_dip_pulse_site.py`) heads a Fakt's citation list "Quellen"; rename it "Belege", matching the Daten export's "Belege je Fakt", whose description should also name Tagesordnungspunkte. (2) The withheld reason for a monthly Kennzahl reads "diese Woche nicht messbar"; make it period-aware. (3) The footer "Spätere Sitzungswochen ändern frühere Karten nicht; nur eine Korrektur an den Rohdaten kann es" understates what changes a Karte: every build re-renders them, so a rule change (threshold, Mindestwert, wording) changes them too, and a Karte whose Beleg no longer resolves disappears. Say so, or make Karten immutable via the publication ledger.

**Why:** CONTEXT.md (Beleg, zurückgehalten, Karte, 2026-09-25). "Quellen" is the site-wide name of sources.html, so the same word names two things on one page.

**Effort:** S
**Priority:** P3
**Depends on:** None; (3) interacts with the publication ledger item

**Completed:** v0.20.7.0 (2026-10-23). Fact citation lists now say "Belege"; the Daten description also names Tagesordnungspunkte. Shared comparison copy uses the existing period kind for "diese Woche" and "diesen Monat", including archive/page status text. Methodik and weekly/monthly page footers explain that rebuilds regenerate cards and data/rule/wording changes can alter them; Methodik also notes that an unresolvable Beleg removes a card. Validation: 153 fact tests and the full Python 3.13 suite (1,373 tests; one skipped) passed, along with script compilation and diff checks. The publication ledger remains a separate open item.

### Add an accessible role to bill search controls

**What:** Give `.bill-controls` `role="search"`, retaining `aria-label="Gesetzesvorhaben finden"`, so the bill overview exposes a named search landmark. Empty publications omit the controls.

**Why:** Accessibility finding from the v0.18.0.0 adversarial review. See [implementation plan](docs/plans/bill-search-accessible-role.md).

**Effort:** S
**Priority:** P3
**Depends on:** None

**Completed:** v0.20.6.1 (2026-10-22). Added the named search landmark and nonempty/empty markup assertions. Validation passed: 29 bill tests, the full suite (1,371 tests; 1 skipped), and desktop/mobile browser checks.

### Cite protocols as „BT-PlPr." per DIP no. 4c

**What:** Change the „BT-PlPr" source labels (e.g. the bill-event `source` built in `scripts/build_dip_pulse_site.py`) to „BT-PlPr." plus number, and check the other citation strings against DIP no. 4c („BT-Drs.").

**Why:** DIP no. 4c prescribes the abbreviations exactly.

**Effort:** S
**Priority:** P3
**Depends on:** None

**Completed:** v0.20.6.0 (2026-10-22). Protocol labels now use `BT-PlPr.`; document citations preserve issuer and type, including BR and protocol documents. Fact receipts resolve the issuer by document ID. See the [implementation and citation audit](docs/plans/protocol-citation-labels.md#implementation-and-citation-audit-2026-10-22).

### Tag the abgeordnetenwatch MP columns with their real source

**Completed:** v0.20.5.1 (2026-10-22). `birth_year`, `gender`, `profession`, `wahlkreis` and `bundesland` now carry the `abgeordnetenwatch` source tag. The export test pins all seven abgeordnetenwatch MP columns, export format 6 invalidates cached manifests, and the "Known gap" paragraph in `docs/data-license.md` is removed.

**Why:** The roster build fills all five from the abgeordnetenwatch resolver (`profile_resolver.resolve` / `fetch_bio`), but the manifest claims `dip`. The per-column licence in `docs/data-license.md` depends on these tags: the columns are CC0, not DIP-terms data. The MP-page footer already credits abgeordnetenwatch.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Stop calling a Plenarstelle a "Debatte" on the bill pages

**What:** The bill detail section "Debatten" and the overview count "N Debatten" (`render_bill_detail`, `render_bills_index` in `scripts/build_dip_pulse_site.py`) count Plenarstellen, i.e. `protocol_refs`. Relabel them (for example "Beratungen im Plenum" or "Plenarstellen", with a glossary tooltip) or count only Plenarstellen with at least one Rede as Debatten. Update the section anchor `#debatten`, the harness section-order assertion and the CHANGELOG wording of the next release.

**Why:** CONTEXT.md lists "Debatte" under Avoid for Plenarstelle and Tagesordnungspunkt, because a Tagesordnungspunkt can pass without any Rede; a count of "3 Debatten" can include sittings where nobody spoke. The v0.18.0.0 docs audit blocked on this; the owner kept the glossary rule and shipped with the conflict named.

**Context:** `xml_speech_count` on each ref (`protocol_refs[].speech_count`) already says whether anyone spoke. Decide label vs count semantics before editing.

**Effort:** S
**Priority:** P2
**Depends on:** None

**Completed:** v0.20.5.0 (2026-10-22). Implemented [the relabeling plan](docs/plans/relabel-bill-debatten.md): overview counts, detail heading/navigation, accessible label, empty state and discovery copy now use "Beratungen im Plenum"; the section anchor is `#plenarstellen`. Every protocol reference still counts and remains linked, including zero or missing speech counts. The explanation reuses the Tagesordnungspunkt glossary. Design documentation and the next-release changelog are aligned. Validation: 28 bill tests passed; the full Python 3.13 suite ran 1,365 tests with one skipped; desktop/mobile browser checks passed. Collection, persisted data and count calculations are unchanged.

### Rename the "Aufmerksamkeitsrang" sidebar and fix its description

**What:** The dossier sidebar is headed "Aufmerksamkeitsrang" (`scripts/render_dip_pulse_html.py`), and sources.html calls it "Aufmerksamkeitsranking … aus extrahierter Redenanzahl und extrahierten Redetext-Zeichen" (`scripts/build_dip_pulse_site.py`), but it sorts by number of Reden only. Rename the heading and the back link (e.g. "Meiste Reden"), keep the `#aufmerksamkeitsrang` anchor or redirect it, and make the sources.html entry say it ranks by Reden while the second bar shows Textanteil.

**Why:** CONTEXT.md (Rangfolge nach Reden, 2026-09-25): the number of Reden mostly follows the debate length agreed in advance, so "Aufmerksamkeit" claims more than the ranking measures.

**Effort:** S
**Priority:** P3
**Depends on:** None

**Completed:** v0.20.4.0 (2026-10-21). The heading and back links now say "Meiste Reden"; the sources entry explains sorting by Reden and the bars’ Redeanteil and Textanteil within the Sitzung. The existing `#aufmerksamkeitsrang` anchor is preserved. Heading, link, empty-state and sources-copy assertions cover the wording; local desktop/mobile rendering and the back link were checked. Python 3.13: 1,364 tests ran, one skipped.

### Recipe copy: compare the selection by range, not by text

**What:** `recipe_copy_runtime_script` (`build_dip_pulse_site.py`) now guards both the success and rejection handlers with `copy !== latestCopy` (fixed in b6e1f8a), but the rejection's "did the reader select something else" check still compares the selection's text. Selecting *identical* text in another recipe passes that comparison, so a late rejection still replaces that selection with its own SQL. Compare the selection's range endpoints instead of its text. Done when a rejection that settles after the reader selected matching text elsewhere leaves that selection alone.

**Why:** Final-round Codex review of v0.6.6.0 (2026-09-26), reproduced with controlled promise settlement. Deferred per the ship's review-round limit; the common cases (rejection with nothing in between, newer click, different selection) are fixed and verified live.

**Effort:** S
**Priority:** P3
**Depends on:** None

**Completed:** 2026-10-21. Copy rejection now compares every range's saved endpoint nodes and offsets, preserving equal text selected elsewhere. The emitted-runtime regression failed before the fix; all 16 new recipe scenarios and existing browser checks pass. Python 3.13: 1,363 tests ran, one skipped. See [implementation receipt](docs/plans/recipe-copy-selection-race.md#implementation-receipt-2026-10-21).

### Keep keyboard focus on reset, and reopen a speech on a repeated link click

**What:** Two small interaction gaps on the bill pages. (1) „Suche und Filter zurücksetzen“ hides itself while it has focus (`apply()` sets `reset.hidden`), so keyboard focus falls to `<body>`; move focus to the search field or the result summary in the reset handler, as prev/next already do with the summary. (2) Clicking the same speech link a second time after closing that speech card in the dossier leaves it closed, because the fragment is unchanged and `hashchange` never fires (`speech_hash_runtime_script` in `scripts/render_dip_pulse_html.py`); also handle the link click itself.

**Why:** Both were found in the v0.18.0.0 adversarial review after the fix-cycle limit was reached. (1) is an accessibility regression for keyboard and screen-reader users; (2) makes a speech link look broken.

**Context:** `render_bill_script` in `scripts/build_dip_pulse_site.py`. Extend `tests/bills_browser_check.js` with a reset-focus assertion; the speech-hash case needs a small dossier fixture (the harness has none yet).

**Effort:** S
**Priority:** P2
**Depends on:** None

**Completed:** v0.20.2.0 (2026-10-20). Reset focuses search; repeated speech links reopen their card. Automated desktop/mobile Chrome checks cover reset state, link guards and actual Enter-key activation.


### Politikfelder: harden the Vorgang fetch and the repersist guard

**Completed:** v0.20.1.0 (2026-10-20). Implemented `docs/plans/politikfelder-hardening.md`, including its adversarial additions: partial-response salvage without negative-caching incomplete membership, separate validation/outage accounting, identity-based replay protection and explicit store-read refusal, cache version/read-error preservation, unique corruption backups, complete atomic-save fallback, and 44px coarse-pointer chips. ID fetches also preserve unrelated cached records. Python 3.13: 1,363 tests ran with one skipped; demo publication checks and Chrome DevTools mobile/desktop fixture checks passed. No live cache/store changes or DIP requests.

**What:** Findings of the second adversarial round of the v0.20.0.0 ship review (2026-10-19), in code that ship added, deferred because its three fix cycles were used:
1. One malformed DIP record fails its whole batch: `validate_dip_protocol.vorgang_cache_record` raises DipError for a Sachgebiet that is not a list of labels, inside `fetch_vorgaenge`'s batch loop, so 99 good Vorgänge are not cached and the batch counts toward the outage breaker. A DIP-wide shape change would trip the breaker and leave every new TOP `not_fetched` in a build that still publishes. Validate per record, keep the good ones, and count shape errors apart from outages.
2. `build_dip_pulse_site.require_vorgang_cache_for_tags` returns on any `sqlite3.Error`, so a locked or corrupt store passes the guard; only "no such table" should pass, anything else should refuse.
3. The same guard compares totals of `not_fetched` rows, not identities, so a cache that recovers some `not_fetched` items while losing others passes (the real store has 0 `not_fetched`, so this needs a store that is already degraded). Compare per TOP and vote id. A vote id that persist cleans to nothing ("" or blanks) also counts in the derivation but not in the store.
4. A falsy malformed value (`sachgebiet: false`, `""`, `{}`; a list answer whose `documents` is `{}`) is defaulted to empty before the shape check and cached as "fetched, nothing known" (`vorgang_cache_record`, `ApiClient.list_all`); see deferred item 6.
5. `politikfelder.load_cache` ignores the cache's `version` and writes it back as 1; drops a record whose Sachgebiet is `null` without a word (normalise to `[]`); a second corruption overwrites the first `.corrupt` copy; and `save_cache` has no fallback when the final rename itself fails after private staging.
6. On touch screens the Politikfeld and Fraktion filter chips on the week radar and the votes archive are 30px tall (`.radar-filter .chip`, `.chip` in `votes_archive_styles`), below the 44px that v0.19.1.0 gives every other control on `puls.html` under `@media (pointer:coarse)`.

**Why:** None is reachable on the reference data (7,511 cached Vorgänge, all well formed; 0 `not_fetched`; the guard passes the real store and refused every 1–50% random cache deletion tried), but 1, 2 and 6 would hurt the first time DIP or a deployment does something unusual.

**Effort:** S
**Priority:** P2
**Depends on:** B3


### A.2 test follow-ups

**What:** Done 2026-10-16 (handoff 06), each mutation-checked; done 2026-10-18: a stale non-roster record of a person who still has current records stays off that person's page (rule in docs/stable-ids.md, `test_a_stale_speaker_record_stays_off_a_page_with_current_records`). Tests the A.2 reviews proposed and nobody wrote: the online `main()` roster wiring with `mp-roster` not selected; `rebuild_database_from_entries` forwarding the `built` set to the facts engine; page eligibility of persons with no current mps row (a former MdB whose roster row vanished, a vote-only historical record); arrival-order independence of `p-NNNNNN` allocation and of `_content_digests`; table-driven occurrence-id cases for vote members, sampled people and the preserved roster; `_inputs_hash` and `_zusammenfuehrung` numbers.

**Why:** Each of these can be disabled today with the suite still green (checked by mutation in the A.2 review).

**Context:** Deferred from the A.2 review (2026-10-01); the generation allowance of /ship was spent. The roster wiring on a selected `mp-roster` and its outage abort, the catalog hand-offs and the unreleased-draft registry were covered in the second A.2 ship round.

**Effort:** M
**Priority:** P2
**Depends on:** None

**Completed:** v0.19.0.0 (2026-10-18)

### A.2 third ship round: deferred findings

**What:** Findings of the third A.2 ship round (2026-10-02) the user chose not to fix before release, none affecting today's data: (1) done 2026-10-12: removing an applied partition from `person_corrections.json` is refused by `reconcile` (`person_registry.require_applied_partitions`), label and profile-owner edits follow the file, and the deliberate undo is a reviewed merge or a fresh rebuild (docs/stable-ids.md); (2) done (verified 2026-10-16, already fixed): `corrected_speaker` compares `derive.first_redner_id`, so a merged double id like `11005304 999990074` meets its reviewed occurrence override (`test_a_combined_redner_id_meets_its_partition`, mutation-checked); (3) done 2026-10-15: `--offline` over a store path that cannot be opened (a directory, an unreadable file) exits 1 naming the store and leaves it as it was (the open is inside the pre-flight `try`; `--offline --repersist` reports it as `ERROR [repersist]`), and `open_readonly` quotes the path into its URI; (4) done 2026-10-14 for id-less rows: the roster ingest, the sampled DIP persons and the preserved roster skip a DIP person without an id with a warning instead of collapsing it into one `name-party:Unbekannt` record; done 2026-10-14: a DIP person id given as `7`, `"7"` or `" 07 "` is one roster occurrence and identity (`stable_ids.canonical_dip_person_id`, the decimal text DIP prints, so issued roster keys stayed); (5) done 2026-10-16 (handoff 08): `reconcile` has no `full_build=False` mode and `_load_rows` no `bound` fallback (liveness is the build's touched set; the rebuild starts it with `person_registry.begin_build`, and a connection without one is refused), and every `bind`/`upsert_mp` names its occurrence; kept: the `vacated` mark, which `is_stale_roster_partner` needs (reachable when two DIP persons fold on one trusted abgeordnetenwatch id and one is later listed under another, `test_a_vacated_roster_record_does_not_rejoin_as_a_stale_partner`), and the refusal stub in `persist_dip_pulse_store.py`, which README and docs/project-documentation.md describe as the script mode; (6) done 2026-10-15: `_first_touch` (and `_touched`) treat only `no such table: registry_touched` as the missing temp table, so any other `OperationalError` fails the staged rebuild and keeps the store; done 2026-10-16 (handoff 08): the rebuild returns `Rebuilt(replaced, facts_report)` instead of filling a `facts_report` out-parameter, and `run_data_pipeline` computes the facts only for `facts_report=None`, so an empty result counts as computed; (7) done (verified 2026-10-16, already fixed since v0.12.0.0): the export reads the person mapping from its distribution copy and refuses a store that changed while it was copied; both guards now have tests; (8) done 2026-10-14: a record keeps the identities its occurrences presented when they differ from its own (`identities` in the evidence), and match_rows pass 1a joins live records presenting one identity, so a corrected roll-call profile link groups like a fresh build; (9) done 2026-10-14: a name-guess group with one contradicting pair stays split as a whole (decided: in a chain A-B-C-D with A and D contradicting any link may be the wrong one, so no subset is supportable; pinned); `aw_match` is read from the build's occurrences since v0.17.1.0 (verified), and two different trusted aw ids on one record now give it none (`AW_CONFLICT`); overlapping reviewed merges are applied as one merge per resulting person, and two survivors for one person are refused; (10) done 2026-10-14 (schema 4, export format 4): a Drucksache is keyed by issuer (`herausgeber`, BT or BR) and canonical number, the URL is an attribute chosen by content, so a URL rewrite keeps document ids, junctions and fact receipts (docs/stable-ids.md, Documents); (11) done 2026-10-14: the debut tie-break reads protocol numbers as Wahlperiode/number with malformed numbers last, and persist, render and bills read agenda indexes through `stable_ids.source_index`; done 2026-10-15: the staged copy, its sidecars and the writer lock live in the store's private directory (`person_registry.private_dir`: `.OUTPUT.private/` beside the output directory), derived from the resolved store path so every spelling of one store shares the lock (docs/stable-ids.md); done 2026-10-18: the facts engine computes read-only and writes a changed snapshot into a staged copy that replaces the store (`run_facts_engine`; `journal_mode=MEMORY`/`OFF` rejected, a crash could corrupt the published store), and the render opens the store read-only; done 2026-10-18: the Daten export keeps its lock, store copies, temp files and the generation it builds in `.OUTPUT.private/exports/` (`export_work_dir`) and renames the finished `g-<hash>/` in before it replaces `datenstand.json` (a failed export leaves the published tree as it was; an old `data/exports/.lock` is harmless and can be deleted); (12) done 2026-10-16 (handoff 06): tests for the rebuild's `full_build=True` call, the offline facts hand-off, `compare_store_values._zusammenfuehrung` rows, the `mps` foreign-key arm, the end-of-rebuild foreign-key and integrity checks and `today` forwarding.

**Why:** (1), (2), (7) and (8) can make an incremental build differ from a fresh one or show the wrong name; the rest are robustness, cost or test gaps.

**Context:** Deferred by decision in the third A.2 ship round after three review rounds converged and the 285-report reference replay stayed unchanged (grouping sha `6f877bf3d1e92af0`). Each item was reproduced or read by a reviewer; see the ship run record for the evidence.

**Effort:** M
**Priority:** P2
**Depends on:** None

**Completed:** v0.19.0.0 (2026-10-18)

### Politikfeld tags on Tagesordnungspunkte and votes

**Completed:** v0.20.0.0 (2026-10-19). A closed list of 13 Politikfelder (`scripts/politikfelder.py`), 1 to 3 tags per TOP and per vote, derived deterministically at persist and render time and never written into a report. Tables `agenda_item_politikfelder` and `vote_politikfelder` (CHECK constraints from the closed lists), `proceedings.sachgebiet`, 27 CSVs, store schema 5, `EXPORT_FORMAT` 5, the tag tables marked `derived`. Chips on the dossier TOP cards, a Politikfeld filter with `?politikfeld=` on `votes/index.html`, and a chip filter on the week radar. Sources, in order: the Sachgebiet of the TOP's Vorgänge (lead first, then by frequency, at most 3), then the Drucksache numbers the TOP names, then the Einzelplan in the heading or TOP id keyed by (Wahlperiode, number); a vote takes its own Drucksachen first, then its TOPs. The Vorgang cache is `data/dip-vorgang-cache.json`, filled by online builds only; a cache miss is stored as `not_fetched`.

Real store (290 Sitzungen, 2,912 TOPs, 217 namentliche Abstimmungen), measured 2026-10-09 after one cache fill and `--offline --repersist` on the final code, and again unchanged on 2026-10-18 after the merge with v0.19.0.0 (documents re-keyed by issuer and number; every figure below is identical):
- Votes without a row: 0 (TOPs: 0). Votes by source: 216 `drucksache` (99.5 %), 1 `untagged` (the Wahlprüfung vote 20/66).
- TOPs by source: 2,109 `sachgebiet` (72.4 %), 196 `drucksache` (6.7 %), 149 `einzelplan` (5.1 %), 458 `untagged` (15.7%), 0 `not_fetched`.
- The 458 untagged TOPs: 77 Fragestunden, 77 Befragungen der Bundesregierung, 119 Wahlen, Geschäftsordnung, Ordnungsmaßnahmen and Immunität, 51 with an empty heading, 103 whose heading names a Gesetz or Antrag but for which DIP gave no usable Vorgang and Sachgebiet, 31 other.
- First tag over TOPs: Außenpolitik 424, Wirtschaft & Finanzen 397, Soziales 390, Energie & Klima 282, Staat & Demokratie 197, Gesundheit 146, Bildung 138, Innere Sicherheit 119, Digitales 102, Justiz 79, Verkehr 75, Migration 70, Verteidigung 35. Over votes: Außenpolitik 57, Energie & Klima 41, Wirtschaft & Finanzen 28, Soziales 19, Innere Sicherheit 16, Gesundheit 14, Staat & Demokratie 12, Migration 11, Verteidigung 8, Justiz 4, Verkehr 3, Digitales 2, Bildung 1.
- The /ship review moved these figures three times, all in the Drucksache-number rule: a vote's numbers are filtered to the sitting's Wahlperiode or the one before (2 of 5,414 numbers were junk such as "76/787"); numbers naming 2 Vorgänge or fewer come before bundles for a vote, and a number naming more than 10 is ignored (73 of 2,401 numbers name 5 or more, 4 name 69), which stopped Sammelübersichten from adding fields to 24 of 216 votes and 11 TOPs; a TOP that has Vorgänge of its own is never tagged from the Drucksachen it only cites (12 TOPs, for example a Wahlprüfung Sammelübersicht that had been tagged Bildung and Gesundheit). TOPs through `drucksache`: 211 before the review, 196 now.
- Measured live (2026-10-04): `/vorgang?f.id` returned 400 ids in one call (batch kept at 100); a repeated `f.dokumentnummer` returns one deduplicated union and cannot say which number belongs to which Vorgang, so numbers are resolved one call per number (25 of 25 sampled Beschlussempfehlungen resolve to a Vorgang of their own TOP). A Sammelübersicht can resolve to several Vorgänge (20/13413 gives 5), so a vote's Vorgänge are ranked by how many of its numbers name them. About 4 lookups a second made DIP's edge answer HTTP 400 with a bot challenge to the whole API for over an hour, so the build pauses before every request: 0.5 s per lookup at first (the first full fill of about 2,400 numbers took 25 minutes, 1,577 s), and since the v0.20.0.0 review also before the second request of each lookup, so a first fill now takes about 45 minutes; later builds fetch only new ones.
- The plan's "113 TOPs headed only Einzelplan 04" is real, but the Einzelplan sits in `top_id`, not the heading (117 TOPs, mostly the Haushaltswoche). The rule reads both; before that fix the Haushaltswoche rows of the radar were untagged (Einzelplan TOPs 37 -> 149, untagged 555 -> 443).
- Mapping surprises, left as designed: a Haushalt vote takes the Sachgebiet of its Haushaltsgesetz Vorgang (Wirtschaft & Finanzen), not its ministry's field; a bundled heading with one Einzelplan sub-item and no Vorgang is tagged from that sub-item alone (20/106 TOP 6); a Regierungserklärung carries every field of its Entschließungsanträge.

### Credit a Zwischenfrage to the MdB who asked it, and keep Gastansprachen out of speech counts

**Implemented on `a1-followups` (2026-10-05):** Nested source segments are stored and linked as separate Beiträge. Guest coverage is qualified: the inspected 2016/2021 memorial addresses precede the plenary sitting and are absent from its XML; no general guest detector or exhaustive ingestion is claimed. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### A1 classifier precision: measure and tighten the Kurzintervention and Fragestunde rules

**Implemented on `a1-followups` (2026-10-05):** Occurrence-role recovery, historical headings/classes, explicit D4 rejection, grant precision, party/name extraction and unique sitting-source asker matching are implemented. The old pronoun example at 21/81 was not reproduced; a pronoun regression is covered without claiming that source finding. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### Stale derived data after `--offline --repersist`

**Implemented on `a1-followups` (2026-10-05):** Persisted input rule version 2 guards facts/export/store-consuming rendering; SHA pairing and proven TOP mappings protect replay. Vote receipts select one coherent source row and dead adapters are removed. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### Regenerate the architecture diagram for the Rede/Beitrag split

**Implemented on `a1-followups` (2026-10-05):** Architecture JSON/HTML regenerated with speech kinds, contributions, replay and persisted-rule refusal; archify validation and Chrome light/dark inspection recorded. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### Zu Protokoll gegebene Reden: decide what they are, then store them

**Implemented on `a1-followups` (2026-10-05):** Approved separate kind `zu_protokoll` is ingested/displayed with nullable TOP/page, including sitting-level submissions. Correction to the original examples: 19/239 (29) and 18/200 (11) are §31 declarations, excluded; 18/100 has 35 explicitly typed written submissions. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### Roll-call member rows link to external profiles, never to our own MP pages

**Completed:** v0.14.0.0 (2026-10-04), B.2. Dossier member rows resolve the shared, normalized vote-member occurrence key through `mp_lookup`, then fall back to the external profile or a plain name. TOP and sitting votes use the same member renderer. The T0 gate required widening scope: surname-first vote names are normalized for matching, roster/speaker pairs settle first, then vote records join one unambiguous person. Conflicting ids, ambiguous namesakes and distinct records present in one roll call stay split. MP pages prefer roster/speaker biography and correctly label a Bundestag profile fallback.

**Measured:** 285-report scratch replay: internal lookup coverage **0 → 147,971 / 154,015 stored member rows (96.08%)**; split-bucket misses **147,971 → 0**; vote-only misses remain **6,044 rows**. All 154,078 vote-member occurrence keys stay byte-identical. Current person groups **3,386 → 1,294** because duplicate vote-source records now join their roster/speaker person. D3 collisions: **0** (no namesake-key TODO needed). Rendered member links: **0 → 166,656 internal**, **173,407 → 6,751 Bundestag** (965 persons); every internal href exists. Browser click-through reaches the matching vote on the Personenseite. Full unittest suite passes.


### Detect Kurzinterventionen and Erwiderungen, and stop counting them as Reden → #68; Stop counting the Fragen and Antworten of the Befragung and Fragestunde as Reden → #70

**Completed:** v0.13.0.0 (2026-10-03), PR 1 of the A1 roadmap item, branch `a1-what-counts-as-rede`. `speeches` holds Reden only; every other unit is a Beitrag in the new `contributions` table, typed by `kind` (`scripts/speech_kinds.py`). The Fragestunde, which has no `<rede>` elements (75 of 76 Fragestunden stored no row), is parsed from its flat `<p klasse="redner">` turns. Every online update now keeps the sitting's XML in `data/xml/`, and `--offline --repersist` re-reads Reden and Beiträge from it.

Reference store (285 Sitzungen), the same cached reports parsed by the code before and after, so only this change moves:
- Reden 34,775 -> 25,800 (-8,975, -26 %); DIP's own `Rede` count for the same sittings is 26,396 (our count is 2.3 % lower). The first measurement of this branch said 26,002; the /ship review found and fixed two classifier defects (below), which moved it by 202.
- Beiträge 14,363: 636 Kurzinterventionen, 581 Erwiderungen, 3,890 Fragen and 3,868 Antworten of the Befragung, 2,701 Fragen and 2,687 Antworten of the Fragestunde.
- `speeches.char_count` sum 114,848,500 -> 107,813,062 (-6.1 %).
- Redeanteil: Bundesregierung 14.6 % -> 4.6 %, CDU/CSU 22.2 -> 24.8, SPD 17.7 -> 21.2, AfD 14.6 -> 15.2, Grüne 13.5 -> 14.5, FDP 7.4 -> 8.5, Linke 6.9 -> 7.4.
- Kurzinterventionen 636 against DIP's 682 (93.3 %), Erwiderungen 581 against 646 (89.9 %); 59 of 285 sittings differ from DIP in one of the two kinds, and in 6 sitting-kinds the XML holds more than DIP. The detector reads the Sitzungsleitung's wording and prefers precision: it misses announcements that only refer back ("das Wort zu einer solchen"), that call it "Intervention" or that contain a negation ("der eine Kurzintervention bekommt, weil er keine Zwischenfrage stellen durfte"). DIP's `Frage`/`Antwort` counts are not comparable (DIP 6,884 + 633 Fragen and 4,198 Antworten against 6,451 and 6,416) and are not checked.
- Fixed in review, measured on the same 285 XMLs (17 sittings moved, nothing else): (1) three items whose heading sits in a `T_ZP_NaS` paragraph (20/143 TOP 2, 20/159 TOP 3 and 4) were not recognised as Befragung or Fragestunde, so 212 Befragung turns counted as Reden and 67 Fragestunde turns were stored nowhere; (2) the Erwiderung wording rule ("Möchten Sie antworten? - Nein") turned real Reden into Erwiderungen (15 Reden back, including Edis's maiden speech in 21/14, which the `erste-reden` Fakt needs); 5 announced Kurzinterventionen that had been read as Erwiderungen or Reden are now typed correctly. Sittings that differ from DIP: 68 -> 59; sitting-kinds where the XML holds more than DIP: 15 -> 6. The Erwiderung total moved away from DIP's 646 (596 -> 581) because the removed ones were false positives.
- Not measured: the Fakt der Woche winners that changed. The reference tree has no cached DIP catalog, so the facts engine posts nothing offline; run an online update, then compare. The five speech metrics are at version 2.

### render_html mutates the report it renders

**Completed:** v0.12.0.0 (2026-10-02). `render_html` corrects copies of the speeches; the cached dossier JSON keeps the printed speaker (pinned by a test that writes a dossier twice).

**What:** `render_dip_pulse_html.render_html` replaces each `speech["speaker"]` with the corrected speaker and adds `speaker["occurrence_id"]` in place. The online path then writes that report to the cached JSON in `write_report_files`, so the cache holds the correction instead of the raw XML evidence.

**Why:** Raw evidence should stay raw. Today the mutation is idempotent, but removing a correction cannot restore the original names, and online and offline builds see slightly different inputs.

**Context:** Deferred from the A.2 review (2026-10-01). Fix with a side map keyed by (item index, sequence) or a copy of the speakers, applied only at render and persist time.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Match roll-call votes to a TOP when Drucksache numbers fail

**Completed:** v0.10.0.0 (2026-09-30). Uniquely matching titles can attach a candidate to a TOP; otherwise fetched candidates remain in `sitting_votes` and persist through `votes.protocol_id`. They appear under “TOP nicht zugeordnet”; acquisition completeness now tracks missing scans and failed fetches separately from missing TOP attribution.

**What:** `enrich_with_api` (`scripts/validate_dip_protocol.py`) attaches a roll-call vote to a TOP only when their Drucksache numbers overlap. A candidate that matches none is logged, counted (`validation_summary.unmatched_roll_call_vote_count`) and, since fix-votes-completeness, makes the sitting's votes `partial` (`unmatched_candidate`). Match by title or vote date where numbers fail, or store the vote against the Sitzung without a TOP.

**Why:** After the 2026-09-29 backfill of the reference copy, 23 candidates in 15 sittings (e.g. 21/83 vote 1008, 21/40 votes 977 and 978) matched no TOP, so those votes are in no dossier and not in the store, and those sittings, with the weeks and months holding them, stay incomplete until this is fixed.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Inverted-vote reading for Beschlussempfehlungen ("Ja = Antrag ablehnen")

**Completed:** v0.10.0.0 (2026-09-30). Confirmed proposition-specific evidence is stored with its source and excerpt; raw vote totals and proposition result stay intact, while dossier and archive views derive the Antrag outcome and Fraktionsposition.

**What:** When the voted document is a committee recommendation to reject a motion, the panel states the reversal in one procedural sentence, prints the legend `Ja = Antrag ablehnen · Nein = Antrag annehmen`, and derives each fraction's position ("für den Antrag" / "gegen den Antrag" / "geteilt") from its `leading_vote`; raw counts stay untouched. Done when the Übergewinnsteuer-style case (plenarwatch post `ablehnung-eines-antrags-zur-uebergewinnsteuer-2026-04-24`) renders the derived positions and a test pins the inversion.

**Why:** Without the inversion the outcome badge from the previous item reads "Angenommen" on a vote whose political meaning is "Antrag abgelehnt", the single most misleading state a vote panel can be in. "Beschlussempfehlung" appears in our code only as glossary prose (`scripts/render_dip_pulse_html.py:59-188`).

**Context:** Detection signal: the DIP `vorgang`/Drucksache title of the voted document starts with "Beschlussempfehlung" and the recommendation text contains "abzulehnen"; DIP's `/drucksache` endpoint carries the title, so no PDF parsing. Store as a boolean on `votes`; render in `render_vote_summary`.

**Effort:** M
**Priority:** P1
**Depends on:** Vote outcome badge

### Majority rule for derived vote outcomes (Art. 79(2), 67, 68 GG)

**Completed:** v0.10.0.0 (2026-09-30). Official attributed results take precedence; without one, recognized special-majority procedures stay unknown. Ordinary votes retain the Ja/Nein rule.

**What:** `validate_dip_protocol.vote_result` derives "Angenommen"/"Abgelehnt" from a plain yes>no majority of votes cast. A Grundgesetz amendment needs two thirds of the members (Art. 79(2) GG); Kanzlerwahl, konstruktives Misstrauensvotum and Vertrauensfrage need an absolute majority of the members (Art. 63, 67, 68 GG). Thread the applicable threshold (from the Vorgang/Drucksache type) into `vote_result`, or return unknown for those vote types when no official result was scraped. Validated with fixtures for each special-majority procedure: without an attributable official result the outcome is unknown, including Ja > Nein; no membership total is inferred.

**Why:** Found by the /ship red-team review of the badge (2026-09-26). Latent: every Grundgesetz vote in the real store is labelled correctly today, but a high-absence sitting would mislabel one silently.

**Context:** The official-result scrape already wins when bundestag.de states the outcome; the gap is only in the derived fallback.

**Effort:** S
**Priority:** P2
**Depends on:** Vote outcome badge

### Vote outcome badge, linked Drucksache and XLSX source on the vote panel

**Completed:** v0.7.0.0 (2026-09-26). Badge ("Angenommen"/"Abgelehnt") from `result_raw`/`result_source` (official bundestag.de wording when scrapable, otherwise derived with a tie counting as rejected), every `document_numbers` entry linked to its Drucksache via the XML/DIP objects that already matched the vote, and a scraped XLSX link (bundestag.de publishes it on a separate Namenslisten page, matched by date and title — never a derived URL). Real store (2026-09-26): 217/217 votes backfilled as derived (166 accepted, 51 rejected, 0 ties); 12/217 XLSX links matched from one live Namenslisten fetch.

### Votes archive across sittings (`votes/index.html`)

**Completed:** v0.7.0.0 (2026-09-26). Reverse-chronological, grouped by month, with client-side Fraktion chips (majority "yes" position); gated by the `votes` feature and added to `NAV_ITEMS`. Row count verified equal to `SELECT count(*) FROM votes`.

### Current-TOP highlight in the ranking sidebar

**Completed:** v0.6.6.0 (2026-09-26). `IntersectionObserver` on `.top-card` plus a frame-throttled scroll/resize re-pick sets `aria-current="true"` on the matching `.attention-row`, styled through `[aria-current]` (screen only); off wherever the aside is static (`ATTENTION_STATIC_LAYOUT_QUERY`). "Reached" is measured against the cards' scroll-margin-top, the lowest visible card wins at the end of a scrolling page, and the row-reveal scrolls only `.attention-list`, instantly (a running smooth list scroll made Chrome drop row-click jumps). Ships alongside the copy-button half of the recipe TODO above.

### Weekday-matched Wochenvergleich when sitting counts differ

**Completed:** 2026-09-25 (v0.6.5.0). Compared shared weekdays by summed counts and recomputed Redeanteil from the matched sittings, with a visible basis note and n/a when no weekday overlaps.

### Enforce the Python version floor

**Completed:** v0.6.4.0 (2026-09-25). Added a Python 3.11 startup check to the build scripts and documented the supported version in the README.

### CONTRIBUTING.md

**Completed:** v0.6.4.0 (2026-09-25). Added a concise command index with README links and the `.env.local` empty-key warning.

### Regenerate the architecture diagram for the Daten export step

**Completed:** v0.6.4.0 (2026-09-25). Updated the diagram to include the Fakten engine, Daten export, generated data paths, manifest override, and Daten page.

### Move the hidden dev-view API dump below the dossier content

**What:** In explicit `--include-dev-view` builds, the `protocol_dev_sections` block (raw API JSON and people list; `.dev-only`) is emitted between the page header and `.layout`. Emit it after `<main>`, or — preferably, given the hosting maths — render it into a separate file loaded on demand.

**Why:** Measured on plenarprotokoll 20/103: 952 KB of hidden markup precede the Aufmerksamkeitsrang aside and the first TOP card, so on a slow connection nothing above the fold can paint until ~1 MB has streamed. Found while placing the aside's toggle script adjacent to the aside (2026-09-14). Added 2026-09-19: across 285 dossiers that is roughly 270 MB of `protocols/` (584 MB total), and the site without `data/` is 1.11 GB — the on-demand variant is the single biggest lever for getting under a 1 GB host cap (see the site-hosting TODO). Note (post-#60, v0.5.0.0): those figures were measured on a build that still emitted the dev block; ordinary publications now omit `dev-view` entirely (`--include-dev-view` refuses to write to the publication directory), so the hosting lever only applies to explicit dev builds — re-measure the public site before relying on it.

**Context:** `render_html` in `scripts/render_dip_pulse_html.py` still interpolates `{protocol_dev_sections}` before `{session_summary_sections}` and `<main>` (2026-09-19). Moving it after `</main>` changes nothing visible (it is `display:none` until toggled) but check `tests/test_render_dip_pulse_html.py::DossierLayoutTests`, which pins the order of `.dev-top-details` inside cards, and the dev-toggle script that reveals `.dev-only`.

**Completed:** 2026-09-25. Verified the existing S variant: protocol dump follows main and ordinary builds omit it; explicit dev builds show `.dev-only` by default and have no dev-toggle (existing behavior retained by user decision).

### Dossier h1 shows the session, "Bundestag-Puls" moves to the eyebrow

**What:** On `protocols/*.html` make the session title the `h1` and demote the product name to an eyebrow/kicker.

**Why:** Every one of the 285 dossiers has the identical `h1 "Bundestag-Puls"`; the page's actual subject is a muted 15px subtitle. Hierarchy should serve the page, not the brand (flagged in the 2026-09-13 design review).

**Context:** the `<h1>Bundestag-Puls</h1>` block in `render_html`'s page template (`scripts/render_dip_pulse_html.py`). puls.html already made this exact move in 0.3.0.0 (`header["h1"]` = "Was der Bundestag in KW … verhandelt hat" with an eyebrow; `render_front_page` in `scripts/build_dip_pulse_site.py`), so copy that pattern. Check `test_global_header.py` expectations before changing the `h1`.

**Completed:** 2026-09-25. Verified the existing session h1/product eyebrow and added explicit title, escaping and fallback regression coverage.

### Site-wide `:visited` and `:focus-visible` rules in `global_header_styles`

**What:** Move the Daten page's `a:visited`/`.recipe a:visited`/`.file a:visited` (teal) and `a:focus-visible` outline rules (`scripts/build_dip_pulse_site.py`, Daten page CSS) up into `global_header_styles()` (`scripts/render_dip_pulse_html.py`) so every link-dense page (catalog, dossiers, MP pages) gets them too.

**Why:** Those pages have the same link-density gap the Daten page closed for itself. Checked 2026-09-19: `global_header_styles()` has neither rule; equivalents exist only on the Daten page, the radar rows and the week labels, each written locally.

**Completed:** 2026-09-25. Shared teal visited links and focus outlines; removed redundant Daten link rules, retaining control and radar/week-specific styles.

### Stop persisting `speeches.paragraphs_json`

**What:** A migration dropping the column from the live schema (duplicate of `speeches.text`, no reader in site code — the only references are the INSERT in `persist_dip_pulse_store.py` and the export-time `DROP COLUMN` in `export_distribution_data`); then remove that export-time `DROP COLUMN` since it would no longer be needed.

**Why:** Measured 2026-09-19: `paragraphs_json` is 114 MB and `text` 113 MB of a 305 MB store, so this saves roughly 37% (not "half"). The distribution copy already drops the column at export time, so the schema change is pure cleanup, not a data-loss risk.

**Context:** Three test fixtures insert into the column and need the same edit: `tests/test_build_dip_pulse_site.py` (~282), `tests/test_daten_export.py` (~144), `tests/_daten_fixture.py` (~133). `test_distribution_copy_drops_paragraphs_json_and_keeps_row_counts` becomes obsolete.

**Completed:** 2026-09-25. Removed schema/INSERT duplication; idempotent migration warns on SQLite < 3.35, and conditional export cleanup preserves legacy-store exports and row counts.

### Escape the pre-existing `index` interpolation in the dossier renderer

**What:** Wrap `item["index"]` with `esc()` at the remaining pre-existing site in `scripts/render_dip_pulse_html.py` (the `top-card` `id="top-{item['index']}"` in `render_html`; still unescaped 2026-09-19).

**Why:** Hygiene. `index` is an int from the XML validator today, so there is no exploit; the `attention_rows` href and the `top-jump` link already escape it, and the last site should match.

**Context:** Pure consistency change; add nothing else. One test asserting anchors still resolve covers it.

**Completed:** 2026-09-25. Escaped TOP card IDs; ranking anchors resolve for numeric and HTML-sensitive indices.

### `agenda_topic()`, the topic line for the Fakten cards

**What:** `agenda_topic(proceeding_title, heading)` and `strip_heading_boilerplate()` in `scripts/render_dip_pulse_html.py`: the DIP Vorgang title first, else the XML heading with its procedural opener stripped, else nothing.

**Completed:** v0.6.0.0 (2026-09-24). Spot check: 29 of the last 30 sitting weeks' longest speeches carry a topic, 27 of them from the clean Vorgang title.

### `parties.name` list-repr duplicates

**What:** `persist_sampled_people` unwraps DIP's list-valued `person.fraktion` (`unwrap_dip_faction`), and `initialize()` migrates existing stores: duplicate `parties` rows merged, `mps`, `vote_fractions` and `vote_members` repointed.

**Completed:** v0.6.0.0 (2026-09-24). On the 2026-09-19 store: 22 party rows → 15, no list reprs, no dangling `party_id`, vote counts unchanged. Residue tracked under Daten.

### Fakt der Woche, A0: read-only replay and sample cards (the test run)

**What:** `scripts/facts.py` with the metric registry, the rule as pure functions, receipts, and a `--replay N --cards DIR` entry point. No writes, no pages, no export.

**Completed:** v0.6.0.0 (2026-09-24), commit `7603e71`. Passed the five pass criteria in the design doc addendum (2026-09-20 result: Merz 6/30 failed criterion 1 on the first run, the rest passed; amendments folded into A1).

### Fakt der Woche, A1: engine in the build, pages, Methodik, export

**What:** `compute_and_store` runs on every build, snapshots `(fact_metrics, facts, fact_sources)` and writes only when the triple differs, the publication floor gates which facts post, `fakt/index.html`/`<period_key>.html`/`<period_key>-<metric_id>.svg`/`methodik.html`, the `facts` component and nav entry, the Daten export's three new CSVs and derived-data documentation.

**Completed:** v0.6.0.0 (2026-09-24), commits `decb17b`..`6449bcd`. Two of the three "done when" criteria verified (unchanged-store skip, byte-identical cards under rerun); the third (rasterise + post a card) split out below - not code, not gated on this ship.

### Fakt der Woche, four more weekly metrics

**What:** `laengste-debatte`, `laengste-sitzung`, `meiste-abweichler`, `erste-reden` - the remaining four of the six weekly metrics.

**Completed:** v0.6.0.0 (2026-09-24), commits `6aa9363`, `87cd883`.

### Fakt der Woche, the monthly post

**What:** A second period (`period_kind = 'month'`) with `aktivste-abgeordnete` and `meistdiskutierter-vorgang`.

**Completed:** v0.6.0.0 (2026-09-24), commit `6449bcd`. Verified against the real store: June 2026 = Alexander Dobrindt (40 Reden), GKV-Beitragssatzstabilisierungsgesetz (19 Reden).

### Guard external payload links with shared source validation

**What:** Route public hrefs from DIP, Bundestag, and abgeordnetenwatch payloads through shared scheme-and-host validation, with safe omission or plain-text fallback for rejected links.

**Completed:** v0.5.0.0 (2026-09-19)

### Check that roll-call votes are still being acquired after June 2026

**What:** Confirm whether bundestag.de published namentliche Abstimmungen after 2026-06-12, and find why the vote scan missed them.

**Completed:** v0.8.0.0 (2026-09-29). Cause: vote scraping was opt-in (`features.json` ships an empty `enrich` list), so every update since June recorded votes as `not_requested`. Votes are now a default enrichment (`--no-votes` opts out). Backfilled into a scratch copy of the reference store: votes 217 -> 232, newest 2026-06-12 -> 2026-09-25 (2026-06-25 1, 07-08 1, 07-09 1, 07-10 8, 09-24 1, 09-25 3).

### One Zusammenschluss per `parties` row

**What:** `parties` had `SPDSPD`, `SPDCDU/CSU`, `BSW`, `BSW (Gruppe)`, `Die Linke (Gruppe)` beside `Gruppe BSW`/`Gruppe Die Linke`, and the Die Linke row mixed the WP 20 Fraktion, the WP 20 Gruppe and the WP 21 Fraktion.

**Completed:** v0.9.0.0 (2026-09-29). `derive.zusammenschluss` maps every spelling to one name and `upsert_party` routes every name through it. A WP 20 Rede from 2023-12-06 on naming "Die Linke" is a Gruppe Die Linke Rede (`derive.speech_zusammenschluss`; 383 Reden move). The merged Bundestag records are read from the printed label (`parse_redner`) or, in cached reports, drop their Fraktion. Reference store: 15 parties -> 9 (10 after this item, 9 after the Regierung item). The cause was not only the table of contents: the merged `<redner>` elements sit inside the `<rede>` too.

### Credit a Rede's text only to its Redner

**Completed:** v0.9.0.0 (2026-09-29). `speech_text_and_paragraphs` keeps only what the Redner said (a `<name>` is the Sitzungsleitung, a `<p klasse="redner">` marker names the speaker); the Redner resumes under an explicit marker, so no resumption is inferred (checked on 961 Reden of 8 sittings, WP 20 and 21). Reference store: 126.300.719 -> 121.793.810 characters (-4.506.909), 21/84 349.531 -> 333.888 (89 of 99 Reden change), `laengste-rede` 54 periods (35 lower value, 4 newly and 5 no longer publishable). The Zwischenfrage and Gastansprache remainder is tracked above.

### Say "nicht abgegeben", never "Abwesend", and stop inventing a Mehrheitsvotum

**Completed:** v0.9.0.0 (2026-09-29). `derive.majority_vote` is the plurality among Ja/Nein/Enthaltung and None on a tie or when nobody voted; persist and the pages derive it from the counts and ignore a cached value. Reference store: 37 `vote_fractions` rows lose their Mehrheitsvotum (29 fraktionslos Ja/Nein ties that read "yes", 3 shared tops, 5 "absent"). The Abgeordnete page and the vote panel say "nicht abgegeben".

### One Abweichung rule: exclude fraktionslose MdBs from `r3-abweichler`, drop "Linie" from the wording

**Completed:** v0.9.0.0 (2026-09-29). `r3-abweichler` excludes `fraktionslos` (381 -> 371 rows, 806 -> 648 Abweichungen; the old top entry was a fraktionsloser MdB with 81), and the recipe title, the `meiste-abweichler` unit, caveat and Karte caption say "anders als die Mehrheit der eigenen Fraktion oder Gruppe".

### Sprechrolle per Rede, no "Regierung" party (ADR 0001, data half)

**Completed:** v0.9.0.0 (2026-09-29). `speeches.sprechrolle` (bundesregierung, bundesrat, weitere) from `SPRECHROLLE_RULES` in `scripts/derive.py`; an unmapped role fails persist with one `ERROR [sprechrolle]` naming all of them. Reference store: Bundesregierung 5.394 Reden, Bundesrat 61, weitere 8; 1.556 Reden of MdBs in a government role leave their Fraktion's Redeanteil. The wording half is tracked above.

### Make the Namensabgleich unique, and stop treating name-found ids as proof

**Completed:** v0.9.0.0 (2026-09-29). Only an abgeordnetenwatch id looked up by the Redner-ID (`match` = ext_id) is a Personenkennung (`mps.aw_match`); Zusammenführung joins by shared Personenkennung (ext_id) or by a unique 1+1 name+party bucket (unique_name), titles ignored, and every Personenseite records its merges. Reference store: five wrong-person matches undone (92 Reden moved to their own Personenseite, 2 new pages), 640 ext_id and 861 unique_name merges, 322 + 397 name buckets left split; Personenseiten 1.040 -> 1.045. A name-found id equal to the trusted id of a same-named record joins the two (`corroborated_name`, 6 merges): the six people with two Redner-IDs are one Personenseite again and debut once in `erste-reden`; Personenseiten 1.039. Follow-up: the shared Redner-ID 11005304.

### Only Gesetzgebungen on the bills pages, and call them "Gesetzesvorhaben"

**Completed:** v0.9.0.0 (2026-09-29). `is_gesetzgebung` (Vorgangstyp) replaces the keyword test; Entschließungsanträge and the like are listed as "Weitere Vorgänge zu diesem Tagesordnungspunkt" on the page of each Gesetzgebung of the same agenda item; labels say Gesetzesvorhaben. Reference store: 903 -> 594 bill pages. The old figures (839 -> 551) were measured on a smaller store.
