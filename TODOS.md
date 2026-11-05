# TODOS

Open work, grouped by area. The roadmap orders the items that lead to v1. Every other item keeps its own priority. Finished items get one line each under Completed. This file was last cleaned up on 2026-11-02, against main v0.31.0.0, and brought up to date on 2026-11-04, against v0.32.0.0.

## Roadmap to v1 (updated 2026-11-04)

The goal comes from PRODUCT.md (2026-09-30): a citable dataset for WP 18 to the present, and a site with two equal angles, the daily view and long-term analysis. Items are named by their headings below. Track D has to be finished before anything goes public.

**Done so far** (see Completed):
- A1: what counts as a Rede (v0.13.0.0 to v0.15.0.0).
- A2: stable ids (v0.12.0.0 onward).
- A3: v1 coverage (v0.27.0.0). 716 Sitzungen of WP 18–21, 85 on the reviewed exclusion list.
- A4: slice 0, every page renders from the store (v0.29.0.0); slice 1, the votes archive from the store (v0.32.0.0).
- B1–B4, the daily vote panel: inverted votes, majority rule, TOP matching, external member links, Politikfelder, and the B4 panel with "Vote reading misses half the inverted votes and never stores it".
- C1: Fraktion seat counts from the MdB-Stammdaten (v0.31.0.0).
- D, the code half:
  - the licence files, Impressum and Datenschutz pages (v0.30.0.0)
  - the release script, data changelog and CITATION.cff (v0.26.0.0)
  - the abgeordnetenwatch source tags (v0.20.5.1)

**A. Counts and coverage: fix what A3 and C1 surfaced, then finish the split**
1. Correctness P1s. Each one moves published figures:
   - "Correct the WP 19/20 roll-call group misattributions (E4) from the MdB-Stammdaten".
   - "The carried-forward registry diverges from a fresh build after A3", part 2: 289 pages of persons who hold only retired bindings. Fix it together with "Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs". The MdB-Stammdaten from C1 can be the membership source.
   - "Tell official addresses and presidium Reden apart from Fraktionsreden (ADR 0004)". This needs an owner decision on the kinds first. 18/1 and 19/1 stay excluded until then.
   - Plan item 1.5 of "A3 /gstack-ship review: deferred findings": measure the abgeordnetenwatch match share of the WP 18/19 Redner.
2. "Split the dataset from the site: the site builds from a release alone" (A4).
   - Slices 0 and 1 are done. The later slices are in `docs/plans/a4-site-from-release.md`.
   - Main is at schema 10 and export format 14, so the next slice takes the numbers after those.

**B. Abstimmungen (daily view)**
1. "B4 extractive fallback: finish validation locally": no population reaches the 90% coverage gate yet. Add one extractor rule at a time. The entry's P1 gate applies before the fallback runs on a larger Drucksache cache.
2. The rest of "Abstimmungen for the daily view: what was decided, by topic, with dissenters". The AI sentence is deferred.
3. "Take namentliche Abstimmungen from the official XLSX instead of the chart markup" can come later. It adds ungültig and Bemerkung but changes no count seen so far.

**Frontend:** "Decide the frontend stack" (owner decision 2026-11-02: hold, prototype first). First "DESIGN.md, tokens and a typeface decision via /design-consultation", then a chart prototype, then a written go/no-go.

**C. Analysen (long-term view)**

A1–A3 are done, so C can start. Per-Fraktion figures take C1's seat table as their denominator. A count fix in track A still moves every series C draws.
1. "Diskursanalyse: precomputed term series per Zusammenschluss and month".
2. "Politikfelder over time: which Zusammenschluss emphasises what".
3. "Zwischenrufe: parse `<kommentar>` and count reactions per Fraktion", which answers "who interrupts most".
4. Then "Muster" and "Präsenz".

**D. Before anything goes public** (items under Recht und Lizenz, Publication and Zitierfähiger Datensatz)
- **Owner inputs and outside answers (no code):**
  - For "Impressum, Datenschutz and licence files before the site goes public": the Impressum address (after question 1 to the lawyer, ADR 0003), a dedicated e-mail address, the host and its log retention, and the supervisory authority. Until then both pages render `data-operator-missing`.
  - The e-mail to parlamentsdokumentation@bundestag.de for "Settle the roll-call source for redistribution".
  - The terms in "Settle the MdB-Stammdaten redistribution terms (`bundestag-stammdaten` layer)".
  - A Zenodo account for "A DOI per release and a citation file".
- **Hosting:** "Site hosting plan for the 2.5 GB generated site" (P1). After A3 the site is 5.4 GB, and still 1.35 GB without `data/` (2026-10-29). The plan also settles the link layout the first real release needs (owner decision (b) in "Write the release script").
- **The first release:**
  - items 1–5 of "Release pipeline: deferred /ship review findings"
  - the first real `--publish` of "Write the release script"
  - CHANGES.md on the Daten page ("Public data changelog per release")
  - the DOI

**Later:** the LLM-content items (Fraktionsblöcke, deterministic validators, Debattenberichte), Fakt der Woche B and C, and the Puls and copy fixes. These stay at their own priorities. WP 1–17 come after v1, because the DIP catalog has no structured XML for them.

## Daten

### Take namentliche Abstimmungen from the official XLSX instead of the chart markup

**What:** `parse_roll_call_list_page()` / `parse_fraction_votes()` (`scripts/validate_dip_protocol.py`) read `data-chart-values` from bundestag.de HTML: four numbers (Ja, Nein, Enthaltung, nicht abgegeben) summing to the seat count, and `vote_counts_from_csv` keeps only the first four numbers it finds. The Bundestag also publishes one XLSX per namentliche Abstimmung (list: `/ajax/filterlist/de/parlament/plenum/abstimmung/liste/462112-462112`, e.g. `https://www.bundestag.de/resource/blob/1217428/20260925_3-xls.xlsx`) with columns `Wahlperiode, Sitzungnr, Abstimmnr, Fraktion/Gruppe, Name, Vorname, Titel, ja, nein, Enthaltung, ungültig, nichtabgegeben, Bezeichnung, Bemerkung`. Ingest that instead (or alongside), store ungültig as its own Stimme value and keep Bemerkung.

**Why:** Ungültig is an official Stimme value we cannot represent; if it ever occurs, the chart numbers either hide it or shift it into another category, silently. Bemerkung gives the stated reason for some uncast Stimmen (30 most recent votes, 2026-09-25: "gesetzlicher Mutterschutz" 42×, "Geburt eines Kindes" 1×), which the site could show next to "nicht abgegeben". The XLSX also carries Sitzungnr/Abstimmnr, a sturdier join to the Sitzung than matching by date.

**Context:** Sample of 30 XLSX files (18,895 Stimmen) had zero ungültig, so today's counts are not wrong in practice; this is about not being able to tell. HTML scraping of the filterlist also breaks whenever bundestag.de changes its markup.

**Prerequisite (A3 review D7, 2026-10-19): page the Namenslisten list.** What: page the Namenslisten list beyond offset 0 so every vote back to WP 18 gets its XLSX link. Why: 0 of 217 stored votes link an XLSX today, and no WP 18/19 vote will. Context: `validate_dip_protocol.py:1576` fetches only `offset=0&limit=200`; offsets 200 and 400 reach 2022 and 2019. Depends on: none.

**Effort:** M
**Priority:** P3
**Depends on:** None

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

### Pilot gate: decide keep/remove for the Daten page

**What:** 8 weeks after the first public data release, decide keep/remove using `gh release view --json assets` download counts, any inbound question or citation, and whether the builder himself used the downloaded file for anything.

**Why:** The user's own go/no-go framing ("if it doesn't work for v1, that is not a deal breaker"); the audience ("developers and researchers") is chosen, not demand-tested, so this is the cheap way to find out without a demand study.

**Effort:** S
**Priority:** P2
**Depends on:** **Blocked** — first public release (PR2); as of 2026-09-19 no release exists, so the 8-week clock has not started.

### Export robustness gaps found by the codebook review

