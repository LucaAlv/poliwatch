# A3: v1 coverage, every Sitzung from WP 18 to the present

## Context

Roadmap A3 (TODOS.md:221) asks for a Dossier for every Sitzung the DIP catalog lists for WP 18–21, a store that stays current, and the covered range stated in README, PRODUCT.md and the Daten page. PRODUCT.md sets v1 coverage at WP 18 onward because that is where structured XML starts. Every C-track series is only as long as this coverage.

Measured today on `~/agent-runs/b3-review-replay/site` (post-v0.20 replay, catalog 2026-10-06):

| WP | In the catalog | Stored |
|---|---|---|
| 18 | 245 | 0 |
| 19 | 239 | 0 |
| 20 | 214 | 201 (from 20/14, 2022-01-27) |
| 21 | 97 with XML | 89 (to 2026-09-11) |

So about 505 Sitzungen are missing. The TODOS table and path are stale.

What blocks a plain `--backfill-incomplete` run today:
- The gate "Validate final merged A1/A2" (TODOS.md:163, P1) is not satisfied. The only combined run, from 2026-10-05, predates speech rule v3–v5, schema 4/5, the issuer-keyed documents and Politikfelder. Its harness lived in `/tmp` and is gone.
- `facts.expected_sittings` (`scripts/facts.py:714`) judges only from the earliest stored week, so WP 18/19 are never selected. Once 18/1 is stored, the backfill re-acquires about 794 sittings, because 281 of the 290 reports lack vote acquisition metadata.
- The roll-call list scan needs ≥73 pages to reach 2013 (live probe: offset 720 is 2013). The default of 30 leaves every WP 18/19 sitting PARTIAL, and `_structural_vote_gap` (`build_dip_pulse_site.py:407`) then skips them.
- A `source_rejected` XML aborts the whole run (`build_dip_pulse_site.py:267-269`) and recurs on every rerun.
- `--sleep` defaults to 0. A DIP bot challenge (2026-10-04) makes sittings `source_unavailable` and they are skipped, yet the build exits 0.
- `ingest_mdb_roster` (`build_dip_pulse_site.py:7041`) takes one WP and replaces the roster, so WP 18/19 leavers get no roster row.
- `fetch_bio` (`scripts/abgeordnetenwatch.py:160`) takes the highest-period mandate, which can be a Landtag mandate.
- `SPRECHROLLE_RULES` (`scripts/derive.py:209`) is fail-fast and built from WP 20/21 roles.
- `EINZELPLAN_TO_POLITIKFELDER` (`scripts/politikfelder.py:98`) has WP 20/21 tables only.
- The spelling table lacks variants seen in old XML, such as `BÜNDNIS 90/DIE GRÜNE N` in 19/100.
- Parties are keyed by name, so whole-store figures (Daten recipes r1–r5, `build_dip_pulse_site.py:2516-2656`) would blend four WPs.

User decisions (2026-10-19):
- **Fraktion identity:** stopgap in A3. Parties stay keyed by name; every whole-store figure and export recipe gets a Wahlperiode dimension or filter so nothing shown blends WPs. Per-WP Fraktion identity becomes its own issue.
- **Former MPs:** full treatment. Union the roster over WP 18–21 and restrict `fetch_bio` to Bundestag mandates, so leavers get normal profile pages.
- **Base store:** the canonical `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site`, which is never mutated. All work runs on APFS clones (`cp -cR`) under `~/agent-runs/a3/`, with absolute `--output-dir`, because the worktree has no `.context/`.

Work happens on branch `worktree-a3-plan`. The first commit does three things:
- saves this plan as `docs/plans/a3-coverage.md`;
- corrects the TODOS A3 table and path;
- writes the three TODOS entries approved in review: D7 (Namenslisten paging, added to B.5), D8 (overview by Wahlperiode) and D9 (MP pages by Wahlperiode).

## Phase 0: the merged A1/A2 gate, as a committed script