**Done in v0.26.0.0 (#123):**
- (1) The publish step undoes the generation swap on any failure after it.
- (2) `validate_public_output` also scans the export's DATA.md and datenstand.json.

Open: (3) and (4) below.

**What:** (3) Smaller: authored-input and licence-layer errors surface only after the store copy and CSV pass (pre-validate the dictionary shape and the licence doc's `## ` section first); `render_daten_recipes` defaults `data_base_url` (make it a required keyword); `_recipes_hash` raises a raw `KeyError` for an old-shape caller recipe; ~~decide whether recipe CSVs keep formula-leading text unchanged~~ recommendation recorded 2026-10-31 (see "CSV formula injection" below, owner decides). (4) Found in /ship runs 4 and 5 (2026-10-30/31), none reachable with today's inputs: export `RuntimeError`s (dictionary drift, recipe failure, copy failure) escape `main()` as a traceback after the store was persisted, so no site renders (pre-existing pattern; run the dictionary check against the source schema before the copy and decide whether `main()` turns them into `data_export_error`); recipe definitions are checked one way only (a definition with no SQL column passes); `_protocol_wahlperiode` accepts Unicode digits; `_demote_headings` treats a fence line with an info string inside an open fence as a close, ignores 1–3-space-indented fences and setext headings, and `_license_notice` has the same edges; `_PLACEHOLDER_RE` rejects legitimate text (`XXX-Straße`, `??`) and `_authored_text`'s bare minimum length 8 rejects short units such as „Anzahl“ (name it or drop it); ~~`_write_recipe_csv` writes `str()` of a BLOB; recipe with duplicate output column names collapses; `_md_cell` leaves `\r`; DATA.md licence line „..“ and names only `--data-license`~~ Done 2026-10-31 (branch `fix/todo-batch-3-export-output`): a BLOB or a repeated recipe column name now raises a `RuntimeError` in the CSV writers (no store column or recipe has either; float cells keep Python's shortest round-trip repr, which is exact), `_md_cell` turns CR and CRLF into `<br>`, the licence line names both `--data-license` and `$BUNDESTAG_PULSE_DATA_LICENSE` and ends in one full stop. A BLOB cell or a duplicate recipe column name now raises a `RuntimeError`, which escapes `main()` as a traceback after the store was persisted (the same pre-existing pattern as the other export `RuntimeError`s; no input today triggers it); floats keep their shortest repr by decision. Follow-up: move the duplicate-name check to the cursor in `export_distribution_data` (before `dict(row)` collapses the rows) once that function is free to edit; today it runs in `_write_recipe_csv`. `_manifest_reusable` keeps an `export_format` parameter that `validate_manifest` overrides with the global; DATA.md's recipe section hard-codes „LIMIT 5“ instead of reading each recipe's limit (D2); ~~`csv.writer(..., lineterminator="\n")` may not quote a bare `\r`~~ Done 2026-10-31: `_write_csv_row` quotes any row holding a `\r` itself (measured: 3.11.15 and 3.13.12 already quote it, so only older patch levels were exposed; a test pins the bytes on every version). Done when each item has a fix and a test, or a recorded decision.

**Why:** Deferred by the owner during the codebook /ship (2026-10-30, decisions D4 and D7). (1) predates the branch and the window is narrow; (2) guards a leak that does not exist today. (4) is latent, cosmetic or naming, deferred under the CLAUDE.md fix-now-or-defer rule (2026-10-31).

**Effort:** M
**Priority:** P2
**Depends on:** None

### Recipe SQL disagrees with the site's own counting rules in edge cases

**What:** ~~(1) r4 and r5 take the "first" sitting by lexicographic `MIN(document_number)` ("21/100" < "21/99"); order numerically (D5).~~ **Done 2026-11-05:** r5 and `_VOTE_PROTOCOL_SQL` (r3, r4, r6) order by Wahlperiode and sitting number. Replay of 716 sittings: r3, r4 and r6 0 rows moved (no vote has TOPs in more than one sitting); r5 278 of 7,925 rows change `erste_drucksache`, for example proceeding 230141 19/21 → 19/5; none of the 278 is in the published LIMIT 5, and all six recipe CSVs are byte-identical, apart from r2's new file name. ~~(2) r4 ranks by `ABS(yes_count - no_count)` with no guard, and the vote parser stores a block without `data-chart-values` as 0:0:0:0 (`validate_dip_protocol.py` pads with 0, `persist_dip_pulse_store.py` `int(total.get("yes") or 0)`), so such a vote would rank as the narrowest; `facts.py` already guards with `yes_count + no_count > 0`. 0 such votes in reference export g-c1944485a5d4.~~ **Done 2026-11-05:** already fixed by export format 14: the parser stores a missing total as NULL and r4 filters NULL counts. (3) r3 excludes only `fraktionslos`; the site's Abweichung rule (`derive.vote_abweichler`) also skips the `Unbekannt` group and groups whose member votes do not match the fraction counts (`partial`). (4) Check whether the shared „Unbekannt“ speaker record (`resolve_speaker` for an unnamed Redner) reaches `mp_canonical` and so r1/r2; 0 such rows in the reference export. (5) r6 groups on the raw `origin_json` urheber, while the vote panels (`derive.vote_committees`) strip and de-duplicate each name, and its `LIKE 'Beschlussempfehlung%'` is case-insensitive where the site's `startswith` is not; neither differs on today's DIP strings. Each change moves published figures: report old and new rows per the CLAUDE.md pre-release rule. Done when each recipe matches the site rule or DATA.md names the difference, with old/new figures recorded.

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

**What:** (1) The CC BY metadata layers (`eigene-metadaten`, `eigene-metadaten-zuordnung`, `eigene-auswertung-uebernommene-quelldaten`) accept `dip`/`bundestag.de` tags, so whether e.g. `mps.identity_key` (built from DIP/XML names) is own metadata rests on authoring judgment; decide per column. (2) Join tables tagged `bundestag.de` may need their own bundestag.de licence layer instead of a DIP one. (3) ~~The Unbekannt party row is not described under `parties.name`.~~ Done 2026-10-31: the dictionary now says it is the project's placeholder for a vote member whose list names no Zusammenschluss. (4) `test_codebook_describes_all_real_columns_and_snapshot_coverage` packs ~40 assertions with negative string pins; `test_codebook_matches_stored_codes_and_period_units` and `test_authored_definitions_distinguish_sources_units_and_exact_quotations` grep German fragments; derive expectations from the store or code where possible (/test-audit). (5) ~~The embedded short string says „Details in LICENSE-DATA.md“, a file only a published release carries; say so in DATA.md or ship the file with every export.~~ Done 2026-11-01: every export carries `LICENSE-DATA.md`, and DATA.md says so. (6) DATA.md links into github.com/LucaAlv/poliwatch (the B4 audit link) and names repo paths; check the repo is public before a release cites them. (7) `person_records.home_person_id` can keep a retired person id within one generation (`person_registry.merge` repoints `person_id` but not `home_person_id`), while DATA.md's alias line speaks only of cross-generation joins; latent today (0 merges in `scripts/person_corrections.json`). (8) The audit's "Could not verify" list (docs/research/codebook-dictionary-audit-2026-10-31.md section 3). Done when each has a decision or a fix.

**Why:** Informational findings from the codebook /ship runs 4 and 5, deferred under the CLAUDE.md fix-now-or-defer rule.

**Effort:** S
**Priority:** P3
**Depends on:** None

### C1 seat counts: deferred findings

**What:** Items from the C1 build (steps 3–9, 2026-11-01). Each was deferred under the fix-now-or-defer rule, because none is a wrong figure today:
1. **`stammdaten.refresh` makes one attempt.** There is no retry and no line in the DIP request log. A failed fetch keeps the previous file, and the next build retries.
2. **A failed ETag sidecar write is reported wrongly.** If the sidecar write fails after the replace, the warning names the old Stand although the new file is cached. The next fetch is then a full download.
3. ~~**The online path's cross-check call has no test of its own.** The offline one does. The Politikfeld summary beside it is in the same position.~~ **Done 2026-11-02** in the /gstack-ship run: `test_backfill.py` pins the online call after the rebuild (the Politikfeld summary beside it is still untested).
4. **A real misattribution can be filed as `change_on_vote_day`.** This happens when it falls on a day whose Zugehörigkeit changes cover the difference. The count rule narrows it, and the reference data has no such case.
5. **A `shift_between_groups` could be a derivation fault rather than a source error.** Step 9 compares the ids with E4 again.
6. **`validate_manifest` does not check the shape of the manifest's `stammdaten`.** A published override manifest with a malformed `stand` makes the Daten page raise in `stammdaten_stand_day`. The export writes the key from the store, so no current input reaches this. Codex (2026-11-02, P2) adds that an object with a valid `stand` but no `sha256`, or a non-object value, also passes and raises in `render_daten_datenstand` (`KeyError('sha256')`) after other pages are written, leaving partly updated output. Fix: accept only null or an object with a parseable `stand` and a 64-hex `sha256`.
7. **An earlier cross-check report can stay in place.** This happens if the store cannot be read when the cross-check runs. The build has just written the store, so no current input reaches this.
8. ~~**`stammdaten.refresh` can create the private directory world-readable.** It runs `path.parent.mkdir(parents=True, exist_ok=True)` without `mode=0o700`, while every other creator of the private directory passes it (`person_registry`, `politikfelder`, the export work dir). The zip itself is written 0600. In a build, the writer lock creates the directory first, so no current input reaches this. Found in step 9, when a direct `refresh` call created `drwxr-xr-x`.~~ **Done 2026-11-05:** closed by item 33: `ensure_private_dir` creates it 0700.

Items 9–20 come from the pre-landing review of 305cfee (2026-11-02: specialists, red team, adversarial pass; Codex still owed). A scan of the live file (Stand 29.04.2026, 4,614 MdB) found 0 zero-length memberships, 0 memberships outside their Mandat and 0 same-start ties, and the seat rows (2,914 / 171) were identical under four `PYTHONHASHSEED` values, so none of these moves a figure today:

9. ~~**`_mandate_stretches` accepts inverted, zero-length and seed-dependent stretches.** Two reviewers asked for this before merge. Rule 2 clips only the endpoints, so a membership wholly before `MDBWP_VON` or after `MDBWP_BIS` gives `valid_until < valid_from`; `party_seats` then emits `seats=-1` (`if count:` is true), and `check_seat_totals` cannot see it. Separately, `records` is a set sorted by start date only, so a one-day membership (`MDBINS_VON == MDBINS_BIS`) on a handover day ties with the next membership: under `PYTHONHASHSEED` 1 and 3 it gives a zero-length row that collides on the primary key with the next row; other seeds raise "two memberships on the same day". Such a file passes `seat_rows`, so `refresh` caches it, and every later rebuild fails at `CHECK (seats > 0)` or the primary key until the cache is deleted by hand. Fix: sort by `(von, record)`, raise StammdatenError for `until is not None and until <= von` after the clip, and refuse `seats <= 0` in `party_seats`; add both shapes to `tests/test_seat_counts.py`. The ship's adversarial pass (2026-11-02) adds: `seat_rows` is the gate `refresh` uses, but it checks less than `persist_seat_counts` enforces (`seats > 0`, the primary keys), so such a file is cached and every later rebuild dies with a raw `sqlite3.IntegrityError` rather than DatabaseRebuildError; make `seat_rows` assert positive seats, `valid_until > valid_from` and key uniqueness.~~ **Done 2026-11-05:** `_mandate_stretches` sorts by `(von, record)` and refuses a stretch that ends no later than it starts, so a one-day membership on a handover day is refused alike under every hash seed. `party_seats` refuses a negative count, and `seat_rows` refuses what the store's CHECK and primary keys would refuse. The live file passes: 2,914 and 171 rows at Stand 29.04.2026, identical to main under four `PYTHONHASHSEED` values.
10. ~~**`read_zip` can raise exceptions other than StammdatenError.** `int(VERSION)` / `datetime.fromtimestamp` raise OverflowError or ValueError for 20+ digits or out-of-range values; `str.isdigit()` accepts non-ASCII digits such as "²", which `int()` then rejects (also `WP`); a corrupt deflate stream raises `zlib.error` and an encrypted member RuntimeError, neither caught by `_xml_bytes`. Then `refresh` crashes instead of keeping the cached file, a bit-rotted cache is never self-healed, and `rebuild_seat_counts` escapes with a traceback instead of DatabaseRebuildError. Fix: make `read_zip` raise only StammdatenError (ASCII-digit checks, wrap the conversions, widen the `_xml_bytes` except).~~ **Done 2026-11-02** in the /gstack-ship run: ASCII-digit checks for VERSION and WP, the timestamp conversion wrapped, `_xml_bytes` also catches `zlib.error`, RuntimeError and NotImplementedError, and the parse also catches LookupError (an unknown declared encoding, found by the ship's adversarial pass); `test_stammdaten.py` has the rows. ~~**Still open:** a corrupt ZIP_LZMA member raises `lzma.LZMAError`, which escapes.~~ **Done 2026-11-03:** `_xml_bytes` also catches `lzma.LZMAError`; `test_stammdaten.py` has corrupt LZMA and bzip2 rows (an encrypted member cannot be written by `zipfile`, so that branch has no test).
11. **`stammdaten.refresh` runs outside `registry.writer_lock`.** Two concurrent online builds can race: the stale-temp sweep unlinks the other build's in-flight temp file (a spurious warning, no corruption), and `read_zip` reads the file twice (parse, then `hashlib.sha256(path.read_bytes())`), so a replace landing between the reads stores a sha256 that names other bytes than the seat rows came from. Fix: hash and parse one buffer; take the writer lock around `refresh` or drop the sweep.
12. ~~**`log_seat_crosscheck` can fail the build.** Its docstring says it never does, but only `sqlite3.Error` is caught; an OSError from `path.unlink`, `path.parent.mkdir` or `dip.write_text_atomic` (full disk, permissions) leaves `main()` after the store swap and before the site and export. Fix: catch OSError around the report write and unlink and print a note.~~ **Done 2026-11-05:** `write_crosscheck_report` turns an OSError into a note, and the summary leaves out the report path when nothing was written.
13. **WP 22 will freeze the seat data quietly.** `BUNDESTAG_SIZES` stops at WP 21. Once the file lists a WP 22 Mandat, `check_seat_totals` raises, `refresh` rejects every new file with a warning, and the seat tables stay at the last accepted Stand while the build passes. Decide whether that should fail the build, and add 22 when its size is known.
14. **The handover-day trim only fires when the newcomer's first row is the leaver's group.** A Nachrücker whose Fraktion membership starts after the Mandat (first row `fraktionslos`) on a leaver's last day counts that day twice, below the cap, so the size check passes it. The live file has no such case; its 6 same-day starts after a leaver's last day are cross-group (e.g. 04.03.2024, the Berlin repeat election), where the source gives both people a Mandat that day.
15. **`refresh` never compares the Stand.** A CDN serving an older zip (ETag mismatch, so no 304) replaces a newer cache, and the seat tables, r2 and the manifest Stand move backwards with only a "fetched" line. Fix: keep the cached file when `fetched.stand < previous.stand` and warn.
16. **`after_stand` compares whole UTC days.** A vote on the Stand's own day, after the file was generated, is filed as `change_on_vote_day` or `unexplained`; the UTC date can also differ from the Berlin date near midnight. Cosmetic.
17. **`ET.fromstring` parses the download without refusing a DOCTYPE.** No external entities are resolved; entity-expansion protection rests on the linked expat version. The source is a fixed https URL. Optional: refuse `<!DOCTYPE`/`<!ENTITY` in the first bytes (the real file has none).
18. ~~**Test gaps.** `log_seat_crosscheck`'s "no seat count on the date", "no group totals" and unreadable-store branches have no test; nor does `refresh` with a corrupt cache plus a stale ETag sidecar (no If-None-Match may be sent).~~ **Done 2026-11-02** in the /gstack-ship run (coverage audit): both not-compared branches, the unreadable store and the corrupt cache with a stale or damaged sidecar have tests.
19. **Cosmetics.** `tests/test_repersist.py` Value headers name `seam=repersist_cached_report` (the function is `repersist_cached_reports`); the two "MdB-Stammdaten nicht geladen" warnings word one condition differently and mix languages; four blank lines before `StammdatenError` in `derive.py`; `CROSSCHECK_NAME` sits ~90 lines below `CACHE_NAME`/`ETAG_NAME`; `log_seat_crosscheck` builds `by_cause` with a `not in` list scan (a dict per cause saves ~3 lines).
20. ~~**`_apply_features_file` and `ENRICHMENT_IDS` are dead code.** No caller reaches `_apply_features_file`, the only reader of `ENRICHMENT_IDS`, which still lists three enrichments without `mdb-stammdaten`. The live path (`ENRICHMENT_REGISTRY`) is right. Delete both.~~ **Done 2026-11-03:** both deleted, with `_apply_feature_tokens` (their only helper) and the imports only they used (`subprocess`, `features.resolve`, `features.REGISTRY`).
21. **A rebuild without the cached zip empties seat tables the previous store held.** `rebuild_seat_counts` warns and returns when no cache exists, and the fresh staged store replaces the old one: r2's `sitzanteil_prozent` goes blank, the manifest's `stammdaten` becomes null, the Daten page says "Sitzzahlen: keine", and the exit code stays 0 (a lost `.OUTPUT.private`, a new machine, another `--database-path`). Documented as designed; the review's D1 (2026-11-02) kept it. Options if it bites: refuse the rebuild when the old store had a Stand row and no cache exists (naming `--enrich mdb-stammdaten`), or carry the three tables forward like `preserve_roster`, which risks stale beats fresh.
22. ~~**A corrupt cache gets the wrong warning.** When the cached zip exists but `read_zip` fails, `refresh` words `kept` as "no cached file: keine Sitzzahlen until a fetch succeeds". If the fetch then fails or the download fails the seat checks, the corrupt file stays and the next `rebuild_seat_counts` raises DatabaseRebuildError, so the build stops rather than running without seat counts. Fix: name the unreadable file in `kept`. (/gstack-ship state-machine review, 2026-11-02.)~~ **Done 2026-11-05:** `kept` names the unreadable file and its cause, and says the next rebuild stops until a fetch succeeds or the file is removed.
23. ~~**A 304 can pin a cached file that newer rules reject.** On 304 `refresh` checks the cached file with `read_zip` only, not `seat_rows`; after a rule change (a new name in `STAMMDATEN_ZUSAMMENSCHLUESSE`, a `BUNDESTAG_SIZES` edit) every rebuild fails while the fetch keeps answering "unchanged" until the cache is deleted by hand. No current input reaches it. Fix: run `seat_rows` on a 304 and drop the ETag when it fails.~~ **Done 2026-11-05:** closed without a change. The proposed ETag drop is a no-op: `refresh` already sends no If-None-Match when `read_zip` fails, and a 200 overwrites the sidecar. Running `seat_rows` on every 304 costs each build a derivation, and no current input needs it.
24. ~~**Untested `refresh` cells.** No cache with a failed cache write; a corrupt cache with an invalid download, a failed fetch, or a failed cache write. The state-machine review's matrix (2026-11-02) lists the expected rows.~~ **Done 2026-11-05:** the rows for no cache with a failed cache write, and a corrupt cache with an invalid download, a failed fetch or a failed cache write, have tests. Still untested: a corrupt cache with a 304 answer.
25. **`read_zip` parses the whole tree, up to three times per build.** `ET.fromstring` on up to `MAX_XML_BYTES` (64 MB; the real XML is 15.3 MB) costs roughly 10-20x in memory, and an `--enrich mdb-stammdaten` build parses the old cache, the download and the cache again in the rebuild. Fix: `iterparse` with element clearing, a lower cap, and a VERSION-only read of the old cache for the log line.
26. ~~**The Daten page's Stammdaten line may overflow at 375px.** The sha256 sits in a bare `<code>`; only `code.sha` gets `overflow-wrap:anywhere`, and `.stammdaten-line` is missing from the 14px rule beside `.coverage-line`. Derived from the CSS by the red team (2026-11-02); not rendered. Fix: use `class="sha"` and add the class to the 14px rule, then check at 375px and in dark mode.~~ **Done 2026-11-03:** `.stammdaten-line` joined the 14px rule and its `<code>` may break anywhere (kept inline rather than `class="sha"`, which is a block); a rendered Daten page overflowed by 148px at 375px before, 0 now.
27. **Two stores in one `OUTPUT/data` share one cross-check report.** `crosscheck_path` is per private directory, not per store, so a second store there would overwrite (or unlink) the first store's `seat-crosscheck.json`. No current build uses two stores per OUTPUT.
28. **`_download` follows redirects to any scheme or host.** urllib's default handler would follow a 30x from the fixed https URL to plain http or another host; the body is then checked only by the zip and seat rules. Optional: refuse a redirect off https://www.bundestag.de.
29. **Cosmetics.** The `stammdaten.py` module docstring names only the cache and the reader, not `refresh`, `seat_rows` and `crosscheck`; the ETag sidecar writes a `fetched_at` nothing reads.
30. ~~**P2: a renamed `INSART_LANG` label would make every MdB fraktionslos and pass every check.** `_mandate_stretches` keeps only institutions whose `INSART_LANG` equals `"Fraktion/Gruppe"`; the closed-name check runs only on those, and rule 3 files every uncovered Mandat day as fraktionslos. If the Bundestag renamed the label, a file with 630 fraktionslos seats in WP 21 passes `check_seat_totals` (630 is the legal size), `refresh` caches it, and r2 and the seat tables publish fraktionslos at 100 % with only cross-check warnings. Reproduced on synthetic records by the ship's adversarial pass (2026-11-02); the live file has the label. Fix: make `seat_rows` refuse a Wahlperiode with Mandate but no matched Fraktion/Gruppe membership (or an implausible fraktionslos share on its first day).~~ **Done 2026-11-05:** `seat_rows` refuses a Wahlperiode whose Mandate are all fraktionslos; no share threshold. The live file passes.
31. ~~**`--enrich all` now downloads the MdB-Stammdaten.** `all` expands to every registered enrichment, so existing `all` configurations fetch and may replace the cache. The tests pin this as intended; say so in the README's enrichment table if it stays.~~ **Done 2026-11-05:** the README says so beside the `--enrich` values.
32. **The download timeout is per socket operation, not total.** `urlopen(..., timeout=60)` then `response.read(MAX_ZIP_BYTES + 1)`: a slow-drip server can stall an online build for a long time. Fix: read in chunks against a monotonic deadline.
33. ~~**P2: `stammdaten.refresh` and `log_seat_crosscheck` skip `registry.ensure_private_dir`.** Every other writer to the private directory (the staged store, politikfelder, the export work dir) calls it first, which refuses a symlink, a foreign owner or a group-writable directory before anything is written or swept. `refresh` reads the cache, sweeps `.mdb-stammdaten.*.tmp`, writes the temp file and the ETag sidecar (following a symlink) before the writer lock validates the directory; `log_seat_crosscheck` writes or unlinks its report after a bare `mkdir`. Codex (2026-11-02) reproduced it: with `.OUTPUT.private` planted as a symlink to an attacker's directory holding `mdb-stammdaten.json -> <a builder-writable file>`, one refresh truncated that file before the writer lock refused the directory. Needs a planted symlink in the site's parent. Fix: call `registry.ensure_private_dir(path.parent)` at the top of `refresh` (warn and keep on PermissionError) and before the report write; this also closes item 8. Deferred by the ship's adjudicated D2 (third fix cycle).~~ **Done 2026-11-05:** `refresh` and the report write call `registry.ensure_private_dir` first; on a refusal `refresh` warns and fetches nothing.
34. **A same-day cross-group handover can overshoot a full Wahlperiode and freeze the seat data.** The Nachrücker trim in `mdb_zugehoerigkeiten` keys on the leaver's group, so a leaver of another group (or a fraktionslos leaver) whose Mandat ends on the day a Nachrücker's starts counts twice that day. WP 21 sits at exactly 630, so that day reads 631, `check_seat_totals` raises, and `refresh` rejects every later file with a warning while the build passes on the old Stand. Reproduced on synthetic records by the ship's second adversarial pass; how often the source dates a Nachrücker on the leaver's last day is not measured. Related to items 13 and 14. Options: key the trim on Wahlperiode and day regardless of group, or make the overshoot a warning with a "Stand frozen" line.
35. **`_repoint_party` does not repoint the seat tables.** `_migrate_party_names` repoints `mps`, `vote_members` and `vote_fractions`, not `mdb_zugehoerigkeiten.party_id` or `party_seats.party_id`; the following `DELETE FROM parties` would hit the foreign key. Seat rows are written with normalized names after `initialize()`, and a schema-8 store is refused, so no current input reaches it.
36. **The Nachrücker trim can take a seat from the wrong leaver.** It pairs a leaver with any same-group Mandat starting on the leaver's last day, before pairing the normal case (a newcomer the day after). With leaver X ending 10.05, leaver Z ending 09.05, Y2 starting 10.05 (for Z) and Y1 starting 11.05 (for X), X loses 10.05 and `party_seats` reads 2, 1, 2 instead of 2, 2, 2; the size check and the cross-check's `change_on_vote_day` cannot see it. Measured on the live file (29.04.2026): the trim fires twice (FDP 2023-08-07, Grüne 2024-03-04) and neither has a same-group leaver the day before or a starter the day after, so no current figure moves. Fix: pair day-after newcomers first, trim only the leftovers. (Ship adversarial pass 3, 2026-11-02.)
37. **`read_zip` accepts any VERSION that fits a datetime as the Stand.** `0` or `99999999999` (year 5138) becomes the Stand, which drives `after_stand`, the manifest, the Daten page and r2's caveat date; a far-future Stand silences the drift warning. Needs a bad source file. Optional: refuse a Stand after now plus a day or before 2017.
38. **A huge in-cap XML can raise MemoryError out of `refresh`.** `ET.fromstring` on up to 64 MB of tiny elements is not a StammdatenError, so the build dies before the writer lock instead of keeping the cache. The crash form of item 25; same remedy.

Done when each has a fix or a decision.

**Why:** Items 1–8 are the "Left open" lists in `docs/plans/c1-seat-counts.md`, steps 4, 5, 7 and 9; items 9–20 are the deferred findings of the 2026-11-02 pre-landing review; items 22–38 are the deferred findings of the 2026-11-02 /gstack-ship review.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Acquire ceremony addresses omitted from sampled plenary XML

**What:** If ceremony addresses are to be ingested, acquire an explicit ceremony source and define its sitting association. The inspected 2016 and 2021 memorial speeches precede their plenary sittings and are absent from the plenary XML; do not synthesize a guest unit or treat all role-less speakers as guests.

**Why:** A1's source-backed guest check corrects the original assumption that those guest addresses inflate delivered Rede counts, but cannot ingest text its source omits.

**Priority:** P2
**Depends on:** Separate source acquisition and evidence-backed association; see [coverage evidence](docs/plans/a1-validation.md).

### Harden the vote acquisition and catalog completeness paths (open review findings)

**Partly done (A3, 2026-10-20):** (2) the backfill now prints its judged range and the selected sittings per Wahlperiode, and judges from the v1 floor; (5) every online build ends with a summary of the sittings it did not acquire and exits 1 when one was lost to an outage.

**What:** Findings from the /ship review rounds of fix-votes-completeness (2026-09-29) that were accepted, not fixed:
(1) `source_stale` (`validate_dip_protocol.enrich_with_api`) holds a genuinely vote-free sitting of the last 14 days partial when the list head is older, delaying its week's and month's vote Fakt by up to two weeks; (2) the judged range starts at the earliest stored sitting, so one old cached dossier turns `--backfill-incomplete` into a job of hundreds of sittings and nothing prints the range; (3) the `numFound` check in `fetch_protocols` hard-stops every build if DIP's count ever includes unretrievable documents, with no override; (4) report JSON, SQLite and the catalog file are written at different points, so a build interrupted between them leaves `--offline` judging completeness from new reports against an old store; (5) a build whose every refresh was skipped exits 0; (6) the build-wide roll-call page cache is a snapshot, and list pagination can shift under a long build (duplicates a boundary entry); (7) `namenslisten_entries()` has no outage cooldown, so an outage costs about 3 minutes per vote; (8) an empty list page after page 1 counts as the end of the list; (9) catalog entries in range with no usable number or date only warn instead of failing closed, and duplicate document numbers keep the last; (10) `api_records.matched_roll_call_votes` and `roll_call_vote_candidates` describe the fresh scan while `agenda_items[].votes` may be cached after a no-scan run; (11) some date checks use the wall clock, not `--today`; (12) a failed vote-detail page stops matching for the rest of that sitting; (13) an uncaught `JSONDecodeError` from the DIP API aborts a build; (14) the offline build trusts the cached catalog with no age check; (15) the in-progress ISO week can be judged complete.

**Why:** Each is a place where a build can publish a slightly stale fact, waste a long backfill, or stop. None was reproduced as a wrong published fact on the reference copy; they were found by reading the code. Codex adversarial and structured reviews of the final tree were unavailable (usage limit), so this list has Claude-only coverage.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Tell official addresses and presidium Reden apart from Fraktionsreden (ADR 0004)

**What:** Detect and treat a turn given on behalf of the Bundestag or in exercise of the Sitzungsleitung when the XML gives it a `<rede>` of its own with a presidium `rolle_lang` (Präsident, Vizepräsident(in), Alterspräsident). Today such a `<rede>` is counted as a Rede of the speaker's Zusammenschluss. Found in the WP 18/19 rule-5 work ([validation record](docs/plans/a3-rule5-validation.md)):
- 19/1: the Alterspräsident's Sitzungsleitung Reden (ID19100100, ID19100200, ID19101000, ID19101200) and Schäuble's inaugural address as the new Präsident (ID19101300), and his Sitzungsleitung ID19101900.
- 18/1: the inaugural address after "ich nehme die Wahl an" (still refused at an earlier turn).
- 18/245: Vizepräsidentin Bulmahn's farewell address (ID1824501400) and Vizepräsident Singhammer's announcement of an election result (ID1824502300).

Then decide what each kind is: Sitzungsleitung (excluded, like a nested presidium marker, 6d), an official address (its own kind, not a Fraktionsrede), or a debate Rede of an MdB who holds the office (counts for the Fraktion, ADR 0004). Until then 18/1 and 19/1 are excluded sittings (`--exclude-document-number`, owner decision 2026-10-20).

**Why:** ADR 0004 says Sitzungsleitung is never a Rede and official addresses are not counted as Fraktionsreden automatically; the parser has the nested half of that (6d) but not the `<rede>` half.

**Priority:** P1 (blocks counting 18/1 and 19/1, and moves 18/245)
**Depends on:** an owner decision on the kinds; the full WP 18/19 download to list every case.

### WP 18/19: nested Erwiderung, Erklärung and Geschäftsordnung turns (rule 5, a later round)

**What:** Three recurring kinds that WP 18/19 prints inside another speaker's `<rede>`, each needing its own rule. Until a rule lands, their sittings stay on the reviewed exclusion list; each leaves the list when its rule lands, with old/new figures (owner decision 5, 2026-10-22, [round 2](docs/plans/a3-rule5-wp18-19-round2.md)).
- **erwiderung-nested:** the addressee answers a Kurzintervention nested, and the chair's wording ("möchte noch kurz erwidern", "wünschen Sie zu erwidern?") is outside `invited`. 18/11, 18/20, 18/42, 18/88, 18/127, 19/12, 19/14.
- **erklaerung-nested:** a persönliche Erklärung, an Erklärung zur Aussprache (§ 30) or zur Abstimmung (§ 31) printed nested. 18/29, 18/97, 18/98, 18/117, 18/118. In 18/29, R3's wider floor wording now splits Groth's § 31 Erklärung (`ID1802902700:2`) as a Rede of its own; DIP lists it as "Mündliche Erklärung gem. § 31", so the rule must keep an Erklärung out of 6c.
- **go-debate:** Geschäftsordnung statements or motions printed nested. 18/2, 18/3, 18/67, 18/89.

**Why:** Each kind blocks 4–7 sittings; together they are about a quarter of the remaining WP 18/19 exclusions ([audit](docs/plans/a3-wp18-19-audit.md), [round-2 result](docs/plans/a3-wp18-19-round2-result.md)).

**Priority:** P2
**Depends on:** an owner yes per rule, then a test-first build and a new-rule unit review, as in round 2.

### 20/11: the chair's handover exchange with the next speaker, filed inside the previous `<rede>`

**What:** In 20/11 TOP 2 the XML keeps, inside Miersch's `<rede id="ID201100900">` after his "Vielen Dank.", the chair's "Nächster Redner: … Karsten Hilse", a remark to Hilse, Hilse's "Das freut mich sehr." and "Jetzt erteile ich Ihnen das Wort für Ihre Rede." The validator refuses the sitting (`unresolved nested contribution at ID201100900 marker 2`), rightly: Hilse's line is no Zwischenfrage. A rule would treat a nested exchange between the chair and the speaker of the next `<rede>`, after a floor grant to that speaker, as Sitzungsleitung, not a nested contribution. Then 20/11 leaves the exclusion list, with old/new figures. The source error is E1 in [docs/source-errors.md](docs/source-errors.md).

**Why:** 20/11 (2022-01-13; TOP 2 is a climate and energy debate with Minister Habeck) is excluded since 2026-10-28 ([a3-phase3.md](docs/plans/a3-phase3.md), 4.4).

**Priority:** P2
**Depends on:** an owner yes on the rule, then test-first, and a check that no WP 18–21 sitting moves except 20/11.

### Check that the identity merge joins the MdBs WP 18/19 prints with an initial

**What:** WP 18/19 XML prints seven MdBs with a middle initial inside `<nachname>`: W. Birkwald, G. Lämmel, G. Wöhrl, S. Neu, M. Huber, E. Fischer, A. Lamers. R4 strips the initial only for the chair's recipient match; the stored `last_name` keeps it (decision 4). After the pilot re-run, check whether the identity merge (name+party pass) joins each of them across WP 18/19 and WP 20/21, and fix `last_name` or the merge if it does not.

**Why:** One person split into two Abgeordnete would halve their counts on both pages.

**Priority:** P2
**Depends on:** the pilot re-run (A3 Phase 1).

### `audit_offline_turns.py` stops on a non-locator ValueError

**What:** `scripts/audit_offline_turns.py` raises out of the whole run on the first `ValueError` that names no `at <rede> marker <n>` locator (for example "conflicting roles"), so one such sitting ends the audit of a directory. Record such a file as a hard error in its result and go on, as the scratch harness `~/agent-runs/a3/tools/rule5/audit_all.py` does. Test-first.

**Why:** The WP 18/19 audit had to run around it twice (18/101 in round 1; 18/124, 18/136, 18/173 in round 2).

**Priority:** P3
**Depends on:** none.

### A3 pre-landing review: deferred findings (2026-11-01)

**What:** Findings of the /gstack-review of `worktree-a3-plan` (tip 41a7781) that are not correctness defects for any current input, so they were recorded instead of fixed (CLAUDE.md). The review fixed the literal `{abdeckung}` in the stored and exported `fact_metrics.caveat` and README rows 163/164; everything below is open. Found by reading the code (specialist, adversarial and red-team passes); none was reproduced as a wrong published figure.
- **Exclusion record (D2):** ~~(a) `--exclude-document-number` with a number the catalog does not list is silently dropped (not recorded, nothing printed), and with `--offline`/`--fetch-xml` the flag is ignored without an error; reject both, as `--include-document-number` already is.~~ **Done 2026-11-05:** an unknown number is refused online with exit 2, and the flag is refused beside `--offline` and `--fetch-xml`. ~~(b) A malformed `data/coverage-exclusions.json` (non-list `exclusions`, a non-dict entry, a missing `document_number`) ends every run, offline included, in a traceback; turn it into an `ERROR [cached input]` exit 1.~~ **Done 2026-11-05:** already done in #132 (`CoverageExclusionsError`). (c) The exclusion is applied after `load_existing_detail_entries`, whose `require_vote_shape` still raises for a stored-then-excluded sitting with an outdated report, so the exclusion cannot rescue that sitting. (d) `protocols/` dossier pages are never pruned (bills, Abgeordnete and Fakt pages are), so a stored-then-excluded sitting keeps an unlinked page on disk. (e) `dossier_failure_reasons` (`excluded`, `source_unavailable`) is set on the catalog dicts and written into `plenarprotokoll-catalog.json` (85 keys on `~/agent-runs/a3/full`); with `fetch_catalog` reusing closed Wahlperioden for 7 days, a sitting taken back with `--include-document-number` but not re-acquired keeps `presentation_state="unavailable"`/`excluded` in the publication manifest while the Daten list no longer names it. Strip the key in `catalog_payload`, or keep the reasons apart (offline renders currently read them back from the file; decide that too).
- **DIP request budget:** (a) `XmlPacer.fetch` raises `SourceSlowError` from `finally`, which discards a complete XML that took over 10 s and replaces an in-flight `DipError` (including `source_rejected`); nothing catches it, so the run ends in a traceback without the `[summary]`. Deliver the body and stop on the next call, and catch it in `main()`. (b) The pacer counts one request per `fetch()`, while `_fetch_page` retries up to twice more. (c) The per-sitting `/person` loop counts a 404 toward `PERSON_FAILURE_LIMIT`, while the breaker treats a 404 as DIP answering; with `DIP_FAILURE_LIMIT = 2` the person limit of 3 is rarely reachable anyway. (d) `DipBreaker` resets on 401/403, so a revoked key or a WAF 403 never stops the run. (e) After a breaker trip, `--enrich mp-roster` fails the rebuild (`DatabaseRebuildError`) before the `[summary]` prints; `ingest_mdb_roster` does not use the person cache `prefetch_dip_bulk --persons` fills. (f) `DipCache.save` rewrites both cache files after every sitting even when nothing changed. (g) The 2.0 s pace is defined three times (`BACKFILL_SLEEP_SECONDS`, `prefetch_dip_bulk.SLEEP_SECONDS`, `XmlPacer.spacing`).
- **Caches and catalog:** (a) `fetch_catalog` accepts the cached merge when the distinct-id count equals DIP's total, so a swap (one sitting gone, one added) in a closed Wahlperiode serves stale rows for up to 7 days. (b) A Vorgang cached from a closed-WP sitting (`linked_drucksachen_for_vorgang` labels it with the sitting's WP) never expires even if it is still extended in the current WP; a build between the WP 18 and WP 19 bulk prefetch embeds partial Drucksache lists in its reports. (c) `prefetch_dip_bulk._merge_vorgaenge` swallows an unreadable other-WP `vorgaenge.json` (`except (OSError, ValueError): pass`), which silently skips the cross-WP drop.
- **Identity and attribution:** (a) `_mp_external_ids` gives a record's one bundestag.de member number to every Wahlperiode it voted in, so a WP 19+20 record carrying its WP 20 number "conflicts" in WP 19 with a WP-19-only record of the same person (false split, not false merge); check against the gate store. (b) `person_registry._vote_evidence` takes a vote's Wahlperiode from `votes.protocol_id`, the recipes from `_VOTE_PROTOCOL_SQL` (agenda item first); share one rule. (c) A Rede split out by 6c cites the start page of its enclosing printed Rede (`rid_pages` from the table of contents), not the page it starts on.
- **Facts and pages:** (a) `write_facts_pages` rewrites `facts/methodik.html` on a render with no store file (since A4 slice 0 only a direct `render_site` call; the demo builds a store since slice 1) with `coverage=None`, overwriting the published "seit …" caveat with the neutral one; guard it like the archive page. (b) `coverage_label` names the earliest stored sitting, which can claim "seit Beginn der 18. Wahlperiode" mid-backfill while later Wahlperioden have gaps.
- **Performance:** `agenda_item_votes` has no index led by `vote_id`; `_VOTE_PROTOCOL_SQL` (r3, r4, r6) is a correlated scan per row (22 s on a synthetic 154k-row shape). Add `idx_agenda_item_votes_vote`.
- **Stderr and tests:** `ingest_mdb_roster` stats (`fetched`, `skipped_no_id`) count a person once per Wahlperiode; `audit_offline_turns.py` skips `mark_presidium_fraktionsreden`; untested: the `CatalogCountMismatch` fallback, `_profiles_conflict`'s mixed number/link branches, the 6c page carry-over, `prefetch_dip_bulk` exit 2 and `--persons`; ~~`if __name__ == "__main__"` sits mid-file in `tests/test_a3_round2.py` and `tests/test_validate_dip_protocol.py`; unused imports in `tests/test_dip_request_log.py` (`re`) and `tests/test_validate_store_gate.py` (`hashlib`)~~ **Done 2026-11-05.** ~~`test_xml_pacing.test_backfill_dip_api_spacing_is_two_seconds` duplicates the backfill test.~~ Not a duplicate, kept: it is the only test pinning the value 2.0.

**Why:** Each is a place where a later edge case, operator typo or DIP outage could cost a run or publish a stale state; the review sorted them out of the A3 landing per the fix-now-or-defer rule.

**Effort:** M
**Priority:** P2 (exclusion record, budget (a)/(e), catalog (e)); P3 for the rest
**Depends on:** A3 merged

### A3 /gstack-ship review: deferred findings (2026-11-01)

**What:** Findings of the /gstack-ship review of `worktree-a3-plan` (after the main v0.26.1.0 merge 752684f) that are not correctness defects for any current input (CLAUDE.md). The same review fixed the stale "gemessen über 58 vergleichbare Wochen" in the knappste-abstimmung caveat, the Abgeordnete index copy for the former-MdB table, the `mps.wahlperiode` dictionary source and five README/PRODUCT.md/stable-ids sentences. Open:
- **Exclusion record (D2), continued:** ~~(f) `update_coverage_exclusions` runs right after the dossier loop (`build_dip_pulse_site.py`, before `reparse_cached_xml`/`require_parsed_reports` and the store rebuild), so a run that then fails with "The previous store is untouched" leaves the record listing a sitting the store still holds. Since A4 slice 0 a plain `--offline` render refuses that state ("recorded as excluded are still in the store", fix `--offline --repersist`) instead of rendering "nicht erfasst (ausgeschlossen)" beside counts that include it. Write the record after the store swap so the refusal cannot arise. (Also raised by the 2026-10-31 adversarial pass.)~~ **Done 2026-11-05:** the record is written after `rebuild_database_from_entries` returns. The window that is left is under "TODO round 2026-11" item 1. (g) `validate_manifest` does not check `coverage.excluded` (list of strings), so a malformed `--data-manifest` crashes `render_daten_datenstand`. (h) Untested cells of the exclusion state matrix: `--include-document-number` for a sitting not on the record (stored, unstored, rejected source), excluding an already-excluded sitting (recorded_at kept), and the plain `--offline` render of a recorded sitting (stored, unstored, already excluded: dossier dropped, store kept, `coverage.excluded` lists it); `test_backfill.py:527` stubs the store rebuild.
- **Publication guard:** the `local-path` lookbehind in `publication_state.py` (added for `www.sr.de/sr/home/` in 19/41) no longer flags `/Volumes/Data/Users/…`, `/mnt/c/Users/…` or `/System/Volumes/Data/home/…`. Exempt only matches inside an http(s) URL instead.
- **Gate and prefetch robustness:** `validate_store_gate.audit_links` raises on a href with `%00` or an over-long path, and resolves `..` outside the site; `_data_clone` `rmtree`s any `fresh`/`half` in `--scratch` without a marker; `prefetch_dip_bulk` and a build rewrite the same `data/dip-*-cache.json` without the writer lock; `dip_cache._closed` accepts non-dict `drucksachen` items (AttributeError later).
- **Parser:** `split_nested_reden` searches the chair text for the raw `last_name`, not `asker_name(last_name)`, so a WP 18/19 name printed with a middle initial ("W. Birkwald") misses a 6c split (no case found in the 716 cached sittings). `audit_offline_turns` looks up `mark_roleless_chairs`/`split_nested_reden` with `getattr` no-op defaults; call them directly. No test fails if the audit drops `mark_roleless_chairs` (18-100 audits the same without it).
- **One key, one rule:** the Wahlperiode of a document number is parsed in `build_dip_pulse_site.wahlperiode_of`, `prefetch_dip_bulk._wahlperiode_of`, `person_registry._vote_evidence`, `facts.coverage_label` and `_wahlperiode_sql`, beside the strict `facts.wahlperiode`; they disagree on malformed input ("21/x", stray whitespace). `compare_store_values` calls the private `registry._vote_evidence`. R3/R6 switched to an inner join on `protocols`, so a vote with NULL `protocol_id` would drop out (persist always sets it today; R4's method text says so, R3/R6 do not).
- **Cleanup (advisory):** `prefetch_dip_bulk.staged_positions` is test-only; `_catalog_list` repeats the cursor-paging loop of `counted_list`/`fetch_protocols`/`list_all`; the export manifest's `split_rede_ids` has no reader. Gate coverage: `validate_store_gate.store_counts`/`_store_identity`/`_persist_clone` run only in the real gate.
- **Adversarial pass leftovers:** (a) `DIP_REQUEST_LOG` logs `parts.netloc` and the full query of a non-DIP URL, so userinfo or a foreign token would land in the log (only DIP-supplied XML/roll-call URLs reach it today); log `hostname` and drop the query. (b) `prefetch_dip_bulk` never refreshes `total.json`, so with `--overlap-only` on the current Wahlperiode a grown DIP count makes every run stop on the final count check until the staging directory is deleted; and early in a Wahlperiode one month chunk can hold every position, which the `below=` guard rejects. Both stop the run; nothing wrong is written. ~~(c) The Daten scope line says "jede Sitzung ab der 18. Wahlperiode, für die der DIP-Katalog ein XML-Protokoll führt" while 85 such sittings are excluded; the next line names them, but the sentence could say "bis auf die ausgeschlossenen".~~ **Done 2026-11-05:** it says so when the build has exclusions.
- **Roster Wahlperioden, rule edges (adversarial pass on 8f13bf1):** (a) `land_office_wahlperioden` trusts `wahlperiode_nummer` to be a list of ints: an int raises TypeError and aborts the whole roster ingest, "²" raises ValueError, "19" becomes {1, 9} (no real record has these shapes); check `isinstance(list)` and `isinstance(n, int)`. (b) The cut is per whole Wahlperiode and only ~200 of 1,360 MdB records carry a Fraktion role, so an MdB who takes a Land office mid-period (e.g. after a 2026 Landtag election) loses that whole period, and with no other period, the roster row; none on today's cache. Require sitting evidence (a vote or speech in that period) before cutting, or accept and document it. (c) Stores keep the old lists until `--enrich mp-roster` runs again (`preserve_roster`).
- **Roster Wahlperioden, residue:** `land_office_wahlperioden` drops the Wahlperioden DIP gives only a Land-government role (fixed in this review: 11 of the 1,360 cached MdB records, e.g. Scholz, Habeck, Högl). An office without a `bundesland` still counts: Eva Högl keeps WP 20, when she was Wehrbeauftragte and no MdB. DIP's `person_roles` mark Fraktion membership for only some periods, so a full rule needs another source (the Bundestag's MdB Stammdaten) or per-WP vote/speech evidence.
- **Plan item 1.5 (Deferred from plan: docs/plans/a3-coverage.md):** the share of WP 18/19 Redner whose redner-id finds an abgeordnetenwatch `ext_id_bundestagsverwaltung` was never measured (a3-pilot.md: "not measured"; Phase 3 ran no aw-profiles). Measure it with `--enrich aw-profiles` on a clone of the A3 store and record it in the [Phase 4 record](docs/plans/a3-phase4.md).

**Why:** Recorded by the ship review so the PR could land; each is a latent edge, a guard gap no current input reaches, or test hygiene.

**Effort:** M
**Priority:** P1 (plan item 1.5); P2 (publication guard); P3 for the rest
**Depends on:** A3 merged

### Refuse a render when the Vorgang cache is newer than the store

**What:** Record a fingerprint of the Vorgang cache (`dip-vorgang-cache.json`, plus the Antrag cache) when the store is persisted. An offline render then refuses when the cache on disk differs, and the message names `--offline --repersist`. This is the same shape as `require_current_speech_rules` (`persist_dip_pulse_store.py:72-92`).

**Why:** From A4 slice 1 on, the votes archive shows the Politikfelder persisted in the store, not tags recomputed from the cache at render time (`docs/plans/a4-site-from-release.md`, R4: `tests/test_politikfelder.py:1445` is rewritten). A cache refreshed without a repersist would therefore leave stale tags on the page, with no warning. No current command updates the cache without a persist, so the issue is latent. It matters more once slices 4–7 read more cache-derived data from the store: "Worum es geht", Antrag passages and dossier tags.

**Context:** Found by the outside voice of the A4 eng review (2026-11-01, O7; decision R9 in the plan). Start from the speech-rule check and add one store table or `PRAGMA user_version`-style row for the fingerprint.

**Update 2026-11-03 (A4 slice 1 built):** the gap is now live for `votes/index.html`: `tests/test_politikfelder.py` `test_the_archive_shows_the_persisted_tags_and_the_front_page_the_render_time_cache` pins that an offline render without a repersist keeps the stored tags while puls.html follows the cache. Still latent in practice: no command refreshes the cache without a persist.

**Effort:** S
**Priority:** P3
**Depends on:** none (A4 slice 1 is built)

### A4 slice 1 /ship review: deferred findings (2026-11-04)

**What:** Non-correctness findings from the manual ship of A4 slice 1 (v0.32.0.0; checklist pass and red team). None moves a figure today.
- (a) **Archive vs dossier after a failed online rebuild.** Online step 2 writes the refreshed reports and dossier pages before `rebuild_database_from_entries`; when that raises `DatabaseRebuildError` the old store stays. A later plain `--offline` passes `store_coverage_gap` (it compares protocol ids only) and renders the dossiers from the new reports but `votes/index.html` from the old store, so a late-published roll-call vote shows in the dossier and not in the archive (R3). Needs the same fix as "Refuse a render when the Vorgang cache is newer than the store": persist a per-report fingerprint and refuse a render whose cached report differs, or leave a "repersist pending" marker after a failed rebuild.
- (b) `_total_count` coerces any value with `int()` (`"3"`, `3.0`, `True` → 3, 3, 1; `12.7` → 12), while `derive.vote_groups_cover_total` on the report path accepts only real ints, so archive and panel could disagree on the Abweichler count. Latent: the parser emits ints or `None`. Store NULL for anything but an int.
- (c) A cached report from before 0.32 still prints "0 Ja, 0 Nein, 0 Enthaltungen" in its dossier lead for a listing that had no chart values, until the sitting is fetched again; the store already holds NULL. Read four zeros as missing on the report path too, or reparse.
- (d) `require_current_schema` checks only `vote_fractions.rank`; a hand-altered store missing `vote_documents.rank` or `agenda_item_documents.rank` fails with a raw SQLite error. No code path makes such a store.
- ~~(e) Wording: the `stored_votes` docstring still says 556 votes / 382,441 `vote_members` (reference store now 619 / 425,322); the `rank` dictionary text says "Position der ersten Nennung" while the value is a dense rank over accepted references; `vote_documents.rank` follows the parser's `sorted(set(...))`, not page order; a double blank line in `features/votes.py` where `write_pages` was.~~ **Done 2026-11-05:** the docstring names no counts, and the dictionary and the persist comment say what the rank is, in the text sort of the parser's list. No export format bump, as in #124.
- (f) Persist runs one `SELECT` per TOP Drucksache reference for its `seen` check; a Python set would do. Not measured.
- ~~(g) Test hygiene: `test_politikfelder.CacheFileTests.test_save_falls_back_to_data_on_another_file_system_or_a_read_only_parent` fails when the suite runs as root (chmod 0o555 does not stop root), as in the cloud container; skip it when `os.geteuid() == 0`. `tests/run_bills_browser_check.mjs` can exit 1 after every check passed, when Chrome still writes into its temp profile during cleanup (`ENOTEMPTY`); retry the `rmSync` or pass `maxRetries`.~~ **Done 2026-11-05:** the read-only-parent half is its own test and skipped as root. As root it passed without testing anything rather than failing, as the entry said. The runner's `rmSync` retries. Chrome now gets 60 s to start (15 s failed one CI run on #131), and an early exit is reported with its code.

**Effort:** S each
**Priority:** P3 ((a) P2)
**Depends on:** none

### A4 slice 0 review: deferred findings

**What:** Non-blocking findings from the `/gstack-review` of A4 slice 0 (e184ccc, 2026-11-01; specialists, Claude adversarial, red team). None moves a figure or breaks a page.
- (a) **The coverage check matches sitting ids only.** `store_coverage_gap` (`build_dip_pulse_site.py:691`) compares the protocol ids, not the content. An online run that refreshes an already-stored sitting (backfill, narrowed `--document-number`, vote enrichment) and then fails its staged rebuild leaves new report JSON beside the old store row, and the offline render passes. Dossiers and `puls.html` then come from the new JSON, while MP pages, facts and the export come from the old store. This predates slice 0, and each later slice that moves a page onto the store shrinks it. The fix is a per-protocol report digest recorded at persist (like `speech_rule_inputs`) and compared in the check.
- (b) **The online call site of `store_coverage_gap`** (after `rebuild_database_from_entries`, `main`) has no refusal test, because `test_backfill.py` mocks the function. It can only fail after the store swap and the first dossier pass. Either move it before the swap or drop it as tautological (the rebuild already refuses missing evidence), and test whichever stays.
- (c) **One key, one function:** the rebuild's missing-evidence check keys on the raw `str(protocol["id"])` (`_rebuild_database_from_entries`), while `persist_report` and `store_coverage_gap` use `pulse_store.clean`. A report with a blank id, or two reports with different ids but one `dokumentnummer`, ends in a refusal `--offline --repersist` cannot cure. Strict repersist and the lenient render load (`load_existing_detail_entries`) also disagree on unreadable or numberless reports. All latent: DIP ids are numeric strings.
- ~~(d) **Refusal text:** the not-stored case names only `--offline --repersist`. When that repersist fails on the same report (pre-A1 without XML, new Sprechrolle), the text should also name moving the report out of `data/` or excluding the sitting in an online run. While an online update runs in another terminal, the offline check can see its fresh reports before the swap and give the same wrong advice. Say "if an online update is running, wait for it", or probe `registry.writer_lock`. (The lockout itself is R2's intent, plan O6.)~~ **Done 2026-11-04:** the not-stored case also says to follow the repersist's own Fix, to move a not-stored report out of `data/` or to exclude the sitting; the offline render adds `CONCURRENT_UPDATE_NOTE` (wait for a running online update). Wording, not a lock probe: the writer lock covers only the rebuild, not the fetch before it.
- ~~(e) The F7 comment "Refused before anything is written" overstates. `main` has already created the output directories, and the Antrag and Politikfeld cache loads can quarantine a corrupt cache. Say "before any page or store is written".~~ **Done 2026-11-04:** the comment says "before any page or store is written" and names the directories and the cache quarantine.
- ~~(f) `docs/project-documentation.md`'s scratch-preview example is an online run: it needs `DIP_API_KEY`, does a full staged rebuild and export, and `cp -c` is macOS-only. Say so, and add the README recipe's non-macOS copy command.~~ **Done 2026-11-04:** the example says it is an online run (`DIP_API_KEY`, whole-store rebuild, facts, export step), gives the non-macOS copy and copies the MdB-Stammdaten cache into `.context/.scratch.private/`; the README recipe does the same.
- ~~(g) Test hygiene: `tests/_site_store_fixture.py` `store_people` has no caller, and `build_site_store`'s `today`, `vorgang_cache` and `catalog` parameters are never passed. Slice 1 either uses them or drops them.~~ **Done 2026-11-03** (A4 slice 1): `vorgang_cache` is used by `archive_rows` and the Politikfeld render test; `store_people` is used by the demo test; `today` (now the module's `TODAY`) and `catalog` are gone.
- ~~(h) **The F7 refusal does not mention a backup.** `error: no store at …` names `--offline --repersist` first. For a store that was lost rather than never built, that repersist starts a fresh person registry (new keys and aliases, no roster); `docs/stable-ids.md` "Backup and recovery" says to restore the build store instead. Say "restore the store from a backup if you have one; otherwise …" in the message and the README row.~~ **Done 2026-11-04:** the refusal, its README row and `docs/project-documentation.md` say to restore a backup first, that a rebuilt store issues person keys anew, and that a repersist without a store has no MdB roster (`--enrich mp-roster`).
- ~~(i) Design records still describe `--no-persist` as live: `docs/designs/daten-page.md` (lines 214, 228, 258, 298, 351-352, 420, 441) and `docs/designs/fakt-der-woche.md:311`. Add a one-line "superseded by A4 slice 0 (v0.29.0.0): `--no-persist` removed" note to each.~~ **Done 2026-11-04:** both records carry a "Superseded in part" line under their header.

**Why:** Each is a robustness or wording gap with no current input that moves a figure. (a) is the largest: it can leave pages that disagree with each other after a failed online refresh.

**Context:** The review's real-store smoke run (A3 full clone, `--offline --repersist` then `--offline`) is recorded in the review log. Codex reviewed the same tip (`codex review --base main`, read-only sandbox) and found no actionable regressions; it ran 11 targeted tests, and the sandbox blocked its full-suite run (the review's own run passed 1914).