1. **Gate script.** Add `scripts/validate_store_gate.py`, a re-creation of the lost harness that is reusable in Phase 4. On a given output dir it runs:
   - `--offline --repersist`, recording integrity_check and the FK check;
   - a fresh vs. half-then-full grouping fingerprint, reusing the fingerprint from the A.2 validation (see `docs/a2-validation.md` and the `tests/` contract tests for where it is computed);
   - a second unchanged replay, which must keep the DB byte-identical or report why;
   - a link audit over the rendered site;
   - an export check against the manifest contracts.

   It writes a JSON receipt like `docs/plans/a1-scratch-validation.json`.
2. **Clones.** Clone the base to `~/agent-runs/a3/gate`. Reacquire 21/50 there with `--document-number 21/50` (TODOS.md:172), or it blocks repersist again.
3. **Run.** Run the full test suite, then the gate script. Record Reden, Beiträge, groups, persons and documents against the 2026-10-05 figures (26,271 / 16,799 / 3,370), with old vs. new values.
4. **Commit.** Commit `docs/plans/a3-gate-validation.md` plus the receipt, and close the TODOS.md:163 gate. Any regression found here is fixed before Phase 1.

## Phase 1: bounded WP 18/19 pilot, collecting data rather than guessing

Run on a clone `~/agent-runs/a3/pilot`, cloned from the repaired, gate-validated `~/agent-runs/a3/gate` (not the base, so the 21/50 repair carries over; O1), with about 25 sittings:
- the 21 from `docs/plans/a1-turn-investigation.md:17`;
- the first and last sitting of WP 18 and of WP 19;
- at least one each of Befragung, Fragestunde and Aktuelle Stunde per WP.

Use `--document-number` repeatedly, `--vote-scan-pages 90` and `--sleep 0.5`, through enrichment, votes, persist, render and facts.

Collect into `docs/plans/a3-pilot.md`:
- the unmapped Sprechrollen, via `derive.find_unmapped_sprechrollen` over the cached reports;
- every distinct raw Fraktion string from the XML, the roll-call vote pages and DIP `/person`, mapped through `derive.zusammenschluss`, with the unknown ones flagged;
- the Einzelplan numbers occurring in WP 18/19 Haushalt TOPs, with each one's ministry from the DIP Drucksache or Haushaltsgesetz title. The table comes from that evidence, not from memory;
- the share of WP 18/19 Redner whose redner-id finds an abgeordnetenwatch `ext_id_bundestagsverwaltung`;
- the roll-call match rate, TOPs without votes, and any vote-page fraction strings;
- DIP requests per second, seconds per sitting, and peak RSS of the persist/render.

The 3.6 GB memory figure is an extrapolation and gets measured here. Then extrapolate the full-run time and memory.

## Phase 2: code changes that an unattended run needs

Each change comes with tests in the style of the existing suite, and trimmed WP 18/19 fixtures from the pilot go under `tests/fixtures/` with provenance in `a1-source-manifest.json`.

1. **Coverage floor and scope.**
   - (D3 = A) Add a constant `V1_FIRST_WAHLPERIODE = 18`, cited to PRODUCT.md:52. Its first catalog date goes as an explicit lower bound into the backfill gap computation only (`incomplete_sitting_protocols`, `build_dip_pulse_site.py:437` → `facts.sitting_gaps`). `facts.expected_sittings` and the Fakt periods keep the earliest-stored-sitting rule. There is no new flag.
   - (D4 = A) `--protocol-wahlperiode N` also scopes `--backfill-incomplete` to one WP per run, and its default changes from 21 to 0 (all). There is no `--backfill-wahlperiode`.
   - Print the judged range and the per-WP counts before acquiring (TODOS.md:203 item 2).
2. **Reviewed exclusion list for rejected sources (D2 = A).** D4 stays: an unlisted `source_rejected` sitting still aborts before any store is promoted. A new repeatable `--exclude-document-number` (allowed with `--backfill-incomplete`) skips listed sittings. Each is written to `data/coverage-exclusions.json` with its D4 diagnostic and counted as "nicht erfasst (Quelle abgelehnt)" in the coverage and Daten figures. A human adds a number only after reading its diagnostic. Tests: an unlisted rejection aborts before promotion; a listed one is skipped and reported.
3. **Pacing and honest exit.**
   - Backfill gets a nonzero default sleep, taken from the pilot's measured safe rate.
   - Print an end-of-run summary of skipped, `source_unavailable` and quarantined sittings.
   - Exit nonzero when any sitting was skipped (TODOS.md:203 item 5).
   - (D5 = A) A build-wide `/person` cache, a dict keyed by DIP person id created next to `roll_call_page_cache` (`build_dip_pulse_site.py:11853`) and passed into `enrich_with_api`. Successes are cached, failures are not, so a repeat person costs no request and no sleep.
4. **Vote budget.** Raise the backfill default `--vote-scan-pages`, or derive it: scan until an entry is older than the oldest target sitting, with a hard cap. A too-small budget must not mark a sitting structurally skipped. `_structural_vote_gap` re-tries once the budget grows (it already compares N), and the docs say so.
5. **Multi-WP roster.**
   - `ingest_mdb_roster` takes a list of WPs and unions them. `--roster-wahlperiode` becomes repeatable, defaulting to every WP from `V1_FIRST_WAHLPERIODE` to the newest catalog WP.
   - Membership is stored per Wahlperiode for each person; "current MdB" is derived as membership in the newest catalog WP, so `is_mdb` does not flag about 1,500 people as current.
   - `preserve_roster` semantics (`build_dip_pulse_site.py:11997`) stay correct.
   - Roster rows from the extra WPs never inherit an `xml_redner_id` (learning repersist-inherited-roster-speaker-id).
   - The Abgeordnete index copy "der laufenden Wahlperiode" (`build_dip_pulse_site.py:7592`) becomes WP-aware: the current WP stays the default, and former MdBs are reachable.
   - Historical membership and roster-source authority (`ever_mdb` at `person_registry.py:445`, `_roster_bio`) stay separate from current status, so former MdBs keep their pages and roster bios (O2). Test: a former MdB with no cached speech gets a page, and it survives an unchanged offline replay.
   - `fetch_bio` filters to Bundestag mandates (`parliament` = Bundestag) before taking the latest one. The bio cache is versioned or invalidated so that cached Landtag picks are re-selected (`abgeordnetenwatch.py:396`; O3). Test: upgrading a populated cache re-selects.
   - Update `tests/test_registry_contracts.py` (it pins `wahlperiode=21`).
6. **Sprechrolle, spelling, Einzelplan.**
   - Add the rules the pilot found to `SPRECHROLLE_RULES`, plus the spelling variants to `derive._SPELLINGS` (`derive.py:53`), only those observed: the spaced "GRÜNE N", and the dotted Linke if seen.
   - Add WP 18 and 19 tables to `EINZELPLAN_TO_POLITIKFELDER`.
   - Fix `tests/test_politikfelder.py:116` so it globs all WPs, and extend `EINZELPLAENE_IN_THE_CACHE`.
   - Extend `speech_kinds.FRAKTION_WORDING` (`speech_kinds.py:251`) with `fraktionslos` if the pilot shows a Kurzintervention miss.
7. **No blended figures (the Fraktion stopgap).**
   - Daten recipes r1–r5 and any whole-store party aggregate gain a Wahlperiode column or a WP filter.
   - The export manifest records it, which is an export format bump; pre-release, so no shim.
   - Open a GitHub issue "Fraktion identity per Wahlperiode" after grepping TODOS.md for an existing item.
8. **Small fixes.**
   - The `facts.py:417` caveat "seit Januar 2022" derives from the coverage start.
   - Add FDP, Gruppe Die Linke and Gruppe BSW to `PARTY_COLORS` (`render_dip_pulse_html.py:34`).
   - The README "offline well under a second" claim gets the measured figures.
   - Document `--protocol-wahlperiode` and the new flags in the README (TODOS.md:80).
   - (D6 = A) `scripts/compare_store_values.py` gains a per-(period_kind, period_key, metric_id) diff of value, denominator and percentile for periods both stores hold. Test: two fixture stores with a moved percentile show old/new/delta.