**Effort:** (a) M; (b), (c) S
**Priority:** P2 for (a); P3 for (b) and (c)
**Depends on:** A4 slice 0 merged

### A stale cached report of an excluded sitting stops every build

**What:** `load_existing_detail_entries` runs `derive.require_vote_shape` on every cached report of the catalog before any caller drops the reviewed exclusions (D2): the `--backfill-incomplete` scan and the existing-entries merge in `main` (`build_dip_pulse_site.py`, both filter `listed` afterwards) and the offline load (`without_recorded_exclusions(load_existing_detail_entries(...))`). An excluded sitting keeps its cached report (`update_coverage_exclusions` deletes none), so a report of it with a stale vote shape stops online, backfill and offline runs with `ERROR [cached input]`, and the printed fix (re-fetch with `--document-number`, or a backfill re-run) acquires nothing for a listed sitting. Pass the exclusions into the load, or skip listed sittings before `require_vote_shape`.

**Why:** Found by the plan review of the refusal-message batch (2026-11-04). Latent: it needs a stale vote shape in the report of a listed sitting, and moving that report out of `data/` is a working manual fix.

**Effort:** S
**Priority:** P3
**Depends on:** None

### TODO round 2026-11: deferred review findings

**What:** Non-correctness findings from building and reviewing `fix/todo-round-2026-11` (2026-11-05):
1. **A stop between the store swap and the exclusion record.** The record is now written after `rebuild_database_from_entries`. A killed process, or an OSError from `write_text_atomic` (a traceback, now after the swap), leaves a store without the freshly excluded sitting and a record that does not list it. A plain `--offline` then refuses with "cached report(s) are not in the store". The state is safe and the refusal names a fix, but that fix re-stores the sitting; re-running the exclusion is the right one. Say so, or write the record before the swap and roll it back on failure. An `--include-document-number` run stopped at that point is the mirror case: the record still lists a sitting the store now holds, the refusal's `--offline --repersist` drops it again, and "edited by hand" (`store_coverage_gap`, README's error table) doesn't describe it.
2. **`--include-document-number` with an unknown number, or one not on the record, is still a silent no-op.** The exclude side now refuses an unknown number.
3. **`resolve_data_base_url` refuses Unicode format characters (category Cf),** including the zero-width non-joiner some IDN host names use. Punycode works. Owner-supplied input.
4. **Test hygiene.** `test_malformed_operator_files`' "nested too deeply" fixture shrank to 50,000 bytes because the 64 KiB cap now fires first, and nothing asserts the order of the two refusals. The hash-seed test in `tests/test_seat_counts.py` shows one outcome across seeds but does not pin the sort key itself.
5. **`log_seat_crosscheck` removing a stale report now creates or chmods the private directory,** through `ensure_private_dir`. A build has normally made it, but a plain `--offline` render of a copied store without seat tables doesn't hold the writer lock: it reproducibly created `.site.private` beside the output and changed an existing one from 0775 to 0700 (review, 2026-11-05). For a removal, skip the call and unlink only if the directory exists. A `refresh` blocked by a bad private directory leaves the cache in use until the writer lock refuses the same directory later in the build; the warning could say so.
6. **`tests/run_bills_browser_check.mjs`.** Only the DevTools wait got the 60 s budget; the steps after it keep 10 s. Chrome runs with `stdio: 'ignore'`, so the early-exit error gives the code but not the reason. 60 s is a judgement, not a measurement.
7. **`vote_documents.rank` follows text order** (20/10000 before 20/9999), and the votes archive prints that order. Use `stable_ids.document_sort_key` if the archive should read numerically; that moves the rank column, so it needs an old/new report.
8. **`docs/plans/a4-slice1-oracle/t11_measure.py` M2 keys its `documents` lookup on the number alone,** so a number both chambers use overwrites itself. That produced the false "BT 19/19" finding. Key it on `(herausgeber, document_number)` if the oracle runs again.
9. **`refresh` checks a download against the seat rules, but not the cached file.** A cached zip that parses and breaks a rule gets a 304 and prints "unchanged", then every rebuild stops until someone deletes the file. The real file passes (2,914 / 171 rows), so this needs a future file or a future rule. Offer no ETag for a cached file that fails `seat_rows`.
10. **A new refusal outranks a stretch the old code absorbed.** Memberships A (P, x to y), Z (P, y to y) and C (Q, from y) used to load and now refuse the whole file. It's the documented intent, and the real file has no such row; whether the shape can occur is unknown.
11. **`--data-issues-url` echoes its value when refused,** so a URL with credentials reaches the log. Same class as the `--data-base-url` leak fixed in this review, but it predates the round.
12. **`erste_drucksache` and r5's method text say "verknüpfte Sitzungen";** the SQL counts only those with a Rede, as the `sitzungen` column says. 0 of 7,925 rows differ on the replay store.
13. **Tests and small things.** `run_exclusion_main` mocks the rebuild and the coverage check, so the new record order never meets a real rebuild. `--operator-file <(…)` now refuses as a FIFO, which is documented, though a sentence should say a scheduled build must write the secret to a file. `causes =", ".join` lacks a space. `seat_rows` repeats its seen-key loop, and the data options and licence file are resolved twice per run.

**Why:** Deferred under the CLAUDE.md fix-now-or-defer rule: none is a wrong figure or a false statement today.

**Effort:** S each
**Priority:** P3
**Depends on:** None

## Protokoll-Dossier

### Split or filter overview.html by Wahlperiode

**What:** Split or filter `overview.html` by Wahlperiode instead of one page with every card.

**Why:** A3 (v1 coverage) takes the page from about 290 to about 800 cards (A3 review D8, 2026-10-19). Page weight after A3: measured in the A3 Phase 4 check.

**Context:** `render_overview` (`scripts/build_dip_pulse_site.py:8748`) renders one card per generated dossier.

**Effort:** S
**Priority:** P3
**Depends on:** A3 (v1 coverage)

### Say when a count covers only Sitzungen mit Dossier

**Part 1 completed:** v0.23.4.0 (2026-10-29). Public copy says "Dossier": the Methodik's "Erzeugtes JSON" bullet ("Jedes Dossier verlinkt …", was "Sitzungsseite"), the overview heading "Erzeugte Dossiers" (was "Sitzungsdossiers"), and the internal component label "Dossiers" (was "Protokoll-Dossiers"). A test keeps the avoided names off both pages.

**What is left:** wherever a published count spans a range for which the catalog lists more Sitzungen than have a Dossier, say so, e.g. "in 60 von 94 Sitzungen (nur Sitzungen mit Dossier)". Audit on main at v0.23.1.0 (2026-10-29):
- Already disclosed: the Daten Datenstand ("N von M Protokollen im Katalog als Dossier erfasst", `render_daten_datenstand`), the votes archive footer ("… der Sitzungen in der Datenbank dieses Builds, also nur Sitzungen mit Dossier", A4 slice 1), and the catalog's "Erzeugte Dossiers" tile and its "Nur mit Dossier" filter.
- Not disclosed: the Abgeordnete list's "Reden" column (`render_abgeordnete_index`), the puls.html header and Wochenvergleich, the Fakten pages and Methodik, and the speech counts on the Gesetzesvorhaben pages.

**Why:** CONTEXT.md "Sitzung mit Dossier": every count covers only Sitzungen mit Dossier, because the store is rebuilt only from Dossier entries (`rebuild_database_from_entries`). A build with `--detail-limit` silently reports a subset as if it were the whole Wahlperiode.

**Context:** Wait for `worktree-a3-plan` to merge: it rewrites `render_abgeordnete_index`, extends `coverage_line` in `render_daten_datenstand`, and adds Fakten coverage text (`facts.coverage_label`, `fill_caveat`). Reuse those rather than adding a second coverage phrase.

**Effort:** S–M
**Priority:** P3
**Depends on:** `worktree-a3-plan` merged

## Puls