9. **Deferred to TODOS, not done here:**
   - Namenslisten paging for XLSX links, which is provenance only;
   - `overview.html` pagination at about 900 cards;
   - the per-MP page length.

   Unless the pilot shows any of these breaks the build or memory.

Re-run the pilot clone with the new code and confirm zero unmapped Sprechrollen and zero unknown Fraktion strings.

## Phase 3: the full backfill

On a fresh clone `~/agent-runs/a3/full` of the gate-validated `~/agent-runs/a3/gate` (O1), with `~/agent-runs/a3/baseline` kept as an untouched clone of the base for comparison:
1. Refresh the catalog with a normal online build.
2. Run `--backfill-incomplete --protocol-wahlperiode 18`, then 19, then 20, then 21, each in the background with a log. After each run, read the skip and quarantine summary and fix or rerun before the next WP.
3. Run the multi-WP roster enrich, then the Vorgang cache fill (about 2 h on a first fill).

The WP 20 and 21 runs also re-acquire about 290 already stored sittings, because 281 of the 290 reports have no vote acquisition metadata. That is wanted: they become vote-complete.

Budget roughly 8–10 h acquisition plus the roster and Vorgang time. Interruptions are safe because reports are written atomically per sitting, and a rerun picks up the missing ones.

## Phase 4: verify and document

1. **Gate script.** Run `scripts/validate_store_gate.py` on `full`.
2. **Missing count.** Re-measure the per-WP missing table on a fresh catalog. The target is 0 missing everywhere; anything not 0 is listed as quarantined or waiting for DIP XML, with a reason.
3. **Value comparison.** Run `scripts/compare_store_values.py ~/agent-runs/a3/baseline ~/agent-runs/a3/full` twice: with `--cohort shared` (value movement on the same sittings) and with `--cohort all` (coverage), reported separately. Report the old and new values for WP 20/21 figures that moved, and say why each moved:
   - re-fetched DIP data;
   - vote metadata now complete;
   - Fakt percentiles with a longer baseline;
   - `erste-reden` numerators that change because earlier speeches are now covered.

   (D6 = A) Fakt values come from the new per-(period, metric) value/denominator/percentile diff in `compare_store_values`.
4. **Spot checks.** Check the site in Chrome, light and dark: one WP 18 and one WP 19 dossier, a former-MdB profile, `votes/index.html`, the Daten page and `overview.html`. Record the size and timing of the store, site and memory.
5. **Docs.** State the covered range in README, PRODUCT.md:80 and the Daten page (a static v1 range line next to the manifest range). Update CONTEXT.md only if a term changed. Move A3 to Completed in TODOS, with the measured numbers. Add the larger site size to the hosting item (TODOS.md:100).

## Critical files

- `scripts/build_dip_pulse_site.py`: selection (373, 437), structural gap (407), the skip and abort loop (237–285), flags (11082–11390), roster (7041, 7592, 11997), Daten recipes (2516–2656)
- `scripts/facts.py`: `expected_sittings` (714), caveat (417)
- `scripts/validate_dip_protocol.py`: roll-call scan (1683), `ApiClient` (149)
- `scripts/derive.py`: spellings (53), Sprechrolle rules (209)
- `scripts/politikfelder.py`: Einzelplan tables (98)
- `scripts/abgeordnetenwatch.py`: `fetch_bio` (160)
- `scripts/render_dip_pulse_html.py`: `PARTY_COLORS` (34)
- new `scripts/validate_store_gate.py`
- `docs/plans/a3-*.md`
- TODOS.md, README.md, PRODUCT.md

## Verification

- Full test suite green after each Phase 2 change.
- New tests:
  - the coverage floor selects WP 18 with an empty WP 18 store, and the Fakt periods are unchanged;
  - an unlisted rejected source still aborts before promotion, and a listed one is skipped and reported;
  - a skipped sitting gives a nonzero exit;
  - the roster union keeps WP 18 leavers;
  - `fetch_bio` ignores Landtag mandates;
  - a WP 18/19 report persists, renders and computes facts from fixtures.
- Gate receipts from Phase 0 and Phase 4 are committed.
- `compare_store_values` old/new report is committed.
- The per-WP missing table reads 0, or explained, on a fresh catalog.