The week radar shipped in 0.3.0.0 (#58, 2026-09-18), so the remaining items are no longer blocked by it. The weekday comparison is completed below.

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

### Puls outward (batch 7): deferred review findings

**What:** The /gstack-review of `fix/todo-batch-7-puls-outward` and the v0.28.0.0 /ship (2026-11-01) left these:
1. Verify `data/sitzungskalender.json` against the first real bundestag.de fetch. The fixtures are hand-written. The parser accepts only `DTSTART;VALUE=DATE`, an exclusive `DTEND` and "Sitzungswoche" in SUMMARY, so a datetime or TZID start rejects the whole file and the old cache stays. Expect about 22 weeks for 2026, Monday to Friday, and no `warning: [sitzungskalender]` line. Record the real event shape in the module docstring. With it, decide: a SUMMARY like "Keine Sitzungswoche" or `STATUS:CANCELLED` still counts as planned; the same week listed twice (or split into two events) is counted twice in the gap sentence and in `MIN_WEEKS_PER_YEAR`, so collapse weeks per ISO week; a parse with 10–15 weeks silently replaces a cached 22-week year, so refuse one that loses cached future weeks; a week spanning New Year rejects its whole year; two files for one year do not merge.
2. A failed calendar fetch never advances `fetched_at`, so while bundestag.de is down or blocking, every online persisting build retries, at up to about 15 minutes each (5 fetches, 60 s timeout, 2 retries). Record the last attempt and add a total time budget. A `fetched_at` in the future (clock jump) makes the cache never due; treat a negative age as due.
3. `week_radar_feed._cut` and `render_rss` keep XML-1.0-illegal control characters such as `\x01`, which make the RSS ill-formed. Strip `[\x00-\x08\x0b\x0c\x0e-\x1f]`. `valid_site_url` also accepts a URL with a user name and password before the host, and a netloc with spaces, which would then be published in the feed; reject both, as `publication_state.validate_external_url` does.
4. An RSS item is published (fixed GUID, fixed pubDate) for any finished week, even when DIP's Plenarprotokoll lag or an incomplete backfill leaves the week with only some sittings; feed readers never re-fetch an item under an unchanged GUID. Hold the item until the week is complete, or add a completeness field. Decide before `BUNDESTAG_PULSE_SITE_URL` is set for a public site.
5. The gap sentence ("… sind hier noch nicht ausgewertet") is false on a pinned `--week`/`--today` build whose archive does hold later weeks; count only planned weeks with no sitting in the archive, or drop the clause when the week is pinned.
6. Smaller: the calendar index page and `.ics` files are read without a size cap, and the index goes through stdlib `html.parser` (quadratic on hostile markup before the 2025 patch releases); `urlopen` follows a redirect from bundestag.de to any host, and the host check ignores the port; the cache and feed temp files are a fixed name in the published `data/` and `feeds/`, with no lock; `refresh_if_due` and `render_site` both load a damaged cache, so it warns twice; `CHANNEL_TITLE` repeats the puls.html `<title>` literal (its comment says it is the one place to change); the feed calls `render_dip_pulse_html._entry_protocol` (private); `_is_due` uses bare literals for October and the daily retry; `build_payload(weeks_back=)` and `refresh_if_due(max_age_days=)` are parameters no caller sets; the RSS range parses `datum` without `[:10]` where week grouping uses it.

**Why:** (1) is the one unverified input format. The rest fail soft, need an operator mistake, or have no current input (RSS is written only with `BUNDESTAG_PULSE_SITE_URL`, which nothing sets yet).

**Effort:** M
**Priority:** P2 ((1) on the first online build, (4) before a public feed)
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

### Link `mdb_zugehoerigkeiten` to the MP pages

**What:** `mdb_zugehoerigkeiten.mdb_id` is the same number as the protocol XML Redner-ID (`mps.xml_redner_id`; checked on Dobrindt 11003516 and Kraft 11004792). Join the two through the person registry. Each Personenseite then shows its Mandat dates and its Zugehörigkeit history per Wahlperiode, and R1/R3 can take the Fraktion of a Rede's or Stimme's date instead of the representative record's.

Done when:
- a Personenseite lists its Mandate and Zugehörigkeiten from the store;
- the join's unmatched ids are counted in the build log.

**Why:** Left out of C1 by design: the seat counts need no person link.

**Context:**
- **Redner-ID collision:** one Redner-ID can name two people (Completed, "The Bundestag XML gives one Redner-ID to two people (11005304)"). Guard that case.
- **Government MdBs:** government MdBs without a roster row have Stammdaten rows, which ties in with "List MdBs in a government office as Abgeordnete".

**Effort:** M
**Priority:** P3
**Depends on:** None

### The carried-forward registry diverges from a fresh build after A3

**What:** The A3 Phase 4 gate failed `replayed_store_groups_like_fresh` on a clone of `~/agent-runs/a3/full` (4,168 vs. 4,165 groups on the fresh store's bindings). Details are in [the Phase 4 record](docs/plans/a3-phase4.md), Step 1. There are two parts:
1. **Köstering/Krampe split.** One person, Jan Krampe (formerly Köstering, Die Linke, WP 21), is a single person with 121 bindings in a fresh build. In the replayed store he is four persons: `dip:8257`, `aw:178656`, and the profiles `koestering_jan-1045564` and `krampe_jan-1045564`. `baseline` had `aw:178656` and the Köstering profile as one person. So A3 newly separates his speeches from his votes, and a replay does not heal it. `full` shows the same split. The cause is not the URL rule. DIP holds two person records for him (8054 Köstering, 8257 Krampe), and the store keeps `dip:8054` as a roster record. An in-memory `match_rows` on `full` joins all five records once `dip:8054` is stale. Why a replay still matches it is untraced. It is part 2's defect.
2. **Orphan persons.** 295 persons hold only retired bindings. Each holds one `roster-v1-…` binding of a `dip:` record that the roster no longer produces: 295 of the 307 retired roster bindings. The other 12, and the 187 retired contribution bindings of speech rule v6, sit on persons that also hold live bindings. 282 of the orphans render an Abgeordnete page and are listed on the index. They raise the store's person count from 4,165 (fresh) to 4,463.

**Re-measured at the branch tip, 2026-10-31** (the "Gate at the branch tip" section of the [Phase 4 record](docs/plans/a3-phase4.md); rule C plus 0f59729 and a508cfa):
- **Part 1 is healed.** The replayed store groups like the fresh one: 1,942 = 1,942 persons on live bindings, the same fingerprint. Krampe is one live person.
- **Part 2 is open:**
  - 302 persons hold only retired bindings, and 289 of them render a page with no Reden and no votes.
  - The index links only 8 of them, down from 282.
  - 281 of the 302 are Bundesrat members. So the fix likely goes with "Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs".

**Re-measured on the merged tree, 2026-11-01** (09b7c5d, A3 plus main v0.26.0.0; complete gate, `all_passed`; "Gate on the merged tree" in the [Phase 4 record](docs/plans/a3-phase4.md)): unchanged.
- Replayed 1,942 = fresh 1,942 on live bindings, the same fingerprint.
- The replayed store has 2,244 persons.
- 302 persons are retired-only, 289 of them with a page, 8 of those linked from the index.
- 494 retired bindings (307 roster / 187 contribution).

Decide whether retired-only persons render a page. Report persons and pages old/new.

**Owner decision, 2026-11-01:** A3 ships with part 2 open. It is fixed after the merge, likely together with "Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs".

**Why:** 289 pages for persons with no live occurrence, reachable by URL.

**Effort:** M
**Priority:** P1
**Depends on:** None

### Group MP pages by Wahlperiode and write abgeordnete.json without indent

**What:** Group or page the speech and vote rows on each MP page by Wahlperiode, and write `data/abgeordnete.json` without `indent=2`.

**Why:** After A3 a long-serving MdB shows up to twelve years of Reden and roll-call votes in one list, and the JSON grows with them (A3 review D9, 2026-10-19). Sizes after A3: measured in the A3 Phase 4 check.

**Context:** MP detail page `scripts/build_dip_pulse_site.py:7652-7740`; JSON dump `:7833`.

**Effort:** M
**Priority:** P3
**Depends on:** A3 (v1 coverage)

### Store DIP `person_roles` so a Rede without a Zusammenschluss uses the Zugehörigkeit of its Wahlperiode

**What:** ADR 0001 says a Rede whose Plenarprotokoll names no Zusammenschluss counts for the speaker's Zugehörigkeit on the date of the Sitzung. The store keeps no membership history: `mps.person_roles_json` is DIP's `funktion` list, and `compact_person` drops DIP's `person_roles` (fraktion and Wahlperiode per role). The Rede therefore counts for the speaker's party as the store holds it. Keep `person_roles`, and let `derive` pick the role of the Rede's Wahlperiode.

**Update 2026-11-01:** `mdb_zugehoerigkeiten` (C1) holds the Zugehörigkeit per day, keyed by the Redner-ID number. With "Link `mdb_zugehoerigkeiten` to the MP pages", the Rede's date can pick it directly, and DIP's `person_roles` are no longer needed for this.

**Why:** Measured 2026-09-29: only 1 Rede (20/109 ID2010905000) has neither a Zusammenschluss nor a Sprechrolle, so the approximation costs almost nothing today; `compare_store_values.py` reports the count so it stays visible.

**Effort:** S
**Priority:** P3
**Depends on:** None

### List MdBs in a government office as Abgeordnete

**What:** DIP's `funktion` holds only a person's current office, so 48 WP 21 MdBs whose office is Parl. Staatssekretär (27), Bundesminister (8), Staatsminister (7), Vizepräsident(in) (4) or another government one are not in the roster: the Abgeordnete list has 589 of about 630. Their Mandat shows in DIP only as a `person_roles` entry with a `fraktion` for the Wahlperiode, and not even that for some (Merz, Dobrindt, Dorothee Bär, Wadephul: roles end at WP 20 on 2026-10-30), so DIP alone cannot list all of them; the Bundestag's MdB-Stammdaten (MDB_STAMMDATEN XML, with MDBWP_VON/BIS) can, and would also give Mandat end dates.

**Why:** They are MdBs (CONTEXT.md) and the list says it is complete.

**Update 2026-11-01:** the MdB-Stammdaten are now in the store (C1). `mdb_zugehoerigkeiten` has a row for every Mandat from WP 18 on, these 48 included, with Mandat dates. The roster rule can take membership from there instead of DIP's `person_roles`; the registry join for party-less Sprechrolle records is still needed.

**Context:** Tried 2026-10-30 with the `person_roles` rule (637 listed) and backed out: the registry's name guesses match on (name, party), and a Rede given as a member of the Bundesregierung has no party, so 29 of the 48 split into an Abgeordnete row without Reden and a separate Redner page with them (5 such splits before). Needs, first, a registry rule that joins a party-less Sprechrolle record to a roster record of the same name (`person_registry.match_rows`, A.2 territory: guard namesakes), then the roster rule (`derive.is_mdb_funktion` plus the Fraktion role, display name = the name segment of DIP's `titel`, Fraktion from the role when the top-level field is empty).

**Effort:** M
**Priority:** P2
**Depends on:** None

### Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs

**What:** Before 2026-10-30 the roster ingest flagged every DIP person whose `funktion` contained "MdB" as an MdB, which matched "MdBR" and "Stellv. MdBR" (151 Bundesrat members for WP 21). `person_registry.bind` records that as sticky `ever_mdb` evidence (`person_registry.py`, `evidence["ever_mdb"]`, `was_mdb`), so the registry still treats them as former roster persons: they stay page-eligible and `is_stale_roster_partner` can apply to them. Decide whether `ever_mdb` is re-derived from the exact rule (`derive.is_mdb_funktion`) or reset once for records whose only roster evidence is a Bundesrat funktion.

**Why:** No page now calls them Abgeordnete (the Personenseite derives "Mitglied des Bundestages laut Plenarprotokoll" from Reden, not from `ever_mdb`), but the evidence says something false about 151 people and feeds identity decisions.

**Context:** A.2 registry territory: needs a registry reviewer. Measure first how many person records carry `ever_mdb` with only Bundesrat funktion evidence on the reference store.

**Measured on the A3 merged-tree gate store, 2026-11-01:**
- `mps` rows with `is_mdb = 1`: 1,360. The 352 Bundesrat roster rows dropped on repersist.
- The registry still holds 302 retired-only persons. 281 of them are Bundesrat members ("MdBR" in the display name), and 289 of the 302 render a page with no Reden and no votes. Only 8 are linked from the index.
- These are the persons this evidence most likely keeps page-eligible. See "The carried-forward registry diverges from a fresh build after A3".

**Effort:** S
**Priority:** P3
**Depends on:** None

### Apply the voter-link patch after refetching the WP 18/19 roll-call lists

**What:** `docs/plans/a3-voter-profile-links.patch` (`derive.person_profile_url` plus tests) accepts bundestag.de's WP 19 archive biographies and `/redirect/<n>` links as voter profile links, so pass 3 can key WP 18/19 voters by member number. It changes nothing on the A3 store until the roll-call lists are fetched again: `full`'s reports were written after #107 dropped the WP 18/19 links. Steps:
1. Refetch about 306 roll-call lists from bundestag.de (WP 18 127, WP 19 179).
2. Apply the patch.
3. Repersist and report persons old/new.

**Why:**
- WP 18/19 voter pages would link to the archived biography.
- WP 18 title variants would become one voter record.
- A partial refetch makes things worse. A hybrid measurement with only 5 linked reports split 16 persons and joined 2 (1,942 → 1,956), because it mixes `/redirect/N` keys with name+party keys. So refetch all 306 lists or none.

**Context:** "The voter-link patch (not applied)" in [the Phase 4 record](docs/plans/a3-phase4.md). Owner decision 2026-11-01: deferred, not part of the A3 merge.

**Effort:** M (mostly fetch time)
**Priority:** P3
**Depends on:** A3 merged

## Design

### DESIGN.md, tokens and a typeface decision via /design-consultation

**What:** Write a DESIGN.md (tokens, type scale, spacing, component vocabulary, focus/visited/selection rules) and decide the site's typeface. Name once the tokens individual pages had to invent, including the Daten page's light `--surface-2`/`--surface-3`.

**Why:** Every page carries its own `:root` token block and the only typeface is Inter / ui-sans-serif / system-ui; every design review re-derives the tokens and flags the default font stack. The Daten page (after the dossier) was the second page to have to invent tokens a shared system would already provide. No `DESIGN.md` exists as of 2026-09-19 (`docs/design/bundestag-pulse-design.md` is the product design doc, not a design system).

**Context:** The week-radar plan writes the radar's tokens into the plan instead. Start with `/gstack-design-consultation`; migrate per-page `:root` blocks to the shared header styles afterwards (the `:visited`/`:focus-visible` item under Daten is the first slice of that migration). Merged from two earlier entries (Daten and Design sections). The puls.html design review of 2026-09-28 also flagged its nested cards (section > panel > tile) for the same pass.

**Raised to P2 (owner decision, 2026-11-02):** this is step 1 of "Decide the frontend stack" below. Do it as plain CSS with one shared stylesheet, in the current Python renderer.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Decide the frontend stack

**What:** Decide whether the site stays Python-generated HTML (PRODUCT.md:58) or moves to a static site generator with islands (Astro-class), under the rule "the frontend computes no figure". A single-page app and a hybrid were rejected. The owner chose "Hold, prototype first" (R17). The order:
1. "DESIGN.md, tokens and a typeface decision via /design-consultation" above, as plain CSS with one shared stylesheet.
2. A chart prototype in a candidate generator, most likely the Diskursanalyse throwaway.
3. A written go/no-go against the stdlib option (SVG charts drawn from Python). Write the criteria down before the prototype.

If the answer is go:
- Resolve outside-voice findings O4–O11 first.
- Write ADR 0005 before building.

**Why:**
- The look is a design problem, and either stack has to solve it.
- The case for a generator rests on interactive long-term charts, and only a chart prototype can show whether that case holds.
- The pilot the eng review planned (the votes archive) tested neither goal: it had no chart and left design out of scope.

**Context:**
- The eng review of 2026-11-02 settled ledger entries R10–R16 and a scope record for the frontend plan: pilot votes archive, parallel build, state codes, payload-diff oracle, strict npm policy, raw-HTML ban, 50 KB island budget. They were meant to go into `docs/plans/a4-site-from-release.md`, but that text never reached main. Redo it from the review if the answer is go.
- PRODUCT.md:58 stays in force until the decision.

**Effort:** M (design pass and prototype); L if the answer is go
**Priority:** P2
**Depends on:** "DESIGN.md, tokens and a typeface decision via /design-consultation"

## Publication

### Site hosting plan for the 2.5 GB generated site

**What:** Make the HTML deployable under a capped static host (e.g. GitHub Pages' 1 GB limit). Measured 2026-09-19: 2.5 GB total; `data/` 1.4 GB (`plenarprotokoll-*.json` 607 MB, `bills.json` 386 MB, `exports/` 91 MB); `protocols/` 584 MB for 285 dossiers. **Without `data/` the site is still 1.11 GB**, so a deploy profile that only excludes `data/` does not fit; the dossiers have to shrink too. Pieces: (a) extend `--data-base-url`-style externalisation to the `data/plenarprotokoll-*.json` links on `puls.html`/dossiers and to `bills.json` (the base-URL pattern exists for the two export files); (b) shrink dossiers — see "Move the hidden dev-view API dump" below: ~952 KB of hidden markup per dossier × 285 ≈ 270 MB, so rendering it into a separate on-demand file roughly halves `protocols/`; (c) or pick a host without the cap.

**Measured after A3 (2026-10-29, `~/agent-runs/a3/full`, 716 Sitzungen):**
- 5.4 GB total; `data/` 4.1 GB (store 848 MB, XML 578 MB, `exports/` 426 MB).
- **Without `data/` the site is 1.35 GB** in 6,750 HTML files: `bills/` 664 MB, `protocols/` 519 MB, `abgeordnete/` 139 MB.
- Before A3 (`baseline`, 290 Sitzungen): 2.3 GB total and 616 MB without `data/`.
- The rendered pages have more than doubled, and the cap problem is now about the pages, not only `data/`.

**Why:** The Daten page and `--data-base-url` make the *data* shippable to a public audience; the *site* itself cannot go to a capped host today. Both outside voices in the `/autoplan` review flagged this; the user's go/no-go framing ("ship to a larger audience in a few weeks") depends on the site being public, not only the download.

**Deploy gate (eng review of `docs/plans/impressum-datenschutz-licence.md`, D6, 2026-11-01):** the deploy step this item adds must refuse to publish while any generated page carries `data-operator-missing`, and must name the missing fields. That marker means the Impressum or Datenschutz page still shows "Angabe folgt." where the operator's address, e-mail, host or supervisory authority belongs (§ 18 MStV).

**Effort:** L
**Priority:** P1
**Depends on:** None (absorbs the former "base URL for report JSON" item)

### Scheduled data-release workflow

**What:** A GitHub Actions workflow on a schedule: online build → export → immutable dated release tag → upload assets → `--offline` rebuild with the release's `--data-base-url` → deploy.

**Why:** The design doc's own constraint is "must stay current automatically"; a manual `scripts/publish_dip_pulse_data.sh` is upkeep a solo maintainer will eventually miss. The user's explicit decision at the Final Gate keeps PR2 manual for now; this is the follow-up once that has been exercised a few times.

**Effort:** M
**Priority:** P2
**Depends on:** **Blocked** — the release script exists since v0.26.0.0 (dry run by default; since 2026-11-01 every export carries `LICENSE-DATA.md` and the item-10 P1 findings of "Release pipeline: deferred /ship review findings" are fixed, so `--publish` is reachable), but no release has been made and `.github/workflows/` holds only `ci.yml` (2026-10-31); a `GITHUB_TOKEN` with release-upload scope as a repo secret.

### Add atomic/versioned publication promotion

**What:** Build a complete static publication in a staging directory, validate it, and atomically promote the validated version with a documented rollback path.

**Why:** The current in-place writer can leave a partial output tree after a late failure. The fixed-public release makes this safe by treating output as disposable and deployable only after exit 0 plus validation, but atomic promotion would prevent readers or deployment tooling from observing a mixed version at all.

**Context:** Start from `scripts/build_dip_pulse_site.py`, which writes many HTML/JSON files directly while SQLite alone uses temporary replacement. Design this together with the real deployment target: staging location, same-filesystem rename requirements, retained versions, cleanup, concurrent-build locking, and rollback semantics. Trigger this work when a deployment pipeline is added, the output directory is served while builds run, or concurrent writers become possible.

**Effort:** L
**Priority:** P3
**Depends on:** A concrete deployment/serving lifecycle

## Community

### Contribution governance: the half that needs the domain

**What:** The parts of ADR 0003 D5 that need no domain shipped in v0.28.0.0 (2026-11-01): `SECURITY.md`, `CODE_OF_CONDUCT.md` (linked from `CONTRIBUTING.md`), the „Datenfehler" and „Fehler auf der Seite" issue forms with triage labels, `config.yml` with `blank_issues_enabled: false` and a security contact link, and the documented `issues_url` that pre-fills the page in the Datenfehler form. Left:
- Switch on GitHub private vulnerability reporting when the repository goes public (SECURITY.md already points to it and says it is not public yet).
- `/.well-known/security.txt` on the site.
- A `config.yml` contact link to the Impressum e-mail for private matters (GDPR, corrections from the people concerned, press).

Done when `security.txt` is served by the preview and the private-matters contact link is in the chooser.

**Why:** Private requests need a non-public channel; vulnerability reports need the GitHub channel SECURITY.md names.

**Context:** Decided 2026-09-29 ([ADR 0003](docs/adr/0003-licences-and-impressum.md), D5, amended 2026-11-01). `security.txt` and the contact link need the final domain and the dedicated e-mail address, both also needed by the Impressum item.

**Effort:** S
**Priority:** P3
**Depends on:** Domain and contact address (Impressum item)

### Contribution governance (batch 8): deferred review findings

**What:** The /gstack-review of `fix/todo-batch-8-governance` (2026-11-01) found three things. (1) The page shows the release notation `Release 2026.10.31`, but the Datenfehler `datenstand` placeholder is `data-2026.10.31`, the tag name. SECURITY.md's `data-<YYYY.MM.DD>` also omits the `.N` same-day suffix. Pick one notation. (2) `tests/test_issue_forms.py` checks only ids, labels, quoting and URL drift. Negative controls passed with these breaks: a missing field `label`, `type: textfield`, `body:` renamed, a label typo, broken `config.yml` indentation, a duplicate field label, and a plain scalar ending in `:` (which Psych rejects). Add dependency-free checks for each. (3) `ID_LINE = re.compile(r"^\s*id:\s*(\S+)\s*$", re.MULTILINE)` also matches an `id:` line inside a markdown block. Scope it to field indentation. (4) From the v0.28.0.0 /ship red team: the Daten footer link always reads „Datenfehler melden (GitHub)", but `--data-issues-url` also accepts `mailto:` and a site-relative path; show „(GitHub)" only for a github.com URL, or accept only the form URL.

**Why:** These are wording and test hygiene. Real schema validity stays an owner check on GitHub (below).

**Effort:** S
**Priority:** P4
**Depends on:** None

### Owner checks after the v0.28.0.0 merge

**What:** Checks that need main or the real store, accepted as pending at the v0.28.0.0 /ship (2026-11-01):
1. GitHub (needs main): the chooser at `/issues/new/choose` lists Datenfehler first, then „Fehler auf der Seite", plus the security link, and blank issues are off; both forms render with no template error; SECURITY.md shows on the Security tab; a Daten page built with the documented `--data-issues-url` opens the Datenfehler form with `seite` filled and the labels applied (repository private: owner only). The three labels exist (checked with `gh label list`).
2. Real store (with A3's owed rebuild): batch 5's replay on main vs. the branch (equal `_content_digests`, mode, gid and lock path, no staged leftovers; with `--force-export` identical file hashes except table CSV modes 0600→0644); batch 6's panel hashes on `a3/full` and `b4-local` (expect 0 of 556 and 0 of 217 to change); batch 7's `--offline` build before and after with the same `--today` (differences only in `feeds/`, the cache file and the puls.html line plus script), and one online persisting build logging a single `[sitzungskalender]` line with about 22 weeks for 2026.
3. A look at the ▸/▾ vote-context toggles in Safari and VoiceOver.

**Why:** The v0.28.0.0 /ship could run only the demo build (puls.html byte-identical to main without the cache), the abstract replay (0 of 8,737 change) and the browser checks (25/25); every batch measurement predates A3.

**Effort:** S
**Priority:** P2
**Depends on:** v0.28.0.0 merged; A3's post-merge store rebuild

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

### Debattenberichte: off-agenda topic mentions across a sitting week

**What:** A detector over speech text that, for a configurable term list, counts mentions per speaker, Fraktion and TOP, and emits a Debattenbericht row when a topic clears the threshold (≥10 speakers from ≥3 Fraktionen across ≥2 TOPs) while being on no TOP title; the report shows total / verified / unverified mention counts, first quote per speaker (max three per Fraktion, sorted by page) and the search terms used. Done when a fixture week with a planted off-agenda term produces exactly one report and a week without produces none ("a missing report is also a data point").

**Why:** Nothing counts topic mentions outside their TOP today (audit 2026-09-19). It is plenarwatch's distinctive post type, but a small share of their output (the Sachsen-Anhalt-Wahl report is the headline case), so it comes after the vote and Fraktion work above.

**Context:** Term list is data, not code (`data/debate-terms.json`); verification = the quote passes the verbatim validator. Reuse the Fraktionsblöcke quote-selection rule. Consider it a week-radar row type on `puls.html` rather than a new page.

**Effort:** L
**Priority:** P4
**Depends on:** Fraktionsblöcke, Deterministic validators

## Recht und Lizenz

### Impressum, Datenschutz and licence files before the site goes public

**Done in v0.30.0.0 (#129)** ([ADR 0003](docs/adr/0003-licences-and-impressum.md), plan `docs/plans/impressum-datenschutz-licence.md`):
- `LICENSE` (MIT).
- The root `LICENSE-DATA.md`, the one licence source, shipped in every export. Its short string is the default `--data-license`.
- `impressum.html` and `datenschutz.html`, rendered from `--operator-file`.
- "Impressum · Datenschutz" in every footer.
- The four-layer licence table on `sources.html#lizenz`.
- A test that pins the AI label.

**What is left (owner inputs):**
- The postal address, after question 1 to the lawyer.
- The dedicated Impressum e-mail address (D5: not a personal address).
- The host and its log retention, after the hosting decision.
- The supervisory authority: the Landesdatenschutzbehörde of the operator's Land.

Until then both pages render these values as `data-operator-missing` placeholders. Also open for the lawyer: § 25 TDDDG on the two localStorage entries (ADR 0003, question 8).

Done when no generated page carries `data-operator-missing`. The deploy gate in "Site hosting plan for the 2.5 GB generated site" refuses to publish until then.

**Why:** Name and address are required for any non-private Telemedium (§ 18 Abs. 1 MStV). The DIP terms require naming the source and marking changes on redistribution. Hosting can't ship without either.

**Context:**
- Decisions are made (ADR 0003).
- Before launch, the ADR's open questions go to a lawyer, first of all whether a c/o address is enough under § 18 MStV. That answer decides which address goes in `impressum.html`.
- Re-check § 5 DDG and DIP no. 4d if donations are added.
- Blocks the hosting item, not the other way round.

**Effort:** S (fill in the operator file once the inputs exist)
**Priority:** P2
**Depends on:** Lawyer answer on the address (ADR 0003, question 1)

### Settle the roll-call source for redistribution

**What:**
- Check whether the Plenarprotokoll's „Endgültiges Ergebnis" also lists non-voters, or only Ja/Nein/Enthalten. **Answered 2026-10-31:** 0 of the 232 „Endgültiges Ergebnis" blocks in the cached WP 20/21 protocol XML list non-voters, so only the XLSX roll-call lists carry them.
- Ask parlamentsdokumentation@bundestag.de whether the roll-call XLSX lists may be redistributed.
- If the answer is no, or only the XLSX carries the non-voters, source per-member votes from the protocol XML or from abgeordnetenwatch (CC0) instead.

**Why:** bundestag.de's default terms are private use only. The Open Data page calls the XLSX lists open data but names no licence (ADR 0003, open question 5).

**Effort:** S (check and e-mail); M if the source must change
**Priority:** P2
**Depends on:** None

### Settle the MdB-Stammdaten redistribution terms (`bundestag-stammdaten` layer)

**What:** The seat tables (`mdb_zugehoerigkeiten`, `party_seats`, `mdb_stammdaten_stand`) carry the licence layer `bundestag-stammdaten` (C1, D7). The Open Data page gives "© Deutscher Bundestag" and says the data "können zur maschinellen Weiterverarbeitung genutzt werden", with no licence. Then:
- ask, together with the roll-call question, whether the derived Zugehörigkeit rows (id, name, dates, group) may be redistributed;
- write the layer's terms into `LICENSE-DATA.md` (which `DATA.md` quotes; it says only that they are open), its attribution short string and ADR 0003, neither of which names the MdB-Stammdaten yet.

Also: DATA.md's sources paragraph (`_codebook_sources_and_citation`) names the open redistribution question for the roll-call data only; name the MdB-Stammdaten there too until the terms are settled (ship adversarial pass 3).

Done when the layer has written terms and DATA.md's attribution names the file.

**Why:** It is a release blocker under track D, not an implementation blocker. The zip itself stays in the private directory, never in OUTPUT (D9).

**Effort:** S
**Priority:** P2
**Depends on:** Settle the roll-call source for redistribution (same e-mail)

### Impressum/licence build: deferred polish (2026-11-01)

**What:** Non-correctness findings from building `docs/plans/impressum-datenschutz-licence.md`: (1) the Datenschutz drift test reads localStorage keys only from `page_head()`/`page_scripts()`; a key written by a page-specific inline script (dossier runtime, Fakt pages) would slip past, so scan the built HTML for `localStorage`/`sessionStorage`/`document.cookie` instead. (2) In the placeholder state the legal pages show doubled punctuation („Angabe folgt.., Anschrift wie oben“); gone once the operator file is complete. (3) On `sources.html#lizenz` the row labels of the licence table inherit the page's uppercase table-header style. (4) The D5 footer comparison covers the 16 pages the demo builds; Abgeordnete detail, Fakt week/month and bill detail footers are checked only by the reference-store footer walk, not by a unit test.

**Why:** Deferred under the CLAUDE.md fix-now-or-defer rule: none changes what a page says today.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Impressum/licence branch: deferred /gstack-review findings (2026-11-01)

**What:** Non-correctness findings from the pre-landing review of `claude/pre-public-items-plan-e8d01d` (specialists, Claude adversarial, red team; Codex found nothing):
1. `test_the_legal_span_is_the_only_footer_change` (`tests/test_demo_site.py`) compares two renders of the same tree, one with `render_legal_links` patched to "". A footer sentence or link lost while editing would be missing from both, so the test cannot catch the regression D5 asked for. Compare against a golden of the pre-change footers (or main's build), or drop the second build and keep the database-unavailable assertions.
2. `previous_manifest_problem` (`scripts/publish_dip_pulse_data.py`): the `protocols`/`votes` shape and `total_rows` branches (bool included) have no test rows, and the docstring says it checks "the fields release_changes reads" although `release_changes` tolerates their absence and reads `tag`, which is not checked.
3. The release gate ties `LICENSE-DATA.md` to the commit but not `manifest["license"]` to its short string: a leftover `$BUNDESTAG_PULSE_DATA_LICENSE` publishes a different string in `datenstand.json`, the Daten page and the DATA.md header. Since `default_license_text()` fills an empty value, the "export carries no licence string" refusal is unreachable from exports this repo writes. Compare against the short string of the commit's blob instead.
4. ~~`--operator-file ""` or an empty `$BUNDESTAG_PULSE_OPERATOR_FILE` (an unset CI secret) is read as "not set" and builds placeholder pages with exit 0; the operator file is also resolved before `--fetch-xml`, so a stale variable blocks runs that render nothing.~~ **Done 2026-11-05:** an empty or blank value is an error (owner decision), and the operator is resolved after the early-exit modes and `--fetch-xml`.
5. The operator e-mail regex accepts `?`, `&`, `%` and `=` in the local part, so `mailto:` can carry header parameters; operator URLs accept whitespace. Owner-controlled input, wrong link at worst.
6. Nothing keeps the operator file out of git: no `.gitignore` entry for a conventional name, and `resolve_operator` accepts a path inside the work tree.
7. `sources.html#lizenz` states the roll-call layer without the caveat DATA.md and `docs/data-methods.md` carry (redistribution of the named votes is still open, ADR 0003). The four layers are authored in `render_sources_page` beside `LICENSE-DATA.md` with no drift test; „Luca Veh“ is a literal there, in `LICENSE-DATA.md`, the dictionary and `CITATION.cff`.
8. The Impressum says errors are reported publicly via GitHub Issues, but no link renders while `--data-issues-url` is unset, and the repository is private (non-members get a 404).
9. ~~A release `--data-tag` with `$BUNDESTAG_PULSE_DATA_MANIFEST` is refused only after `run_facts_engine` wrote the facts tables (idempotent, a wasted pass); move the check before it.~~ **Done 2026-11-05:** refused at the head of `main()`.
10. A blob committed with CRLF is exported as LF, so the shipped `LICENSE-DATA.md` is not byte-identical to "the one that commit holds" (docstring and docs); add `.gitattributes` `eol=lf` for the three codebook inputs or soften the claim.
11. Smaller: `_read_codebook_inputs` normalises CRLF and `text_sha256` normalises again; the `os.chdir` in `test_relative_directories_reach_gh_as_absolute_paths_and_a_hash_is_refused` should be `contextlib.chdir`; README, `CONTEXT.md` and `docs/stable-ids.md` still name "export format 11" in sentences that stay true but cite an old number; the C1 seat-count work also plans export format 12, so whichever lands second takes 13.
12. ~~Not run in the review: the reference-store export replay.~~ **Done 2026-11-01** in the /gstack-ship run: a clone of the reference store, repersisted with this branch, then offline builds. 290 protocols, every row count, vote, Rede character sum, Sprechrolle and Beitrag count and all 710 stored Fakten unchanged; the store's SQLite hash unchanged by the offline build; a format-12 export listing `LICENSE-DATA.md` with the default short string; a further build on identical inputs printed `export: reused data/exports (unchanged)`.
13. Browser check (375px, dark, 2026-11-01, demo build plus both legal pages rendered from a dummy operator file): no horizontal scroll, dark tokens apply, links and the `cdn.example.net` host sentence correct, no operator marker left when the file is complete. Cosmetic only:
    - ~~the Impressum heading wraps between „§“ and „18“ (use `&nbsp;` after each `§`);~~ done 2026-11-03 (a no-break space after each `§` in the Impressum headings);
    - the placeholder state reads „Angabe folgt., Anschrift wie oben.“ and „Angabe folgt..“ (doubled punctuation; only the deploy gate planned under "Site hosting plan" will refuse these pages: `validate_publication_directory` accepts them, since CI validates the placeholder demo build);
    - Datenschutz grammar breaks on some operator values: „erhält dessen Server“ after a feminine provider („die … GmbH“) and „etwa bei Berliner Beauftragte für …“ (needs a dative article/ending); rephrase so the inserted names stand alone („Server des Hosters“, „Aufsichtsbehörde: …“);
    - the footer Impressum/Datenschutz links are 14px tall, below the 24px touch-target minimum;
    - in `sources.html#lizenz` the intro sentence renders at 16px while the layer texts render at 14px.
    The demo build has no export, so its Daten page lacks the `LICENSE-DATA.md` link that sources.html mentions; a build with an export renders it (`render_daten_downloads`), and the release gate never publishes without one.

**Why:** Deferred under the CLAUDE.md fix-now-or-defer rule. The review fixed the crashes (operator-file lone surrogate, deep nesting and unparseable URL host; a malformed or host-less `--data-base-url`), the Datenschutz download host for a protocol-relative base URL, the Datenschutz source sentence (roll-call results were credited to abgeordnetenwatch.de too), „LICENSE-DATA.md in jedem Download“ (only the export carries it), and two stale claims.

**Effort:** M
**Priority:** P2 (items 3 and 6 before the site goes public), P3 (rest)
**Depends on:** None

### Impressum/licence branch: deferred /gstack-ship findings (2026-11-01)

**What:** Non-correctness findings from the /gstack-ship review of `claude/pre-public-items-plan-e8d01d` (merged specialists, red team, functional QA), not already listed above:
1. ~~The release run's follow-up × `--publish` cell has no test: every `--publish` test in `tests/test_publish_dip_pulse_data.py` passes `--initial`. Add a `FollowUpReleaseTests` case running `--previous-manifest <file> --changes <file> --publish` with `Runner(gh_tags=[<previous tag>])` that asserts exit 0, one `gh release create`, `changes.json` `previous_version`, and that the previous tag does not block.~~ **Done 2026-11-05:** `FollowUpReleaseTests.test_a_follow_up_release_is_published_although_gh_lists_the_previous_tag`.
2. ~~`test_a_release_tag_that_exports_nothing_stops_the_build` (`tests/test_data_pipeline_cli.py`) does not clear `$BUNDESTAG_PULSE_DATA_MANIFEST`; with that variable exported, the manifest refusal fires first and the test fails. Wrap it in `mock.patch.dict(os.environ)` without the variable.~~ **Done 2026-11-05:** the test clears the variable.
3. ~~`_operator_authority`'s half-filled branch (only `supervisory_authority.name` or only `.url`) has no test row.~~ **Done 2026-11-05:** `LegalPagesTests.test_a_half_filled_supervisory_authority_marks_the_missing_half`.
4. ~~`test_the_default_licence_string_is_the_short_string_of_license_data` pins the live prefix „Quelldaten: Deutscher Bundestag/Bundesrat – DIP“, so rewording the short string fails it; keep the `endswith("Details in LICENSE-DATA.md.")` check (`render_daten_downloads` links that mention) and use `tempfile.TemporaryDirectory` instead of `__import__("shutil")`.~~ **Done 2026-11-05:** the live prefix is gone and the test uses `tempfile.TemporaryDirectory`.
5. `verify_export`'s `licence["bytes"] == 0` clause cannot decide the outcome (an empty file never matches a non-empty commit blob, and `_read_codebook_inputs` refuses an empty one); drop it and reword the message, or give it a test.
6. `render_datenschutz_page`'s `except ValueError` is unreachable from the CLI (`resolve_data_base_url` refuses such bases first).
7. ~~`load_operator` echoes the e-mail value into its error message; once a scheduled build reads the operator file from a repository secret, a malformed address would print into public CI logs. Drop the value from the message before that workflow exists.~~ **Done 2026-11-05:** the message names the field only.
8. ~~The `--data-base-url` and `--data-issues-url` refusals run inside `run_data_pipeline`, after fetch, persist and facts; a typo wastes a whole online update. Resolve both at the top of `main()` beside `resolve_operator`.~~ **Done 2026-11-05:** both are resolved at the head of `main()`, after the early-exit modes.
9. ~~The footer of the legal pages and of the database-unavailable page reads „Quellen und Methode Impressum · Datenschutz“ with no separator before „Impressum“.~~ **Done 2026-11-03:** `render_legal_links` brings its own leading `&middot;`, so every footer (not only these) sets the links off.
10. ~~Predates this branch: in dark mode the two hint boxes on `abgeordnete/index.html` („Der vollständige Abgeordnetenkader wurde nicht abgerufen“) show pale text on a pale background.~~ **Done 2026-11-03:** `.mp-notice` takes the dark warning colours.
11. ~~`resolve_data_base_url` still accepts bases a browser misreads or cannot use: a scheme without `//` (`javascript:x` becomes the prefix of every download href; `https:/host/`, `https:host`), a bad port (`https://h:abc/`, `https://h:99999/`), whitespace in the host, a leading space or tab before `//host` (it takes the relative-path branch, so the host and credential checks never run; browsers strip the whitespace), and a query or fragment (`https://h/?x` becomes `https://h/?x/`). Refuse any `scheme:` other than `https://`/`http://`, touch `parsed.port` inside the existing `try`, and refuse whitespace, control characters, `?` and `#`. Owner-supplied input; the datenschutz host sentence can disagree with the hrefs for some of these.~~ **Done 2026-11-05:** every listed form is refused; relative paths, `https://`, `http://` and `//host/x` stay accepted.
12. ~~The credential refusal promises not to echo the value, but the test rows only assert `ValueError`; assert the userinfo and host are absent from the message.~~ **Done 2026-11-05:** the rows assert the userinfo and host are absent.
13. ~~The operator file: duplicate JSON keys pass silently (the last one wins, so a pasted-twice `email` changes the Impressum without an error; refuse them with an `object_pairs_hook`); there is no size or file-type check, so a FIFO, `/dev/zero` or a huge file hangs or exhausts memory (stat for a regular file, read at most about 64 KiB).~~ **Done 2026-11-05:** duplicate keys, a non-regular file and anything over 64 KiB are refused. Still open: the e-mail regex accepts a digit-only TLD and refuses IDN domains (punycode works).
14. `previous_manifest_problem` refuses a previous `datenstand.json` that lacks any of `release_changes.SCHEMA_FIELDS`, although `release_changes.assemble` reads them with `.get()`. No release exists yet; decide before the second release whether such a manifest is refused or tolerated.
15. ~~Predates this branch: `publish_dip_pulse_data._read_json` catches `JSONDecodeError` but not a plain `ValueError`, so a `--previous-manifest` or `--changes` file with an integer past 4300 digits ends in a traceback (`load_operator` got the same fix on this branch).~~ **Done 2026-11-03:** `_read_json` and, for `--changes`, `release_changes.load_authored` catch `ValueError` and `RecursionError`; five refusal rows in `test_publish_dip_pulse_data.py`.
16. `default_license_text` reads `LICENSE-DATA.md` a second time, apart from `_read_codebook_inputs`; an edit between the two reads gives `manifest["license"]` from another revision than the shipped copy. Derive the default from `CodebookInputs.license` (the consequence is item 3 of the section above).
17. For the lawyer: the Datenschutz page states purposes but no legal basis (Art. 6 DSGVO) for the server logs, the e-mail contact or the people in the data; ADR 0003 open question 8 asks this only for localStorage.

**Why:** Deferred under the CLAUDE.md fix-now-or-defer rule. The ship review fixed the three correctness defects it found: `--data-base-url` now refuses a backslash (browsers read `/\host/` as another site while the privacy page named no host) and credentials, `datenschutz.html` names a download host only when the build renders a manifest, and an operator file with an integer past 4300 digits is refused instead of ending in a traceback. Codex could not run in this session (it must write `~/.codex`, and the out-of-sandbox run was refused), so the outside review is missing.

**Effort:** S
**Priority:** P2 (item 17 before the site goes public), P3 (rest)
**Depends on:** None

## Zitierfähiger Datensatz

PRODUCT.md (2026-09-30) makes the dataset a product in its own right: a source researchers and journalists cite. Citable means a reader can name a version, get exactly those rows back later, and look up what changed since. Stable ids are complete; the release script, release changelog and DOI remain. The licence files and the roll-call redistribution question (both under Plenarwatch-Lücken) block any public release that contains votes.

When the first release goes out, the "Project stage: pre-release" section of CLAUDE.md has to become a stability policy: what may change between releases, and how a change is recorded.

### Write the release script: versioned, immutable data releases

**Done in v0.26.0.0 (#123):**
- `scripts/publish_dip_pulse_data.py` (with a thin `.sh` wrapper) builds an immutable `data-<version>/` directory from a release-tagged export. It writes CHANGES.md, changes.json and SHA256SUMS, and under `--publish` it runs one `gh release create`.
- Versions are calendar dates `YYYY.MM.DD` (`scripts/release_version.py`).
- What it refuses is listed in the script and in CHANGELOG 0.26.0.0.

Since v0.30.0.0 every export carries `LICENSE-DATA.md`, and items 6 and 10 of "Release pipeline: deferred /ship review findings" are fixed, so `--publish` is reachable.

**What is left:**
- The first real `--publish`. It waits for three things:
  - items 1–5 of "Release pipeline: deferred /ship review findings", which that entry says to fix first
  - the roll-call source decision ("Settle the roll-call source for redistribution")
  - a host the site can link to
- Open owner decisions:
  - (a) The version scheme is a default. Change `release_version.py` to switch to semver.
  - (b) The hosting layout. GitHub release assets are flat, but the site links `<base><generation>/<file>`. So no GitHub release URL works as `--data-base-url` until the site's link scheme (`generation_file_href`) or the host changes. The dry run says so. See "Site hosting plan for the 2.5 GB generated site".
  - (c) `docs/designs/daten-page.md` planned `gh release upload --clobber`, which overwrites. This script creates each version once and never overwrites.
- Only this script enforces immutability. Anyone with write access can still edit a GitHub release.

**Why:** Without a release, "the dataset" is whatever the last local build produced. Nothing can be cited or downloaded twice with the same result. "Scheduled data-release workflow" and the Daten items are blocked on this.

**Effort:** S (the run itself, once the dependencies are settled)
**Priority:** P1
**Depends on:** "Settle the roll-call source for redistribution" (before votes are released); a host from "Site hosting plan for the 2.5 GB generated site"

### Release pipeline: deferred /ship review findings (lane/release, 2026-10-31)

**What:** The v1 release /ship review fixed four defects (dangling „Geändert laut Manifest: .“ in CHANGES.md, tracebacks on a non-object `--previous-manifest`, a non-file in the generation and a missing git/gh or full disk, `--data-tag` accepting any token). These remain, none reached by a current input, deferred under the CLAUDE.md fix-now-or-defer rule:
1. Workflow dead ends: a dry run writes `data-<version>/`, so `--publish` into the same `--output-dir` refuses „already exists“; a failed `gh release create` keeps the directory (and may leave a remote tag or release), and neither refusal names the recovery step. Say „remove the directory or use a fresh --output-dir“, or let `--publish` accept an existing directory whose files match the verified export.
2. `gh release create <tag> --target <commit>` attaches to an existing remote tag that has no release and ignores `--target`; add `--verify-tag`-style protection or check `git ls-remote --tags`.
3. `full_commit` resolves the 12-hex revision with `rev-parse --verify <hex>^{commit}`, so a branch or tag named like those digits wins (reproduced in a temp repo); resolve with `--disambiguate` and require one commit.
4. `--previous-manifest` is not tied to the latest existing release nor validated beyond being an object; an older manifest gives false deltas and can hide a schema change from the authored-schema_changes guard. Require its version to be the latest known and run `validate_manifest` on it.
5. TOCTOU: `verify_export` hashes the export, `build_release_directory` re-reads `datenstand.json` and links the files later; re-verify the staging directory against the manifest before the rename, or hold the export lock.
6. ~~`LICENSE-DATA.md` is copied from the working tree, not from the manifest commit, and an empty file passes the `--publish` gate.~~ Done 2026-11-01 (branch `claude/pre-public-items-plan-e8d01d`): every export carries `LICENSE-DATA.md` (manifest kind `license`, the codebook input's bytes); the release script copies nothing from the working tree and refuses a listed file that is empty or not the one the manifest commit holds.
7. Release directory mode is 0700 (mkdtemp), which a web host copy cannot read; `SHA256SUMS` lists `g-<hash>/<file>` paths that cannot be checked against flat GitHub assets, and its filter skips any file named SHA256SUMS at any depth; generation files are hard-linked (shared inodes) and symlinks are not refused.
8. `build_revision._PINNED_CONFIG` leaves `diff.suppressBlankEmpty` (reproduced: another `-dirty-` hash), `diff.srcPrefix`/`dstPrefix`, `core.autocrlf`, `core.fileMode` and `diff.ignoreSubmodules` unpinned, so a dirty revision can differ between machines (release revisions are bare commits, unaffected). Pin them or narrow the docstring.
9. Smaller: `release_version` `\d` accepts Unicode digits (re.ASCII); `release_changes` accepts NaN (parse_constant, allow_nan=False); the Daten page tests `"-" in commit` instead of `build_revision.is_release_revision`; `REVISION_LENGTH` and the `{12}` regex are written twice; `_sha256` duplicates `_hash_file`; release files are hashed twice; `import subprocess` is dead in `build_dip_pulse_site.py`; the export undo uses `rmtree(ignore_errors=True)`, so a partial removal skips the aside restore; tests: `--publish` x staging failure untested, `_link_or_copy` copy fallback, `render_markdown` minor lines, the `docs/data-changelog.md` example not parsed by a test, dry-run licence notices only substring-checked, one long multi-scenario test in `test_build_revision.py` and a duplicated `git()` helper.

10. ~~**P1, fix before the first real `--publish`**~~ **Done 2026-11-01** (branch `claude/pre-public-items-plan-e8d01d`, each with a test): (a) a `--previous-manifest` must be an object with the fields `release_changes` reads (`null`, numbers and lists refused; the site's `validate_manifest` is not used because it refuses every export format but the current one, which the release after a format bump needs); (b) both directories are resolved before gh sees them and an `--output-dir` with `#` is refused; (c) a release `--data-tag` refuses `--data-manifest` in `parse_args` (`--no-persist` no longer exists since 0.29.0.0), and `run_data_pipeline` stops when no export carries it (no store, `DataExportUnavailable`, `$BUNDESTAG_PULSE_DATA_MANIFEST`); (d) the exporter and `blob_sha256` both hash with CRLF read as LF (`build_revision.text_sha256`). Original finding (adversarial review, adjudicated defer 2026-10-31 because `--publish` refuses until LICENSE-DATA.md exists): (a) a `--previous-manifest` file holding JSON `null` passes the object check, so a follow-up release is labelled „Erste Veröffentlichung“, needs no changes file and skips the existing-release check (Codex reproduced it against an existing remote release); require an object whenever the option is given. (b) A relative `--output-dir`/`--exports-dir` run from outside the repository root: gh runs with `cwd=repo_root`, so the asset and `--notes-file` paths point elsewhere and can upload stale same-named files; `.resolve()` them (and refuse `#`, gh's label separator). (c) `--data-tag <version>` with `--data-manifest` (or a missing store / `DataExportUnavailable`) exports nothing yet exits 0, leaving an older release-tagged export for the script; `parser.error` on those combinations and require the export's tag to equal the requested one. (d) With `core.autocrlf=true` the exporter hashes CRLF working-tree bytes while `blob_sha256` hashes the committed LF blob, so a clean checkout builds an export the release script refuses; normalise one side.
11. Cycle-2 and adversarial deferrals: the `main` comment says the release directory „was already rolled back“, true only for failures inside `build_release_directory`; CHANGES.md states „Keine Korrekturen veröffentlichter Werte.“ as fact when the author lists none (say „angegeben“, or check `source_sha256`/`inputs_hash` against the previous manifest); a `--changes` file holding `null` reads as no file; a numeric `commit` in a hand-edited manifest raises TypeError in `is_release_revision`; `--next-version` reads local tags only (fetch tags or ask gh); DATA.md of a release export still says no immutable download reference was given; CITATION.cff's title „poliwatch“ differs from the CC BY attribution name „Bundestag-Puls“; CHANGES.md, changes.json and LICENSE-DATA.md are not run through the publication denylist; `ValueError` (lone surrogate, a 5000-digit integer) still escapes `main`; files flagged assume-unchanged/skip-worktree are invisible to the clean-revision and authored-input checks; `committed = True` is set one statement after the manifest rename (interrupt window); the schema-change guard accepts any entry, corrections name unchecked tables/columns, count drops need no note, and a type change („1“ to 1) renders as no change in CHANGES.md; the dry run's `--initial` check sees local tags only; the printed `--data-manifest` path is not shell-quoted.

**Why:** First release pipeline; the reviewed paths fail closed or need hand-crafted input today, but items 1-6 and 10 matter before the first real `--publish`.

**Effort:** M
**Priority:** P2 (item 10 done 2026-11-01)
**Depends on:** Write the release script (above)

### Public data changelog per release

**Done in v0.26.0.0 (#123):** each release carries `CHANGES.md` and `changes.json` ([format](docs/data-changelog.md)). They are derived from the previous and current manifests plus an authored file (summary, schema changes, coverage added, corrections with old and new value). A schema change without authored `schema_changes` refuses the release.

**What is left:**
- Show CHANGES.md on the Daten page. The release script does not render it there.
- A person has to write the corrections for each release.

**Why:** A researcher who cited version N must be able to see whether a later fix touched their numbers. The Fakt der Woche publication ledger covers cards only, and CHANGELOG.md covers code.

**Effort:** S
**Priority:** P2
**Depends on:** The release script

### A DOI per release and a citation file

**Done:** `CITATION.cff` at the repository root (v0.26.0.0, #123), guarded by `tests/test_citation_file.py`. It claims no DOI, version, date or `repository-code` yet; add `repository-code` and `url` when the repository is public. The root `LICENSE` (MIT, code only) exists since v0.30.0.0.

**What is left:**
- Archive each release's data files through Zenodo's upload API from the release script. Zenodo's GitHub integration archives only the source zip, not the release assets. The upload gives a concept DOI plus one DOI per version.
- Show "Zitieren als …" with the version DOI on the Daten page and in the codebook.
- This needs a Zenodo account and token.

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

### Correct the WP 19/20 roll-call group misattributions (E4) from the MdB-Stammdaten

**What:** On 55 roll-calls in WP 19 and WP 20 (rebuilt store, 2026-11-02; 47 in the older store file), bundestag.de files six MdBs under the wrong group: Kamann, Bülow, Pasemann, Witt, Huber and Heßenkemper (`docs/source-errors.md` E4). `vote_members.party_id` and `vote_fractions` copy the pages, so these members' Stimmen count for the wrong group. That affects the vote panel's group blocks, the Mehrheitsvotum and Abweichler (R3, Fakten). Re-file each member's Stimme under their Zugehörigkeit on the vote's date from `mdb_zugehoerigkeiten`, recompute the affected `vote_fractions` rows and Mehrheitsvoten, and report old and new values per vote.

Done when:
- the C1 cross-check (`seat-crosscheck.json`) shows no `shift_between_groups` roll-call;
- the page's totals stay available as the source's own figures;
- the fix runs on every rebuild, not as a one-off patch.

**Why:** The C1 cross-check measured it on 2026-11-01. The Textarchiv backs the Stammdaten in every case. Until this is fixed, the published group counts of those 55 votes are wrong.

**Context:**
- **Vote ids:** `docs/plans/c1-seat-counts.md` "Step 9 result" lists them: 38 from 487 to 571, 10 from 696 to 706, 750–754 and 756–757.
- **Where the rule goes:** at persist time, after the C1 tables exist in the staged store. The rebuild order puts `rebuild_seat_counts` after the reports are persisted, so the rule needs a pass after it, or the seat tables must move earlier.
- **Votes from before WP 18** have no Stammdaten rows and stay as the source has them.
- **Decide** whether a Stimme keeps the page's group as a second column, the page being the source.

**Effort:** M
**Priority:** P1 (a wrong published figure)
**Depends on:** Fraktion seat counts in the store (done)

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

**Context:** Correctness items come first. "Inverted-vote reading for Beschlussempfehlungen" shipped in v0.10.0.0. A plain-language description of a rejected Beschlussempfehlung that doesn't handle the inversion would be wrong. The remaining interpretation and replay defects are fixed in v0.22.0.0: see the completed "Vote reading misses half the inverted votes and never stores it" item. Full analysis of the bundestag.de vote pages (2026-10-20): [docs/research/bundestag-vote-pages.md](docs/research/bundestag-vote-pages.md).

**Effort:** M
**Priority:** P2
**Depends on:** Vote reading misses half the inverted votes and never stores it; deterministic validators (only for the deferred AI fallback in 1)

### B4 extractive fallback: finish validation locally (open items from PR #113)

**What:** Validate quoted-Antrag fallback coverage and fidelity, retaining measured failures as separate extractor follow-ups.

**Status: OPEN — 2026-10-31 follow-up (extractor 9): zero incorrect passages on the saved 91-document corpus, coverage still below 90%.** [Plan](docs/plans/b4-extractive-antrag.md#local-validation-outcome-2026-10-29), [Run 3 evidence](docs/research/b4-antrag-extraction.md#run-3-local-reference-and-mid-period-validation-2026-10-29), [Run 4: fidelity and interposed anchors](docs/research/b4-antrag-extraction.md#run-4-source-fidelity-and-interposed-anchors-2026-10-31-extractor-7-to-9), [91-document audit](docs/research/b4-local-audit-2026-10-29.csv).

**Done 2026-10-29:** the local validation. The canonical cache was preserved. Vote descriptions went from 153/217 to 196/217. 20 mid-period documents were audited. Protected fields were unchanged, and the full checks passed. The details are in the [Run 3 research note](docs/research/b4-antrag-extraction.md#run-3-local-reference-and-mid-period-validation-2026-10-29).

**Done 2026-10-31 (lane/correctness, extractor 7 to 9, offline replay over the saved corpus, no site build):** (a) source fidelity: `18/2742` (lost hard hyphen) and `18/3154` (lost bullet markers) are `no_passage`, `19/16794` is quoted without the printer imprint, each with a real DIP-text fixture; incorrect accepted passages **3 to 0**. (b) The measured interposed-anchor clauses and the `dazu` variant are supported with the whole sentence as the opening: ten reference documents become extractable. Checking them found and fixed two more defects (`20/13415` a)-z) then aa) folded into z); `20/2345` DIP dropped a hyphen and glued `Überoder`, now refused; DIP source defect for a correction request). (c) Re-audit, explicit denominators: reference cohort **50/71 to 60/71** (84.5%; 50/68 to **60/68** = 88.2% with a demands section); wholly abstract-less **43/60 to 53/60** (53/59 = 89.8%); mid-period **16/20 to 14/20** (14/16 = 87.5%, two incorrect-quote documents now refused); all 91 **66/91 to 74/91** (74/84 = 88.1%); incorrect **3 to 0**. Derived from the audit mapping, not site-measured: narrow-cohort descriptions 196/217 would become 206/217.

**Remaining:** no population reaches the 90% gate (reference cohort needs 62/68, i.e. two more of: footnote documents `20/9155`, `21/354`, `21/4750`, `21/2553` (fail closed by design); `möge beschließen` `20/10055`; `fordert` without a Bundesregierung object `20/14699`; direct motion to revoke `20/3596`; the others are `20/2345` (source defect) and the two refused mid-period documents). Each is a separate rule with its own fidelity risk; take one at a time with a real fixture and the PDF-layout check used in Run 4. Cloud inverted cases `20/4666`, `19/30983` are still unsupported: their texts are not in the saved corpus and could not be re-checked offline. Not done: step 5 site-level before/after and the store replay (`--offline --repersist` with extractor 9). The historical cloud result (32/36, 89%) does not override the local results; do not close this TODO on the description percentage. Owner decision for the hyphen rule: a lowercase line-end hyphen after a 5+ letter part the text itself uses as a word is refused unless the joined word is spelled elsewhere (cost on this corpus: 1 document, 18/2742); recommendation keep, relax only if a larger corpus shows many false refusals.

**Smallest follow-up:** pick the next rule from the list above (footnote removal is the largest group, 4 of the 10 remaining demand-bearing misses), add its real fixture, check every new quote against `pdftotext -layout` as in Run 4, bump `EXTRACTOR_VERSION`, re-audit. Substantial extraction work belongs in that separate session.

**Review findings deferred (lane/correctness /ship, 2026-10-31; none reached by the saved corpus, all under the CLAUDE.md fix-now-or-defer rule):**
1. The imprint drops in `_LAYOUT_LINE` remove any whole line that starts with `Druck:` (with GmbH or www.) or `Vertrieb:` (with Verlag), wherever it stands; a wrapped content line of that shape inside the operative part would vanish from a quote that still ends in a full stop (red team, synthetic repro). Bound the drop to page-foot matter, or refuse the passage when such a label line sits inside a clause.
2. The imprint patterns are single-line: a `Gesamtherstellung:` line wrapped before the address, or `Druck: Bonner Universitäts-Buchdruckerei, 53113 Bonn` (no GmbH or www.), stays inside the demand (not a regression: extractor 7 kept all of it). The Run 4 note's "dropped like running heads" holds for the 19/16794 single-line shape only.
3. `_GLUED_ODER` catches only a capital-led token: `kurzoder` (lowercase truncated part) is quoted; `und` glue is undetectable by this pattern (comment says so). Its comment's "no German word ends in oder after a capital" is false (Decoder, Encoder: refused, a safe loss).
4. Tests: the "Hintergrund oder" row in `test_a_conjunction_glued_to_a_truncated_compound_is_not_quoted` cannot match the pattern (it has a space), so it proves nothing about real words; no boundary row for `_WHOLE_WORD_LENGTH` (4 vs 5 letters) or the other `_WORD_ENDINGS`; `test_engine_refuses_a_distribution_copy_and_leaves_it_untouched` imports shutil inside its loop.
5. The comment "A word a line-end hyphen leaves standing" now sits above `_WORD_ENDINGS` instead of `_KEEPS_HYPHEN`, and the `_join` docstring has one over-long line.

**P1 gate before the fallback runs on any Drucksache cache larger than the saved corpus (resumed /ship of v0.25.2.0, 2026-10-31).** Three review sources (red team, Codex adversarial, Claude adversarial) independently found inputs that would publish a wrong verbatim quote. All of them are synthetic: none occurs in the saved 91 documents, and the only cache on the machine (`.context/b4-local-20261029-163417/working/data/dip-drucksache-text-cache.json.gz`) holds those documents alone. The extractor widened in v0.25.2.0 exposes items 1-3 to more openings: Codex reproduced items 2 and 3 under the new „zum Schutz der … auf,“ opening, which the base refused. Before a larger cache (WP 21, A3 backfill) is extracted, fix these or measure them on that cache. Each new quote should be checked against `pdftotext -layout`, as in Run 4. The A3 store (merged-tree gate, 2026-11-01) has no Drucksache text cache yet. 114 of its 619 votes are `not_fetched` (WP 19: 15, WP 20: 63, WP 21: 36) and 505 are `not_applicable`; no vote quotes a passage. That fill is the online build this gate guards.
6. A lowercase line-end hyphen after a part the text never prints elsewhere joins silently (synthetic `türkisch-` + `syrischen` gives „türkischsyrischen“; `deutsch-` + `französischen` gives „deutschfranzösischen“). Absence from the lexicon proves nothing; candidate rule: refuse a 5+ letter adjective-suffix part (-isch, -lich, -ig) without lexicon support, then re-measure coverage.
7. The dropped-bullet refusal in `_lines` fires only after a line ending in „.“ or „;“. Indented items ending in „,“ or „:“ are flattened into one sentence, and the first dropped bullet after „auf,“ is never caught. Fix: widen the predecessor test, or refuse on two or more indented non-item lines.
8. Fail-closed coverage loss: a Vorabfassung watermark after a full stop leaves a leading space after `_WATERMARK.sub("\n", …)`. A line starting with NBSP does the same. The new dropped-bullet check then refuses a passage that extractor 7 quoted. Measured: 0 of 112 replayed texts change with the fix, and the cached texts contain no watermark. Fix before any WP 21 advance-copy cache: make the substitution swallow trailing `[ \t]*`.
9. The 5+ letter hyphen rule refuses common compounds whose first part the text also prints alone (`Rahmen-` + `bedingungen` with „Rahmen“ elsewhere, `gleich-` + `zeitig`). The saved corpus prices this at 1 document, but the trigger words are frequent, so expect more refusals on a larger cache. The owner note above („relax only if a larger corpus shows many false refusals“) covers this decision.
10. Tests: the clause cap is pinned at 29/31 words, not 30, and `{0,30}` in `_INTERPOSED` is an unnamed literal (name it `_MAX_CLAUSE_WORDS`). `test_rebuild_refuses_a_distribution_copy_and_leaves_it_untouched` covers only the `user_version` marker, not `datenstand`, and does not assert that no staged files are left over. No break row covers a 5+ letter part absent from the text.

**Why:** The local audit found actual errors in quoted older-period texts. The reference population has now been read; fidelity beyond that population remains unproven until the failing sample documents are fixed or safely refused.

**Context:** PR #113, branch `claude/charming-lovelace-4a229o`; `EXTRACTOR_VERSION` 9 (7 at PR #113). The Drucksache cache rides in the in-memory Vorgang cache under `antrag_text.CACHE_NAMESPACE`; A3 coordination was on the former A3 entry (`git show c932255:TODOS.md`).

**Effort:** M (remaining source fidelity and measured anchor follow-ups)
**Priority:** P2
**Depends on:** Saved local corpus; no new backfill required

### Fill the Drucksache text cache for the WP 18–21 store

**What:** The A3 store has no Drucksache text cache, so the Antrag extractor (`EXTRACTOR_VERSION` 9) quotes no passage on it. On the merged-tree gate store (2026-11-01): 114 votes are `not_fetched`, 505 are `not_applicable`, and 0 passages are quoted. Fill the cache through DIP with A3's request pacing (the third stage of `refresh_vorgang_cache`), then repersist and report quoted passages old/new.

**Why:** Votes on an Antrag get no extractive description until the cache exists. #122's "196 → 206 of 217" applies only to the saved 91-document corpus, not to this store.

**Context:** Owner decision 2026-11-01: left out of the A3 merge. First clear the P1 item in "B4 extractive fallback: finish validation locally" above, which says to gate the fallback before it runs on any cache larger than the saved corpus. Also add the text cache to `validate_store_gate.py`'s replay inputs (see the A3 entry's B4 note). "Gate on the merged tree" in [the Phase 4 record](docs/plans/a3-phase4.md).

**Effort:** M (DIP request time plus the quote audit)
**Priority:** P2
**Depends on:** The P1 extractor gate above; A3 merged

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
1. ~~No per-vote cap on "Worum es geht" blocks.~~ Done in v0.28.0.0 (2026-11-01): the panel shows 3 Vorgang blocks and folds the rest behind "N weitere Vorgänge anzeigen" when 2 or more would be hidden; the not-fetched note stays outside the fold. 0 of 556 panels change (none has more than 3 Vorgänge).
2. ~~`abstract_text` output can differ across Python patch levels (it feeds the content-hashed export).~~ Done 2026-10-31: `abstract_text` no longer uses html.parser. `dip_text` scans markup by its own rule (`_tag_ends`, `_markup_end`), so the 2025 parser changes (end-of-input tags, comment closers, script and CDATA handling) cannot reach it. The 3,922 cached abstracts read alike on 3.11.15, 3.13.2 and 3.13.12 before and after (0 differ between interpreters; 0 of 3,922 changed by the rewrite). The full suite passes on 3.11.15, 3.13.2, 3.13.12 and 3.15.1. Only malformed markup reads differently from before: abstracts the old fallback read as one paragraph now keep their paragraphs, and an unclosed `<!--` with a later `>` ends there.
3. CSV formula injection now reaches free-text DIP columns (`proceedings.abstract`, titles). **Decision pending, recommendation 2026-10-31 (code unchanged):** keep cell values verbatim (SQLite and CSV stay byte-faithful to DIP, DATA.md's „unverändert“ stays true); the risk is a spreadsheet double-click evaluating a cell that starts with `=`, `+`, `-` or `@`, and the source is the official DIP, not user input. Reference store (`~/agent-runs/a3/full`): 45 text cells start with one of those characters, all DIP titles beginning „- “ (e.g. „- Sammelübersicht 730 des Petitionsausschusses…“, 15 values in `proceedings.title`, `proceeding_positions.title`, `documents.title`), 0 in `proceedings.abstract`. DATA.md now warns about this in plain words. Alternative if the owner wants safety over fidelity: prefix such cells with `'` only in the CSVs and say so in DATA.md and the manifest; that alters 45 cells and breaks CSV-to-SQLite equality for them. Recipe CSVs follow whichever choice is made.
4. ~~The teaser can cut after "(Abs.".~~ Done 2026-10-30: an opening bracket or quote is stripped off the token before the abbreviation test. 10 of 3,922 cached abstracts had a teaser ending in "(sog."; they now end at a word with " …" or at an earlier sentence end. For example, "Umsetzung der Erneuerbare-Energie-Richtlinie (sog." became "Umsetzung der Erneuerbare-Energie-Richtlinie (sog. RED III) zur Verkürzung … für Windenergieanlagen an Land …". Render-only, no stored value moves.
5. ~~`derive.vote_identity` uses the raw id while persist cleans it.~~ Done 2026-10-31 (with item 10): `derive.vote_identity` cleans the id with `_clean`, the rule persist uses, and persist's `_vote_id` now calls it, so there is one rule. Two ids equal after cleaning are one vote in `iter_report_votes` (the first copy wins), as in the store. Reference: 246 of 246 vote ids unchanged.
6. One member/count mismatch hides a whole group's Abweichler.
7. ~~`derive.vote_abweichler` dedupes member rows by name~~ Done 2026-10-22 (B4 Codex P2 F3): it dedupes on `derive.vote_member_identity`, the key persist hands `upsert_mp`, vote-wide. The 63 occurrences the old Abstimmung-page "profile URL" folded were unfolded by rebuilding the reference store's registry from scratch (2026-10-22, `vote_members` 154,078). Left: merges `registry.bind` makes later are not seen by derive.
8. ~~`derive.member_profile_url` links an abgeordnetenwatch profile whatever its match kind, so a name-guessed aw match can put an external profile beside a named Abweichler (0 cached Einzelstimmen rows carry an aw URL; B4 ship run 2 adversarial review, 2026-10-22).~~ Done 2026-10-31: the aw profile URL counts only when `trusted_aw_id` accepts the profile (match kind `ext_id`, the Redner-ID join); a name match or an unrecorded kind falls back to the member's own `profile_url`. Reference: 0 of 173,407 Einzelstimmen rows carry an aw URL, so 0 links and 0 `profile:` identities move.
9. An online Vorgang refetch replaces the cached record whole (`cache["vorgaenge"].update(records)` in `build_dip_pulse_site.py`), so an answer without `titel` or `abstract` drops ones the cache had; the replay guard sees only `not_fetched` transitions.
10. ~~`derive.vote_identity` turns an id of None into `"None"` when `fetch_targets` reads a fresh report before `require_vote_shape`; `features.votes.dip_vorgang_url` puts a non-digit Vorgang id into the DIP path unchecked.~~ Done 2026-10-31: `vote_identity` raises ValueError for a None or blank id; `dip_vorgang_url` raises for a non-digit id and the panel then shows the label unlinked. Reference: 0 of 246 votes without an id, 0 of 7,511 cached Vorgang ids not digits, so nothing moves.

Found by the B4 ship run 3 adversarial passes (2026-10-23, Codex and a Claude subagent) and deferred by the owner; none occurs on the reference data:
11. ~~A Fraktion missing from both the fraction rows and the Einzelstimmen leaves the other groups "complete", so the panel can say "Niemand stimmt anders …" and the archive show 0 while `vote.total` shows the missing Stimmen. Require the groups' totals to equal the vote total before any vote-wide claim (`build_dip_pulse_site.py` `_abweichler_count`, `features/votes.py` `_abweichler_summary_html`). 217 of 217 reference votes have matching totals.~~ Done 2026-10-30: `derive.vote_groups_cover_total` (fraction rows incl. fraktionslos and Unbekannt against `vote.total` on every count; no total, no row or a count that is not a number covers nothing) gates `derive.vote_abweichler_count`, the one vote-wide count the archive and the panel share; the panel shows the gap note instead, once (under the vote only when no short group already carries it). Reference: "Niemand stimmt anders" 122 → 122 votes, archive counts 217 → 217. The Fakt and r3 SQL (item 12) do not use it yet.
12. Pages and the Fakt `meiste-abweichler` / recipe `r3-abweichler` count Abweichler differently on an incomplete vote: `derive.vote_abweichler` withholds a group whose Einzelstimmen do not match its tally and excludes `Unbekannt`, the SQL (`facts.py`, the r3 recipe) does neither. Decide whether the SQL takes the page's completeness rule. 0 partial groups on the reference data.
13. `derive.report_drucksachen` keeps the first TOP's copy of a Drucksache while persist keeps the fullest, so an empty `urheber` first can make the panel say "Ausschuss nicht ermittelt" while `r6-ausschuss` counts the committee. D15 shows 0 of 217 differ.
14. ~~`derive.person_profile_url` accepts a `..` segment (`/abgeordnete/../apps/na/x` resolves to the Abstimmung page it exists to exclude).~~ Done 2026-10-30: a `.` or `..` path segment, also percent-encoded (`%2E%2e`), makes the URL no profile. No reference row carries one, so no stored value moves.
15. ~~The 10,000-character cut in `dip_text.abstract_text` can leave a cut tag or entity (`<a hr`, `&am`) as visible text; the longest reference abstract has 5,111 characters.~~ Done 2026-10-30: on the cut path only, a character reference the cut splits and the one tag the cut splits (opened before the cut, closed after it, read with the scan `_strip_tags` uses: a quote counts only as an attribute value after "=", a comment runs to its "-->") are dropped; a "<" that never closes stays text, as in an abstract that fits. No reference abstract reaches the cut, so 0 of 3,922 texts move. What the 2026-10-31 ship review left open is item 19.
16. html.parser is quadratic on runs like `'<a "'`: 10,000 characters take about 0.9 s per call, paid per persist and per vote panel. Computing the plain text once at cache-write time removes it.
17. ~~Vote ids are not limited to anchor-safe characters, so an id with spaces makes an invalid `id="vote- 7 "` and an archive link that does not scroll (reference ids are numeric).~~ Done 2026-10-31: `features.votes.vote_anchor_id` (used by the panel id and the archive link) writes every character outside `[A-Za-z0-9-]` as `_<hex>_`, so the anchor is safe, injective and equal in both places. Reference: 246 of 246 ids already safe, 0 anchors change.
18. ~~`.vote-context-block:has(…)` hides the teaser with no fallback (a browser without `:has()` shows it twice), and `ul.vote-abweichler-list { display:inline }` drops the list semantics in Safari/VoiceOver.~~ Done 2026-10-31: a long abstract's teaser sits in the details summary and `details[open]` hides it (no `:has()`); both Abweichler lists carry `role="list"`. Render-only: the 3,922 cached abstracts and stored values do not move; the vote panels with a "Ganze Beschreibung" fold change markup. Not checked in Safari/VoiceOver.

Found by the five-more-todos-3 `/ship` review (2026-10-31: red team, Codex adversarial, a Claude subagent) in the item-15 trim, and deferred by the owner; no reference abstract reaches the cut (longest 5,111 characters):
19. ~~The trim reads tags by hand to guess where html.parser ends them, and three review rounds each found a shape it reads differently. Two empty a whole over-limit abstract where main keeps it: an end tag, `<?…?>` or `<!…>` holding `="` before the cut with a quote after it (`'Anfang </p class="x> ' + 'wort ' * 3000 + 'ende "> z'`: 6 characters, main 9,987), and a quote after "=" inside an unquoted value (`'<b data=x=">Anfang ' + 'wort ' * 2500 + '">'`: 0, main 9,988). A trailing `&` plus letters is dropped as a partial reference even when it is none (`GmbH&C|o.` at the cut keeps `GmbH`). The scan reads the whole raw abstract, not 10,000 characters (about 2 s and 16 MB at 2 million). The comment rule copies Python 3.13.2's html.parser (`<!-->` and `--!>` close a comment in later patch levels; see item 2). Candidate fixes: bound it (look 2,000 characters past the cut, drop only a tag that starts within 2,000 before it, check `&x` against real entity names), or revert to main's plain cut and accept the visible fragment. `_strip_tags`, the malformed-markup fallback, shares the quote rule and loses words on the end-tag/PI shapes too ("Anfang Ende"), on main as well.~~ Done 2026-10-31 with item 2: one scanner (`dip_text._tag_ends`, a right-to-left pass, linear) decides where every tag, end tag, `<?…>`, `<!…>` and comment ends, for the cut and for the text alike; a quote opens an attribute value only after "=" and spaces, an end tag, `<?…>` and `<!…>` end at their first ">", a comment at its first "-->". The cut reads only the first 10,000 + 2,000 characters (2 million characters: about 0.4 s before, a few ms now); a tag that starts before the cut and ends after it, or has no end in the window and starts within 2,000 before it, is dropped. A trailing "&" and letters is dropped only when it reads whole as a different character reference (`GmbH&Co.` keeps `GmbH&C`). Both listed reproducers now keep the abstract (6 and 0 characters before; the text after the tag, cut at 10,000, now). One regression test per reproducer. 0 of 3,922 cached texts move. Left, no reference abstract reaches it: a tag that begins more than 2,000 characters before the cut and ends beyond the window shows as text. Malformed markup also reads differently in spacing, found in review: an unclosed `<script>`/`<style>` no longer adds a space (`a<script>x` was `a x`, now `ax`), a `<![` declaration now inserts one, and a self-closing `<script/>` is special-cased; no cached abstract has any of them (0 of 3,922 move).
20. Judgement calls left from the review of item 19's scanner (`dip_text.py`), not defects: the tag `kind` is a bare string ("tag"/"end"/"comment"/"other"/"block"), so an enum or NamedTuple would catch a typo; `(text, cut, truncated)` travel together and `truncated` is derivable from them; `_tag_ends` and the `end = len(text) + 1` sentinel in `_paragraphs` want clearer names. **Priority:** P4, **Effort:** S.
21. Found by the review of the 2026-10-31 vote-panel batch (items 5, 8, 10, 17, 18), deferred (P3/P4, S): (a) when the aw profile is not trusted, `derive.member_profile_url` still links the member's own `profile_url`, and `person_profile_url` accepts an abgeordnetenwatch host there too, so a name-guessed aw URL could arrive through that field; unlikely from the Bundestag source (0 of 173,407 reference rows carry an aw URL in either field). (b) `derive._clean` and `persist_dip_pulse_store.clean` repeat the same whitespace body (one returns "", the other None); one should call the other. (c) "First copy wins" (item 5) changes which of two ids equal after cleaning the store keeps within one report (before: the last, via INSERT OR REPLACE); 0 reference cases, all 246 ids numeric and unique per report.
22. Found by the v0.26.1.0 /ship review cycles (2026-11-01), deferred because no cached abstract reaches them (longest 5,111 characters, 0 of 3,922 differ from main). The scanner (`dip_text.py`) still differs from html.parser (Python 3.13.12) on malformed or truncated markup: (a) P2: a `<script>` or `<style>` that starts shortly before the 10,000-character cut and closes beyond the 12,000-character window looks unclosed, so its body stays as text (`"x"*9990 + "<script>" + "y"*2500 + "</script>tail"` keeps the `y`s; html.parser on main drops them). Fix: when truncated, drop to the cut from a skipped tag with no close in the window, or search the close tag in the whole raw text. (b) `_tag_ends` treats an attribute that starts with "=" as the "=" sign, so a following quote swallows text (`A <script ="> z </script> B` shows the tag and `z`; html.parser reads `="` as an attribute name). (c) A quote after "= " with no closing quote makes the tag run to the end in `_tag_ends` and `_self_closing`, where html.parser backtracks to an empty value (`A <b a= "x> B </b> C`). (d) The docstrings of `_markup_end` and `abstract_text` do not say that an unclosed comment ends at its first ">". P2 for (a), P3 for the rest, S. (a) and (d) are done in v0.28.0.0 (2026-11-01): the close tag of a script/style skipped before the cut is searched in the raw text past the window (memoised per tag name, linear), and the docstrings say an unclosed comment ends at its first ">"; 0 of 8,737 cached abstracts change. (b) and (c) stay open.
23. Found by the same review cycles, deferred (P3/P4, S): (a) `validate_dip_protocol.py` (lines ~1616, 1781, 2421) still keys votes on the raw `str(vote["id"])` while derive, persist and the anchors clean it (`derive.vote_identity`); latent while ids are numeric. (b) ~~`.vote-context .vote-context-more > summary { display:block }` removes the disclosure triangle; the blue "Ganze Beschreibung" toggle still marks it.~~ Done in v0.28.0.0 (2026-11-01): the three vote-context toggles carry a ▸/▾ marker with empty alt text. (c) Test hygiene: `test_a_huge_abstract_is_read_in_bounded_time` asserts a 0.5 s wall-clock bound (assert a bounded scan length instead); `test_teaser_hides_on_open_without_has` asserts the whole page CSS has no `:has(` (scope it to the vote-context rules); `tests/test_politikfelder.py` doubles as the radar fixture CLI in its `__main__` (move the writer to a helper both runners import).

**Why:** 3 lets a DIP text run as a formula in a spreadsheet that opens the export. 11 is the one item that can make a public statement false.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Vote panel tail (batch 6): deferred review findings

**What:** The /gstack-review of `fix/todo-batch-6-vote-panel-tail` (2026-11-01) found three things. (1) `test_a_huge_abstract_is_read_in_bounded_time` keeps a 0.5 s wall-clock bound, `self.assertLess(time.perf_counter() - started, 0.5)`, and now covers two 1.8M-character script-close inputs as well. Add a `gstack-timing-ok` reason or bound the operation count. (2) The `@media print` block does not open `details.vote-context-overflow`, or the abstract fold, so folded Vorgänge are missing on paper. (3) A folded block with a record but no abstract and no Antrag text keeps its `CONTEXT_TEXT_NOT_FETCHED` note inside the fold. The DD3 trailing note covers only a missing record. From the v0.28.0.0 /ship (2026-11-01): (4) `render_vote_context`'s docstring does not mention the fold or where the gap note sits; (5) `test_context_toggles_show_their_state_and_folded_blocks_stay_separated` asserts exact CSS strings, so a reformat breaks it; a browser check of the computed `::before` content and the 44 px target would prove the behaviour.

**Why:** (2) and (3) need 5 or more Vorgänge per vote; the maximum today is 3. (1) could flake on a slow CI runner.

**Effort:** S
**Priority:** P4
**Depends on:** None

### Politikfelder: findings deferred from the B3 review

**What:** Nine findings of the /ship review (2026-10-09) that B3 does not fix:
1. A missing lead Vorgang or number makes the tags come from the survivors with the wrong lead, and the source says `sachgebiet` or `drucksache`, not that something was missing. Record a partial flag, or count partial results in the build summary.
2. A non-empty Sachgebiet or resolved number is never refreshed, so a changed DIP label never reaches the tags. Use `aktualisiert` (already cached) to refetch Vorgänge DIP has updated.
3. Pages derive the tags from the cache file at render time, the Daten tables hold the snapshot of the last persist. A plain `--offline` build after the cache changed shows different tags than it exports. Since B4 the same holds for the vote panels' DIP abstracts and their Vorgang selection (`proceedings.abstract`, `vote_proceedings`, `votes.context_state`). Put a cache digest into `datenstand`, or render from the store; one fix covers all three.
4. The cache sits in the published `data/` directory and holds DIP `abstract` and `titel` text, which the vote panels now show (B4), so dropping it is no longer an option. Settle with "Site hosting plan" whether `data/` is deployed wholesale; if so, hosting must exclude `data/dip-vorgang-cache.json` or the cache moves out of `data/`.
5. The week radar's inline filter script is now checked by `tests/radar_browser_check.js` (run by `node tests/run_bills_browser_check.mjs`, 2026-10-31). ~~Still open: the inline filter script on `votes/index.html` is checked only by a headless-Chromium probe run by hand (2026-10-09); add a browser check for it the same way.~~ Done in v0.28.0.0 (2026-11-01): `tests/votes_archive_browser_check.js` checks the filter and the `?politikfeld` preload on desktop and mobile, run by `node tests/run_bills_browser_check.mjs`.
6. A Vorgang DIP does not return, or a number it resolves to nothing, is stored as "fetched, nothing known" and counted as fetched, so an offline repersist stores `untagged`, not `not_fetched`, until the next online build. Empty Sachgebiet records (4,086 of 7,511 cached Vorgänge, most pulled in by numbers with a huge fan-out) and empty lookups are asked again on every online build, about 40 batches and a pause each; bound that with `aktualisiert` or a fetched-at date.
7. A Sachgebiet label the mapping does not know is skipped at tag time, so tagging can fall through to a weaker source; the build summary names the label afterwards. Consider a `not_fetched`-like source for an unmapped label.
8. A TOP that names many specific Drucksachen (a bundled Beratung) is tagged with the three most frequent of up to eight fields, in first-seen order on ties: the plan's cap of 3, not a measure of what the TOP is about (65 of 207 TOPs tagged through their Drucksachen carry more than 3 fields). Decide whether a TOP over some breadth should stay untagged.
9. A Bundesrat Drucksache whose number looks like a Bundestag one is skipped only in `linked_drucksachen` (by its `/brd/` URL), not in a vote's numbers or a heading. `load_cache` leaves a file it could not read in place, but an online build then overwrites it with what it has fetched. A non-empty `dokumentnummern` list is never refreshed, so whether a number is "narrow" depends on when it was fetched.

10. Two online builds on one output directory both fetch before either takes the writer lock: the DIP rate doubles, and the last cache save wins, so the other build's fetches are re-fetched next time (`build_dip_pulse_site.py` `refresh_vorgang_cache` call in `main`, before `rebuild_database_from_entries`). Take the writer lock before the fetch, or merge new keys under a lock before each save.
11. The fetch breaker counts any five failed calls in a row, so five permanently failing numbers in a row (a 4xx, an odd body) stop the number pass on every build and leave the rest `not_fetched`; remember per-number failures with a date, or trip only on challenge-like errors (`refresh_vorgang_cache.resolve_numbers`).
12. A non-JSON 200 is retried three times per call (`validate_dip_protocol.ApiClient.get_json`), about 15 extra requests during a bot challenge before the breaker trips.
13. The online rebuild has no guard against storing more `not_fetched` rows than the previous store (an outage during a first fill); only `--offline --repersist` has one (`require_vorgang_cache_for_tags`).
14. Fixed (2026-10-31): the filter script marks the last visible row `is-last`, which drops its bottom border; `tests/radar_browser_check.js` covers it.

**Why:** None of them changes a number in the real store today (0 not_fetched, 0 partial, one empty lookup), and each needs a decision beyond B3's plan. Items 10–14 were deferred in the v0.20.0.0 ship review (2026-10-19).

**Effort:** S each
**Priority:** P3
**Depends on:** B3

### Fill the remaining untagged Tagesordnungspunkte

**What:** The 103 TOPs of the real store whose heading names a Gesetz or Antrag but that have no Vorgangsposition and name no Drucksache, and the 31 "other" ones, stay `untagged` after B3. Tag them from the heading with a model, restricted to the closed list, stored with a source of its own (for example `llm`) so a reader can tell it from a DIP-derived tag. Leave Fragestunde, Befragung, Wahlen and Geschäftsordnung untagged: they have no policy area.

**Why:** B3 stays deterministic on purpose, so the Daten export carries no model output (LICENSE-DATA.md). Measure first how many of the 134 a better deterministic rule can still reach, for example matching the heading against `/vorgang` titles.

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

**What:** Findings of the v0.19.0.0 ship review (2026-10-18) deferred by decision, P1 first: (1) **done** (lane/correctness): `run_facts_engine` now applies `pulse_store.require_build_store` (the distribution-copy guard `connect` uses) before computing or staging, so an exported SQLite given as `--database-path` is refused and left byte-identical; the /ship QA of that branch (2026-10-31, probes 004/005) found the rebuild replacing such a file (user_version 1 became 0, new inode), so `_rebuild_database_from_entries` now applies the same guard before staging. Still open from that review: the read-only paths that open `--database-path` as the build store (online pre-check, mp-pages read, post-rebuild read, export source check in `build_dip_pulse_site.py`) call only `require_current_schema`, so a distribution copy is read as the build store instead of refused up front (no write, no figure known to move). (2)–(4) and (6) are done (Done in v0.28.0.0 (2026-11-01), TODO batch 5): the staged copy gets the store's group before persisting (a group the builder cannot set stops the write), the sweep matches only this store's mkstemp names, a `data` directory directly under `/` keeps its private directory beside the store, and `person_registry.ensure_private_dir` refuses a symlinked, non-directory or foreign-owned private directory before any write or sweep; (5) now fails with a message naming the requirement (OUTPUT's parent writable and on the store's file system, docs/stable-ids.md), no override yet. Was: (2) `_replace_store` keeps the file mode but not the group, so a group-shared web root can lose read access after a rebuild or facts write (staging moved out of `data/`, whose group the old temp file inherited); (3) the staging sweep `glob(f"{name}.*.tmp*")` also matches a prefix-named sibling store's temp files and a lock of a store literally named `<name>.x.tmp`; restrict it to this store's mkstemp names; (4) `private_dir` treats any store whose directory is named `data` as `OUTPUT/data`, so an explicit `--database-path ~/stores/data/x.sqlite` stages in `~/.stores.private` and `/data/x.sqlite` in `/..private`; derive it from the real OUTPUT or fall back to the store's own directory; (5) the private directory needs a writable OUTPUT parent on the same file system, so OUTPUT as a mount point (container bind mount, CI volume) or under a read-only parent fails every rebuild, facts write and export; add an override or a fallback; (6) the private directory and its `exports/` are not checked for symlink or foreign owner before the sweep deletes their contents (shared `/tmp`); (7) the Daten export reads the store by path (schema check, stat, hash, backup) without the writer lock, so a concurrent rebuild can mislabel `datenstand.json` until the next export; (8) a forced same-name re-export killed between `published.replace(aside)` and `gen_dir.replace(published)` loses the published generation, and the next sweep deletes the set-aside copy; restore `replaced` on sweep; (9) `require_applied_partitions` catches a partition removed from the corrections file but not one added after the build (offline pages apply it, the registry does not); (10) a store from before DIP-id canonicalization holding `dip:07` splits that person on replay (new `dip:7` record, two pages; the real store has no such id); (11) `REPRESENTATIVE_SQL` orders `is_mdb DESC, xml_redner_id IS NULL, identity_key` but `collect_abgeordnete` orders `is_mdb` rows by `identity_key` only, so r1/r3 and the Personenseite can name a person with two MdB rows differently (0 such persons in the real store); (12) persist skips XML Drucksachen off the bundestag-xml host without a count or warning (all 4,699 real ones pass); (13) smaller: `_write_new_file` unlinks then creates, so a person page is briefly missing; an href-less date-like "21/09" folds into Drucksache 21/9; `document_issuer` falls back to BT without herausgeber or URL; a legacy `-journal` sidecar beside the store is not removed before the swap; `canonical_dip_person_id` raises on a >4,300-digit id; a local `document_id` in persist shadows the imported `stable_ids.document_id`; `tests/test_facts.py` computes two goldens with `facts._id_sort_key` (accepted, D25A).

**Why:** (1) can modify a downloaded distribution file; (2)-(6) break deployments other than the default layout; the rest are latent on the reference cache.

**Context:** Deferred in the v0.19.0.0 /ship run after three review passes, a red team per pass, a Claude adversarial pass and Codex adversarial and structured passes (structured gate passed, no P0/P1); Step 9 had used two of its three fix cycles. Verified false positive, not to re-file: a case-differing OUTPUT spelling shares one writer lock on macOS (same inode, second writer refused).

**Effort:** M
**Priority:** P2 (the P1 item (1) is done)
**Depends on:** None

### Store staging (batch 5): deferred review findings

**What:** The /gstack-review of `fix/todo-batch-5-store-staging` (2026-11-01) found four things. (1) `export_distribution_data` creates `work_dir` with `work_dir.mkdir(mode=0o700, parents=True, exist_ok=True)` (`build_dip_pulse_site.py:~4116`) instead of `person_registry.ensure_private_dir`. Three effects follow. A symlinked private directory still gets an empty `exports/` before the refusal. When an export runs before any writer lock, `.OUTPUT.private` ends at 0755, because `mode` applies only to the leaf and `ensure_private_dir` repairs only `0o022`. A dangling `exports` symlink reports a bare "File exists" instead of the symlink refusal. Fix: create it through `ensure_private_dir`, and have that function repair `0o077`. (2) `_write_csv` runs `os.fchmod(fd, 0o644)` outside the `try` that closes the fd and unlinks the temp file. ~~(3) `import glob` in `build_dip_pulse_site.py` is unused since the sweep rewrite.~~ Done 2026-11-03. From the v0.28.0.0 /ship (2026-11-01): (4) the cross-file-system refusal in `_staged_store_path` has no test (needs a `Path.stat` st_dev mock); (5) both group-keeping tests in `tests/test_private_staging.py` skip on a user without a second group (single-group CI), so the chown branch can go unexercised there: add a variant that patches `os.chown` and the store's gid; (6) a pre-existing private directory owned by another user (an earlier `sudo` run) is now a hard refusal where it was reused before; the message names the fix; (7) `politikfelder.write_atomic` falls back to staging beside the target in `data/` when `ensure_private_dir` refuses; (8) `_staged_store_path`'s sweep raises if a directory matches `_is_staged_copy`.

**Why:** These are latent. No figure moves. With a standalone export, only file names in the private directory are readable; the staged copies stay 0600.

**Effort:** S
**Priority:** P3
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

`render_site` calls its page builders directly. `votes`, `summaries` and `aw_profiles` do real work and stay as plain modules without `ctx`. (A4 slice 1, 2026-11-03, did the votes archive part: `VotesComponent.write_pages` and the `collect_votes_archive`/`write_votes_archive_page` ctx callables are gone, and `render_site` calls `write_votes_archive_page(votes_archive_rows(database_path))`.)

**Why:** It is a seam with only one adapter: nothing varies across it, and every signature pays for it. CLAUDE.md's pre-release rule says to drop compatibility shims rather than carry them.

**Context:** Found by the architecture review of 2026-10-03. ("Global header nav links to a page a build didn't write when its feature is off" is already closed as moot, see Completed.) Several `render_*` functions in `build_dip_pulse_site.py` still take a `features` parameter they no longer pass to `render_global_header` (some still use it for `page_head`/`page_scripts`); remove it with this item. Also check the `AbgeordneteComponent.after_persist` path that "A.2 second-round review leftovers" (3) proposes to drop.

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

One line per finished item, giving the version and PR that shipped it, or the date it closed. When you finish an item, replace its entry with one line here. What changed belongs in CHANGELOG.md and the PR. The full entries up to the 2026-11-02 cleanup are in git history (`git show c932255:TODOS.md`).

- Unmatched roll-call votes never reach the report (`sitting_votes`): fixed by v0.22.0.0 (#109); checked 2026-11-05 on a clone of `~/agent-runs/a3/full` repersisted from main: 619 votes, 63 with no TOP, 41 dossiers with "TOP nicht zugeordnet"
- `documents.url` of BT-Drs. 19/19 is the Bundesrat PDF: closed 2026-11-05, no defect: BT 19/19 (`btd/19/000/1900019.pdf`) and BR 19/19 (`brd/2019/0019-19.pdf`) are two correct rows, 0 rows of either issuer carry the other chamber's url, and `docs/plans/a4-slice1-oracle/t11_measure.py` M2 keyed its lookup on the number alone
- "Validate a data correction" copies no private directory, so `after` loses the seat tables: `fix/todo-round-2026-11`, 2026-11-05
- Textanteil for the r2 Daten recipe, the rest of the ADR 0001 UI half: `fix/todo-round-2026-11`, 2026-11-05: `r2-textanteil-fraktion`, ordered by characters; export format 15; the published rows do not change
- Stale cached-report error lines: polish: #134, 2026-11-04
- A malformed coverage-exclusions.json ends a build with a traceback: #132, 2026-11-03
- Dossier header: the "Drucksachen" card counts only XML-tagged Drucksachen, and WP 18 prints an empty "verteilt am": #132, 2026-11-03
- Rename `GRUPPE_DIE_LINKE_SINCE`: #132, 2026-11-03
- Dark mode and overflow defects found in the A3 spot checks: #132, 2026-11-03
- `test_help_documents_argument_order_cohort_default_and_exit_codes` fails in a narrow terminal: #132, 2026-11-03
- Validate final merged A1/A2 before the A3 backfill: 2026-10-19 (A3 Phase 0; [gate record](docs/plans/a3-gate-validation.md))
- Stable ids for every row a release publishes: v0.12.0.0 (#81), 2026-10-02 (A.2; [key and backup contract](docs/stable-ids.md))
- Store loses roll-call member rows in 22 groups of 11 votes: fixed by v0.21.0.0 (#107); 0 of 3,866 groups short on the repersisted A3 clone, 2026-11-01 (slice map in `docs/plans/a4-site-from-release.md`)
- Bundesrat members are ingested as MdBs (`_has_mdb_funktion` matches "MdBR"): fixed by v0.24.1.0 (#119), the same fix as "Call only current MdBs" below: `derive.is_mdb_funktion` takes "MdB" as an exact value, and `_has_mdb_funktion` no longer exists
- Cached report 21/50 no longer matches its XML: closed 2026-11-02: the reference store accepts 21/50 (2026-10-19), and the `right-counts-a1/after` cache it was found on no longer exists
- Fraktion seat counts in the store: v0.31.0.0 (#130), 2026-11-02 (C1)
- "Nächste Sitzungswoche" in the puls.html header: v0.28.0.0 (#127), 2026-11-01
- Week radar as data: `data/week-radar.json` and an RSS feed: v0.28.0.0 (#127), 2026-11-01
- v1 coverage: every Sitzung from WP 18 to the present: v0.27.0.0 (#126), 2026-10-29 (A3; 716 Sitzungen of WP 18–21, 85 on the reviewed exclusion list)
- Global header nav links to a page a build didn't write when its feature is off: closed as moot, 2026-10-31
- Make the build revision reproducible before the release script passes a tag: v0.26.0.0 (#123), 2026-10-31
- Fakt cards cut off the caveats of `knappste-abstimmung` and `meiste-abweichler`: v0.25.1.0 (#120), 2026-10-31
- Link the vote panel's "namentlich" wording to `bundestag.html`: v0.25.1.0 (#120), 2026-10-31
- Audit every `data_dictionary.json` definition against the code that writes the column: v0.25.0.0 (#121), 2026-10-31
- Codebook (`DATA.md`) and recipe result CSVs in the release: v0.25.0.0 (#121), 2026-10-29
- Call only current MdBs "Abgeordnete" on the Personenseiten: v0.24.1.0 (#119), 2026-10-30
- "So arbeitet der Bundestag" explainer page: v0.24.1.0 (#119), 2026-10-30
- Fakt der Woche, stop crediting a bundled TOP's Reden to one Vorgang (`meistdiskutierter-vorgang`): v0.24.1.0 (#119), 2026-10-30
- The demo fixture predates the A1 Rede rules (16 Reden in the fixture, 14 from today's parser): v0.24.1.0 (#119), 2026-10-30
- The Bundestag XML gives one Redner-ID to two people (11005304): v0.12.0.0 (#81), 2026-10-02
- `2/3-Mehrheit` phrasing can spuriously trip the document-number mismatch check: v0.23.6.0 (#118), 2026-10-29
- A Drucksache reference can be a URL fragment: v0.23.6.0 (#118), 2026-10-29
- Validate remote-manifest recipes before showing their SQL: v0.23.6.0 (#118), 2026-10-29
- Bill overview polish: same-day step ties: v0.23.5.0 (#116), 2026-10-29
- Combined Antrag titles render as one four-line bold block on puls.html: v0.23.3.0 (#115), 2026-10-29
- Staleness of the "Aktueller Puls" week is only gray meta text: v0.23.2.0 (#114), 2026-10-29
- Say "Woche mit Sitzung", not "Sitzungswoche", for the reporting period: v0.23.2.0 (#114), 2026-10-29
- Bill overview: accent-insensitive search: v0.23.1.0 (#112), 2026-10-28
- Week comparison with no basis still draws every n/a slot: v0.22.1.0, 2026-10-26
- Vote reading misses half the inverted votes and never stores it: v0.22.0.0 (#109), 2026-10-24
- Test the independently loaded historical parser and classifier: v0.21.1.0 (#108), 2026-10-23
- Debattenprofil counts Tagesordnungspunkte, and "Wieder auf der Tagesordnung" replaces "Verfahren, die zurückkehren": 2026-10-23
- Document `--protocol-wahlperiode` in the README: v0.20.6.2 (#104), 2026-10-22
- Fakt der Woche, copy fixes from the glossary review: v0.20.7.0 (#105), 2026-10-23
- Add an accessible role to bill search controls: v0.20.6.1 (#103), 2026-10-22
- Cite protocols as „BT-PlPr." per DIP no. 4c: v0.20.6.0 (#102), 2026-10-22
- Tag the abgeordnetenwatch MP columns with their real source: v0.20.5.1 (#101), 2026-10-22
- Stop calling a Plenarstelle a "Debatte" on the bill pages: v0.20.5.0 (#100), 2026-10-22
- Rename the "Aufmerksamkeitsrang" sidebar and fix its description: v0.20.4.0 (#99), 2026-10-21
- Recipe copy: compare the selection by range, not by text: 2026-10-21
- Keep keyboard focus on reset, and reopen a speech on a repeated link click: v0.20.2.0 (#97), 2026-10-20
- Politikfelder: harden the Vorgang fetch and the repersist guard: v0.20.1.0 (#95), 2026-10-20
- A.2 test follow-ups: v0.19.0.0 (#91), 2026-10-18
- A.2 third ship round: deferred findings: v0.19.0.0 (#91), 2026-10-18
- Politikfeld tags on Tagesordnungspunkte and votes: v0.20.0.0 (#93), 2026-10-19
- Credit a Zwischenfrage to the MdB who asked it, and keep Gastansprachen out of speech counts: v0.15.0.0 (#85), 2026-10-05
- A1 classifier precision: measure and tighten the Kurzintervention and Fragestunde rules: v0.15.0.0 (#85), 2026-10-05
- Stale derived data after `--offline --repersist`: v0.15.0.0 (#85), 2026-10-05
- Regenerate the architecture diagram for the Rede/Beitrag split: v0.15.0.0 (#85), 2026-10-05
- Zu Protokoll gegebene Reden: decide what they are, then store them: v0.15.0.0 (#85), 2026-10-05
- Roll-call member rows link to external profiles, never to our own MP pages: v0.14.0.0 (#84), 2026-10-04
- Detect Kurzinterventionen and Erwiderungen, and stop counting them as Reden → #68; Stop counting the Fragen and Antworten of the Befragung and Fragestunde as Reden → #70: v0.13.0.0 (#80), 2026-10-03
- render_html mutates the report it renders: v0.12.0.0 (#81), 2026-10-02
- Match roll-call votes to a TOP when Drucksache numbers fail: v0.10.0.0 (#79), 2026-09-30
- Inverted-vote reading for Beschlussempfehlungen ("Ja = Antrag ablehnen"): v0.10.0.0 (#79), 2026-09-30
- Majority rule for derived vote outcomes (Art. 79(2), 67, 68 GG): v0.10.0.0 (#79), 2026-09-30
- Vote outcome badge, linked Drucksache and XLSX source on the vote panel: v0.7.0.0 (#73), 2026-09-26
- Votes archive across sittings (`votes/index.html`): v0.7.0.0 (#73), 2026-09-26
- Current-TOP highlight in the ranking sidebar: v0.6.6.0 (#72), 2026-09-26
- Weekday-matched Wochenvergleich when sitting counts differ: v0.6.5.0 (#67), 2026-09-25
- Enforce the Python version floor: v0.6.4.0 (#66), 2026-09-25
- CONTRIBUTING.md: v0.6.4.0 (#66), 2026-09-25
- Regenerate the architecture diagram for the Daten export step: v0.6.4.0 (#66), 2026-09-25
- Move the hidden dev-view API dump below the dossier content: 2026-09-25
- Dossier h1 shows the session, "Bundestag-Puls" moves to the eyebrow: 2026-09-25
- Site-wide `:visited` and `:focus-visible` rules in `global_header_styles`: 2026-09-25
- Stop persisting `speeches.paragraphs_json`: 2026-09-25
- Escape the pre-existing `index` interpolation in the dossier renderer: 2026-09-25
- `agenda_topic()`, the topic line for the Fakten cards: v0.6.0.0, 2026-09-24
- `parties.name` list-repr duplicates: v0.6.0.0, 2026-09-24
- Fakt der Woche, A0: read-only replay and sample cards (the test run): v0.6.0.0, 2026-09-24
- Fakt der Woche, A1: engine in the build, pages, Methodik, export: v0.6.0.0, 2026-09-24
- Fakt der Woche, four more weekly metrics: v0.6.0.0, 2026-09-24
- Fakt der Woche, the monthly post: v0.6.0.0, 2026-09-24
- Guard external payload links with shared source validation: v0.5.0.0, 2026-09-19
- Check that roll-call votes are still being acquired after June 2026: v0.8.0.0 (#75), 2026-09-29
- One Zusammenschluss per `parties` row: v0.9.0.0 (#77), 2026-09-29
- Credit a Rede's text only to its Redner: v0.9.0.0 (#77), 2026-09-29
- Say "nicht abgegeben", never "Abwesend", and stop inventing a Mehrheitsvotum: v0.9.0.0 (#77), 2026-09-29
- One Abweichung rule: exclude fraktionslose MdBs from `r3-abweichler`, drop "Linie" from the wording: v0.9.0.0 (#77), 2026-09-29
- Sprechrolle per Rede, no "Regierung" party (ADR 0001, data half): v0.9.0.0 (#77), 2026-09-29
- Make the Namensabgleich unique, and stop treating name-found ids as proof: v0.9.0.0 (#77), 2026-09-29
- Only Gesetzgebungen on the bills pages, and call them "Gesetzesvorhaben": v0.9.0.0 (#77), 2026-09-29
