# TODOS

Open work, grouped by area. The roadmap orders the items that lead to v1. Every other item keeps its own priority. Finished items get one line each under Completed. This file was last cleaned up on 2026-11-02, against main v0.31.0.0, brought up to date on 2026-11-04, against v0.32.0.0, and checked entry by entry on 2026-11-14, against v0.41.0.0. The roadmap was rewritten on 2026-11-06 from the owner's answers in `docs/plans/v1-scope-review.md`.

## Roadmap to v1 (updated 2026-11-06)

The goal comes from PRODUCT.md: a citable dataset for WP 18 to the present, and one site with two equal angles, the daily view and long-term analysis. Scope decisions: `docs/plans/v1-scope-review.md`. Items are named by their headings below. There are three stages, and the data comes first.

**Done so far** (see Completed):
- A1 what counts as a Rede; A2 stable ids; A3 coverage run (v0.27.0.0).
- A4 slices 0 and 1 (v0.29.0.0, v0.32.0.0).
- B1–B4, the daily vote panel. C1, Fraktion seat counts (v0.31.0.0).
- The code half of D: licence files, Impressum and Datenschutz pages (v0.30.0.0), release script, data changelog, CITATION.cff (v0.26.0.0), abgeordnetenwatch source tags (v0.20.5.1).
- E4 roll-call re-filing (v0.34.0.0), shared Redner-IDs (v0.35.0.0), coverage gate PR 1 and PR 2 (v0.37.0.0, v0.39.0.0, ADR 0005), ADR 0004 kinds (v0.40.0.0), the registry fix (v0.41.0.0). A fresh reference store of 718 sittings (2026-11-12).

**Stage 1: the data release.** Needs no redesign, no site host and no A4 slice.
1. "Coverage gate before the first data release". Today 801 sittings after T4 (2026-11-17): WP 18 242 of 245, WP 19 all 239. 18/20 stays out, 18/62 and 18/90 wait for a rule, and 21/107 to 21/109 wait for the next online update.
2. Correctness P1s:
   - ~~"Correct the WP 19/20 roll-call group misattributions (E4)", merged as #138; the repersist is owed.~~ **Done 2026-11-12:** the owner rebuilt the store online from 28799ac instead of repersisting it. The new reference store, `.context/dip-pulse-site`, holds the E4 correction exactly as recorded: 100 Stimmen, 55 roll-calls, the six MdBs and the committed TSV byte for byte (`docs/plans/e4-repersist.md`, "Outcome").
   - ~~"The carried-forward registry diverges from a fresh build after A3", part 2, with "Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs".~~ **Done 2026-11-13** (see Completed). Follow-ups: "Roster MdB records that never join their speaker", "Government-office DIP records: a second person without a page", "Registry fix review: deferred findings".
   - ADR 0004 kinds: built (see Completed); the owner decisions left are in "ADR 0004 follow-ups".
   - ~~Plan item 1.5 of "A3 /gstack-ship review: deferred findings".~~ Measured 2026-11-12: 937 of 945 WP 18/19 MdB ids find their abgeordnetenwatch profile, no wrong person ([a3-phase4.md](docs/plans/a3-phase4.md), "Plan item 1.5"). Follow-ups: "abgeordnetenwatch profiles for WP 18/19: what item 1.5 leaves open".
   - "Check that vote links are right".
   - ~~Before T4: facts must treat a sitting with withheld Reden as partial (P1 under "Found by PR 2's ship review" in the coverage gate entry).~~ **Built in PR A of `docs/plans/withheld-before-t4.md`** (2026-11-14, ADR 0005 "Facts").
3. "Main and stable releases": the review checklist, the stability policy in `CLAUDE.md`.
4. "Rename the project to open-parlament" and "Comparison and joinable ids in DATA.md".
5. Owner inputs: the e-mail for "Settle the roll-call source for redistribution" (best sent early: the coverage gate leans on votes, and a no changes their source), the terms in "Settle the MdB-Stammdaten redistribution terms", a Zenodo account, the trademark check.
6. The first release: the first real `--publish` of "Write the release script", "A DOI per release and a citation file" (DOI on stable releases only). Items 1–5 of "Release pipeline: deferred /ship review findings", which had to come first, are done (2026-11-17).
7. "Public repository: follow-ups".

**Stage 2: the public site.** Daily view plus one analysis.
1. "Split the dataset from the site" (A4), "Apply DESIGN.md to the site" and "Apply the v1 surface list", in the order of `docs/plans/render-layer-and-order.md` (decided 2026-11-10):
   - step 0, the surface cuts;
   - step 1, the shared layer (`scripts/render/`, one stylesheet, fonts, page shell);
   - step 2, the pilot restyle of `votes/index.html`;
   - then each page group as move and port (the A4 slice, strict oracle), then restyle (content oracle), never both in one PR.

   Slice 11 dissolves into the per-page moves and a closing PR. All of it comes before going public. Slice details are in `docs/plans/a4-site-from-release.md`. Main is at schema 12 and export format 18 (v0.41.0.0), so the next slice takes the numbers after those. Decided: D8 no summaries, D9 no new third-party data, D10 both dumps dropped.
2. ~~"Persist or prove the vote outcome and Abweichler count", before slice 2.~~ **Done in #160 (v0.44.0.0):** schema 13, export format 19.
3. "Politikfelder over time: which Zusammenschluss emphasises what", the first analysis. It takes C1's seat table where it needs a denominator. Agenda-item tag coverage in WP 18 is 60.7% (1,445 of 2,381 items, the tagging replayed over the reports of the 801-sitting store on 2026-11-18; its stored tables read 1,443 until the next repersist; 59.7% was measured before T4): check it before calling the analysis good enough. The Reden-character coverage in `docs/plans/v1-scope-review.md` E9 (92.7% for WP 18) is still the 2026-11-06 measure: in the stored tables of the 801-sitting store, 91.6% of WP 18 Reden characters sit under a TOP with a Politikfeld (71,915,490 of 78,488,817, read 2026-11-19), and 91.9% once the two Einzelplan 21 TOPs (25 Reden, 192,790 characters) are repersisted. Re-measure all four Wahlperioden with the analysis.
4. Abstimmungen: "B4 extractive fallback: finish validation locally" and the rest of "Abstimmungen for the daily view".
5. "Site hosting plan": a German host with SSH, provider to pick; `generation_file_href` changes; `data/` is not deployed wholesale; the deploy gate. Then the Impressum inputs and Datenschutz values.
6. Automatic main releases: "Scheduled data-release workflow", with an alert when an update fails.
7. "Reader test before launch".

**Stage 3: further analyses,** each when ready.
1. "Diskursanalyse: precomputed term series per Zusammenschluss and month". Term lists are confirmed; the neutrality review gates publication.
2. "Zwischenrufe: parse `<kommentar>` and count reactions per Fraktion".
3. "Muster" and "Präsenz".

**Later:** AI summaries and the LLM-content items, "Rebuild Fakt der Woche", the XLSX roll-call source, Puls and copy fixes. WP 1–17 come after v1, because the DIP catalog has no structured XML for them.

## v1 scope items (2026-11-06)

### Coverage gate before the first data release

**What:** The reference store holds 801 sittings since T4 (2026-11-17), up from 718; 18/20, 18/62 and 18/90 stay on the record, and 21/107 to 21/109 (published by DIP after T4 began) wait for the next online update. Decision N1 (2026-11-07) replaces the whole-sitting rule of 2026-10-22: one refused unit no longer keeps out a sitting. Before the first release:
1. Keep each sitting and its TOPs, Drucksache links and votes. Withhold only refused `<rede>` units, flagged with a reason, text kept, outside all Reden counts. Record this in an ADR. **Built in coverage gate PR 2 (2026-11-13, ADR 0005, `docs/plans/coverage-gate-pr2.md`):** located refusals and reviewed entries are withheld into `withheld_units`/`withheld_turns`; speech rule 8, schema 12, export format 17.
2. Account for every unit: each `<rede>` id in a sitting's XML ends up stored, withheld with a reason, or excluded by a named rule such as §31. The build refuses a sitting that does not add up. This would have caught "Reden the parser drops without refusing". **Reconciliation done in v0.37.0.0 (2026-11-12, coverage gate PR 1):** every `<rede>` now ends stored, procedural or excluded by a named rule, or the sitting is refused; "withheld with a reason" arrives with PR 2.
3. Counts name the units they omit as well as the sittings. Coverage is published per year, by sittings and by units, and the withheld share by words per sitting, year and Fraktion (N9). **Built in PR 2:** DATA.md "Abdeckung nach Jahr und zurückgehaltene Reden" and the Daten page; the share is own words over own words of all Reden.
4. A written bar: a sitting stays out whole only with a named source defect, or a defect that cannot be narrowed to single units. 18/20, whose file holds sitting 21, stays out. Replace the bare "excluded" in `coverage-exclusions.json` with each sitting's real reason. **Built in PR 2:** reason codes `source_defect`, `not_narrowable`, `awaiting_rule`, `awaiting_acquisition` plus a sentence; the loader refuses a bare "excluded". The 86 reasons of the pre-T4 record are in `docs/plans/coverage-gate-pr2/coverage-exclusions.json`; it was copied into the reference store's `data/` on 2026-11-14. Since T4 (2026-11-17) the store's own `data/coverage-exclusions.json` is the current record, with 3 entries (18/20 `source_defect`, 18/62 and 18/90 `awaiting_rule`). Do not seed a store from the 86-entry file: it would keep the 83 restored sittings out again.
5. Parser rounds then shrink the withheld list, one owner-approved rule at a time.
6. Fetch the 85 sittings. Their votes, TOPs and links were never acquired (decision 0 of 2026-10-22). Fetch the XML first and scan it for shared ids and Reden outside a TOP. Check whether the bulk prefetch covers the rest; otherwise about 26 DIP requests per sitting, about 2,200 in all [estimated from A3]. **XML fetched and audited 2026-11-12** (`docs/plans/withholding-preflight/report.md`): re-audited 2026-11-13 after #147 and after the parser learned to read 19/36's Anlage 2 (a Zu-Protokoll continuation by Stamm-Fibich, TOP 5, printed under the title "Liste der entschuldigten Abgeordneten"; `docs/source-errors.md` E8): 71 of the 85 parse once single Reden are withheld, all refusals `located_nested_contribution` (107 markers; 90 Reden, 94,707 words; share per sitting median 1.69%, max 8.42%); 13 parse with no refusal (the N7, ADR 0004 and round 2 sittings below); 18/20 is rejected as expected. Between the two re-audits 19/36 refused as `rede_reconciliation` (70 / 89 Reden / 93,582 words / median 1.71%). The votes, TOPs and links are still to acquire. **Planned in `docs/plans/t4-acquire.md`** (owner accepted all nine decisions on 2026-11-15): 83 sittings back (82 of the 85 plus 21/106), about 600 to 800 DIP requests with the bulk caches, N8 on W1's XML before the fetch, T4 before vote-link PR C. **Done 2026-11-17** ([t4-acquire.md](docs/plans/t4-acquire.md), "Outcome"): 83 sittings restored, record 86 → 3 entries (18/20 `source_defect`, 18/62 and 18/90 `awaiting_rule`), 801 protocols, 102 withheld Reden in 74 sittings, votes 619 → 727. 982 DIP requests against the budget of 600 to 800, because of restarts (V4). The store gate passed at adfe50c (V5). Left: the rule and two-sitting run for 18/62 and 18/90 (decision 4), and an online update for 21/107 to 21/109.
7. Measure: votes against the roll-call list, date by date; TOPs restored; the abgeordnetenwatch match share of WP 18/19 Redner (re-run `scripts/measure_aw_match_share.py` on the step 6 output with the same scratch cache, then cite both receipts: the first is `docs/plans/a3-aw-match-share.json`); and a per-sitting comparison with CPP-BT by `rede_id`, surname and tokens. **Done 2026-11-18** ([t4-acquire.md](docs/plans/t4-acquire.md), "Outcome"; receipts in `docs/plans/t4-acquire/`): votes per restored sitting match their list candidates (108 = 101 + 7, 0 fetch errors), TOPs equal the XML in every sitting (8,189), E4 re-files 157 Stimmen in 87 roll-calls, all in its windows, and the figures moved are named old → new (M6) with the coverage tables for N9 (M7). The whole roll-call list (74 pages, 2026-11-18) is accounted for: 727 entries stored under their dates, 1 on 18/20, and 9 on 21/108 and 21/109 for the next update. The 63 vote-id gaps left are ids the list never shows. abgeordnetenwatch (M3): 941 / 949 WP 18/19 MdB found (0.9916, was 937 / 945), 32,361 / 32,908 Reden (0.9834, was 0.9827), the same 8 flags, 12 of 12 name links (Laumann new, read: right person). CPP-BT (M4): no id of ours missing, all 972 new difference rows in restored sittings and explained; the 77 procedural ids were added to `scripts/cpp_bt_known_differences.tsv`. M4 found 33 more speeches printed as `<name>` and counted nowhere ("ADR 0004 follow-ups").
   For `erste-reden` v3 (ADR 0005 "Facts"), also measure on the T4 store: how many withheld Reden carry a Redner-ID that `scripts/person_corrections.json` partitions (expected 0; each one drops every sharer from the debut count), and how many carry a Redner-ID that no `mps` row holds. The second binds no one, so if its speaker has stored Reden under a record without a Redner-ID, their next stored Rede posts as a debut. On the 2026-11-14 store, 8 persons with Reden have no record with a Redner-ID (11 Reden): 5 Länder or government guests, one MdB (Maika Friemann-Jennert), Peter Altmaier filed by name and party, and one record named `Unbekannt`. Look at each such withheld Rede before the gate passes. The gate's `every_withheld_rede_has_a_redner_id` check (PR B) must read true. **Answered by M5 of [t4-acquire.md](docs/plans/t4-acquire.md) (2026-11-18):** 0 withheld Reden carry a partitioned Redner-ID, 0 carry one no `mps` row holds, and the gate check reads true. The persons without a record with a Redner-ID went 8 → 9: Monika Heinold (18/180), whom #171's partition of `999990055` files under her DIP person. No withheld Rede carries her name or that id, so none can post a false debut.
8. Rebuild the store on current main and run the gate on it. **Replayed 2026-11-14:** the reference store `.context/dip-pulse-site` went through one `--offline --repersist` on v0.41.0.0 (schema 11 → 12, speech rule 9): Reden 54,937 → 54,855, Personenseiten 1,658, 0 withheld units; the pre-replay copy is `.context/dip-pulse-site.pre-v0.41`. **Done 2026-11-17 with T4:** the store gate ran on the 801-sitting store at adfe50c (v0.46.6.0) and passed all 15 checks (`docs/plans/t4-acquire.md`, V5). A rebuild on a later main still needs a fresh gate run before the release. The first release must not go out while any exclusion still reads `awaiting_rule` or `awaiting_acquisition`: the bar allows only `source_defect` and `not_narrowable`. Enforced by PR B of `docs/plans/withheld-before-t4.md` (2026-11-14) in `publish_dip_pulse_data.run_release`: `--publish` refuses while any exclusion reads another code, the first release included; dry runs stay allowed (owner decision D6, 2026-11-14).

**Found by PR 2's re-measure at its tip (2026-11-13), for T4 and ADR 0004:**
- ~~**19/36 needs an annex rule.**~~ **Done by #150 (2026-11-13):** the parser reads its Anlage 2 as the Zu-Protokoll continuation its heading names (`MISTITLED_ZU_PROTOKOLL`, `docs/source-errors.md` E8). Re-measured on PR 2 merged with #150: 19/36 parses once `ID193612200` is withheld (954 own and 171 nested words) and passes the persist role check.
- ~~**18/173 and 18/193 wait on ADR 0004 too.**~~ **Done by v0.40.0.0 (ADR 0004):** the reviewed list names their presidium `<rede>`s (`ID1817301900`, `ID1819300700`) and 18/215's; all three, and the seven, parse and pass the persist role check on W1's XML. `coverage-exclusions.json` records the ten as `awaiting_acquisition`.
- **So T4 can restore 82 of the 85 plus 21/106:** 68 that parse once withheld and persist, N7's four with their reviewed entries, and the ten ADR 0004 sittings (v0.40.0.0). 18/62 and 18/90 wait on a rule for a Vizepräsidentin's Nachfrage in the Fragestunde, and 18/20 stays out.

**Found by PR 2's ship review (2026-11-13), latent until a withheld Rede is stored (T4 or 21/106):**
- ~~**P1, before T4: facts must treat a sitting with withheld Reden as partial.**~~ **Built in PR A of `docs/plans/withheld-before-t4.md` (2026-11-14):** a sitting with `withheld_rede_count > 0` is incomplete for speeches with the note "Sitzung X: N Reden zurückgehalten", an absent count is unknown, `erste-reden` v3 ranks withheld Reden beside stored ones, and the backfill leaves a sitting that only withheld Reden. Original finding: `facts.completeness_from_reports` (`scripts/facts.py:940`) counts a sitting's speeches as complete once its XML parsed. Before ADR 0005 a sitting with a refused Rede stayed out and the week's speech facts were withheld as `not_persisted`; after T4 they would publish on partial data with no gap note. For `erste-reden` it is a false statement: if a member's real debut Rede is withheld, their next stored Rede is posted as their first. Fix: read `validation_summary.withheld_rede_count > 0` as a partial speeches gap with a gap note ("Sitzung X: N Reden zurückgehalten"), and withhold `erste-reden` for anyone with a withheld Rede on or before their first stored one. Test-first; record the rule in ADR 0005.
- ~~**P3: the refusal for a report stale only by its reviewed digest names the wrong cause.**~~ **Built in PR B of `docs/plans/withheld-before-t4.md` (2026-11-14):** `stale_causes` names the speech rule, the reviewed list or both. Original finding: `require_parsed_reports` (`scripts/build_dip_pulse_site.py`) says the report "predates the current speech-counting rule" when it was parsed under other reviewed-list entries and its XML is not cached. The fix (`--fetch-xml`, then `--offline --repersist`) is the same; say which of the two made it stale.
- ~~**P2, before the first release: the withheld cap trusts the manifest's own list**~~ **Built in PR B of `docs/plans/withheld-before-t4.md` (2026-11-14):** `release_changes.withheld_list` refuses a missing or malformed list (a previous one before format 17 may lack it), and `publish_dip_pulse_data.withheld_export_problem` matches it against the exported `withheld_units` rows. Original finding: (Codex, twice, at PR 2's ship). `release_changes.withheld_changes` reads a missing or empty `withheld_reden` as "none withheld", and nothing reconciles the list with the exported `withheld_units` rows, so a format-17 manifest with the list removed passes the cap of two with no confirmation and no changelog lines. Our exporter always writes it, so only a hand-edited manifest reaches this. Fix: require the list in a current manifest (allow its absence only in a previous one before format 17) and check it against the export's withheld rows.
- ~~**P3: a report without `reviewed_digest` is taken as current.**~~ **Built in PR B of `docs/plans/withheld-before-t4.md` (2026-11-14):** an absent digest is stale; the demo fixture carries its parsed digest, pinned by a test. Original finding: `persist_report` writes the current list's digest when the key is absent, and `unparsed_reports` treats the absence as fresh (Codex). Every parse since rule 8 sets the key, so only hand-built reports reach this, among them the committed demo fixture `tests/fixtures/demo-report-21-84.json`. Fix: treat an absent digest as stale, and have `extract_demo_fixture.py` keep the parsed digest.
- ~~**P3: the store gate's "withheld also counted" check misses nested Beiträge**~~ **Built in PR B of `docs/plans/withheld-before-t4.md` (2026-11-14):** the check also flags a stored Beitrag whose `parent_rede_id` is the withheld Rede. Original finding: (Codex). `validate_store_gate.withheld_also_counted` compares equal `rede_id` only, so a counted `nested:R2:2` whose `parent_rede_id` is a withheld R2 passes. The parser's commit-on-finish never emits one; extend the query as a guard on that.
- ~~**P3: a missing `scripts/reviewed_units.json` reads as an empty list**~~ **Built in PR B of `docs/plans/withheld-before-t4.md` (2026-11-14):** `reviewed_units.load` refuses it. Original finding: (red team and the targeted gate reader). `reviewed_units.load` turns `FileNotFoundError` into no entries, so a deleted or renamed file silently releases the five reviewed Reden after the forced repersist. The file is checked in; refuse its absence.
- **P3: pass-1 diagnostics of a withheld Rede stay in `xml_turn_diagnostics`** (adversarial pass). A `merged_erwiderung`, `merged_rede` or procedural entry that targets a withheld Rede is kept; only `check_withhold_one.py` reads these, and nothing persists them. Fix (corrected 2026-11-14, `docs/plans/withheld-before-t4.md` B7): keep them, because ADR 0005 D7 records "partly merged into X, rest withheld" there; mark them `withheld` if they ever reach the store or a page. The only renderer reader, `reviewed_procedural`, looks for `(reviewed)` presidium evidence a withheld Rede cannot carry.
- ~~**P3: the reviewed digest is keyed by two spellings of the sitting**~~ **Built in PR B of `docs/plans/withheld-before-t4.md` (2026-11-14):** the online `build_report` refuses an XML whose `wahlperiode/sitzung-nr` differs from `dokumentnummer` (one helper, `xml_sitting_mismatch`, for the online parse, `--fetch-xml` and the re-parse), so both spellings are equal for every stored report; 718 of 718 are on the reference store. Original finding: (adversarial pass): the parse by the XML's `wahlperiode/sitzung-nr`, persist and the cache check by `dokumentnummer`. They agree for all five listed sittings; a padded `dokumentnummer` with a listed entry would read as stale on every run. Key both by one normalized number.

**Decided 2026-11-07, in `docs/plans/v1-scope-review.md`:**
- N7 A: 18/2, 18/29, 18/83 and 19/25 have known wrong units and no refusal, so step 1 alone does not reach them. They come back with a reviewed list of single units to withhold, each with a reason, in the same withheld state as step 1.
- N8 A: restored sittings get the same merge and attribution review as the 400 kept sittings, about human ~3 days / CC ~half a day [estimated]. Any wrong unit goes on that withheld list with a reason. The gate in step 8 does not pass until this review has.

Also listed with no refusal, and not part of N7: 18/178, 18/223, 18/245, 19/1, 19/9, 19/19 and 19/73 parse with their ADR 0004 kinds since that build and leave the list in step 6's fetch, after the N8 review; 18/1 parses too since its nested acceptance is read (6d); 18/62 and 18/90 stay out by the owner's round 2 decision.

**21/106 joined the list on 2026-11-12 (owner, during the fresh build).** The parser refuses `21/106 Zusatzpunkt 13: unresolved nested contribution at ID2110609100:4 marker 2`. In Bessin's (AfD) Rede, the chair asks whether she allows a Zwischenfrage from Edis (Die Linke). She says "Selbstverständlich" (marker 2), then answers a heckle from the Regierungsbank in a second turn before Edis is called, and only then does Edis ask. No rule covers a same-speaker turn between the grant and the question. This is a parser gap, not a source defect, so under step 4's bar 21/106 comes back as one withheld Rede (or with a rule) and leaves the list with `--include-document-number 21/106`. It is one of three sittings with XML after the old store's 21/103. The other two, 21/104 and 21/105, are in the fresh store; 21/107 to 21/109 had no XML on 2026-11-12. The list now holds 86.

The implementer must prove (answered by PR 1 and PR 2, v0.37.0.0 and v0.39.0.0: `docs/plans/coverage-gate-pr2.md`, `scripts/check_withhold_one.py`, ADR 0005; the classes that could not be narrowed are on the record as `awaiting_rule`, 18/62 and 18/90. Line numbers are from 2026-11-09: `split_nested_reden` is now `validate_dip_protocol.py:1045`, called at `:1718`, and the pass-1 merge rules sit near `:1830-1950`):
- withholding one unit leaves every other unit's id, sequence and text unchanged, although classification carries state across turns and TOPs;
- each refusal class has a home: Fragestunde markers have no rede id, Befragung turns raise a different error, "conflicting roles" is sitting-wide, and 18/90's defect is outside any `<rede>`. A class that cannot be narrowed stays out under the bar;
- step 2 also accounts for Fragestunde turns, which have no `rede_id`;
- step 2 inventories the raw XML before `split_nested_reden` (`validate_dip_protocol.py:943`, called at `:1396`), because that and two other functions edit the tree, and a source id in storage does not prove its split-off units survived;
- withholding has a written rule for split-off units and for text moved between units (`merged_rede`, `merged_erwiderung`, `resumed`, `merged_zwischenfrage`, `:1450-1562`).

**Settled by `/plan-eng-review` on 2026-11-09 (`docs/plans/v1-scope-review.md`, "Eng review: the withholding build", tasks W1-W8):**
- Two PRs: first the raw XML inventory and reconciliation, then withholding.
- First fetch only the XML of the 85 and audit it, before PR 2.
- Withheld units go in a separate `withheld_units` table.
- `speeches.sequence` becomes the source position.
- Only the refused part of a split Rede is withheld. Text that pass 1 moved out of it stays where it went.
- A weekly release goes out and lists newly withheld Reden, but stops above 2.
- The audit script is deleted in PR 2.

All ten choices were answered by the owner's adjudicator hook.

**N9, decided 2026-11-09:** no bar on sittings. Every sitting stays in, and each analysis on the site declares a minimum coverage, marking a period below it as thin. The owner sets the number after step 6's fetch measures the withheld share by words.

**N10, decided 2026-11-09:** a reviewed sample of vote links before the first release, in "Check that vote links are right".

Withholding works on the whole `<rede>`, as decided. After round 2's rules that means 90 Reden in 71 sittings (W1 run, 2026-11-12, and again after #147 and #150 on 2026-11-13; the blockers file lists 86 Reden, 87 counting ID1802102900 under both 18/20 and 18/21), and no refused marker is a Rede's first, so each withheld Rede includes an opening nobody questioned. The ADR says so. `scripts/audit_offline_turns.py` showed the idea; PR 2 builds it into the parser and retires the script (D10).

**Why:** The sittings left out hold links no single other dataset was found to combine: the store has 0 of its 556 votes on those dates. For those years the parts exist separately, ParlLawSpeech to 2021 and BTVote to WP 19. Long-term analysis needs those years too. Measured against CPP-BT on 2026-11-07, the sittings left out are longer than the rest, with median Reden 70 against 54 in WP 18 and 125 against 102.5 in WP 19. By words, we hold 69.0% of 2018, 73.0% of 2014 and 73.1% of 2015. A trend across those years compares unlike coverage, and the shortfall falls on the longest days.

**Context:** Refused markers after round 2's rules: 103 in 69 sittings, at most 4 per sitting (`docs/plans/a3-wp18-19-round2-blockers.tsv`). Fallback: release WP 20 and 21 first as a complete set, if the first of the proofs above fails or the per-unit change passes twice its estimate. Evidence: `docs/research/bundestag-corpora-landscape-2026-11.md`, `docs/plans/v1-scope-review.md` (N1, N7, N8).

**Effort:** L (the per-unit change alone: human ~3–4 weeks / CC ~3–5 days, estimated; first stated as ~2 weeks / ~1–2 days)
**Priority:** P1
**Depends on:** the correctness P1s of stage 1

### Withheld-Reden PRs A and B: deferred review findings (2026-11-15)

Found by the code review of PR A (127e1c2) and PR B (fc1676e) of `docs/plans/withheld-before-t4.md`. None moves a figure today; fix when the code is next touched.

- **A, console: the incomplete report's last line can be false.** `build_dip_pulse_site.format_incomplete_report` prints "Fix: none available now; run an online update once DIP publishes the missing protocols" whenever `acquirable` is empty. After T4 a store whose only gaps are withheld-Reden sittings gets that line, though nothing awaits DIP: the line above it ("N sittings hold withheld Reden …") names the real remedy. The same false line predates PR A for a store whose only gaps are structural vote gaps. Fix: say which remedy applies (parser rule or reviewed list, then `--offline --repersist`; a better match rule; a larger `--vote-scan-pages`) and keep "online update" for the not-yet-published case.
- **A, console: the partial counter prints the reason code.** The same function lists "speeches: withheld_reden (N×)" under "in the store but not fully acquired" (a deliberate choice of PR A, so the count does not split per number). A sitting with withheld Reden and a votes gap, built with votes off, lands in `incomplete_sitting_protocols`'s `vote_only` list ("held back only by votes"), so main's `[backfill]` withheld line does not name it. Word both for a reader.
- **A, latent: `facts.gap_note` renders "None Reden zurückgehalten"** for a gap with reason `withheld_reden` and no count (`gap.get("withheld_reden")` has no fallback). `completeness_from_reports` always sets the count with the reason, and `period_gaps` copies it, so no input reaches it today.
- **A, console: one sitting can be named on two lines.** In `format_incomplete_report`, a sitting that is structural for votes and also holds withheld Reden is named both on the vote-structural line and on the withheld line. Both statements are true and no figure moves; say once that it is on both, or name it only on the line of its first gap. Found by /ship's adversarial pass on PR A.
- **A, hygiene:** the comment of `test_a_sitting_held_back_only_by_withheld_reden_is_not_reacquired` (`tests/test_backfill.py`) still names `_structural_vote_gap`, renamed `_structural_gap` by PR A.
- **B, design: `every_withheld_rede_has_a_redner_id` has no pass path for a Rede the source prints with `<redner id="">`.** 4 of about 77,000 cached Reden do (19/2 `ID19205800` Altmaier, 18/46 `ID1804617400`, 18/76 `ID1807611000`, 18/104 `ID1810402200`); none is in the 85 sittings T4 acquires. If one is ever withheld, the gate fails until the owner decides how it binds (item 7 of the coverage gate entry already asks for a look at each).
- ~~**B, robustness: a missing `scripts/reviewed_units.json` is a traceback, not a clean stop, in two tools.**~~ **Done 2026-11-18 for `validate_store_gate.main` (exit 2), `measure_aw_match_share.main` (exit 2) and `build_demo_site.main` (exit 1):** each loads the list at startup and prints `ERROR [reviewed-units]`. **Still open:** `reparse_cached_xml`'s except list lacks `ReviewedUnitsError`, and the stale-report paths (`unparsed_reports`, `warn_unparsed_reports`, `require_parsed_reports`) still raise it as a traceback when called outside a build entry point (both in `build_dip_pulse_site.py`, held by another branch). Original text: `validate_store_gate` (its `--persist-only` order-independence clones) and `measure_aw_match_share` never call `reviewed_units.load()` at startup, and `reparse_cached_xml`'s except list lacks `ReviewedUnitsError`. The gate still fails and the build's own entry points stop cleanly. /ship's adversarial pass on PR B found the same gap in `build_demo_site.build_demo_store` and in the stale-report paths (`unparsed_reports`, `warn_unparsed_reports`, `require_parsed_reports`), which reach `sitting_digest` through `stale_causes`: a missing list fails closed there too, but as a traceback. Fix: load the list at each tool's start.
- **B, latent: the offline re-parse still checks the sitting after the parse** (review of the 2026-11-18 online fix). `build_dip_pulse_site.reparse_cached_xml` runs `parse_protocol_xml` (which applies the reviewed list for the XML's own number) before `reparse_report_xml` reaches `check_xml_belongs_to_report`; only the online `build_report` now compares the root first. A cached `data/xml` file whose root names another sitting and that a stale reviewed entry makes the parser refuse would end `--offline` with a `ReviewedUnitsError` traceback, not a "wrong sitting" `CachedReportError`; adding `ReviewedUnitsError` to the except list (the item above) would still print the generic "not the Plenarprotokoll XML" message. No input reaches it: all 801 cached XMLs of the reference store name their own sitting in the root (checked 2026-11-18), and a file is cached only after the online check or `fetch_missing_xml`'s root check. Fix: in `reparse_cached_xml`, parse the root and run `dip.xml_sitting_mismatch(document_number, dip.xml_root_sitting(root))` before `parse_protocol_xml`, raising `CachedReportError` with the mismatch; `fetch_missing_xml` can use `xml_root_sitting` in place of its hand-built header.
- **B, online sitting check: what the v0.46.28.0 ship review left open** (native adversarial reader, 2026-11-20; none moves a figure, all fail closed):
  1. **A right-sitting `ReviewedUnitsError` or `SprechrolleError` still escapes `build_report` as a traceback.** Both subclass `Exception`, not `ValueError`, so `build_report`'s `except (ET.ParseError, ValueError)` around `parse_protocol_xml` misses them and `build_dossiers_with_progress` re-raises. Predates the branch, which only moved the wrong-sitting case to a refusal. Fix: catch each apart with its own fix pointer (a stale reviewed entry: `scripts/reviewed_units.json`; an unmapped Sprechrolle: the role table).
  2. **A well-formed non-protocol page (an XHTML maintenance page served with HTTP 200) is refused as "it is the XML of /, not of 21/42".** `build_report` never checks `root.tag == "dbtplenarprotokoll"` as `fetch_missing_xml` does. Base printed the same line (the page parsed, then failed the sitting check), so this predates the branch. The refusal is `source_rejected`, which stops the build and points at `--exclude-document-number`, though the cause is a transient outage. Fix: check the root tag first and raise a not-source-rejected `DipError` (source unavailable) so the sitting is skipped, not excluded.
  3. **The missing-dokumentnummer refusal prints "the XML of /" when the root also lacks the attributes** (`xml_sitting_mismatch`). Wording only; no DIP record lacks the field.
  4. **Each sitting's XML is parsed twice online** (`ET.fromstring` for the root check, then again in `parse_protocol_xml`). A few MB per sitting, sequential build; let `parse_protocol_xml` take a root if it ever shows in a profile.
  5. **`measure_aw_match_share` prints an unknown-Fraktion refusal without its fix** (fix-check and red team, pass 2). The replay error now carries the spelling-list remedy in `CachedReportError.fix`, and the script's handler (`measure_aw_match_share.py`, `except (build.CachedReportError, ...)`) raises `UsageError(str(exc))`, which prints only the message. Nothing false prints and it exits 2; it already dropped the `fix` of `require_parsed_reports`' error. Fix: print `f"{exc}. {build.cached_report_fix(exc)}"` for a `CachedReportError`.
  6. **`validate_store_gate --persist-only` lets a `CachedReportError` escape as a traceback** into the child log (it catches only `CachedRosterError`), so an unknown spelling shows without its fix. The traceback predates v0.46.28.0; the gate fails closed. Fix: catch `site.CachedReportError`, print `ERROR [gate]: {exc}. {site.cached_report_fix(exc)}` and exit 2.
  7. **Wording:** the `--repersist` refusal for an error with its own `fix` ends "<fix>. Docs: …" without the "then re-run" the default branch prints.
- **B, docs gaps (found by /ship's docs audit on PR B):** README has no troubleshooting row for "scripts/reviewed_units.json is missing", which now stops every run. CONTRIBUTING and the German README release paragraph do not say that `--publish` refuses while an exclusion awaits acquisition or a rule (ADR 0005 and `docs/project-documentation.md` do). `docs/project-documentation.md`'s `validate_store_gate.py` entry does not list the two withheld-Rede checks, and ADR 0005 names only the Redner-ID one.
- **B, latent: `withheld_export_problem` would merge a duplicate exported row.** It keys the exported `withheld_units` rows by (sitting, Rede-ID), so two identical rows would read as one, while the manifest list refuses a duplicate. No store can export one: `withheld_units` has `UNIQUE(protocol_id, rede_id)` (`persist_dip_pulse_store.py:378`). Count the rows if the export ever stops coming from the store.
- **B, wording:** `stale_clauses` reads "1 predate …" / "1 were parsed …", and a report stale for both causes is counted in both clauses, so they can sum past the header's count. Three older texts still name only the licence as a `--publish` refusal: the `--publish` help in `publish_dip_pulse_data.parse_args`, the header comment of `scripts/publish_dip_pulse_data.sh`, and the dated status note in `docs/designs/daten-page.md` (about line 335).

### Refuse a release while a v1 sitting is neither stored nor excluded

**Done 2026-11-17 (branch `claude/release-script-batch-45ef0a`, owner decision 6 of `docs/plans/t4-acquire.md`):** `publish_dip_pulse_data.unreleased_sittings_problem` reads the DIP catalog the build leaves next to the exports directory (`plenarprotokoll-catalog.json`, or `--catalog`). `--publish` refuses, naming them, while a sitting from WP 18 on that the catalog lists with an XML URL is neither in the export's `protocols` table nor on `coverage.excluded`; the dry run says the same and still builds. A sitting DIP lists without XML (`incomplete_sitting_protocols`' `waiting`) is not refused. Every run refuses a catalog it cannot read or that is not `"authoritative": true`, and `--publish` refuses a catalog that lacks a stored v1 sitting (older than the export). On the reference export of 2026-11-16 it names one sitting, 21/107 (dated 2026-11-11: XML listed, not stored, not excluded). Tests: `MissingSittingTests` in `tests/test_publish_dip_pulse_data.py`. Not done: having `--include-document-number` drop from the record only the sittings the run stored (the refusal now catches what it leaves). Limit (adversarial review, 2026-11-17): the check trusts the catalog the build left; nothing binds that file to the export, so a catalog older than DIP's current list cannot show sittings DIP listed since, and a leftover file from an earlier build passes as long as it lists every stored sitting. Record the catalog's `fetched_at` (or hash) in the manifest at export and compare it at release; that is an export-format change, so it waits for the next format bump.

### N8 findings that are not N8 entries (2026-11-15)

From the N8 review of the 82 restored sittings ([n8-review.md](docs/plans/t4-acquire/n8-review.md); rows in `n8-review.tsv` by `class`). The 10 wrong units N8 found are withheld by the entries of #165 (v0.46.1.0). The two sitting-level defects, 18/158's 37 § 31 declarations printed in the Sitzungsverlauf and 19/13's Befragung under the broken heading "Befr agung", are read by the parser rules of #166 (v0.46.2.0). What follows applies to all 801 sittings:

- **Beiträge stored as Reden** (`storewide_beitrag_as_rede`, 33 in the 82): Kurzinterventionen and Erwiderungen announced in wording `classify_reden` does not read ("hat die Möglichkeit, zu reagieren", "zu einer Erwiderung", a bare name), Erklärungen nach § 30 and § 32 printed as a `<rede>`, and one procedural exchange (19/192 Thomae). This is ADR 0002's precision-first detector. In the 718 stored sittings, 0.6 % (WP 18) and 0.9 % (WP 19) of stored Reden are under 2,500 characters and open without a salutation, against about 1 % in the 82. Measure the class in all 801 sittings, decide a rule with the owner, and replay it with old and new figures. Kurzintervention and Erwiderung counts are checked against DIP's `aktivitaetsart`, which helps: ADR 0002 measured 636 against DIP's 682.
- **Reden zu Protokoll printed inside a TOP** (`storewide_zu_protokoll_in_top`): 18/60 TOPs 17 and 18 and the kept 18/39, 18/46 and 18/54 print the TOP's Reden zu Protokoll as `<rede>`s, which are stored as Reden. The decision of 2026-09-30 types written submissions as `zu_protokoll`. Check whether that decision covers these, and count them.
- **A presidium member's Zwischenfrage read as the chair** (`presidium_member_as_mdb`): 18/113 `ID1811302500`. Pau, printed with her Vizepräsidentin role, asks Castellucci a question, and the turn is ruled `procedural`. Widen D4's rule for 18/62 and 18/90 (`docs/plans/t4-acquire.md`, step 5) to cover it.
- **45 withheld Reden whose refused turn is admissible** (`withheld_admissible`): ordinary granted Zwischenfragen ("Gerne", "Ja, bitte") and announced Kurzinterventionen whose grant wording the rules do not read. They cost coverage, not correctness. The rule rounds of "WP 18/19: nested Erwiderung, Erklärung and Geschäftsordnung turns" can take them as test cases.
- **A floor form `split_nested_reden` misses:** "Als Nächstes für <Fraktion> die Kollegin <Name>" (19/18, Dröge). N8 withholds that Rede by entry. A `NESTED_REDE_FLOOR` form for "Als Nächste(s)" would keep Ernst's and Dröge's Reden instead, but it applies to every sitting, so it needs a replay.

**Priority:** P2. The 33 Beiträge stored as Reden are P1 before the first release if the owner reads them as wrong figures.
**Depends on:** T4 (it measures all 801 sittings).

### Keep the raw vote pages and DIP sitting records (check thoroughly first)

**Status: idea, not specced. Do not build it until the checks below are done and the owner has seen their result.**

**What:** Every online fetch keeps its raw response in the store's private directory, the way the Plenarprotokoll XML is kept in `data/xml/` since A1:
1. The bundestag.de roll-call (namentliche Abstimmung) pages, as fetched.
2. The per-sitting DIP Plenarprotokoll record each report is built from. The person, Vorgang and Drucksache caches already keep DIP's answers, so this part matters less.

`--offline --repersist` would then re-read the raw pages as it re-reads the XML today, and refuse a vote whose raw page is missing.

**Why:** Today the official result, its scope and the page's own Fraktion counts exist only inside the cached report JSON, already parsed. A fix to the vote-page parser cannot be applied offline, and a figure that moves cannot be explained afterwards. Found on 2026-11-12: on the fresh reference store `result_scope = application` is 34, where 24 was recorded. The scope is read at fetch time and the old store is gone, so which 10 are new, and why, cannot be told (E4 verification, `docs/plans/e4-repersist.md` "Outcome").

**Check thoroughly before implementing:**
- **Redistribution:** whether the raw pages may be kept and published. Until "Settle the roll-call source for redistribution" is answered, they stay in `.OUTPUT.private/`, never in the published tree.
- **Disk:** measure the size of the 619 vote pages and the DIP records. Not measured; expected small next to the 5.5 GB store directory.
- **Requests:** what re-fetching all 619 vote pages once costs, so existing sittings get their raw page too. Without it they only get one on their next online fetch. A re-fetch cannot settle the 34 vs 24: the fresh build already fetched every page and the old store is gone. It gives a kept baseline from which a later change can be told.
- **Coverage:** which values in a report come only from a fetch (official result, scope, page counts, anything else), measured from the code, not assumed.
- **Parser:** whether the vote-page parser can re-read a stored page without its fetch context (URL, date, the TOP it was matched to).
- **Refusal:** how a re-persist treats a vote with no raw page, and how a store moves from today's reports to raw pages without a mixed state.
- **Change detection:** whether bundestag.de pages change after publication, and how a changed page is detected and recorded.

**Context:** Raised 2026-11-13 after the fresh store build. The XML precedent: `data/xml/`, README §"Re-persist the cached reports". Related: "Persist or prove the vote outcome and Abweichler count", "Check that vote links are right", "Settle the roll-call source for redistribution".

**Effort:** unknown until the checks are done; roughly one PR for the vote pages and a smaller one for the DIP records [estimated]
**Priority:** P2. Decide before the first data release, because the coverage gate leans on votes.
**Depends on:** the checks above; the redistribution answer for anything published

### Shared Redner-IDs: what the fix leaves open

**What:** The fix of 2026-11-07 (`docs/stable-ids.md`, `docs/source-errors.md` E7; figures in `docs/plans/shared-redner-ids-old-new.tsv`) leaves these:
1. **Dr. Carsten Sieling keeps two pages:** the MdB record `xml:11004157` (7 Reden, 62 Stimmen) and the empty DIP row `dip:1886` (MdBR, Bremen). This predates the fix: a DIP row with no party joins no name+party bucket. A reviewed merge names person keys, which are reissued in a fresh build, so it needs a stable way to name them.
2. ~~**Not scanned: 21/106.**~~ **Done 2026-11-17:** v0.46.6.0 scanned the 719 stored sittings and the 83 T4 sittings' XML and gave `11004105`, `11002190` and `999990055` entries. 21/106 was fetched by T4's last run, whose `reconcile` name check passed (exit 0), so it prints no shared id without an entry.
3. **`999990109` and `11003609` have no entry,** because their second person sits in an annex and a speaker list that are not stored. The Reden fix of 2026-11-07 did not store Tim Ostermann's annex unit of 19/234; if a later rule does, the build refuses until `999990109` has an entry.
4. **The name check does not catch two people who share a word,** such as a given name: a surname change looks the same.
5. **C5 (Föhr/Mende) was not checked against the PDF.** Its six reviewed occurrences and its partition are unchanged, 0 of its units moved.
6. ~~Done 2026-11-17~~ (see Completed, "Shared Redner-IDs: loader checks, role words, one record load", and "Roster and replay-profile edges": `test_a_reparse_copies_no_profile_across_a_shared_id` and `ReparseProfileTests` both drive `reparse_cached_xml`).
7. ~~Done 2026-11-17~~ (see Completed, "Shared Redner-IDs: loader checks, role words, one record load").
8. **`_on_shared_id` knows only `xml:` keys.** An old record keyed `aw:` (a trusted lookup under the shared id) or `profile:` that holds a shared id keeps a dip-only rebind, so a replay differs from a fresh build. None exists in the A3 store. Decide on the record's evidence instead of its key prefix.
9. ~~Done 2026-11-17~~ (see Completed, "Shared Redner-IDs: loader checks, role words, one record load").
10. ~~Done 2026-11-17~~ (see Completed, "Shared Redner-IDs: loader checks, role words, one record load").
11. **`render_dip_pulse_html` corrects only `xml_speakers`;** the `xml_speakers_first` fallback of a legacy truncated item still links the raw shared-id speaker. No cached item hits it today.
12. ~~Done in part, v0.46.10.0~~: office words are dropped from the name check (see Completed, "Shared Redner-IDs: loader checks, role words, one record load"). The rest of the printed office phrase still counts: "Redner-ID name check: what the v0.46.10.0 ship review left open", item 1.
13. **Profile coverage metadata counts raw profiles** (`build_dip_pulse_site.py`, the ready/partial counts), including the trusted ones `corrected_speaker` drops for shared ids: off by a few speakers.
14. ~~Done 2026-11-17~~ (see Completed, "Shared Redner-IDs: loader checks, role words, one record load").
15. ~~Done 2026-11-17~~ (see Completed, "Shared Redner-IDs: loader checks, role words, one record load").
16. **The name check compares names within one record only.** Two records that share a Redner-ID (an `aw:` and an `xml:` record) and hold one name each pass it, and pass 1 of `match_rows` then joins them on the Redner-ID. A cross-record check over the A3 store's 784 multi-record Redner-ID groups found no clash today. Compare names across each pass-1 component.
17. ~~**A name-matched profile of a partition's profile owner can reach another owner.**~~ **Done (2026-11-17):** `registry.redner_id_profile_reaches` replaces `profile_follows_redner_id`; see Completed.
18. **An `xml:` own id is checked for shape, not for canonical form** (left from item 15, which covers `dip:` own ids only): `xml:011004157` passes `OWN_ID_RE`, but Redner-IDs are compared as printed strings, so the occurrence would bind a record no speaker line names. No entry does this today. Decide the canonical form of a Redner-ID (`derive.first_redner_id` keeps leading zeros) before refusing one.
19. **`attach_speaker_profiles`' same-identity branch ignores the partition.** Within one agenda item a re-parsed speaker takes the profile a cached speaker of the same `(xml_redner_id, first_name, last_name)` carried, before the Redner-ID fallback and its owner check. Two owners of a shared id printed with the same garbled name fields in one item (the 11005304 double name "Dirk-UlrichAlexander Mende Föhr") would share a profile. Each garbled occurrence sits in a different sitting today, so no item has two. Key the branch by occurrence (`rede_id`) or apply `redner_id_profile_reaches` there too. Found by the roster-profile-build TODO run, 2026-11-17.
20. ~~**The profile check reads the raw `rede_id`.**~~ **Done (2026-11-18):** `profile_rede_id` passes the id persist keys the occurrence by; see Completed, "Profile check rede id and Redner-ID name check edges".
21. ~~**`profile_rede_id` keys an `xml_speakers_first` entry by its list position, not its sequence.**~~ **Done (v0.46.29.0, 2026-11-20):** it takes the sequence of the `xml_speakers` entry at the same position; see Completed.
22. ~~**No test pins `profile_rede_id`'s Beitrag branch.**~~ **Done (v0.46.29.0, 2026-11-20):** `ReparseProfileTests` asserts a Beitrag with no rede id is looked up by None; see Completed.

**Why:** None of them is a wrong unit in the store today. Items 6–16 come from the pre-landing and adversarial reviews of 2026-11-09; item 17 from the /ship review of v0.46.6.0.

**Effort:** S each
**Priority:** P3
**Depends on:** None

### Redner-ID name check: what the v0.46.10.0 ship review left open

**What:** v0.46.10.0 drops office words from `person_registry._name_words` ("Shared Redner-IDs: what the fix leaves open", item 12). Its /ship review left these. No current input reaches any of them: on the 801-sitting replay the check refuses nothing and no figure moves, none of the 9,648 printed and roster names it reads reduces to no words, and no MdB-Stammdaten name word reads as an office.
1. **The rest of the office phrase still counts as a shared word.** Printed names carry the whole phrase ("Parl. Staatssekr., Bundesministerium für Umwelt, …", "Stellv. MdBR (Minister für …), Bayern"), so "bundesministerium", "für", "des", the ministry's subject and the Land stay. Two officials of one ministry or Land under one Redner-ID pass the check. Today no record with a Redner-ID holds such a name: the XML's name fields carry at most the office word. Drop the words after an office marker, or compare only the given name and surname fields.
2. ~~**A name that is only an office word empties and is skipped (fail-open).**~~ **Done (2026-11-18):** see Completed, "Profile check rede id and Redner-ID name check edges".
3. ~~**A surname that ends like an office refuses one person (fail-closed).**~~ **Done (v0.46.29.0):** same Completed line. Two names that share only an office-like word are one person when both are a given name plus that word, unbracketed, and the given names agree (one is the other or its one-letter initial): "Karl Bürgermeister"/"K. Bürgermeister" link, "Sieling Bürgermeister"/"Bovenschulte Bürgermeister" and "Anna Innenministerin"/"Bea Innenministerin" stop the build.
4. ~~**Compound offices outside the endings list.**~~ **Done (2026-11-18):** same Completed line. `bundeskanzler(in)` stays a whole word; an ending "kanzler" would read the surname Kanzler as an office.
5. **`test_reconcile_loads_the_records_once_before_the_guesses` asserts a call count** (`_load_rows` called twice), not that the name check reads the live rows the merges read. Replace it with a reconcile-level refusal test, or keep it as a performance guard and say so.
6. **`scripts/measure_aw_match_share.py` shares the private `_name_words`,** so its precision check now drops offices and strips brackets too, while `derive.person_name_key` and `_vote_member_name_parts` do not ("Architecture review 2026-11-15" names the divergence). A rerun of the A3 item 1.5 measurement can move by a label whose name word was bracketed.
7. **The duplicate own-id refusal compares exact strings:** one person given `xml:<id>` in one partition and `dip:<id>` in another forms two reviewed records. No entry does this.
8. **An office-only name beside the same office used as a surname refuses one person (fail-closed).** "Bürgermeister" and "Karl Bürgermeister" under one Redner-ID share no word ({bürgermeister} and {karl}), and `_same_office_surname` needs both names in the given-name-plus-office shape, so the build stops. Before v0.46.29.0 the pair linked; the bare office could equally be the office holder Sieling, so linking it is a guess. No stored name has this pair. Found by the v0.46.29.0 /ship review (red team, fix-check).
9. **A longer spelling of one given name with an office-like surname refuses one person (fail-closed).** "Karl Bürgermeister" and "Karl-Heinz Bürgermeister" (or "K.-H. Bürgermeister") share no word, and `_same_office_surname` accepts only an equal given name or a one-letter initial, so the build stops; "K. Bürgermeister" and "Karl-Heinz Bürgermeister" link. Compare the first part of a hyphenated given name if it ever occurs. No stored name has this pair. Found by the v0.46.29.0 /ship review (fix-check, red team).

**Why:** The check guards every future sitting against filing two people as one person. Items 1 and 2 are ways it lets two people through.

**Effort:** S each
**Priority:** P3
**Depends on:** None

### Check that vote links are right

**What:** A namentliche Abstimmung links to a Tagesordnungspunkt of its own Sitzung in one of two ways. Since PR B of `docs/plans/vote-links-and-figures.md` (branch `claude/vote-link-attribution`, built 2026-11-14) one function, `scripts/vote_links.py`, applies the rule online (`enrich_with_api`), on replay (`reparse_cached_xml`, with and without XML) and after carry-forward, and persist refuses a report that disagrees with it:
- **Shared Drucksache.** The vote's Drucksachen overlap the Tagesordnungspunkt's: those its XML prints under it plus those DIP links to its Vorgangspositionen, `mitberaten` Vorgänge included. A vote can link to several Tagesordnungspunkte this way.
- **Unique title.** A vote whose Drucksachen overlap no Tagesordnungspunkt of the Sitzung is matched by `vote_links.title_matches` against each Tagesordnungspunkt's heading and linked Vorgang titles. It is linked only when exactly one Tagesordnungspunkt matches. The match is fuzzy: a substring in either direction, or at least 65% of the vote title's words longer than four letters.

`agenda_item_votes.basis` records the step: 174 `drucksache_xml`, 401 `drucksache_vorgang`, 15 `title` of the 590 links on the reference store.

Until 2026-11-15 this entry cited `match_roll_call_votes` (3355) as the rule. That helper did not ship: it had no production caller since v0.10.0.0 and no title fallback (see "One module for the link between a namentliche Abstimmung and its Tagesordnungspunkt"). PR B deletes it.

No test or gate yet checks that a link is right. Decision N10 (2026-11-09), sized in the plan (owner decision 4, 2026-11-14, which includes all title links): review 329 links in about 155 units before the first release:
- S1: all 13 votes linked to more than one TOP (47 links), ten of them Haushalt votes; six link to 4 to 7 Haushalt TOPs (votes 894, 898, 960, 961, 979, 980);
- S2: all 84 TOPs with more than one vote (238 links);
- S3: all 15 title links: votes 317, 369, 374, 432, 495, 514, 535, 595, 638, 703, 704, 758, 759, 805 and 863. Four of them (514, 535, 638, 863) carry no Drucksache at all, so for those the title is the only evidence there can be;
- S4: 50 random plain links (34 Vorgang-only, 16 printed), seed recorded in the sheet.

Measured on the A3 store, 2026-11-07: 590 links, 556 votes, 0 across protocols. Counted again on 2026-11-15 from the cached reports of the 718-sitting reference store: the same 590 links, 575 through a shared Drucksache and 15 through a unique title. `scripts/vote_link_review.py` writes the sheet (`docs/plans/vote-links-review.tsv`). Run the review with the N8 review once the 85 sittings are fetched, and add their multi-link and title cases. A link means the TOP that dealt with the voted Vorlage, the most specific sub-item; it does not mean the vote alone settled that TOP (owner decision 1; `docs/data-methods.md`, "Abstimmungen und Tagesordnungspunkte"). Report how many reviewed links were right, fixed or flagged.

**Decided (2026-11-14):** a pattern is fixed in the rule; a one-off wrong link is dropped and the vote page says so; an unsure link stays, flagged (owner decision 2). Gate: a release refuses a vote linked to two or more TOPs without a review row (decision 6). PR C carries all three.

**For PR C:** the rule compares Drucksache numbers as plain strings, as the live rule always did, so a leading zero ("20/0301" against "20/301") shares nothing; `derive.canonical_document_number` would match them. Count such pairs on the store before changing it (a false negative, not covered by the review's sample). The sheet's `tally` column reads `several` for 138 of 329 rows, likely the chair's announcement plus the result annex; tell the reviewer, or keep only the Sitzungsverlauf match.

**Deferred from the PR B code review (2026-11-15), none a wrong figure today:**
1. **Online run, kept reports.** An online build re-parses only stale cached reports (`unparsed_reports`, `build_dip_pulse_site.py:15078`), so a kept report reaches `persist_report` without `vote_links.attribute_votes`. Today every cached placement equals the rule (replay: 590 = 590 links), but a rule change without a schema bump would make `placement_errors` refuse every kept sitting and stop the online build. PR C bumps the schema, which forces `--offline --repersist` first; any later rule change must too, or attribute every entry before persist. The ship's Codex pass adds: the replay corrects placement only in memory and never rewrites the cached JSON, so after a rule change `--offline --repersist` alone does not stop the next online build refusing a kept report. Attribute every retained report before persist, or write the repaired placement back.
2. ~~**Review sheet `shared` column.**~~ **Done (2026-11-17):** a number printed under the TOP and Vorgang-linked shows as `number:type:Vorgang:xml`; printed-only stays `number:xml:-`. The `basis` column was already right.
3. **Two rule runs in `enrich_with_api`.** `candidate_tops` (from list candidates, `validate_dip_protocol.py:4195`) drives the unmatched warnings; `attribute_votes` (from fetched votes) drives placement. They agree because `fetch_roll_call_vote_detail` keeps `title` and `document_numbers`; derive the warnings from `placed` instead.

**Deferred from the PR B ship review (2026-11-15):**
4. **Carry-forward drops the votes of a repeated TOP id (predates PR B).** `reuse_existing_dossier_enrichments` keys the cached items by `agenda_item_reuse_keys`, so of two cached TOPs sharing a `top_id` the last wins and the first one's votes are never collected; `attribute_votes` then places only what was carried. On main the first occurrence got a copy of the last one's votes instead, losing the same votes. Real sittings with votes under a repeated `top_id`: 20/152 ("Tagesordnungspunkt I" twice, both occurrences hold votes 897 and 898) and 21/25 (one vote under both), so nothing is lost today; a sitting whose repeated TOPs hold different votes would lose the first one's. Collect every cached vote (all TOPs and `sitting_votes`) independently of TOP reuse before `attribute_votes`, with a test on a repeated `top_id`. Found by Codex.
5. ~~**Persist's placement gate does not check `sitting_votes` is whole.**~~ **Done (2026-11-18):** `vote_links.placement_errors` also names a vote the rule links to no TOP that `sitting_votes` lacks.
6. ~~**Review sheet evidence by `item_index`.**~~ **Done (2026-11-17):** `build_sheet` reads the cached report's TOP by `(top_id, top_occurrence)`, counted as the store counts them, so a replay that renumbers the store no longer shows another TOP's Drucksachen. It shows `?` when the cached report lacks the TOP or holds its `top_id` a different number of times than the store (a replay that adopted a TOP under a repeated `top_id` shifts the occurrences). Left from the ship review, none a wrong row today: of two cached TOPs with the same `index` and `top_id` the file order decides; Drucksache numbers are compared without stripping whitespace (predates the change). A cached report of the wrong shape that persist would also refuse (`agenda_items` not a list, `api` or an `xml_drucksachen` entry not an object) still ends in a traceback, not exit 2; no producer writes one. Still open, from the same review: the sheet reads the cached JSON, which a replay never rewrites (item 1), so a TOP whose content a replay changed without changing how often its `top_id` occurs shows the cached Drucksachen; replay the report before the review, or also require the cleaned heading to match. And the `shared` format reads by field count (`n:xml:-` puts `xml` in the type slot, `n:type:id:xml` appends it); say so in the reviewer's notes. From the PR #169 code review (2026-11-17): the occurrence count is written twice, in `stored_links` (store rows by `item_index`) and `CachedTops` (cached items by `source_index`), and the two must agree for the pairing to hold; one shared helper over `(top_id, index)` pairs would keep them from drifting. And the example sitting with "Tagesordnungspunkt I" twice differs between the module docstring (21/24), the plan (961) and item 4 above (20/152, 21/25); check which sittings hold it and use one.
7. ~~**One rule for printed Drucksachen.**~~ **Done (2026-11-18):** `vote_links.top_links` and `vote_link_review.shared_documents` read the references through `derive.xml_drucksachen`. Counted on the 801 cached reports of the reference store: 0 of 8,189 TOPs give another number set, 0 reports change a link, 0 placement errors.
8. **Tests.** No test covers `reparse_cached_xml`'s XML branch placing votes under a TOP the re-parse adds or a vote id given twice (last entry decides) (still open). **Sheet part done (2026-11-17):** a test covers `top_occurrence` 2 in the review sheet, and the 2-second bound in `tests/test_vote_link_review.py` carries its `gstack-timing-ok` reason.

**Deferred from the vote-link rules ship review (v0.46.26.0, 2026-11-20), none a wrong figure today:**
9. **A linked vote that also sits in `sitting_votes` passes the gate.** `vote_links.placement_errors` names a vote missing from `sitting_votes`, but not one that sits there while the rule links it to a TOP. Persist stores it once (`derive.iter_report_votes` yields each id once, TOP first), but `derive.refile_report_votes` and any reader of `report["sitting_votes"]` would show it twice. No producer writes this: `attribute_votes` rebuilds `sitting_votes` from the unlinked votes. Fix: also name `sitting & {v for v, t in placed.items() if t}`.
10. **Two host checks for printed Drucksachen.** `enrich_with_api`'s `position_matches_top` (`validate_dip_protocol.py` ~4170) reads the parser's raw `drucksachen`, while the vote links read `derive.xml_drucksachen`. They agree only because `extract_drucksachen` applies the same host test as `derive.is_bundestag_xml_url`. Fix: one host test both call.
11. **An id-less `api_records` vote fails persist without the protocol number.** `report_votes` calls `derive.vote_identity` on `api_records.sitting_votes` and `matched_roll_call_votes`, which `derive.require_vote_shape` does not check, so the "has no id" ValueError surfaces from `placement_errors` without naming the report. Predates v0.46.26.0; the scraper always sets an id.
12. **One misplaced unlinked vote gives two errors.** A vote the rule links to no TOP, held under a TOP and missing from `sitting_votes`, is named twice ("linked to no TOP and missing from sitting_votes" and "sits under X"); persist shows the first three errors, so the pair can hide a third fault. Wording only.
13. **`vote_links` uses the private `derive._clean`** (`norm_title`, `_vote_order`). Make it public or give `derive` a public text cleaner.

**Why:** The links are the stated difference from other datasets (`PRODUCT.md`, Positioning), and every planned count could pass with a misleading link. The likeliest errors: an amendment that shares a Drucksache with an unrelated TOP on the same day, and a fuzzy title match that binds a neighbouring TOP (review checklist class 7).

**Effort:** M (human ~2 days / CC ~2 h, estimated)
**Priority:** P1
**Depends on:** None. T4 restored the 83 sittings on 2026-11-17: 701 links on the store now (174 `drucksache_xml`, 507 `drucksache_vorgang`, 20 `title`), 111 of them in restored sittings, which carry `batch = t4` in the review (`docs/plans/t4-acquire.md`, step 4).

### Comparison and joinable ids in DATA.md

**What:** Add a short "Vergleich" table to the release's `DATA.md`: this dataset, CPP-BT, GermaParl, ParlLawSpeech and BTVote, by coverage, unit, links and licence, with the date it was checked. Document that `rede_id` and `xml_redner_id` are the Bundestag's own ids and join to CPP-BT, and how: the " (neu)" protocol numbers, sub-ids with `:N`, our `nested*` ids, and shared speaker ids. State what we leave out and CPP-BT keeps, chiefly the §31 declarations. Say these are independent projects with no affiliation. Decision N4.

**Why:** Researchers can use our links alongside text they already hold, and will compare the two anyway.

**Effort:** S
**Priority:** P1
**Depends on:** "Coverage gate before the first data release", for the figures

### Main and stable releases

**What:** Main release: automatic per completed Sitzungswoche, published only if every check passes; every one kept, with a date and checksums. Stable release: one frozen main release, reviewed by the owner about every three months, with a DOI; a marker on that release, not a second database. Needed: a written review checklist (coverage per year, figures moved since the last stable, spot checks against protocols, a per-sitting comparison by `rede_id`, surname and tokens with CPP-BT's newest speech metadata, outside the build and with no dependency on it; method in `docs/research/bundestag-corpora-landscape-2026-11.md`, and the first run's script was throwaway, so write one when the checklist is built); the rule that a bug found in review is fixed in a new main release, the change is checked, and that release becomes stable; both downloads and the last review date on the Daten page, which also explains why the two can differ; each page naming its main release; the site showing the age of its data; the `CLAUDE.md` pre-release section rewritten as a stability policy.

**Done 2026-11-15 (the release review PR):** `docs/release-review.md`, `scripts/compare_cpp_bt.py` with `scripts/cpp_bt_known_differences.tsv`, and the first run (`docs/release-reviews/cpp-bt-first-run-2026-11-14.md`). **Left:** the owner signs off the token-ratio thresholds (15%, 50 tokens) and the spot-check size; the stability policy in `CLAUDE.md` (plan PR D, after the first `--publish`); the first release's review record and `stable-<version>` tag.

**Lower-priority edges of `scripts/compare_cpp_bt.py`** (the PR's review found them; none is reached by the first run's inputs):
- A Rede whose speaker has no `mp_id` has no name on our side, so its surname is not compared; Fraktion is not compared for 9,616 shared ids (about 13%). Neither count is in the pass rule of `docs/release-review.md` step 4. Add both to the rule, or list the not-compared Reden missing from the known file.
- Corrupt input still gives a traceback, not exit 2: an encrypted or unsupported zip, an unwritable `--out` directory. (~~a `.sqlite.gz` with a bad deflate stream, a known-differences file that is not UTF-8~~ done 2026-11-18.)
- ~~A known-differences row with `only_theirs` and an empty `rede_id`~~ is refused now (2026-11-18). A duplicate id in CPP-BT is first-wins and only counted.

**Why:** The owner cannot review every release once the project is live. Decision Q3.

**Effort:** M
**Priority:** P1 (checklist and policy for the first release; the rest for the site)
**Depends on:** The release script

### Rename the project to open-parlament

**What:** Replace "Bundestag-Puls" and "poliwatch" in the site, code (44 lines in `scripts/` name Bundestag-Puls, 2026-11-14), README, `CITATION.cff`, the CC BY attribution string and `CONTEXT.md`. Check whether storage keys and file names such as `bundestag-pulse.sqlite` follow.

**Why:** Decision Q11. Citations copy whatever the first release says.

**Effort:** M
**Priority:** P1
**Depends on:** None

### Apply the v1 surface list

**What:** Cut `api-sitzungen.html` (WP 1–17 metadata goes to the release through slice 2, the exclusion list to `overview.html`) and `settings.html`. Remove the 333 KB sitting list from `sources.html`. Take Fakt der Woche off `puls.html`, the nav and its archive pages, and its `facts` tables out of the release. Set the nav to Aktuell, Sitzungen, Abstimmungen, Gesetzesvorhaben, Abgeordnete, Analysen (once it exists), Daten, and the footer to Quellen und Methode, So arbeitet der Bundestag, Impressum, Datenschutz. Drop the "Erfasste Quelldaten" block in slice 7, after checking no field readers need exists only there. Shorten the Daten page.

**Why:** Decisions Q5, Q6, Q7, Q10.

**Order (2026-11-10, `docs/plans/render-layer-and-order.md`):**
- The page cuts (`api-sitzungen.html`, `settings.html`, the Fakt pages and their references, the `sources.html` sitting list) are step 0, before any port or restyle. That PR edits the same regions of `build_dip_pulse_site.py` as the `facts` tables leaving the release, which stays with the release work, so land one first and rebase the other.
- The nav change comes with the new page shell (step 1).
- The "Erfasste Quelldaten" block goes in slice 7.
- The Daten page comes at step 10.

**Effort:** M
**Priority:** P2
**Depends on:** Fits with A4 slices 2 and 7 and "Apply DESIGN.md to the site"

### Public repository: follow-ups

**Done 2026-11-14** (`docs/plans/release-readiness.md`, item 1): `SECURITY.md` no longer says the repository is not public; `CITATION.cff` has `repository-code` (its test asserts the line). `url` stays out until the site has a host (owner decision).

**Full-history scan, 2026-11-14, clean.** gitleaks 8.30.1 (`--redact`) over a mirror clone: 153 `refs/pull/*` and 22 branches, 1,068 commits scanned, 27 findings. 22 are test fixtures of the vendored gstack in `e5f86e1` under `.claude/skills/gstack/` (AWS, GCP, GitHub-PAT, JWT and generic-key shapes). The other 5 were read by hand and are false positives, all rule `generic-api-key`: three are the test placeholders at `tests/test_dip_request_log.py:19` (commits `4705fb3`, `8b93eb5`, `874fa3f`), two match the words "keys, A2-coordinated contract" at `docs/plans/a1-followups.md:350` (commits `92e4946`, `ae1886b`). No secret in the history; no value is written down here.

**What is left:**
- The owner turns on secret scanning and push protection (Settings → Code security), and "Block command line pushes that expose my email". The commit history stays as it is (decided 2026-11-14); this repo's `user.email` is the GitHub noreply address.
- One sentence in the roll-call e-mail ("Settle the roll-call source for redistribution"): are test excerpts of the roll-call pages in a public code repository covered (`tests/fixtures/roll_call_detail_*.html`, `member_votes.html`, `namenslisten_list.html`, `roll_call_1002.json`, and named Stimmen in `docs/plans/e4-refiled-votes-old-new.tsv`)?

**Why:** Found by the v1 scope review.

**Effort:** S
**Priority:** P1
**Depends on:** None

### Reader test before launch

**What:** Five outside readers on a frozen build of the finished site, with tasks from PRODUCT.md criteria 1 to 3 on desktop and mobile; measure correct answers and time. Covers the grey ground and vote wall that `DESIGN.md` leaves open. Open: a pass rule (proposed: fix any task fewer than four of five complete correctly). The owner handles the researcher check of the data release (decision N5).

**Why:** Nobody outside the project has seen the site. Decision Q16 puts it after the rollout, so `DESIGN.md` choices stay easy to change until then. Replaces the five-reader week radar test.

**Effort:** M; the owner recruits, about 45 minutes per reader
**Priority:** P1 for launch
**Depends on:** "Apply DESIGN.md to the site"

### Rebuild Fakt der Woche

**What:** Rethink it before it returns. Start from "what happened this week that a citizen should know, and what does the record show that a headline would not?", not "what number was unusual?". Test on outside readers before building.

**Why:** The last three weekly cards in the A3 build all won on the longest sitting. The owner would not subscribe to it. Improving it is required, but not for v1. "Fakt der Woche, rasterize and post one card", the ledger, Approach B and Approach C wait for this rethink.

**Effort:** L
**Priority:** P3
**Depends on:** v1

## Daten

### Give the agenda items of 18/49 and 18/44 adopted from the Inhaltsverzeichnis their DIP links

**What:** Offline replay gives the adopted items an empty `api`, because the cached report holds no match for them. A fresh online acquisition alone fixes only "Tagesordnungspunkt 1" of 18/49, the one adopted item with a heading (the T_ paragraphs it takes from `<sitzungsbeginn>`). `enrich_with_api` matches positions through `position_matches_top`, which with no Drucksache in the XML falls back to `title_matches(top["heading"], titel)`, and that is False for an empty heading. "Zur Geschäftsordnung" (18/44), "Allgemeine Finanzdebatte" and "Einzelplan 06" (18/49) have heading "" [measured on the fixtures, 2026-11-09], so they would get activities by page range but no position. DIP's positions are there: 18/49 "1. Beratung" 4459–4544 and "1. Beratung (Einzelpläne)" 4459–4485 and 4485–4507; 18/44 "Geschäftsordnungsantrag auf Absetzung von der TO" 3927–3931.

Speakers of the 29 adopted Reden also get an abgeordnetenwatch profile on replay only through the `by_redner_id` fallback (profiles other cached reports resolved), since the old report held no item for them; a fresh build resolves them itself. Not measured how many go without.

**Why:** Until then these items show no Vorgang or Drucksache link. Reden are counted; only the links are missing.

**Context:** Needs a matching rule for an adopted item first (for example `title_matches` against `top_id`, or the page range alone when the item's top_source is `inhaltsverzeichnis`), then re-acquisition: about 26 DIP requests per sitting, with the DIP key. `reparse_report_xml` keeps the items once they are in the report. Re-match from `api_records` offline only if the key stays out of reach. Report moved figures.

**Effort:** S
**Priority:** P2
**Depends on:** a DIP key

### Reden outside a TOP: what the ship review left open

**What:** Latent findings of the 2026-11-09/10 ship review of `adopt_reden_outside_tops`; no current input reaches them.
1. `no_api_fields()` restates the `api` shape `enrich_with_api` builds inline; a field added to one is missing from the other. Build both from one helper.
2. ~~A non-Rede element between two Reden in `<sitzungsverlauf>` is refused with "after a TOP".~~ **Completed:** 2026-11-17, v0.46.8.0. The refusal names the element ("after a `<p>` element"). The `open_block = None` reset stays: a second `<sitzungsbeginn>` between two Reden would reach it.
3. An Inhaltsverzeichnis title ending in "-" with no `A_TOP` continuation is cut silently.
4. ~~Tests do not pin the T_ paragraph move or `ZU_PROTOKOLL_ANNEX`'s end anchor.~~ **Completed:** 2026-11-17, v0.46.8.0 (`SitzungsbeginnParagraphTests`, `ZuProtokollAnnexTitleTests`; the four mutants are killed).
5. ~~**A Rede listed in two Inhaltsverzeichnis blocks goes to the first one.**~~ **Completed:** 2026-11-17, v0.46.8.0. Refused when the blocks name different items (`toc_block_label`); two blocks of one title still adopt it once.
6. ~~**`top_source` is read back from the XML attribute.**~~ **Completed:** 2026-11-17, v0.46.8.0. `adopt_reden_outside_tops` strips it from every `<sitzungsverlauf>` element first, also in sittings with no Rede outside a TOP, and tracks the TOPs it adopts by object.
7. **The Politikfelder regression guard keys TOPs by index** (`build_dip_pulse_site.py`, `missing_tops`/`known_tops`). After renumbering, a store whose Vorgang cache lacks 18/2000 and 18/2001 would refuse naming the wrong item, and a real `not_fetched` regression on a moved item would go unseen. The A3 replay of 2026-11-10 did not trip it. Key the guard by (protocol, top_id, heading), or skip sittings whose item set changed.
8. **A second replay can refuse** when an adopted item and a real item share a `top_id` and an empty heading and the adopted one has no Reden ("ambiguous or missing source TOP"). Match on `top_source` too. Not the case in 18/44 or 18/49.
9. **`reparse_report_xml` leaves stale fields:** `xml_top_fields` omits a falsy `top_source`, so a stale flag is never cleared, and `validation_summary.xml_drucksache_count`/`tops_with_xml_drucksachen` are not refreshed after T_ paragraphs move. Neither is displayed.
10. **Replay and a fresh build can attach votes differently** on an adopted item that now holds a Drucksache (18/49 item 1 holds 18/2000 and 18/2001): replay keeps `votes: []`. No roll-call vote touches them today.
11. ~~**An annex title not seen yet still drops its Reden silently.**~~ **Completed:** v0.37.0.0 (2026-11-12). An annex holding Reden now needs a named rule (`ANNEX_EXCLUSIONS`) or the Zu-Protokoll title, else the sitting is refused.

**Why:** Each is a wrong refusal message or an unguarded rule that a later edit could break without a failing test.

**Context:** `scripts/validate_dip_protocol.py` `adopt_reden_outside_tops`, `no_api_fields`, `ZU_PROTOKOLL_ANNEX`; tests in `tests/test_reden_outside_tops.py`, `tests/test_written_top_association.py`.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Rede reconciliation (coverage gate PR 1): what it leaves open

**What:** The reconciliation in `parse_protocol_xml` (plan `docs/plans/coverage-gate-w1-w2.md`) leaves these, all predating it:
1. **Dead `unplaced` path.** `speech_kinds.fragestunde_turns` never sets `speaker = "unplaced"`, so `unplaced_turn_count` is always 0 and the summary key it feeds says nothing. Remove the path or make it fire for a marker that names no one.
2. **`derive.SprechrolleError` escapes `build_report`.** It subclasses `Exception` (`derive.py:309`), so an unmapped Sprechrolle raised inside the parser leaves a fresh build without `source_rejected`. The offline reparse already catches it.
3. **Marker-level losses inside a stored Rede are not reconciled:** other speakers' segments in an annex Rede (`_nested` in `written_contributions`), segments with no text, and the later markers of a merged Zwischenfrage, which keep no unit id. Markers standing directly in a TOP that is not a Fragestunde belong to no `<rede>` and are not counted either. The PR 1 corpus run (2026-11-12, 718 held sittings) counted 50 such markers in 24 sittings, against 16,389 Fragestunde markers; the ones read were a Redner's short reply outside any `<rede>`, such as accepting a Zwischenfrage ("Ja, gerne.", 19/114 TOP 1, 20/9 TOP 7, 21/24 Einzelplan 23), but the longest run to 292 words (median 8, about 1,750 in all). The list per sitting (TOP and marker count) is in the plan's "PR 1 validation".
4. **The Fragestunde marker check guards only future edits.** `parse_protocol_xml` compares the direct `<p klasse="redner">` children of the TOP with the turns `fragestunde_turns` opened from the same children, and that function appends one item per marker or raises, so the check cannot fire today. No tree edit moves a Fragestunde marker, so a raw-tree count would give the same number. Keep it as a guard on `fragestunde_turns`, or count markers that open a turn with text if an empty turn should become visible.
5. **Pass 1's duplicate-id guards are unreachable.** `raw_rede_inventory` now refuses any repeated `<rede>` id before pass 1 runs, so the `sum(r.get("id") == … for r in redes) == 1` checks in the `reply`, `resumed` and `unique_next` rules, and the last-wins `by_id` dict, never see a duplicate. The two `test_a1_followups.py` duplicate mutations now expect the inventory's message. Remove the guards or turn them into asserts.
6. ~~**A raw `<rede>` id shaped like a split part could hide an unread Rede.**~~ **Done 2026-11-18:** `raw_rede_inventory` refuses a source id containing ":" (`test_a_source_rede_id_with_a_colon_refuses`); none of the 801 cached XMLs trips it.
7. **The 19/115 continuation rule matches any title starting "Zu der Abstimmung über".** `ANNEX_EXCLUSIONS` `paragraph_31_continuation` (`zu der abstimmung über .+`) was written for the second block of 19/115's §31 declarations and matches only that block in the 718 held sittings, but a future annex with such a title would drop its Reden without the review the table asks for. Pin it to the observed title, or require that the block follow a §31 block in the same `anlage`.
8. **`record_status`'s "has two statuses" error names no sitting.** Every other reconciliation message starts with wp/nr; the online and offline callers prefix the document number, but `extract_demo_fixture.py` does not. Pass the sitting in. (Held back 2026-11-18: the change makes `sitting` a parameter of `record_status`, and one caller is `exclude_annex_reden_in_verlauf`, which another branch of that night's batch was editing. The other callers are `written_contributions` (has `root`) and three in `parse_protocol_xml` (has `sitting`); the call in `exclude_annex_reden_in_verlauf` runs first on an empty dict with ids the inventory made unique, so it cannot raise today. Update `tests/test_rede_reconciliation.py`'s direct call too.)
9. ~~**The pre-gate skips two parser test files when only `validate_dip_protocol.py` changes.**~~ **Done 2026-11-18:** both are in the mapping.
10. **"nested contribution needs a source rede id" is unreachable.** `raw_rede_inventory` refuses every `<rede>` without id outside an annex before the walk, and the walk reads only TOP Reden, so the check at `validate_dip_protocol.py:1891` never fires. `report.md`'s list of classes that did not occur still names it as `nested_needs_source_id` (the W1 audit script that classified it is retired with PR 2). Remove the check or turn it into an assert.
11. ~~**The W1 `preflight.json` writes the median share as an unrounded float** (`0.017099999999999997`): `statistics.median` averages two rounded shares. Round it in `fetch_and_audit.py`'s `summary()`.~~ **Moot:** coverage gate PR 2 retires `fetch_and_audit.py`; `preflight.json` stays as W1's record.

**Why:** Each is below the `<rede>` grain the coverage gate is defined on, or a refusal path that predates the change; CLAUDE.md sends them here.

**Effort:** S each
**Priority:** P3
**Depends on:** None

### T4 parser rules for 18/158 and 19/13: what they leave open (2026-11-15)

**What:** The two rules of #166 (v0.46.2.0, `docs/source-errors.md` E9, E10) leave these:
1. ~~**`scripts/compare_cpp_bt.py` will list 18/158's 37 declarations as `in_top_other`.**~~ **Done 2026-11-18 (T4 M4):** it did, and the 37 are now in `scripts/cpp_bt_known_differences.tsv` with E9 as the reason.
2. **The 18/158 rule needs the annex number to match.** In 18/212, 18/237, 19/71, 20/66 and 20/73 the Inhaltsverzeichnis numbers its "Anlage" blocks differently from the `<anlage>`s (18/212's "Anlage 8" lists the Reden of Anlage 10), and 18/221 writes "Anlage16"; their Reden all stand in the annexes, so nothing is lost. A future sitting with both an offset and Reden printed in the Sitzungsverlauf would store those Reden as Reden without a word. Refusing a Sitzungsverlauf `<rede>` that the Inhaltsverzeichnis lists under any "Anlage" block the rule does not place would make that visible; no sitting of the 802 does it today.
3. **Eight other headings split a word** (E10's list, all WP 19 and all stored). They decide no count, but the pages print them as the source does, and `title_matches` loses the split word ("Bun desregierung" in 19/69) when it scores a heading against a DIP title. Fix the display with a general join only if one can be found that the 38,011 headings of the 802 sittings do not contradict.
4. **The moved declarations leave the Fragestunde asker candidates** (code-review, 2026-11-16). `exclude_annex_reden_in_verlauf` removes the `<rede>`s before `speech_kinds.asker_candidates(root.iter("redner"))` runs, so their markers no longer count as candidates, while § 31 declarants in a real annex still do. 18/158 has no Fragestunde, so nothing moves today. In a future sitting with both, a read-out question could get a different `mp_id`, or none, than it would if the same declaration were printed in an annex. Build the candidates before the move, or collect the moved markers and pass them in.
5. ~~**`heading_formats` rebuilds the unspaced prefixes on every call**~~ **Done 2026-11-18:** `speech_kinds._UNSPACED_BEFRAGUNG_PREFIXES` is a module constant.
6. **Three walks map a rid to its Inhaltsverzeichnis block** (code-review, 2026-11-16): `exclude_annex_reden_in_verlauf` (later block wins), `adopt_reden_outside_tops` (drops untitled blocks, refuses two different remaining labels, and groups a run by `toc_block_label`, not by block) and `parse_protocol_xml`'s `rid_pages` merge over `parse_toc`'s blocks (refuses a rid two blocks list at different `{page, quadrant}`, since 2026-11-18). Inside one block `parse_toc` still keeps the last xref of a rid without comparing (item 6 of "One rule for which Inhaltsverzeichnis block a Rede belongs to"). One shared helper would let a fix to one reach the others.
7. ~~**The empty-TOP cleanup also drops TOPs that were empty in the source**~~ **Done 2026-11-18:** `exclude_annex_reden_in_verlauf` removes only a TOP it took a `<rede>` from and left childless. Parsing the 801 cached XMLs with the old and the new rule gives the same TOP list in every sitting (only 18/158 triggers the rule; the childless TOPs of 21/18, 21/28, 21/42, 21/45 and 21/93 are untouched by both).

**Why:** None moves a figure of the 718 stored sittings or of the two sittings the rules are for; CLAUDE.md sends them here.

**Effort:** S each
**Priority:** P3
**Depends on:** T4 storing 18/158 (item 1)

### Printed Drucksachen are read only from links

**What:** `validate_dip_protocol.extract_drucksachen` reads a TOP's Drucksachen only from `<a>` elements. All 481 WP 18/19 files and 119 of the 214 WP 20 files (20/1 to 20/116, plus 20/139, 20/201 and 20/212) print them as plain text in `T_Drs` paragraphs: 20/11 prints 10 under its TOPs. So these sittings have `xml_drucksache_count` 0 and no `agenda_item_documents` row with `source = xml`, and their vote links rest on DIP Vorgang positions and titles alone (all 174 `basis = drucksache_xml` links are in WP 20 from 20/120 on, 82, and in WP 21, 92). Read the numbers from `T_Drs` text as well, behind the host filter, then count how many TOP Drucksachen and vote links it adds and check them. A rule change moves `agenda_item_documents` and possibly `agenda_item_votes`, so it goes with or after vote PR C and its review.

**Why:** The XML holds the TOP-to-Drucksache link the store leaves out for 600 sittings. DIP covers much of it (2,918 of the 5,010 WP 18 and 19 TOPs, 58%, have a Vorgang link), but not where DIP assigns no position. Found by T4 step 2 (2026-11-18). It predates T4 and hits kept and restored sittings alike.

**Effort:** M (human ~1 day / CC ~1 h, plus the re-measure)
**Priority:** P2
**Depends on:** vote PR C ("Check that vote links are right")

### Reden whose Inhaltsverzeichnis entry prints no page

**What:** After the repeated-title fix (2026-11-17, v0.46.8.0), 416 of 61,284 stored Reden in 7 sittings still have no `source_page` [measured: offline replay of the 801-sitting reference store]. 20/97 (152), 20/210 (134), 19/161 (106) and 20/7 (14) list every Rede in the Inhaltsverzeichnis with an empty page (`<xref pnr="" div="">`, `<seite/>`); 20/85 (5), 19/18 (4) and 19/33 (1) print Reden the Inhaltsverzeichnis does not list.

**Why:** A Rede with no page has no citation, and a TOP whose Reden all lack one has no page range for DIP's position matching (36 TOPs with Reden have none).

**Context:** `validate_dip_protocol.py` `parse_toc` / `rid_pages`. The Sitzungsverlauf carries `<a typ="druckseitennummer">` markers, which `written_contributions` already reads for annex Reden (`annex_pages`); the last marker before a `<rede>` could stand in when the Inhaltsverzeichnis has no page. Check the quadrant (the marker has none) and report moved figures.

**Effort:** S
**Priority:** P2
**Depends on:** None

### One rule for which Inhaltsverzeichnis block a Rede belongs to (v0.46.8.0 ship review)

**What:** Findings from the v0.46.8.0 ship review of `parse_toc` / `adopt_reden_outside_tops`. All are latent: none occurs in the 801 stored sittings.
1. ~~**A Rede listed at two different pages gets the later block's page, with no refusal.**~~ **Done 2026-11-18:** the `rid_pages` merge refuses a rid two blocks list at different `{page, quadrant}`; across the 801 cached XMLs none refuses and every parse is unchanged.
2. ~~**`adopt_reden_outside_tops`' "before" scan is cubic.**~~ **Done 2026-11-18:** it tracks the first disallowed element directly.
3. ~~**One item's run splits into several adopted TOPs.**~~ **Done 2026-11-18:** runs are compared by `toc_block_label`.
4. ~~**An untitled block beside a titled one gives a confusing refusal.**~~ **Done 2026-11-18:** empty labels are dropped before counting, and the Rede takes the titled block's label.
5. The three rid → block walks (item 6 of "T4 parser rules for 18/158 and 19/13") were the common cause of 1 and 3, both now closed in place; one helper with one ambiguity rule is still open there. 18/89 is a third sitting with Reden outside a TOP (15, adopted as "Zusatztagesordnungspunkt 4"); `docs/data-methods.md` and `docs/source-errors.md` C7 name it since v0.46.8.0, but the `adopt_reden_outside_tops` docstring still names only 18/44 and 18/49, and "Give the agenda items of 18/49 and 18/44 adopted from the Inhaltsverzeichnis their DIP links" should check whether 18/89's adopted item lacks its DIP links too.
6. **A Rede listed twice in one block at two pages still takes the later page, with no refusal** (review of `todo/parser-toc-reconcile`, 2026-11-18). Item 1's refusal compares blocks only; inside one block `parse_toc` writes `rid_pages[rid] = page_ref` per xref, so a block listing Rede X at 100 A and again at 200 B would cite 200 B. Measured 2026-11-18 with a scratch script: none of the 801 cached XMLs lists a rid twice in one block at different `{page, quadrant}`. Fix: the same `setdefault`-and-compare refusal in `parse_toc`'s xref loop (it needs the sitting for the message, or raise a bare message the caller prefixes), with a doctored-18/44 test beside `tests/test_reden_outside_tops.py`'s two-page case. The v0.46.30.0 red team adds a mixed case the cross-block check also misses: block A lists X at P1 then P2 and block B lists X at P2, so P1 is lost without a refusal. The in-block refusal closes both.

Left by the v0.46.30.0 /ship review (red team, native adversarial reader; Codex adversarial and structured were clean). All latent: none occurs in the 801 cached XMLs.
7. **On replay the new two-pages refusal names the wrong fix** (red team and native adversarial). It is a plain `ValueError`, so `reparse_cached_xml` (`scripts/build_dip_pulse_site.py`, the `except (dip.ET.ParseError, OSError, UnicodeDecodeError, ValueError, derive.SprechrolleError)` branch) prints "is not the Plenarprotokoll XML of … delete corrupt XML and run --fetch-xml again", and a re-fetch returns the same file. The existing `adopt_reden_outside_tops` refusals (no entry, two titles, Rede after a TOP or other element) print the same wrong advice. Online all of them are a correct `source_rejected`. Fix: one source-shape exception (or `ReconciliationError`) for these refusals, caught apart in `reparse_cached_xml` with a `fix=` that points to `docs/source-errors.md`, plus a test of the printed line like `test_rede_reconciliation.py`'s "names itself, not a corrupt file". Deferred at ship by the AUQ adjudicator (wording on a path no input reaches).
8. **Grouping by label could fuse two different items that share a title.** Since item 3, two adjacent runs under, say, two separate "Zur Geschäftsordnung" blocks become one adopted TOP. That is right for a "(Fortsetzung)" listing, which is what 18/44, 18/49 and 18/89 show (their parse is unchanged), but a future sitting with two real same-titled items would get one. Option: merge across blocks only when the later block is a continuation (no Drucksachen of its own, or "Fortsetzung" in its title), else refuse.
9. **Untitled blocks.** A Rede listed in an untitled and a titled block now takes the titled label, with nothing proving the untitled block belongs to that item; a Rede listed only in untitled blocks refuses with "no Inhaltsverzeichnis entry", which is false (it has an entry without a title). No stored block is untitled. Name the untitled block in the message, or refuse whenever a listing block is untitled.
10. **The two-pages compare is exact and covers every xref.** `{page, quadrant}` is compared as parsed: the quadrant from `div` or `<seitenbereich>` is not stripped or case-folded, so "A" against " A" would refuse a sitting over nothing, and `parse_toc` keeps every `xref` with a `rid` whatever its `ref-type`, while the message says "Rede". Normalise the quadrant and limit the check (or the wording) to Rede xrefs.
11. **Alternating labels give two adopted TOPs with one `top-id`** (predates v0.46.30.0). Runs X, Y, X under `<sitzungsverlauf>` produce three TOPs, two of them `top-id` X, and nothing downstream refuses a repeated `top-id`. Decide whether a repeat should refuse.
12. **The colon refusal also covers annex Reden**, which `split_nested_reden` never splits, so it is broader than the rule needs (0 of 85,352 source ids contain a colon). `raw_rede_id("annex:1:2")` would return "annex"; no caller passes an annex key to it today.

**Why:** Item 1 would put a wrong page into a citation without a refusal if a future sitting listed one Rede at two pages; the rest are cost and clarity.

**Context:** `scripts/validate_dip_protocol.py` `parse_toc`, `parse_protocol_xml` (the `rid_pages` merge), `adopt_reden_outside_tops`, `toc_block_label`. Deferred under CLAUDE.md "Review findings: fix now or defer" (latent, no current input reaches them).

**Effort:** S
**Priority:** P2
**Depends on:** None

### Fraktion check and vote binding: what the v0.46.9.0 ship review left open

**What:** Findings of the v0.46.9.0 ship review of `derive.printed_fraktion` and the vote re-scope. None moves a figure of the 801 cached sittings.
1. **An unknown `<fraktion>` stops the whole online update, not one sitting** (native adversarial; owner decision). `printed_fraktion` raises inside `parse_redner`; online that becomes `DipError(source_rejected=True)`, which `build_dossiers_with_progress` re-raises (D4), so a scheduled update keeps failing until code changes. 126 `<redner>` in the cached XML print values the check would refuse ("zur Geschäftsordnung" ×58, "Erklärung nach § 29/30/31 GO" ×46, "BÜNDNIS 90/" ×3, "DIE LINKE T", ...), all in the Inhaltsverzeichnis, the Rednerliste or an unread annex today. Decide: refuse the build (today), or skip the sitting onto the exclusion record with a reason.
2. ~~**On replay the refusal names the wrong fix**~~ **Done 2026-11-18:** `reparse_cached_xml` and `build_report` catch `UnknownFraktionError` apart and name `derive._SPELLINGS` and `docs/source-errors.md` (`derive.UNKNOWN_FRAKTION_FIX`). Online it is still a source refusal that stops the run (item 1 decides that). The dev tools `check_withhold_one.py` and `extract_demo_fixture.py` still show it as a traceback.
3. **The colon rule is general:** any "<known name>:<anything>" reads as the name ("fraktionslos: AfD" → fraktionslos). The two real cases (18/222, 19/30) are spoken text. Limit it to known shapes if a second label ever appears.
4. **A replay cannot undo an old re-scope:** `interpret_sitting_votes` seeds `result_scope` from the stored copy and `_read_contradicted_official_result` only narrows, so a vote an older parser re-scoped on a title alone keeps `proposition` until a fresh fetch. Only 990 is re-scoped today, on the chair's evidence.
5. **`speech_kinds._fraktion` still reads the raw `<fraktion>`** (asker candidates, the Kurzintervention check), so a C6-shaped value there would give another party key than the stored one. No Fragestunde or Kurzintervention unit carries one.
6. **A page with no Enthaltungen figure cannot bind a DIP decision** whose tally ends in ":0" (`tally_of` reads the missing count as unknown, by design). Say so in `docs/project-documentation.md`, or read a missing trailing count as 0 only when Ja and Nein are given.
7. ~~The comment above the two new `derive._SPELLINGS` entries describes the code before they were added.~~ **Done 2026-11-18.**

**Why:** 1 decides whether one garbled source value can stop the data updates; the rest are wording and latent edges.

**Context:** `scripts/derive.py` (`printed_fraktion`, `_SPELLINGS`), `scripts/validate_dip_protocol.py` (`parse_redner`, `dip_decision_evidence`, `_read_contradicted_official_result`, `interpret_sitting_votes`), `scripts/build_dip_pulse_site.py` (`reparse_cached_xml`, `build_dossiers_with_progress`), `scripts/speech_kinds.py`. Deferred under CLAUDE.md "Review findings: fix now or defer".

**Effort:** S
**Priority:** P2
**Depends on:** item 1 needs the owner's choice

### Which text stands for a "Neudruck eines Redebeitrages"

**What:** 19/35 reprints a Rede of Birgit Malsack-Winkemann from 19/34 (`ID193402300`), 19/45 one from 19/44. Both stay out of the store, so the original is what counts. The reprint is not a small correction: the texts of 19/34 and 19/35 match at a ratio of 0.65 [measured: `difflib`], and the order of arguments changes.

**Why:** A reader citing the 19/34 Rede gets the text the Bundestag later replaced, with no note. 19/44 is among the excluded sittings, so that original is not held at all.

**Context:** Owner decision: keep the first print, show the reprint as the text, or keep both. Other reprint titles ("Neudruck: Antwort", "Technisch bedingter Neudruck der zu Protokoll gegebenen Rede") hold no `<rede>` in the 716 files and were not read.

**Effort:** S
**Priority:** P3
**Depends on:** the coverage gate, for 19/44

### Take namentliche Abstimmungen from the official XLSX instead of the chart markup

**What:** `parse_roll_call_list_page()` / `parse_fraction_votes()` (`scripts/validate_dip_protocol.py`) read `data-chart-values` from bundestag.de HTML: four numbers (Ja, Nein, Enthaltung, nicht abgegeben) summing to the seat count, and `vote_counts_from_csv` keeps only the first four numbers it finds. The Bundestag also publishes one XLSX per namentliche Abstimmung (list: `/ajax/filterlist/de/parlament/plenum/abstimmung/liste/462112-462112`, e.g. `https://www.bundestag.de/resource/blob/1217428/20260925_3-xls.xlsx`) with columns `Wahlperiode, Sitzungnr, Abstimmnr, Fraktion/Gruppe, Name, Vorname, Titel, ja, nein, Enthaltung, ungültig, nichtabgegeben, Bezeichnung, Bemerkung`. Ingest that instead (or alongside), store ungültig as its own Stimme value and keep Bemerkung.

**Why:** Ungültig is an official Stimme value we cannot represent; if it ever occurs, the chart numbers either hide it or shift it into another category, silently. Bemerkung gives the stated reason for some uncast Stimmen (30 most recent votes, 2026-09-25: "gesetzlicher Mutterschutz" 42×, "Geburt eines Kindes" 1×), which the site could show next to "nicht abgegeben". The XLSX also carries Sitzungnr/Abstimmnr, a sturdier join to the Sitzung than matching by date.

**Context:** Sample of 30 XLSX files (18,895 Stimmen) had zero ungültig, so today's counts are not wrong in practice; this is about not being able to tell. HTML scraping of the filterlist also breaks whenever bundestag.de changes its markup.

**Prerequisite (A3 review D7, 2026-10-19): page the Namenslisten list.** What: page the Namenslisten list beyond offset 0 so every vote back to WP 18 gets its XLSX link. Why: 10 of 619 stored votes link an XLSX (fresh store, 2026-11-14), and no WP 18/19 vote will. Context: `validate_dip_protocol.py:2931` fetches only `offset=0&limit=200`; offsets 200 and 400 reach 2022 and 2019. Depends on: none.

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

**What:** ~~(1) r4 and r5 take the "first" sitting by lexicographic `MIN(document_number)` ("21/100" < "21/99"); order numerically (D5).~~ **Done 2026-11-05:** r5 and `_VOTE_PROTOCOL_SQL` (r3, r4, r6) order by Wahlperiode and sitting number. Replay of 716 sittings: r3, r4 and r6 0 rows moved (no vote has TOPs in more than one sitting); r5 278 of 7,925 rows change `erste_drucksache`, for example proceeding 230141 19/21 → 19/5; none of the 278 is in the published LIMIT 5, and all six recipe CSVs are byte-identical, apart from r2's new file name. ~~(2) r4 ranks by `ABS(yes_count - no_count)` with no guard, and the vote parser stores a block without `data-chart-values` as 0:0:0:0 (`validate_dip_protocol.py` pads with 0, `persist_dip_pulse_store.py` `int(total.get("yes") or 0)`), so such a vote would rank as the narrowest; `facts.py` already guards with `yes_count + no_count > 0`. 0 such votes in reference export g-c1944485a5d4.~~ **Done 2026-11-05:** already fixed by export format 14: the parser stores a missing total as NULL and r4 filters NULL counts. ~~(3) r3 excludes only `fraktionslos`; the site's Abweichung rule (`derive.vote_abweichler`) also skips the `Unbekannt` group and groups whose member votes do not match the fraction counts (`partial`).~~ **Built 2026-11-14** with "Persist or prove the vote outcome and Abweichler count": r3 counts `vote_members.abweichung = 1`, written by the site's rule; 0 rows moved on the reference store. (4) Check whether the shared „Unbekannt“ speaker record (`resolve_speaker` for an unnamed Redner) reaches `mp_canonical` and so r1/r2; 0 such rows in the reference export. (5) r6 groups on the raw `origin_json` urheber, while the vote panels (`derive.vote_committees`) strip and de-duplicate each name, and its `LIKE 'Beschlussempfehlung%'` is case-insensitive where the site's `startswith` is not; neither differs on today's DIP strings. Each change moves published figures: report old and new rows per the CLAUDE.md pre-release rule. Done when each recipe matches the site rule or DATA.md names the difference, with old/new figures recorded.

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

### compare_store_values: review notes on the vote figures and the export copy

**What:** Notes from the v0.46.3.0 /gstack-ship review (adversarial pass) and its build. None is a wrong figure on a store the current code builds:
1. ~~One-sided votes are not named.~~ Done in v0.46.14.0.
2. **A re-keyed member reads as two lines.** Members are keyed by `mps.identity_key`, so a person whose key changes between stores shows as "only in old" and "only in new" member rows instead of one move.
3. **Member moves are silent when one side lacks `vote_members.abweichung`.** `member_changes` returns nothing then, and the "N votes ... changed" header counts outcome and count moves only. Unreachable today: schema 13 added the three columns together. Fix: say on which side the member flags are unavailable.
4. ~~Manifest names are joined unchecked.~~ Done in v0.46.14.0.
5. ~~A corrupt `.gz` copy raises.~~ Done in v0.46.14.0.
6. **The copy can be older than the store.** `datenstand.json` names the last export, which can predate the store being compared, as the old glob could. A check against the manifest's source size or mtime would warn.
7. ~~An open store on the exit-2 path.~~ Done in v0.46.14.0.
8. ~~A member-list change reads as an Abweichung move.~~ Done in v0.46.14.0.
9. ~~Orphan member rows drop out silently.~~ Done in v0.46.14.0.

From the v0.46.14.0 /gstack-ship review (specialist and adversarial passes, 2026-11-18). None is reachable by a store the current code builds, or each is wording only:
10. **The one-sided member rows header can be false.** It says "the member list changed, no Abweichung moved", but a re-keyed member (item 2) or an orphan row on one side can carry abweichung 1 in old and 0 in new: a real flag move then reads as a list change. Figures stay right, and the vote still lists under "changed" through `abweichler_count`. Fix: drop "no Abweichung moved", or count the one-sided rows that carry abweichung 1.
11. ~~**Stale docstrings.**~~ Done 2026-11-18.
12. ~~**The vote groups section reads "(all) present -> present" when one store lacks the vote figures.**~~ Done 2026-11-18: the side reads `unavailable`.
13. **Two keys can fold into one.** A `vote_fractions` row whose party has no `parties` row is keyed "None" in the count lines (the member lines print "NULL"), so two such rows in one vote collapse; an orphan `mp_id` equal to another member's `identity_key` would collapse the same way. Unreachable: `party_id` is a NOT NULL foreign key with ON DELETE CASCADE, and 0 such rows exist on the reference store. Fix: key a missing party by `vf.party_id` with a marker, and prefix orphan keys (`mp_id:<id>`).
14. ~~**Every OSError while unpacking the export copy reads "unavailable".**~~ Done 2026-11-18: only `gzip.BadGzipFile`, `EOFError` and `zlib.error` do.
15. ~~**One-sided member rows are not tested past the list limits.**~~ Done 2026-11-18.

The earlier entry here, "compare_store_values cannot find a tagged export's SQLite copy", is done in v0.46.3.0: the copy is the first file of the generation `datenstand.json` names.

**Why:** below the fix-now floor under CLAUDE.md "Review findings" (latent, wording, or predating the change). Found 2026-11-17.

**Effort:** S
**Priority:** P3
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
5. ~~**A `shift_between_groups` could be a derivation fault rather than a source error.** Step 9 compares the ids with E4 again.~~ **Done by v0.34.0.0 (#138):** E4 re-filed the 100 Stimmen from the MdB-Stammdaten, `shift_between_groups` 55 → 0. Independence of that check: "E4 /gstack-review" item 4.
6. **`validate_manifest` does not check the shape of the manifest's `stammdaten`.** A published override manifest with a malformed `stand` makes the Daten page raise in `stammdaten_stand_day`. The export writes the key from the store, so no current input reaches this. Codex (2026-11-02, P2) adds that an object with a valid `stand` but no `sha256`, or a non-object value, also passes and raises in `render_daten_datenstand` (`KeyError('sha256')`) after other pages are written, leaving partly updated output. Fix: accept only null or an object with a parseable `stand` and a 64-hex `sha256`.
7. **An earlier cross-check report can stay in place.** This happens if the store cannot be read when the cross-check runs. The build has just written the store, so no current input reaches this.
8. ~~**`stammdaten.refresh` can create the private directory world-readable.** It runs `path.parent.mkdir(parents=True, exist_ok=True)` without `mode=0o700`, while every other creator of the private directory passes it (`person_registry`, `politikfelder`, the export work dir). The zip itself is written 0600. In a build, the writer lock creates the directory first, so no current input reaches this. Found in step 9, when a direct `refresh` call created `drwxr-xr-x`.~~ **Done 2026-11-05:** closed by item 33: `ensure_private_dir` creates it 0700.

Items 9–20 come from the pre-landing review of 305cfee (2026-11-02: specialists, red team, adversarial pass; Codex still owed). A scan of the live file (Stand 29.04.2026, 4,614 MdB) found 0 zero-length memberships, 0 memberships outside their Mandat and 0 same-start ties, and the seat rows (2,914 / 171) were identical under four `PYTHONHASHSEED` values, so none of these moves a figure today:

9. ~~**`_mandate_stretches` accepts inverted, zero-length and seed-dependent stretches.** Two reviewers asked for this before merge. Rule 2 clips only the endpoints, so a membership wholly before `MDBWP_VON` or after `MDBWP_BIS` gives `valid_until < valid_from`; `party_seats` then emits `seats=-1` (`if count:` is true), and `check_seat_totals` cannot see it. Separately, `records` is a set sorted by start date only, so a one-day membership (`MDBINS_VON == MDBINS_BIS`) on a handover day ties with the next membership: under `PYTHONHASHSEED` 1 and 3 it gives a zero-length row that collides on the primary key with the next row; other seeds raise "two memberships on the same day". Such a file passes `seat_rows`, so `refresh` caches it, and every later rebuild fails at `CHECK (seats > 0)` or the primary key until the cache is deleted by hand. Fix: sort by `(von, record)`, raise StammdatenError for `until is not None and until <= von` after the clip, and refuse `seats <= 0` in `party_seats`; add both shapes to `tests/test_seat_counts.py`. The ship's adversarial pass (2026-11-02) adds: `seat_rows` is the gate `refresh` uses, but it checks less than `persist_seat_counts` enforces (`seats > 0`, the primary keys), so such a file is cached and every later rebuild dies with a raw `sqlite3.IntegrityError` rather than DatabaseRebuildError; make `seat_rows` assert positive seats, `valid_until > valid_from` and key uniqueness.~~ **Done 2026-11-05:** `_mandate_stretches` sorts by `(von, record)` and refuses a stretch that ends no later than it starts, so a one-day membership on a handover day is refused alike under every hash seed. `party_seats` refuses a negative count, and `seat_rows` refuses what the store's CHECK and primary keys would refuse. The live file passes: 2,914 and 171 rows at Stand 29.04.2026, identical to main under four `PYTHONHASHSEED` values.
10. ~~**`read_zip` can raise exceptions other than StammdatenError.** `int(VERSION)` / `datetime.fromtimestamp` raise OverflowError or ValueError for 20+ digits or out-of-range values; `str.isdigit()` accepts non-ASCII digits such as "²", which `int()` then rejects (also `WP`); a corrupt deflate stream raises `zlib.error` and an encrypted member RuntimeError, neither caught by `_xml_bytes`. Then `refresh` crashes instead of keeping the cached file, a bit-rotted cache is never self-healed, and `rebuild_seat_counts` escapes with a traceback instead of DatabaseRebuildError. Fix: make `read_zip` raise only StammdatenError (ASCII-digit checks, wrap the conversions, widen the `_xml_bytes` except).~~ **Done 2026-11-02** in the /gstack-ship run: ASCII-digit checks for VERSION and WP, the timestamp conversion wrapped, `_xml_bytes` also catches `zlib.error`, RuntimeError and NotImplementedError, and the parse also catches LookupError (an unknown declared encoding, found by the ship's adversarial pass); `test_stammdaten.py` has the rows. ~~**Still open:** a corrupt ZIP_LZMA member raises `lzma.LZMAError`, which escapes.~~ **Done 2026-11-03:** `_xml_bytes` also catches `lzma.LZMAError`; `test_stammdaten.py` has corrupt LZMA and bzip2 rows (an encrypted member cannot be written by `zipfile`, so that branch has no test).
11. **`stammdaten.refresh` runs outside `registry.writer_lock`.** Two concurrent online builds can race: the stale-temp sweep unlinks the other build's in-flight temp file (a spurious warning, no corruption). Fix: take the writer lock around `refresh` or drop the sweep. (The double read of the zip, parse then hash, is fixed: `read_zip` hashes the buffer it parsed, v0.46.15.0.)
12. ~~**`log_seat_crosscheck` can fail the build.** Its docstring says it never does, but only `sqlite3.Error` is caught; an OSError from `path.unlink`, `path.parent.mkdir` or `dip.write_text_atomic` (full disk, permissions) leaves `main()` after the store swap and before the site and export. Fix: catch OSError around the report write and unlink and print a note.~~ **Done 2026-11-05:** `write_crosscheck_report` turns an OSError into a note, and the summary leaves out the report path when nothing was written.
13. **WP 22 will freeze the seat data quietly.** `BUNDESTAG_SIZES` stops at WP 21. Once the file lists a WP 22 Mandat, `check_seat_totals` raises, `refresh` rejects every new file with a warning, and the seat tables stay at the last accepted Stand while the build passes. Decide whether that should fail the build, and add 22 when its size is known.
14. **The handover-day trim only fires when the newcomer's first row is the leaver's group.** A Nachrücker whose Fraktion membership starts after the Mandat (first row `fraktionslos`) on a leaver's last day counts that day twice, below the cap, so the size check passes it. The live file has no such case; its 6 same-day starts after a leaver's last day are cross-group (e.g. 04.03.2024, the Berlin repeat election), where the source gives both people a Mandat that day.
15. ~~**`refresh` never compares the Stand.**~~ **Done in v0.46.15.0**: an older download keeps the cached file and its ETag and warns. A download with the same Stand and other bytes still replaces it.
16. **`after_stand` compares whole UTC days.** A vote on the Stand's own day, after the file was generated, is filed as `change_on_vote_day` or `unexplained`; the UTC date can also differ from the Berlin date near midnight. Cosmetic.
17. ~~**`ET.fromstring` parses the download without refusing a DOCTYPE.**~~ **Done in v0.46.15.0**. The premise "the real file has none" was wrong: the real file opens with `<!DOCTYPE DOCUMENT SYSTEM "MDB_STAMMDATEN.DTD">`, so `read_zip` accepts one DOCTYPE naming an external DTD only (ElementTree never loads it) and refuses an internal subset, a bare `<!ENTITY`, and a prolog that reaches no root element within its first 64 KiB.
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
28. ~~**`_download` follows redirects to any scheme or host.** urllib's default handler would follow a 30x from the fixed https URL to plain http or another host; the body is then checked only by the zip and seat rules. Optional: refuse a redirect off https://www.bundestag.de.~~ **Done 2026-11-18:** `_SameHostRedirects` refuses any redirect that does not stay on https://www.bundestag.de/.
29. **Cosmetics.** The `stammdaten.py` module docstring names only the cache and the reader, not `refresh`, `seat_rows` and `crosscheck`; the ETag sidecar writes a `fetched_at` nothing reads.
30. ~~**P2: a renamed `INSART_LANG` label would make every MdB fraktionslos and pass every check.** `_mandate_stretches` keeps only institutions whose `INSART_LANG` equals `"Fraktion/Gruppe"`; the closed-name check runs only on those, and rule 3 files every uncovered Mandat day as fraktionslos. If the Bundestag renamed the label, a file with 630 fraktionslos seats in WP 21 passes `check_seat_totals` (630 is the legal size), `refresh` caches it, and r2 and the seat tables publish fraktionslos at 100 % with only cross-check warnings. Reproduced on synthetic records by the ship's adversarial pass (2026-11-02); the live file has the label. Fix: make `seat_rows` refuse a Wahlperiode with Mandate but no matched Fraktion/Gruppe membership (or an implausible fraktionslos share on its first day).~~ **Done 2026-11-05:** `seat_rows` refuses a Wahlperiode whose Mandate are all fraktionslos; no share threshold. The live file passes.
31. ~~**`--enrich all` now downloads the MdB-Stammdaten.** `all` expands to every registered enrichment, so existing `all` configurations fetch and may replace the cache. The tests pin this as intended; say so in the README's enrichment table if it stays.~~ **Done 2026-11-05:** the README says so beside the `--enrich` values.
32. ~~**The download timeout is per socket operation, not total.** `urlopen(..., timeout=60)` then `response.read(MAX_ZIP_BYTES + 1)`: a slow-drip server can stall an online build for a long time. Fix: read in chunks against a monotonic deadline.~~ **Done v0.46.27.0:** `_download` reads with `read1` (one socket read each, at most 64 KiB) against a 5-minute monotonic deadline (`FETCH_DEADLINE_SECONDS`); the /ship review replaced `read(64 KiB)`, which waited for a whole chunk. Chunk framing and the header phase stay open in item 45.
33. ~~**P2: `stammdaten.refresh` and `log_seat_crosscheck` skip `registry.ensure_private_dir`.** Every other writer to the private directory (the staged store, politikfelder, the export work dir) calls it first, which refuses a symlink, a foreign owner or a group-writable directory before anything is written or swept. `refresh` reads the cache, sweeps `.mdb-stammdaten.*.tmp`, writes the temp file and the ETag sidecar (following a symlink) before the writer lock validates the directory; `log_seat_crosscheck` writes or unlinks its report after a bare `mkdir`. Codex (2026-11-02) reproduced it: with `.OUTPUT.private` planted as a symlink to an attacker's directory holding `mdb-stammdaten.json -> <a builder-writable file>`, one refresh truncated that file before the writer lock refused the directory. Needs a planted symlink in the site's parent. Fix: call `registry.ensure_private_dir(path.parent)` at the top of `refresh` (warn and keep on PermissionError) and before the report write; this also closes item 8. Deferred by the ship's adjudicated D2 (third fix cycle).~~ **Done 2026-11-05:** `refresh` and the report write call `registry.ensure_private_dir` first; on a refusal `refresh` warns and fetches nothing.
34. **A same-day cross-group handover can overshoot a full Wahlperiode and freeze the seat data.** The Nachrücker trim in `mdb_zugehoerigkeiten` keys on the leaver's group, so a leaver of another group (or a fraktionslos leaver) whose Mandat ends on the day a Nachrücker's starts counts twice that day. WP 21 sits at exactly 630, so that day reads 631, `check_seat_totals` raises, and `refresh` rejects every later file with a warning while the build passes on the old Stand. Reproduced on synthetic records by the ship's second adversarial pass; how often the source dates a Nachrücker on the leaver's last day is not measured. Related to items 13 and 14. Options: key the trim on Wahlperiode and day regardless of group, or make the overshoot a warning with a "Stand frozen" line.
35. **`_repoint_party` does not repoint the seat tables.** `_migrate_party_names` repoints `mps`, `vote_members` and `vote_fractions`, not `mdb_zugehoerigkeiten.party_id` or `party_seats.party_id`; the following `DELETE FROM parties` would hit the foreign key. Seat rows are written with normalized names after `initialize()`, and a schema-8 store is refused, so no current input reaches it.
36. **The Nachrücker trim can take a seat from the wrong leaver.** It pairs a leaver with any same-group Mandat starting on the leaver's last day, before pairing the normal case (a newcomer the day after). With leaver X ending 10.05, leaver Z ending 09.05, Y2 starting 10.05 (for Z) and Y1 starting 11.05 (for X), X loses 10.05 and `party_seats` reads 2, 1, 2 instead of 2, 2, 2; the size check and the cross-check's `change_on_vote_day` cannot see it. Measured on the live file (29.04.2026): the trim fires twice (FDP 2023-08-07, Grüne 2024-03-04) and neither has a same-group leaver the day before or a starter the day after, so no current figure moves. Fix: pair day-after newcomers first, trim only the leftovers. (Ship adversarial pass 3, 2026-11-02.)
37. ~~**`read_zip` accepts any VERSION that fits a datetime as the Stand.**~~ **Done in v0.46.15.0**: a Stand before 2017-01-01 or after now plus a day is refused.
38. **A huge in-cap XML can raise MemoryError out of `refresh`.** `ET.fromstring` on up to 64 MB of tiny elements is not a StammdatenError, so the build dies before the writer lock instead of keeping the cache. The crash form of item 25; same remedy. **2026-11-18:** the oversized-file route (item 42) is closed; an in-cap 64 MB XML of tiny elements can still raise MemoryError, so this stays open with item 25.
39. **Stammdaten refresh keeps an older-Stand cache: re-downloads every run** (review of the stammdaten store gate, 2026-11-17): `stammdaten.refresh` keeps the cached file when the fetched Stand is older, but also keeps the old ETag sidecar, so each later refresh downloads the full zip again and warns again. Cosmetic cost (bandwidth, one warning); fix by a "seen older" marker beside the ETag.
40. ~~**A store the offline Stammdaten check cannot query stops the render with no fix** (v0.46.15.0 /gstack-ship review, specialist and adversarial). `stammdaten_store_mismatch`'s `sqlite3.Error` branch (a store from an older schema without `mdb_stammdaten_stand`, or no SQLite file) prints "the store … cannot be read (…); it is left as it is" and stops a plain `--offline` render before `require_current_schema` could name the remedy. Untested. Fix: end the message with the `--offline --repersist` pointer, or let a missing table fall through to the schema check; add a test with the table dropped.~~ **Done 2026-11-18:** the message ends with the `--offline --repersist` pointer; a missing table does not fall through to the schema check (decision kept conservative); tested.
41. ~~**`_data_clone` can end the store gate with a traceback and no receipt**~~ **Done 2026-11-18:** `validate_store_gate.main` turns OSError and a failed `cp` clone (CalledProcessError) into `ERROR [gate]` with exit 2.
42. ~~**`read_zip` reads the cached zip whole with no size cap** (v0.46.15.0 ship review). `MAX_ZIP_BYTES` applies to downloads only; a hand-placed oversized file gives MemoryError, not StammdatenError, in `refresh` and `rebuild_seat_counts`. The cache is only ever written from a capped download. Fix: stat the file and refuse above `MAX_ZIP_BYTES` before reading.~~ **Done 2026-11-18:** `read_zip` stats the file and raises StammdatenError above `MAX_ZIP_BYTES` before reading.
43. **The future-Stand bound reads the host clock on every cache read** (v0.46.15.0 ship review). `_stand` refuses a Stand more than a day after now on each read, so a build host whose clock runs more than a day behind the file's VERSION makes a cache that passed before unreadable: rebuilds stop and `refresh` sends no If-None-Match. Decide whether the future bound belongs only in `refresh`, where the file arrives.
44. **Four untested refusal branches** (v0.46.15.0 ship coverage audit): `read_zip` on a missing or unreadable path (the OSError branch); `stammdaten_store_mismatch` on an unreadable store (item 40); `run_gate` with `store_counts` raising DatabaseError (`counts_before` unavailable); and `run_gate`'s `input_store.get("roster")` with an unavailable snapshot when the fresh build succeeds. **2026-11-18:** the first two (`read_zip` on a missing path, `stammdaten_store_mismatch` on an unreadable store) now have tests; the `run_gate` two remain.
45. **The download deadline still misses chunk framing and the header phase** (v0.46.27.0 /ship review: red team and native adversarial reader). `_download` reads the body with `response.read1`, so a body of declared length is cut off within one socket read of `FETCH_DEADLINE_SECONDS`. With `Transfer-Encoding: chunked`, `read1` goes through `http.client`'s `_read1_chunked`, whose chunk-size line `readline` (up to 64 KiB) and trailer lines can each take many socket reads of up to 60 s; the status line and headers are read inside `opener.open` before the first deadline check (that half predates item 32). Only www.bundestag.de itself can do this (TLS, same-host redirects); a failed fetch keeps the cached file. Fix: a watchdog that shuts the socket down at the deadline, covering headers and framing, with a chunked-body test. The `_download` docstring's "overrun by at most one socket read" holds for the body loop only; narrow it with the fix.
46. **A refused redirect leaves the 30x response open** (v0.46.27.0 /ship review, native adversarial). `_SameHostRedirects.redirect_request` raises before urllib's `http_error_302` reads and closes `fp`, so the socket stays open until garbage collection: one per refused build. Fix: close `fp` (when not None) before raising.
47. **`read_zip` checks the size and reads in two steps** (v0.46.27.0 /ship review, native adversarial). A cached file swapped for a larger one between `stat()` and `read_bytes()` is read whole (MemoryError). Swapping it needs write access to the private cache directory. Fix: open once and `read(MAX_ZIP_BYTES + 1)`.

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

### Vote direction: what the 2026-11-07 fix left open

Found while fixing how vote pages state the outcome of a Beschlussempfehlung to reject (votes 990, 638, 695, 774, 777, 801). None of these is a false statement: a vote without an established direction reads "Beschlussempfehlung: Angenommen" and "Die Beschlussempfehlung wurde angenommen".

1. **Vote 883 is a rejection the replay cannot establish.** bundestag.de: "Beschlussempfehlung 20/9559 (Antrag 20/9305 ablehnen)". It sits in report 20/141 (date 2023-11-30), but its documents are in the XML of 20/140 (2023-11-29), whose positions hold no decision on it. It needs (2) or (3).
2. **Votes whose documents their own report's XML never names.** 11 of 619: 883, 944, 945, 943, 948, 956, 969, 978, 977, 1008, 1034. For 883 and 956 the documents are in the previous sitting's XML, and the vote's date is the next sitting's, which is likely why they were filed there. The others were not traced. Chair evidence and the TOP link cannot reach any of them. Find out whether they are filed under the wrong sitting, and whether `votes.protocol_id` is wrong.
3. **The page's "(Antrag X ablehnen)" is not cached.** It states the direction outright on 990, 774, 777 and 883, and not on 638 and 695; 801 reads "(Entschl 20/2347)" with no direction. `fetch_roll_call_vote_detail` could keep it as evidence, but a replay gains nothing until each sitting is fetched again.
4. **The chair parser misses two shapes DIP now covers.** `_ANTRAG_WORD_RE` does not match "Entschließungsantrag" (777), and `fits` refuses a clause naming no Antrag number (774). A sitting cached before DIP records its decision would miss these until it is fetched again. How long DIP takes to record a decision was not measured. If it matters, take the Antrag number from the TOP's earlier sentence and diff all records and conflicts over the 619 votes.
5. **No state for a direction never established.** `inverted` is 1 or NULL, so the store cannot tell an established recommendation to accept from an unknown one. A state on the page needs a stored value: `inverted = 0` is free, and DIP's recorded acceptance ("Annahme …" or "Zustimmung …") on 108 Beschlussempfehlung votes is the evidence it would use, beside the chair's "anzunehmen". After this fix 15 Beschlussempfehlung votes have neither: Haushalt 374, 435, 531, 556, 705, 778; Bundeswehr 261, 611, 943, 944, 945, 948; and 883, 1008, 1034. Owner decision on the wording.
6. **DESIGN.md has no subject for a non-inverted Beschlussempfehlung.** Verdict and Vote lead name the Antrag on an inverted vote, and neither says what a non-inverted Beschlussempfehlung's verdict reads. Whoever applies them should carry "Beschlussempfehlung angenommen" over from `features.votes._badge_subject`, or the display verdict brings back the bare word this fix removed.
7. **DIP has a result where the site says "Ergebnis nicht verfügbar".** 12 votes with no result (special-majority procedures) have a DIP decision bound by tally: 481, 465, 467, 468, 307, 308, 574, 612, 613, 624, 970, 971. DIP's Beschlusstenor could supply the outcome. On the 350 votes with both a decision bound by tally and an outcome, it never disagrees with `derive.vote_outcome` after this fix, so it could also be a standing cross-check in the replay.
8. **The re-scope sticks in a saved report.** `_read_contradicted_official_result` writes `proposition` into the report. If a vote like 990 later lost its established direction, a replay would keep `proposition` where a fresh fetch gives `application`. No current input reaches this: 990 stands on both the chair and DIP, and either reading says the ballot passed. Keeping the page's scope in its own report field, as `official_result` keeps its word, would end it.
9. **The long badge wraps at 375px on the dossier panel.** Uppercased, "BESCHLUSSEMPFEHLUNG: ANGENOMMEN (BERECHNET)" breaks onto two lines inside its pill (20/210). It stays inside the card and the page does not scroll. Cosmetic, and the Stimmkarte work replaces this pill.
10. **A latent edge in the DIP binding (red team, 2026-11-07).** "Beschlussempfehlung auf Ablehnung" could also stand on a Gesetzentwurf, and the page would then say "den Antrag abzulehnen"; all 86 bound votes are on an Antrag or Entschließungsantrag. Gate on a linked document's type. (The second edge, `tally_of` reading an unknown count as 0, is done: see Completed.) The rival half is done too (v0.46.9.0). Left beside it (v0.46.9.0 ship review): a rival whose `total` is empty reads as compatible with every tally, so one roll-call with no parsed tally blocks every tally-only bind in its sitting (fails closed; no cached sitting has one; narrow it to rivals with at least one known count); a vote with document numbers is bound with no rival check at all; and `tally_of` calls `int()` on a rival's count unguarded, so a non-numeric count such as "–" refuses the sitting (as before).
11. ~~**The re-scope trusts any inversion source (ship review, 2026-11-09).**~~ Done 2026-11-17, see Completed.
12. **`derive.vote_outcome` turns a failed recommendation to reject into "Antrag angenommen".** On an inverted vote with Nein ≥ Ja it flips the derived "rejected" to "accepted", and the lead says "der Antrag wurde angenommen"; but the Antrag can still fall in a vote of its own. The DIP route accepts "Ablehnung der Beschlussempfehlung auf Ablehnung" as direction, which is right for `inverted`, and adds a way into this flip. 0 of 95 inverted votes have Nein ≥ Ja. Return None (or say "die Empfehlung wurde abgelehnt") there unless the result is official and about the Antrag.
13. **The DIP route has no rival check where the chair route has one.** For a vote whose listing is neither Vorlage nor Beschlussempfehlung, an Antrag number shared with the decision plus an equal tally binds; equal tallies on distinct votes are common (1026, 1027, 1028 all 445:132:1). 3 of 86 bound votes are of that kind (720, 575, 1003), all correct. A tally-only bind (no document numbers, 638) also trusts that the sitting's roll-calls were all acquired. Require the protocol path's rivals check, or a complete acquisition state, for those cases.
14. **A no-XML replay lets DIP re-open a vote the chair refused.** Without cached XML, evidence is None unless a protocol inversion was kept, so a chair "accept" or "conflict" recorded earlier is not carried forward, and a DIP decision can set `inverted`. A later XML pass where the chair refutes it also leaves item 8's `proposition`. No real case.
15. **Malformed DIP input.** `dip_vote_decisions` skips a non-dict position, a non-list `beschlussfassung` and non-ASCII digits since 2026-11-17 (see Completed). Left: the older `context_items` loop in `interpret_sitting_votes` (and `position_drucksache_numbers`) still raises on a position that is not a dict, and `clamp_text(note, 300)` could cut the rejecting phrase from a long note (fails closed). No cached record has either shape.
16. **The archive badge reads stored rows without `vote_heading`.** `_badge_subject` classifies over description, `vote_heading` and title, and the votes table keeps no `vote_heading`, so a vote whose Beschlussempfehlung wording sat only there would read differently on the archive and the dossier panel. Measured 2026-11-09: 0 of 597 badges differ. `_badge_subject` and `render_vote_lead` are also two copies of one decision (the lead names the Antrag for any application scope); have both read one helper.
17. ~~**Smaller structure.**~~ Done 2026-11-17: `dip_vote_decisions` returns `DipDecision` NamedTuples, see Completed.
18. **`result_scope = application` is 34 on the fresh reference store, against 24 recorded by #140.** Measured 2026-11-12 on `.context/dip-pulse-site`, which was built online from 28799ac and fetched every roll-call page again (`docs/plans/a3-phase4.md`, "Fresh reference store"). The 34 are 710, 712, 750, 753, 754, 760, 763, 768–771, 780–782, 802, 813, 842, 846, 848, 849, 851, 864, 865, 870, 877, 878, 891, 900, 919, 921, 938, 981, 996 and 1011. In 33 of them the official word agrees with the Ja or Nein majority. 996 is an inverted Beschlussempfehlung to reject whose box says "abgelehnt", which is the right word. The scope is read at fetch time and a replay keeps it. So either bundestag.de changed these pages after the A3 store cached them, or the A3 store's reports predate the scope rule. The A3 store is not on this machine, so nobody can tell which 10 votes are new. Read the pages of a few of them, such as 750, 753 and 754, check that each badge ("Antrag: …") is true, and correct `docs/source-errors.md` E6's scale if the pages say otherwise. 990 stays `proposition`.

**Effort:** M
**Priority:** P2 (1 and 2 first: a real rejection reads without its direction)
**Depends on:** None

### ADR 0004 follow-ups (owner decisions and deferred findings)

**What:** The ADR 0004 build (`docs/plans/adr-0004-presidium-kinds.md`) took every choice the plan auto-decided and left these:
- **Owner decisions.** O13: the nominations printed as a `<rede>` (20/1 `ID20100700` Mützenich, 21/1 `ID21101200` Merz, kept; 18/1 `ID1800100100`, 19/1 `ID19100900`, excluded) still count as Reden (option A, status quo); option B, procedural by list entry, moves Reden 54,855 → 54,853, CDU/CSU and SPD −1 each. To confirm: O1–O12 and O14–O18, and the hard cases H2 (19/1's empty `<rede>`, built as Sitzungsleitung), H3 (18/245 Singhammer, built as Ansprache), H4 (18/173 Lammert, built as Ansprache), H5 (18/1 Hintze, built as procedural with the chair's announcement printed under him; check the PDF page).
- **H1, O18: 19/1 Schäuble's address carries Solms's Redner-ID 11002190.** Done in v0.46.6.0 (2026-11-17): the entry for 11002190 names Solms as the id's holder, so his records stay as they are and only the Ansprache binds to Schäuble (11001938). The reviewed-units list entry still names the id as printed, which is right.
- **H7: 18/113 marker 3**, Pau's 1,897-character contribution as an Antrag's author, dropped by 6d inside another Redner's `<rede>`. Goes with the 18/96 / 18/109 rule below.
- **18/96 and 18/109** (`a3-pilot.md:207-208`): a Vizepräsidentin's Befragung Nachfrage dropped inside de Maizière's answer, and Bulmahn's closing text after another chair's marker. Pre-existing misses on kept sittings; they need their own rule and owner decision. Check first whether the A3 rule-5 work already restored 18/109's closing text (the commit once cited here, 5cc5982, is not in this repository's history).
- **Speakers printed as `<name>` who are not the chair** (census finding 8): Wanka 39 turns, Maas 4, Schwesig 2, Biermann 2, Woidke, Ramelow, Bentele and about 40 MdBs in WP 18/19 kept sittings are read as chair text and counted nowhere. In 18/4 this is why Maas's, Schwesig's and Wanka's oath answers were never counted. **Measured after T4 (2026-11-18, M4 of `docs/plans/t4-acquire.md`; receipt `docs/plans/t4-acquire/name-tag-speakers.tsv`):** turns of 15 words or more under a non-chair `<name>` inside another speaker's `<rede>`, whose text is in no table of the store (phrase test): 131 turns, 65,422 words, in 38 sittings, 130 of them in WP 18. 98 turns (45,561 words, 28 sittings) were there before T4; T4 adds 33 (19,861 words, 10 restored sittings, 13 in 18/29 alone, e.g. Krüger 1,552 words, Frei 652, Bartz 629; Schavan 1,067 in 18/42). Many are whole Reden given the floor separately, others Befragung answers (Wanka in 18/25 and 18/35, whose questions are stored as `befragung_frage`). They are counted in no figure and in none of M7's withheld shares, and a person whose first Rede is one of them gets a later debut. Needs a rule (store as the named speaker's Rede or Beitrag, or withhold under ADR 0005) and an owner decision before the first release.
- **A stage direction printed as `<name>` cuts the speaker short** (found by the review of T4 step 2, 2026-11-18). 20/25 `ID202506700`: Lamya Kaddor's `<rede>` holds `<name>(Vizepräsident Wolfgang Kubicki räuspert sich)</name>`. Her own closing 52 words follow it ("– Sofort, Herr Präsident. – Eines ist aber auch klar: …"), are read as chair text, and are in no table. A `<name>` in parentheses, or one naming no speaker, should continue the current speaker. Count such tags over the 801 files first. One is known, in a kept sitting, so it predates T4.
- **Display gaps, no figure:** addresses a WP 20/21 protocol prints as `<name>` chair text are not shown as Ansprachen; Solms's 19/1 opening address is loose `<p>` text after the empty `ID19100200`; an Ansprache's `char_count` and text can include chairing (whole-`<rede>` grain, O2).
- **A stored role for Ansprachen** (O10): the Dossier card's "Ansprache · Präsident" comes from the report. The A4 slice that moves the Dossier onto the store must persist the role (schema bump) or drop the suffix; add it to that slice's requirements in `docs/plans/a4-site-from-release.md`.
- **Guest person pages** (risk 4): a guest bound by Redner-ID gets an `mps` row and a page, as Bundesrat members do. Decide whether a non-MdB guest gets a page under `abgeordnete/`.
- **Census re-run** before step 6 admits the excluded sittings and before each data release: `docs/plans/adr-0004-census/census.py` and `review.py`; a row `review.py` cannot place is a new case for the owner. 18/20 is not in the census (W1's fetch failed for it).
- **The "Ja." acceptance test** (`validate_dip_protocol.procedural_candidate`) reads only the TOP heading and the previous `<rede>`'s trailing chair text; a "Ja." under a prompt printed elsewhere is counted as a Rede, caught only by the census re-run.
- ~~**AGENTS.md interpreter path** `/opt/miniconda3/bin/python3.13` does not exist on the current machine.~~ **Done in v0.37.0.0 (#147):** AGENTS.md names uv's CPython 3.13.18.
- **Ship review 2026-11-13, adversarial pass: deferred** (none reached by any current input). Three earlier items closed on the rebase onto #152: a list edit now forces a re-read of exactly the sittings it touches (`reviewed_digest`, ADR 0005 R3), and an unlisted unit or another speaker's turn in a listed procedural `<rede>` is withheld instead of refusing the sitting. Open:
  - A candidate flagged on a 6c split part (`IDxxx:N`) can never be listed: ADR 0004 entries name a whole `<rede>` and are matched before the split. It is withheld (`unreviewed_presidium`) instead.
  - `derive.presidium_reden` strips the display name, first and last name from a role; the parser also strips `namenszusatz`. Defence in depth only (the speech rule bump re-parses every report).

**Why:** the build counts no presidium `<rede>`, oath answer or acceptance unread (an unlisted one is withheld); these are the decisions and gaps it did not settle.

**Priority:** P2 (O13 and H1 before the first data release; the display gaps after)
**Depends on:** the owner for the decisions; coverage gate step 6 for H1.

### WP 18/19: nested Erwiderung, Erklärung and Geschäftsordnung turns (rule 5, a later round)

**What:** Three recurring kinds that WP 18/19 prints inside another speaker's `<rede>`, each needing its own rule. Since v0.39.0.0 (ADR 0005) their sittings parse with the refused Reden withheld, and leave the exclusion list at coverage-gate step 6 (T4); each rule then moves its withheld Reden back into the counts, with old/new figures (owner decision 5, 2026-10-22, [round 2](docs/plans/a3-rule5-wp18-19-round2.md)).
- **erwiderung-nested:** the addressee answers a Kurzintervention nested, and the chair's wording ("möchte noch kurz erwidern", "wünschen Sie zu erwidern?") is outside `invited`. 18/11, 18/20, 18/42, 18/88, 18/127, 19/12, 19/14.
- **erklaerung-nested:** a persönliche Erklärung, an Erklärung zur Aussprache (§ 30) or zur Abstimmung (§ 31) printed nested. 18/29, 18/97, 18/98, 18/117, 18/118. In 18/29, R3's wider floor wording now splits Groth's § 31 Erklärung (`ID1802902700:2`) as a Rede of its own; DIP lists it as "Mündliche Erklärung gem. § 31", so the rule must keep an Erklärung out of 6c.
- **go-debate:** Geschäftsordnung statements or motions printed nested. 18/2, 18/3, 18/67, 18/89.

**Why:** Each kind blocks 4–7 sittings; together they are about a quarter of the remaining WP 18/19 exclusions ([audit](docs/plans/a3-wp18-19-audit.md), [round-2 result](docs/plans/a3-wp18-19-round2-result.md)).

**Priority:** P2
**Depends on:** an owner yes per rule, then a test-first build and a new-rule unit review, as in round 2.

### 20/11: the chair's handover exchange with the next speaker, filed inside the previous `<rede>`

**What:** In 20/11 TOP 2 the XML keeps, inside Miersch's `<rede id="ID201100900">` after his "Vielen Dank.", the chair's "Nächster Redner: … Karsten Hilse", a remark to Hilse, Hilse's "Das freut mich sehr." and "Jetzt erteile ich Ihnen das Wort für Ihre Rede." The validator refuses the sitting (`unresolved nested contribution at ID201100900 marker 2`), rightly: Hilse's line is no Zwischenfrage. A rule would treat a nested exchange between the chair and the speaker of the next `<rede>`, after a floor grant to that speaker, as Sitzungsleitung, not a nested contribution. Since v0.39.0.0 20/11 parses with `ID201100900` withheld (ADR 0005, `awaiting_acquisition` on the exclusion record); the rule would restore that Rede to the counts, with old/new figures. The source error is E1 in [docs/source-errors.md](docs/source-errors.md).

**Why:** 20/11 (2022-01-13; TOP 2 is a climate and energy debate with Minister Habeck) is excluded since 2026-10-28 ([a3-phase3.md](docs/plans/a3-phase3.md), 4.4).

**Priority:** P2
**Depends on:** an owner yes on the rule, then test-first, and a check that no WP 18–21 sitting moves except 20/11.

### A3 pre-landing review: deferred findings (2026-11-01)

**What:** Findings of the /gstack-review of `worktree-a3-plan` (tip 41a7781) that are not correctness defects for any current input, so they were recorded instead of fixed (CLAUDE.md). The review fixed the literal `{abdeckung}` in the stored and exported `fact_metrics.caveat` and README rows 163/164; everything below is open. Found by reading the code (specialist, adversarial and red-team passes); none was reproduced as a wrong published figure.
- **Exclusion record (D2):** ~~(a) `--exclude-document-number` with a number the catalog does not list is silently dropped (not recorded, nothing printed), and with `--offline`/`--fetch-xml` the flag is ignored without an error; reject both, as `--include-document-number` already is.~~ **Done 2026-11-05:** an unknown number is refused online with exit 2, and the flag is refused beside `--offline` and `--fetch-xml`. ~~(b) A malformed `data/coverage-exclusions.json` (non-list `exclusions`, a non-dict entry, a missing `document_number`) ends every run, offline included, in a traceback; turn it into an `ERROR [cached input]` exit 1.~~ **Done 2026-11-05:** already done in #132 (`CoverageExclusionsError`). (c) The exclusion is applied after `load_existing_detail_entries`, whose `require_vote_shape` still raises for a stored-then-excluded sitting with an outdated report, so the exclusion cannot rescue that sitting. (d) `protocols/` dossier pages are never pruned (bills, Abgeordnete and Fakt pages are), so a stored-then-excluded sitting keeps an unlinked page on disk. (e) `dossier_failure_reasons` (`excluded`, `source_unavailable`) is set on the catalog dicts and written into `plenarprotokoll-catalog.json` (85 keys on `~/agent-runs/a3/full`); with `fetch_catalog` reusing closed Wahlperioden for 7 days, a sitting taken back with `--include-document-number` but not re-acquired keeps `presentation_state="unavailable"`/`excluded` in the publication manifest while the Daten list no longer names it. Strip the key in `catalog_payload`, or keep the reasons apart (offline renders currently read them back from the file; decide that too).
- **DIP request budget:** (a) `XmlPacer.fetch` raises `SourceSlowError` from `finally`, which discards a complete XML that took over 10 s and replaces an in-flight `DipError` (including `source_rejected`); nothing catches it, so the run ends in a traceback without the `[summary]`. Deliver the body and stop on the next call, and catch it in `main()`. (b) The pacer counts one request per `fetch()`, while `_fetch_page` retries up to twice more. (c) The per-sitting `/person` loop counts a 404 toward `PERSON_FAILURE_LIMIT`, while the breaker treats a 404 as DIP answering; with `DIP_FAILURE_LIMIT = 2` the person limit of 3 is rarely reachable anyway. (d) `DipBreaker` resets on 401/403, so a revoked key or a WAF 403 never stops the run. (e) After a breaker trip, `--enrich mp-roster` fails the rebuild (`DatabaseRebuildError`) before the `[summary]` prints; `ingest_mdb_roster` does not use the person cache `prefetch_dip_bulk --persons` fills. (f) `DipCache.save` rewrites both cache files after every sitting even when nothing changed. (g) The 2.0 s pace is defined three times (`BACKFILL_SLEEP_SECONDS`, `prefetch_dip_bulk.SLEEP_SECONDS`, `XmlPacer.spacing`).
- **Caches and catalog:** (a) `fetch_catalog` accepts the cached merge when the distinct-id count equals DIP's total, so a swap (one sitting gone, one added) in a closed Wahlperiode serves stale rows for up to 7 days. (b) A Vorgang cached from a closed-WP sitting (`linked_drucksachen_for_vorgang` labels it with the sitting's WP) never expires even if it is still extended in the current WP; a build between the WP 18 and WP 19 bulk prefetch embeds partial Drucksache lists in its reports. (c) `prefetch_dip_bulk._merge_vorgaenge` swallows an unreadable other-WP `vorgaenge.json` (`except (OSError, ValueError): pass`), which silently skips the cross-WP drop.
- **Identity and attribution:** (a) `_mp_external_ids` gives a record's one bundestag.de member number to every Wahlperiode it voted in, so a WP 19+20 record carrying its WP 20 number "conflicts" in WP 19 with a WP-19-only record of the same person (false split, not false merge); check against the gate store. (b) `person_registry._vote_evidence` takes a vote's Wahlperiode from `votes.protocol_id`, the recipes from `_VOTE_PROTOCOL_SQL` (agenda item first); share one rule. (c) A Rede split out by 6c cites the start page of its enclosing printed Rede (`rid_pages` from the table of contents), not the page it starts on.
- **Facts and pages:** (a) `write_facts_pages` rewrites `facts/methodik.html` on a render with no store file (since A4 slice 0 only a direct `render_site` call; the demo builds a store since slice 1) with `coverage=None`, overwriting the published "seit …" caveat with the neutral one; guard it like the archive page. (b) `coverage_label` names the earliest stored sitting, which can claim "seit Beginn der 18. Wahlperiode" mid-backfill while later Wahlperioden have gaps.
- **Performance:** `agenda_item_votes` has no index led by `vote_id`; `_VOTE_PROTOCOL_SQL` (r3, r4, r6) is a correlated scan per row (22 s on a synthetic 154k-row shape). Add `idx_agenda_item_votes_vote`.
- **Stderr and tests:** `ingest_mdb_roster` stats (`fetched`, `skipped_no_id`) count a person once per Wahlperiode; untested: the `CatalogCountMismatch` fallback, `_profiles_conflict`'s mixed number/link branches, the 6c page carry-over, `prefetch_dip_bulk` exit 2 and `--persons`; ~~`if __name__ == "__main__"` sits mid-file in `tests/test_a3_round2.py` and `tests/test_validate_dip_protocol.py`; unused imports in `tests/test_dip_request_log.py` (`re`) and `tests/test_validate_store_gate.py` (`hashlib`)~~ **Done 2026-11-05.** ~~`test_xml_pacing.test_backfill_dip_api_spacing_is_two_seconds` duplicates the backfill test.~~ Not a duplicate, kept: it is the only test pinning the value 2.0.

**Why:** Each is a place where a later edge case, operator typo or DIP outage could cost a run or publish a stale state; the review sorted them out of the A3 landing per the fix-now-or-defer rule.

**Effort:** M
**Priority:** P2 (exclusion record, budget (a)/(e), catalog (e)); P3 for the rest
**Depends on:** A3 merged

### A3 /gstack-ship review: deferred findings (2026-11-01)

**What:** Findings of the /gstack-ship review of `worktree-a3-plan` (after the main v0.26.1.0 merge 752684f) that are not correctness defects for any current input (CLAUDE.md). The same review fixed the stale "gemessen über 58 vergleichbare Wochen" in the knappste-abstimmung caveat, the Abgeordnete index copy for the former-MdB table, the `mps.wahlperiode` dictionary source and five README/PRODUCT.md/stable-ids sentences. Open:
- **Exclusion record (D2), continued:** ~~(f) `update_coverage_exclusions` runs right after the dossier loop (`build_dip_pulse_site.py`, before `reparse_cached_xml`/`require_parsed_reports` and the store rebuild), so a run that then fails with "The previous store is untouched" leaves the record listing a sitting the store still holds. Since A4 slice 0 a plain `--offline` render refuses that state ("recorded as excluded are still in the store", fix `--offline --repersist`) instead of rendering "nicht erfasst (ausgeschlossen)" beside counts that include it. Write the record after the store swap so the refusal cannot arise. (Also raised by the 2026-10-31 adversarial pass.)~~ **Done 2026-11-05:** the record is written after `rebuild_database_from_entries` returns. The window that is left is under "TODO round 2026-11" item 1. (g) `validate_manifest` does not check `coverage.excluded` (list of strings), so a malformed `--data-manifest` crashes `render_daten_datenstand`. (h) Untested cells of the exclusion state matrix: `--include-document-number` for a sitting not on the record (stored, unstored, rejected source), excluding an already-excluded sitting (recorded_at kept), and the plain `--offline` render of a recorded sitting (stored, unstored, already excluded: dossier dropped, store kept, `coverage.excluded` lists it); `test_backfill.py:527` stubs the store rebuild.
- **Gate and prefetch robustness:** `validate_store_gate.audit_links` raises on a href with `%00` or an over-long path, and resolves `..` outside the site; `_data_clone` `rmtree`s any `fresh`/`half` in `--scratch` without a marker; `prefetch_dip_bulk` and a build rewrite the same `data/dip-*-cache.json` without the writer lock; `dip_cache._closed` accepts non-dict `drucksachen` items (AttributeError later).
- **Parser:** `split_nested_reden` searches the chair text for the raw `last_name`, not `asker_name(last_name)`, so a WP 18/19 name printed with a middle initial ("W. Birkwald") misses a 6c split (no case found in the 716 cached sittings). `audit_offline_turns` looks up `mark_roleless_chairs`/`split_nested_reden` with `getattr` no-op defaults; call them directly. No test fails if the audit drops `mark_roleless_chairs` (18-100 audits the same without it).
- **One key, one rule:** the Wahlperiode of a document number is parsed in `build_dip_pulse_site.wahlperiode_of`, `prefetch_dip_bulk._wahlperiode_of`, `person_registry._vote_evidence`, `facts.coverage_label` and `_wahlperiode_sql`, beside the strict `facts.wahlperiode`; they disagree on malformed input ("21/x", stray whitespace). `compare_store_values` calls the private `registry._vote_evidence`. R3/R6 switched to an inner join on `protocols`, so a vote with NULL `protocol_id` would drop out (persist always sets it today; R4's method text says so, R3/R6 do not).
- **Cleanup (advisory):** `prefetch_dip_bulk.staged_positions` is test-only; `_catalog_list` repeats the cursor-paging loop of `counted_list`/`fetch_protocols`/`list_all`; the export manifest's `split_rede_ids` has no reader. Gate coverage: `validate_store_gate.store_counts`/`_store_identity`/`_persist_clone` run only in the real gate.
- **Adversarial pass leftovers:** (a) `DIP_REQUEST_LOG` logs `parts.netloc` and the full query of a non-DIP URL, so userinfo or a foreign token would land in the log (only DIP-supplied XML/roll-call URLs reach it today); log `hostname` and drop the query. (b) `prefetch_dip_bulk` never refreshes `total.json`, so with `--overlap-only` on the current Wahlperiode a grown DIP count makes every run stop on the final count check until the staging directory is deleted; and early in a Wahlperiode one month chunk can hold every position, which the `below=` guard rejects. Both stop the run; nothing wrong is written. ~~(c) The Daten scope line says "jede Sitzung ab der 18. Wahlperiode, für die der DIP-Katalog ein XML-Protokoll führt" while 85 such sittings are excluded; the next line names them, but the sentence could say "bis auf die ausgeschlossenen".~~ **Done 2026-11-05:** it says so when the build has exclusions.
- **Roster Wahlperioden, rule edges (adversarial pass on 8f13bf1):** ~~(a) list-of-ints check~~ done 2026-11-17 (see Completed). (b) The cut is per whole Wahlperiode and only ~200 of 1,360 MdB records carry a Fraktion role, so an MdB who takes a Land office mid-period (e.g. after a 2026 Landtag election) loses that whole period, and with no other period, the roster row; none on today's cache. Require sitting evidence (a vote or speech in that period) before cutting, or accept and document it. (c) Stores keep the old lists until `--enrich mp-roster` runs again (`preserve_roster`).
- **Roster Wahlperioden, residue:** `land_office_wahlperioden` drops the Wahlperioden DIP gives only a Land-government role (fixed in this review: 11 of the 1,360 cached MdB records, e.g. Scholz, Habeck, Högl). An office without a `bundesland` still counts: Eva Högl keeps WP 20, when she was Wehrbeauftragte and no MdB. DIP's `person_roles` mark Fraktion membership for only some periods, so a full rule needs another source (the Bundestag's MdB Stammdaten) or per-WP vote/speech evidence.
- ~~**Plan item 1.5 (Deferred from plan: docs/plans/a3-coverage.md):** the share of WP 18/19 Redner whose redner-id finds an abgeordnetenwatch `ext_id_bundestagsverwaltung` was never measured (a3-pilot.md: "not measured"; Phase 3 ran no aw-profiles). Measure it with `--enrich aw-profiles` on a clone of the A3 store and record it in the [Phase 4 record](docs/plans/a3-phase4.md).~~ **Done 2026-11-12** with the read-only `scripts/measure_aw_match_share.py` instead (0 DIP requests): M1 640/640 (WP 18), 719/727 (WP 19), 937/945 distinct MdB ids; Reden-weighted 98.3%; 8 name-rule flags and 11 name-found links reviewed, all the right person. Record: [a3-phase4.md](docs/plans/a3-phase4.md), "Plan item 1.5"; receipt `docs/plans/a3-aw-match-share.json`. Coverage-gate step 7 re-runs it.

**Why:** Recorded by the ship review so the PR could land; each is a latent edge, a guard gap no current input reaches, or test hygiene.

**Effort:** M
**Priority:** P2 (publication guard); P3 for the rest
**Depends on:** A3 merged

### abgeordnetenwatch profiles for WP 18/19: what item 1.5 leaves open

**What:** The measurement of 2026-11-12 ([a3-phase4.md](docs/plans/a3-phase4.md), "Plan item 1.5") found no wrong person. It leaves:
1. **Enriching WP 18/19 in the store (owner decision).** The fresh store (28799ac) holds no abgeordnetenwatch data at all: 0 `mps` rows with `aw_match`, no `abgeordnetenwatch-cache.json`, so all 945 distinct WP 18/19 MdB ids carry no profile link (M6). With a clean M3/M4, they could. Ways: `--enrich aw-profiles` on an online rebuild (a re-acquisition, about 26 DIP requests per sitting), or new code that attaches cached ext_id profiles offline in `reparse_cached_xml`, gated by `registry.redner_id_profile_reaches`. The scratch cache `~/agent-runs/aw-match/scratch/aw-cache.json` holds every answer of the run. Until then the Daten source card ("Rednerinnen und Redner werden … verknüpft — primär über die Bundestags-Redner-ID", `build_dip_pulse_site.py`) describes a link a store built without `aw-profiles` does not have.
2. **Person pages link name-found profiles.** `render_abgeordnete_detail` (`build_dip_pulse_site.py`) links `mps.profile_url` as "abgeordnetenwatch.de-Profil" whatever `aw_match` says, and persist writes `profile_url` for `aw_match = 'name'`. 91 such rows were in the reference store of 2026-10-31. In WP 18/19 a build would name-link 11 speakers (8 MdBs whose abgeordnetenwatch ext id is wrong, see 3, and 3 without one); all 11 are the right person today, by name and birth year. Roll-call links were restricted to trusted matches on 2026-10-31; person pages were not. Predates item 1.5.
3. **abgeordnetenwatch holds a four-digit `ext_id_bundestagsverwaltung` for 8 WP 19 MdBs** who left during the period: Bayaz `2028` (Bundestag id `11004664`), Beer `2031`, Gehrke `2085`, Hebner `2100`, Jung `2130`, Kemmerich `2136`, Löbel `2165`, Schüle `2239`. Seehofer, Kramp-Karrenbauer and Pinkwart have none. A source error at abgeordnetenwatch (outside `docs/source-errors.md`, which lists Bundestag sources); reporting it needs the owner's go.
4. ~~**The merged-record lookup key.**~~ **Done 2026-11-17** (`todo/abgeordnetenwatch-client`): `enrich_report_with_profiles` passes `derive.first_redner_id`. Offline on a clone of the 801-sitting store, with the item 1.5 scratch cache, the 10 merged-id speakers (Svenja Schulze, WP 21) get no profile either way (neither key nor her name search is cached); online they would be asked by `11005217`, not by the raw value.
5. **The roster's abgeordnetenwatch lookup is a name search only** (`ingest_mdb_roster`), so its biography columns are unverified in the same way. Also, `candidacies-mandates?politician=` returned no WP 18/19 Bundestag mandate for the 19 profiles reviewed (Franz-Josef Jung: 0 rows), so `fetch_bio` likely gives WP 18/19 leavers no Wahlkreis; not measured.
6. **A mandate check per hit, or the birth-year check in code,** if a future M3 flag is not settled by the name and the ext id. The review of 2026-11-12 compared birth years by hand (Stammdaten `GEBURTSDATUM` against `year_of_birth`), all 19 equal.

**Why:** None is a wrong link today; 1 is a coverage decision, 2 a latent false link, 3 a source error, 5 and 6 latent edges.

**Effort:** S each, except 1 (M with the offline attach, or the re-acquisition's run time)
**Priority:** P2 (1, 2); P3 for the rest
**Depends on:** 1 on the owner; 2 before any WP 18/19 store enrichment

### A3 item 1.5 review (2026-11-13): deferred findings

**What:** `/code-review high` and the `/ship` review of the item 1.5 branch. The review's findings 1–4 were fixed in 6daafe2; ship fixed the M2 share with unanswered ids and the `--json` overwrite (c08fb0f, 8c1ef51). These are not correctness defects in any current figure:
1. **The 2 s pace and the 60 s 429 wait apply to every build** (`abgeordnetenwatch.DEFAULT_MIN_INTERVAL`, `HTTP_429_WAIT_SECONDS`). A cold-cache `--enrich aw-profiles` run, about 1,300 roster name searches and `fetch_bio` calls, takes about 43 min instead of about 11. A 429 does not count toward the cut-off, so a run of them costs up to 4 × 60 s per request with no overall limit. The build's `--abgeordnetenwatch-sleep` accepts values below 2.0, while the script refuses them. The owner should confirm the fair-use reading of the API page (2026-11-12) and the cost.
2. **A failed ext_id lookup leaves a name-found link that later builds never retry** (predates item 1.5). `resolve` falls through to the name search after a `failed` lookup. The `match = 'name'` profile is then stored in the report, and `enrich_report_with_profiles` skips any speaker that already holds an `abgeordnetenwatch` key, so a transient error gives that speaker an untrusted link in that report for good.
3. ~~**No test covers a sitting the exclusion record lists.**~~ **Done** in e275e62 (`test_a_sitting_in_the_exclusion_record_is_skipped_and_reported`).
4. ~~**`lookup_ext_id` ignores `enabled`.**~~ **Done 2026-11-17** (`todo/abgeordnetenwatch-client`, with 5, 6, 8 and 11).
5. ~~**Dead exponential back-off.**~~ **Done 2026-11-17**: one 60 s wait per 429 (`HTTP_429_WAIT_SECONDS`); `Retry-After` is still not read.
6. ~~**A dropped connection or read timeout ends a run with a traceback.**~~ **Done 2026-11-17**: `OSError` and `http.client.HTTPException` are counted failures; `name_fallback` saves in `finally`.
7. **`--offline` exits 0 while ids are unanswered,** although `--help` says 0 is a complete result. The shares print as bounds, so no figure is wrong; only automation reading the exit status is misled. Return a distinct code, or document offline as always 0.
8. ~~**A malformed entry inside the answers file gives a traceback.**~~ **Done 2026-11-17**: exit 2 naming the file and the id.
9. ~~**A partial `mdb_zugehoerigkeiten` table is used whole.** `mdb_sources` takes the table as the Mandat source if it holds any row; a store built with `--roster-wahlperiode 21` only would push WP 18/19 MdBs from M1 to M1a/M1b and shift the M1 share, visible only as zip disagreements. Fall back to the zip, or refuse, when the table has no WP 18 or WP 19 row. Check before the coverage-gate step 7 re-run on a new store. Checked on the T4 store (2026-11-18): the table holds WP 18 to 21 rows, the receipt reads `mdb_zugehoerigkeiten`, 0 disagreements with the zip.~~ **Done 2026-11-18** (`todo/aw-measure`): the table is the Mandat source only with a WP 18 and a WP 19 row; otherwise the zip, or exit 2 naming `--roster-wahlperiode` when there is none.
10. **An answer is reused by state alone.** `lookup_all` reuses an earlier answer when the cache still holds the same state, not the same profile; a cache re-seeded from an enriched store could pair one run's candidate count with another profile. Store the profile id in the answer and require it to match.
11. ~~**`save()` uses a fixed `<cache>.tmp` name.**~~ **Done 2026-11-17**: the cache and the answers file go through `aw.write_text_atomic` (mkstemp in the same directory). Left open (P3, hygiene): a save killed with SIGKILL leaves its hidden `.<name>.<random>.tmp` beside the cache, and nothing removes it later (`politikfelder.write_atomic` removes such files after `STALE_TEMP_SECONDS`).
12. **The store guard misses a symlinked `OUTPUT_DIR/data`.** `run()` protects the resolved OUTPUT_DIR and private directory; if `data` links outside OUTPUT_DIR, `--json` at the store path resolves outside both and would overwrite it. Add the resolved store path's directory to the protected roots.
13. ~~**The offline request count ignores the answers file.** `--offline` prints "an online run sends N ext_id requests" with N = every Redner-ID, but online `lookup_all` skips an id once it is answered. On the T4 store it printed 1,041, where the online run asks 20 (the ids its own table counts as uncached), plus the name searches. Print the unanswered count. Found by T4 step 2 (2026-11-18).~~ **Done 2026-11-18** (`todo/aw-measure`): the offline line counts the ids with no non-failed answer in the answers file (the receipt's `requests.ext_id_keys` still holds every id). **Left open (review 2026-11-18, no figure moves):** the count is a lower bound. Online `lookup_all` also asks again when the cache no longer holds an answered id (`lookup_ext_id(key, network=False).state` differs from the answer's state: cache deleted or reformatted), which the offline line does not count. Count with the same state comparison, or print "at least N" (the tests at `tests/test_measure_aw_match_share.py` 408 and 411 pin the wording).
14. ~~**`write_text_atomic` sets mode 0644 outright** (`os.fchmod`), ignoring the umask, so under umask 077 the cache and answers files are world-readable where `write_text` kept them private. They hold public abgeordnetenwatch data. Use `0o666 & ~umask`. From the v0.46.13.0 /ship review (adversarial reader).~~ **Done 2026-11-18** (`todo/aw-measure`): the file gets `0o666 & ~umask`.
15. **Two `write_text_atomic` helpers.** `validate_dip_protocol.write_text_atomic`, used by about 15 build call sites, still writes through a fixed `.<name>.tmp` name, so the two-writer collision item 11 fixed for the aw cache remains for build outputs. Make one mkstemp-based helper and import it. From the v0.46.13.0 /ship review.
16. **The cooldown ends with the retries.** After the last 429 retry `_request` returns, and the next lookup (or `resolve`'s name fallback) asks again after the normal 2 s interval, not 60 s. The old loop had the same gap. Keep a resolver-wide cooldown on every 429. From Codex's structured review of v0.46.13.0 (P2).
17. ~~**The answers file is checked for its state only.** A hand-edited entry with state `hit` but a non-integer `candidates` or no `cached_id` passes `_load_answers` and raises later in `measure`. Validate the fields an entry is reused with. From Codex's structured review of v0.46.13.0 (P2).~~ **Done 2026-11-18** (`todo/aw-measure`): `_load_answers` refuses (exit 2, file and id) an entry without `cached_id` or with a `candidates`/`cached_id` that is neither None nor an int. `cached_id` may be None: a fresh hit on an uncached id writes it so.
18. ~~**A build gives no warning when abgeordnetenwatch lookups fail.** A dropped connection or timeout is a counted failure recorded only in `stats` and `last_error`, so a flaky network gives fewer profile links without a line in the build output. Failures are not cached, so the next build asks again. Print the error count when it is above zero. From the v0.46.13.0 /ship review.~~ **Done 2026-11-18** (`todo/aw-measure`): already done: `build_dip_pulse_site` prints the abgeordnetenwatch summary line with the `errors` count after every run, in a `finally` block.
19. **`write_text_atomic` reads the umask by setting it** (v0.46.27.0 /ship review, native adversarial). `os.umask(0)` then restoring it leaves the process umask at 0 for a moment; a file another thread created then would get mode 0666. No caller is threaded today. Fix: read the umask once at import.

**Why:** 1 is a build-time cost and a policy reading; 2 is a latent untrusted link; 9 can skew a future run; the rest are hygiene or latent.

**Effort:** S each
**Priority:** P2 (1, 2, 9); P3 for the rest
**Depends on:** 1 on the owner

### Refuse a render when the Vorgang cache is newer than the store

**What:** Record a fingerprint of the Vorgang cache (`dip-vorgang-cache.json`, plus the Antrag cache) when the store is persisted. An offline render then refuses when the cache on disk differs, and the message names `--offline --repersist`. This is the same shape as `require_current_speech_rules` (`persist_dip_pulse_store.py:93`).

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
- (a) **The coverage check matches sitting ids only.** `store_coverage_gap` (`build_dip_pulse_site.py:759`) compares the protocol ids, not the content. An online run that refreshes an already-stored sitting (backfill, narrowed `--document-number`, vote enrichment) and then fails its staged rebuild leaves new report JSON beside the old store row, and the offline render passes. Dossiers and `puls.html` then come from the new JSON, while MP pages, facts and the export come from the old store. This predates slice 0, and each later slice that moves a page onto the store shrinks it. The fix is a per-protocol report digest recorded at persist (like `speech_rule_inputs`) and compared in the check.
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

### TODO round 2026-11: deferred review findings

**What:** Non-correctness findings from building and reviewing `fix/todo-round-2026-11` (2026-11-05):
1. **A stop between the store swap and the exclusion record.** The record is now written after `rebuild_database_from_entries`. A killed process, or an OSError from `write_text_atomic` (a traceback, now after the swap), leaves a store without the freshly excluded sitting and a record that does not list it. A plain `--offline` then refuses with "cached report(s) are not in the store". The state is safe and the refusal names a fix, but that fix re-stores the sitting; re-running the exclusion is the right one. Say so, or write the record before the swap and roll it back on failure. The write also sits outside any `except OSError`, so a full disk gives a traceback; catch it there and print the online re-run command. An `--include-document-number` run stopped at that point is the mirror case: the record still lists a sitting the store now holds, the refusal's `--offline --repersist` drops it again, and "edited by hand" (`store_coverage_gap`, README's error table) doesn't describe it.
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
14. **Uncovered state cells.** No test excludes a sitting that `--limit`, `--protocol-wahlperiode` or `--document-number` narrows out of the acquisition; all exclusion tests run with `--backfill-incomplete`, so a regression that built `listed_in_catalog` from `acquisition_scope` would refuse real sittings unnoticed. The code is right today (`protocols` is the whole catalog). Also untested, and safe today: a recorded exclusion when the rebuild fails, a bad operator file with `--validate-publication`, and a bad operator file or data option with `--list-features`.
15. **r3 re-runs `_VOTE_PROTOCOL_SQL` for every `vote_members` row.** About 14 s on the reference store, against 0.06 s with `vp AS MATERIALIZED (SELECT v.id, <expr> FROM votes v)` (measured on a COUNT over the same joins, not on r3 itself; the new order adds nothing measurable). Predates the round. Materialize it in r3, or index `agenda_item_votes(vote_id)`.
16. **Two docstrings overstate.** `seat_rows` says the store's tables would refuse an empty or inverted row; the schema has only `CHECK (seats > 0)` and the primary keys, so these checks are the only guard for intervals. `refresh` says every outcome is one stderr line; a lost ETag write prints two. Its comment says a group-writable private directory is refused; `ensure_private_dir` repairs it and refuses only when the bits stay. `docs/designs/daten-page.md`'s r2 sketch orders by characters alone, the recipe by Wahlperiode first.
17. **The Daten page's `curl -LO` and `url =` snippets embed `data_base_url` unquoted,** and the guard still accepts `;`, `$`, quotes and backticks. The value is operator-supplied.
18. **The Fakt der Woche places a vote by another rule than the recipes.** `facts.py` takes the vote's own protocol first, then the smallest DIP protocol id; `_VOTE_PROTOCOL_SQL` takes the first sitting whose agenda item claims the vote, by number, then its own protocol. Predates this round, which only makes the recipe side precise. 0 of 619 votes differ on the replay store, so no figure moves today; a vote claimed in two sittings could.
19. **A refused Stammdaten download only warns.** A future file with a one-day row on a handover day is refused, so the seat tables stay on the old Stand with a green build; the cross-check's `after_stand` warning is the only other signal. Related to item 10.
20. **Small ones.** A failed write leaves the earlier cross-check report in the private directory, and the summary line only drops its path. No test pins that a non-ASCII `--data-base-url` with no secret shows the placeholder, which also hides a legitimate IDN host from the message.

**Why:** Deferred under the CLAUDE.md fix-now-or-defer rule: none is a wrong figure or a false statement today.

**Effort:** S each
**Priority:** P3
**Depends on:** None

## Protokoll-Dossier

### Split or filter overview.html by Wahlperiode

**What:** Split or filter `overview.html` by Wahlperiode instead of one page with every card.

**Why:** A3 (v1 coverage) took the page from about 290 to 718 cards (A3 review D8, 2026-10-19; the fresh store of 2026-11-12). Page weight after A3: measured in the A3 Phase 4 check.

**Context:** `render_overview` (`scripts/build_dip_pulse_site.py:11044`) renders one card per generated dossier.

**Effort:** S
**Priority:** P3
**Depends on:** A3 (v1 coverage)

### Say when a count covers only Sitzungen mit Dossier

**Part 1 completed:** v0.23.4.0 (2026-10-29). Public copy says "Dossier": the Methodik's "Erzeugtes JSON" bullet ("Jedes Dossier verlinkt …", was "Sitzungsseite"), the overview heading "Erzeugte Dossiers" (was "Sitzungsdossiers"), and the internal component label "Dossiers" (was "Protokoll-Dossiers"). A test keeps the avoided names off both pages.

**What is left:** wherever a published count spans a range for which the catalog lists more Sitzungen than have a Dossier, say so, e.g. "in 60 von 94 Sitzungen (nur Sitzungen mit Dossier)". Audit on main at v0.23.1.0 (2026-10-29):
- Already disclosed: the Daten Datenstand ("N von M Protokollen im Katalog als Dossier erfasst", `render_daten_datenstand`), the votes archive footer ("… der Sitzungen in der Datenbank dieses Builds, also nur Sitzungen mit Dossier", A4 slice 1), and the catalog's "Erzeugte Dossiers" tile and its "Nur mit Dossier" filter.
- Not disclosed: the Abgeordnete list's "Reden" column (`render_abgeordnete_index`), the puls.html header and Wochenvergleich, the Fakten pages and Methodik, and the speech counts on the Gesetzesvorhaben pages.

**Why:** CONTEXT.md "Sitzung mit Dossier": every count covers only Sitzungen mit Dossier, because the store is rebuilt only from Dossier entries (`rebuild_database_from_entries`). A build with `--detail-limit` silently reports a subset as if it were the whole Wahlperiode.

**Context:** A3 merged (v0.27.0.0): `render_abgeordnete_index` (`build_dip_pulse_site.py:9697`), `coverage_line` in `render_daten_datenstand` (`:5265`) and the Fakten coverage text (`facts.coverage_label`, `fill_caveat`, `facts.py:2464`, `:2480`) exist. Reuse those rather than adding a second coverage phrase.

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

### Puls outward (batch 7): deferred review findings

**What:** The /gstack-review of `fix/todo-batch-7-puls-outward` and the v0.28.0.0 /ship (2026-11-01) left these:
1. ~~Verify `data/sitzungskalender.json` against the first real bundestag.de fetch.~~ Verified by the fresh online build (2026-11-12): 43 weeks from 2 files, 22 for 2026, 21 for 2027; the module docstring now records it, and a week listed twice or split into two events is merged per ISO week (done 2026-11-17). Left, decisions: a SUMMARY like "Keine Sitzungswoche" or `STATUS:CANCELLED` still counts as planned; a parse with 10–15 weeks silently replaces a cached 22-week year, so refuse one that loses cached future weeks; a week spanning New Year rejects its whole year, and since 0.46.17.0 the per-ISO-week merge also builds such a week from two events either side of 31 December (both in one ISO week), so key the merge on (calendar year, ISO week) or split the merged week at 31 December when deciding this (ship review of 0.46.17.0, specialist red team and adversarial); two files for one year do not merge (the later file replaces the earlier one's year).
2. A failed calendar fetch never advances `fetched_at`, so while bundestag.de is down or blocking, every online persisting build retries, at up to about 15 minutes each (5 fetches, 60 s timeout, 2 retries). Record the last attempt and add a total time budget. (A `fetched_at` in the future is now treated as due, 2026-11-17.)
4. An RSS item is published (fixed GUID, fixed pubDate) for any finished week, even when DIP's Plenarprotokoll lag or an incomplete backfill leaves the week with only some sittings; feed readers never re-fetch an item under an unchanged GUID. Hold the item until the week is complete, or add a completeness field. Decide before `BUNDESTAG_PULSE_SITE_URL` is set for a public site.
5. The gap sentence ("… sind hier noch nicht ausgewertet") is false on a pinned `--week`/`--today` build whose archive does hold later weeks; count only planned weeks with no sitting in the archive, or drop the clause when the week is pinned.
6. Smaller: the calendar index page and `.ics` files are read without a size cap, and the index goes through stdlib `html.parser` (quadratic on hostile markup before the 2025 patch releases); `urlopen` follows a redirect from bundestag.de to any host, and the host check ignores the port; the cache and feed temp files are a fixed name in the published `data/` and `feeds/`, with no lock; `refresh_if_due` and `render_site` both load a damaged cache, so it warns twice; `CHANNEL_TITLE` repeats the puls.html `<title>` literal (its comment says it is the one place to change); the feed calls `render_dip_pulse_html._entry_protocol` (private); `_is_due` uses bare literals for October and the daily retry; `build_payload(weeks_back=)` and `refresh_if_due(max_age_days=)` are parameters no caller sets.
7. ~~From the 0.46.17.0 ship review: `_cut` separator controls, `_XML_ILLEGAL` surrogates and U+FFFE/U+FFFF, the invalid-URL warning with `repr()` or fully hidden `@` value~~ (done 2026-11-18: spaced, extended, and the warning shows `scheme://host/` with userinfo masked, `ungueltig` when unparseable). Still open from that fix's review: (a) `_XML_ILLEGAL` covers the RSS text only, `write()` first dumps the JSON payload with `ensure_ascii=False` and writes UTF-8, which still raises `UnicodeEncodeError` on a lone surrogate in a title (`'a\ud800b'`); no current input carries one (entries come from the store or cache, sqlite text cannot hold one), fix by sanitising titles when the payload is built or by `ensure_ascii=True`; (b) `_shown_url` masks the host as `***` whenever `@` appears outside the netloc, also for a harmless query (`https://pulse.example.org/?mail=a@b` logs `https://***/`); conservative and leaks nothing, mask only when the netloc itself is the secret if the operator needs the host; (c) from the v0.46.25.0 ship review: the separator spacing sits in `_cut`, which only the item title uses, so the item description (`_item_description`, written through `_xml_text` alone) still glues two words at a `\x0b`, `\x0c` or `\x1c`-`\x1f` in a lead title or sibling title (`Titel\x0bmit` reads `Titelmit`); whether any stored title carries one is not checked; fix by spacing `_SPLIT_SEPARATORS` inside `_xml_text` so both paths share it; (d) `_shown_url` logs an IPv6 host without brackets (`https://::1/`), log line only.

**Why:** (1) is the one unverified input format. The rest fail soft, need an operator mistake, or have no current input (RSS is written only with `BUNDESTAG_PULSE_SITE_URL`, which nothing sets yet).

**Effort:** M
**Priority:** P2 ((4) before a public feed)
**Depends on:** None

## Fakten

Design doc: `docs/designs/fakt-der-woche.md` (office hours, 2026-09-19). The session chose Approach A (engine + two metrics + one weekly SVG card + Methodik, registry-shaped) as a **test run** of the concept; Approach A (A0 + A1, all eight metrics, weekly and monthly) shipped in v0.6.0.0. The items below are Approach B/C, the full implementation A was the test for. They are deliberately not discarded.

### Resolve fact citations by id

**What:** `_fact_agenda_item_citation` and `_fact_proceeding_citation` in `scripts/build_dip_pulse_site.py` find a receipt's agenda item by `(document_number, page_start = ?, page_start_quadrant IS ?)`. An agenda item without a printed page has a NULL `page_start`, which `= ?` never matches, so its citation does not resolve and `_renderable_fact` drops the fact. `IS ?` would be wrong too: several page-less items of one protocol would tie. Look the item up by the receipt's `source_entity_id` (`ai.id = ?`) instead. In the 2026-11-17 reference store, all 317 agenda-item receipts resolve by id. `_fact_speech_citation` has the same flaw in its page anchor for synthetic rede ids (`s.page = ?`); no receipt reaches it today, but resolve it by id too.

**Why:** Found by `tests/test_code_rules.py` (class 5, absent vs zero) on 2026-11-18. The reference store has 1,810 agenda items with a NULL `page_start`, 106 of them with speeches. Today only two withheld `laengste-debatte` facts cite one (2023-W16 on 20/97 as `below_floor`, 2025-W28 on 21/17 as `no_topic`), so no page changes. A page-less item that wins a publishable fact would vanish without a warning.

**Context:** When it's fixed, remove the three page entries from `nullable_comparisons` in `tests/code_rules_baseline.json`. The docstrings' "0 duplicates, measured 2026-09-22" covers only the page key.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Fakt der Woche, rasterize and post one card

**What:** Open a published Fakt der Woche card, rasterise it with `qlmanage` (or equivalent), and post it. The one A1 "done when" criterion that isn't code - split out on its own so it doesn't keep a fully-shipped engineering item sitting open.

**Why:** A1's design doc lists this as part of proving the cards are postable; intentionally not gated on the v0.6.0.0 ship (2026-09-24 ship decision D1: manual/promotional action, unrelated to code correctness).

**Effort:** S
**Priority:** P3
**Depends on:** A1 shipped (done)

### Fakt der Woche, publication ledger (`facts_published`)

**What:** A `facts_published` table (or a JSON file under `data/`) appended the first time a week's card is selected, preserved across online rebuilds the way roster rows are (`rebuild_database_from_entries`, `scripts/build_dip_pulse_site.py:1606`), never overwritten; the week page shows "veröffentlicht als … / aktuell …" when they differ.

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

### Placeholder Redner ids put one speaker on two Personenseiten

**What:** (Re-measured 2026-11-12 on the fresh 718-sitting store: 93 placeholder records, 89 with Reden; Dahmen 7/37 and Giffey 34 unchanged. The other per-person figures below predate #141.) 98 `mps` records have an `xml:99999…` key, a placeholder-looking Redner id in the Bundestag XML. 86 of them are a person of their own although the same name also has another person, holding 463 Reden and 1,423 other Beiträge. Examples: Svenja Schulze (48 Reden, 262 Beiträge), Dr. Franziska Giffey (34, 119), Klara Geywitz (27, 157), Dr. Janosch Dahmen (7 Reden under `999990105`, 37 on his main page). Measured 2026-11-05 on e7b06f3: the same in a store-less build and an upgraded store, and E4 does not touch it. Since 2026-11-07 the records `xml:999990108`, `xml:999990124`, `xml:999990127`, `xml:999990134` and `xml:999990141` are gone (`docs/source-errors.md` E7, C8). So for Widmann-Mauz, Kramme and Ferlemann this decision was taken ahead of it: their Staatssekretär units are on their main pages, because no record could stay on an id shared with someone else. Object here if that is wrong for them.

**Why:** A reader sees part of a person's Reden on each page, so a page's Reden count is short. This has not been checked against the intent: a comment in `derive.py` reads one such id (`999990013`) as an explicit government role, so the split may be deliberate for some of them, though not obviously for Dahmen, who held no government post. Decide that first, then report the moved person counts and pages old/new.

**Context:** The name matching behind these counts ignores titles and anything after the first comma. Registry territory: needs a registry reviewer.

**Effort:** M
**Priority:** P2
**Depends on:** None

### The Abgeordnete index scrolls sideways at 375px

**What:** At 375px the table on `abgeordnete/index.html` (`table.mp-table`, columns Name, Fraktion, Wahlkreis / Bundesland, Reden) is 404px wide, so the page scrolls horizontally and the Reden column sits past the edge. Found in the /ship browser check of 0.41.0.0 (2026-11-13, dark mode, store of 718 sittings); that release touches no rendering code, so this predates it. The Personenseiten themselves do not overflow.

**Why:** On a phone the Reden count is cut off unless the reader scrolls the whole page sideways.

**Context:** Fix with a scroll container around the table or by folding Wahlkreis / Bundesland under the name below a breakpoint, then check at 375px and in dark mode (DESIGN.md).

**Effort:** S
**Priority:** P3
**Depends on:** None

### Roster MdB records that never join their speaker: 56 empty duplicate Personenseiten

**What:** On the fresh reference store (2026-11-12, 28799ac plus the registry fix of `docs/plans/registry-split-koestering-krampe.md`) 56 Personenseiten show 0 Reden, 0 Beiträge and 0 Stimmen. Each is a DIP roster record (exact "MdB" funktion) that pass 2 of `person_registry.match_rows` did not join to the speaker and roll-call person of the same human being. 54 of them have a twin page with activity under the same name once titles, accents and a bracketed Wahlkreis are ignored, for example:
- "Achim Post (Minden)" beside "Achim Post" (35 Reden, 534 Stimmen);
- "Aniko Glogowski-Merten" beside "Anikó Glogowski-Merten" (25 Reden, 187 Stimmen);
- "Anita Schäfer (Saalstadt)", "Axel E. Fischer (Karlsruhe-Land)", "Axel Schäfer (Bochum)", "Carsten Müller (Braunschweig)": DIP's `titel` carries the Wahlkreis in brackets, the Plenarprotokoll does not;
- "Alexander Bartz", "Bela Bach": the same printed name on both sides, so the block is elsewhere (the party, or a second name+party bucket).

The other 2 have no exact twin: "Heinz Wiese (Ehingen)" and "Uda Carmen Freia Heller" (printed "Uda Heller"). The real page then lacks the roster biography (`is_mdb` false, no Wahlperioden from the roster), and the duplicate is listed on the index.

**Why:** Two pages for one MdB, one of them empty; the page with the Reden does not say the person is an MdB.

**Context:** Found while measuring the registry fix (step 0). Not a replay/fresh divergence: the fresh online build and its replay agree. The fix is a normalisation of the DIP `titel` name (bracketed Wahlkreis, accents) before `name_party_keys`, or a reviewed list; registry territory, needs the namesake guard checked.

**Effort:** M
**Priority:** P1
**Depends on:** None

### Government-office DIP records: a second person without a page

**What:** DIP issued five MdBs a new person record for a government office and keeps the old MdB record on the roster: Linnemann 1173 → 8250, Otte 615 → 8226, Steiniger 1624 → 8255, Castellucci 1537 → 8247, Bilger 1013 → 8251 (2026-11-12 store). The new record is a person of its own with no Reden, no Stimmen and no page; the MdB page is complete. They are not in `dip_successors`, because there the old record would lose `is_mdb` and the page its biography.

**Why:** The published registry tables count each of them as two persons. No page or figure on a page moves.

**Context:** A `dip_successors` entry in the other direction (new → old), or a reviewed merge, would join them. Decide when the registry tables are first published.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Registry fix review (dip_successors, live preserved roster rows): deferred findings (2026-11-13)

**What:** Non-correctness findings from the `code-review high` of the registry fix (`docs/plans/registry-split-koestering-krampe.md`). None moves a figure on the 2026-11-12 reference store. The review's one gate gap (no hard replay-vs-fresh check once the input is itself a replay) was fixed in the same branch with `replay_vs_fresh`, and so was the page keying of `person_pages` (a person with a binding the input lacks showed as lost plus gained instead of changed).
- (a) **A `dip_successors` entry cannot be withdrawn in a replay.** Pass 1 joins the old and new records durably (the retired person key stays an alias), and the old row is stored with `is_mdb = 0` and no `ever_mdb`. Deleting or correcting the entry therefore leaves the merge in place. `_read_roster_rows` then keeps the old row only through `is_mdb`, `roster_member` or `superseded_dip_person`, and all three are false, so every offline replay drops the record until the next `--enrich mp-roster` build. A wrong entry needs a `splits` entry, and the removal needs the old row to come back from the roster. Latent: both entries are reviewed.
- (b) **A successor the roster stops listing.** `ingest_mdb_roster` warns when the roster lists a superseded id without its successor, but `upsert_mp` still stores the old record as a non-MdB, so the person has no roster MdB record at all. If DIP dropped 8257 and kept 8054, Krampe's page would lose `is_mdb`, the roster Wahlperioden and the biography until the entry is edited. Consider keeping `is_mdb` on the old record when its successor is not on this roster, or refusing the build. Latent.
- (d) **Test gap:** no test drives `run_gate` with the new checks (`replay_keeps_input_grouping_and_pages`, `fresh_build_lists_the_input_roster`, `replay_groups_like_fresh`): the snapshot taken before the replay, and the fresh store passed to `replay_vs_fresh`. A refactor that snapshots after the replay would pass every unit test. Only the full-data receipt shows the checks working.
- (e) ~~**Efficiency:** `dip_successors()` rebuilt its dict on every call.~~ Done 2026-11-17 (see Completed, "Shared Redner-IDs: loader checks, role words, one record load").
- (f) **Left from the fix of 2026-11-17** (`_read_roster_rows` now keeps a superseded-id row only when its `function` holds the exact "MdB"): a row a report sampled under the old id whose DIP `funktion` is itself "MdB" still reads as a roster row, since `mps` keeps no mark of which source wrote a row. Every cached report samples only the successor ids. A sharper test would also require `person_roles_json`, which only the roster ingest writes; check that every stored roster row of an older store carries it first.
- ~~(i) **A gate edge in `validate_store_gate.persist_only`**~~ **Not open (checked 2026-11-18):** `persist_only` reads its protocols with `load_cached_protocols`, which already merges `data/plenarprotokoll-catalog.json` with the cached reports, so a catalog Wahlperiode with no cached sitting is counted; pinned by a test. (Its second half was fixed 2026-11-17.)

**Effort:** S each
**Priority:** P3 ((a) and (b) P2 if an entry is ever revised)
**Depends on:** None

### Group MP pages by Wahlperiode and write abgeordnete.json without indent

**What:** Group or page the speech and vote rows on each MP page by Wahlperiode, and write `data/abgeordnete.json` without `indent=2`.

**Why:** After A3 a long-serving MdB shows up to twelve years of Reden and roll-call votes in one list, and the JSON grows with them (A3 review D9, 2026-10-19). Sizes after A3: measured in the A3 Phase 4 check.

**Context:** MP detail page `render_abgeordnete_detail` (`scripts/build_dip_pulse_site.py:9902`); JSON dump `:10102`.

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

### Apply DESIGN.md to the site

**What:** `DESIGN.md` ("Stimmkarte") was written and approved by the owner on 2026-11-04, and revised with the owner on 2026-11-06. No site page uses it yet. Apply it in the current Python renderer:
1. **One shared stylesheet.** Replace each page's inline `<style>` (41,232 bytes on a dossier, repeated on every page) and its own `:root` block with one cached file, linked relatively so every page depth works.
2. **Fonts.** Self-host D-DIN Condensed Bold, Atkinson Hyperlegible Next and Mono as WOFF2 (about 95 KB), with their OFL licence texts. Serve D-DIN unmodified: its names are reserved. The Datenschutz sentence about same-host assets stays true; check it when this lands.
3. **Fraktion colours.** Replace `PARTY_COLORS` in `render_dip_pulse_html.py` with the tuned values. Bundesregierung, Bundesrat and fraktionslos lose their hues. Today's values were not tuned against the design's grounds.
4. **Components.** Vote wall and strip, tally, source line, origin line, gap, slip versus ground, navigation, Stand line, Zitieren line, vote lead, home doors, Daten's release blocks and CSV control. Votes pages first: the archive now renders from the store (#133). Do not convert `api-sitzungen.html`, `settings.html`, Fakt der Woche or the AI summary: all are out of v1 (`docs/plans/v1-scope-review.md`).

**Why:** the owner finds the site unattractive, and the design system does nothing until pages use it. Every page has to carry the token blocks and the font stack today.

**Context:**
- `DESIGN.md` holds the rules and a component inventory with tokens for the stylesheet.
- Preview on real data, every surface at 375 px and in dark mode, with a switch back to the earlier look and a page comparing grounds: `~/.gstack/projects/LucaAlv-poliwatch/designs/design-system-20261104/stimmkarte-v2.html`, generator `build_preview_v2.py` beside it, for values and markup.
- Known limits are in DESIGN.md under Colors: Fraktion hues fail colour-blind separation, so the rules "always with the name" and "facet, never overlay" are binding. Ja and Nein are close in lightness in dark mode.
- Nobody outside this project has seen the design. The five-reader test runs after this rollout, just before launch (decision Q16), so keep to `DESIGN.md` "Held Open Until the Reader Test": the ground and the vote wall stay token-only. Beside its tasks, ask what the edged sheet means and what a Ja on the BAföG vote means.
- Age and overdue are worked out in the browser (`DESIGN.md`, Stand line), which retires `STALE_AFTER_WEEKS`, "Auswertung vom" and the "Woche läuft" state in `build_dip_pulse_site.py`. The due date needs the scheduled workflow's rule; the identifier format needs the release work.
- The Zitieren line (`DESIGN.md`) needs three things from the release work: which Sitzungen the stable release holds, a comparison of each record against that release (without it, "unverändert" may not be printed), and a page rebuild whenever a release is marked stable. A site build today has none of them.
- The origin line must name what each sheet's rows were actually read from, so check each renderer's source when applying it. A person page mixes DIP (Funktion, Wahlperioden) and abgeordnetenwatch.de (Geburtsjahr, Beruf, Bundesland, Wahlkreis). The preview's person sheet is too narrow to show this: it has one DIP line, and its Fraktion and Wahlkreis rows need checking.
- The CSV control lists a release's files, because no single archive exists. One archive per release would make it a direct download; decide that in the release work.
- The nested cards the puls.html review flagged are absorbed here. `DESIGN.md` makes visited links look like unvisited ones, so every link `:visited` rule goes (`render_dip_pulse_html.py`, `build_dip_pulse_site.py`).
- Tests assert CSS and markup strings, so expect churn (`tests/test_render_dip_pulse_html.py`, `tests/test_build_dip_pulse_site.py`, the browser checks). Put an inverted vote in the tests.
- The preview and the chart prototype exist only on the owner's machine, under `~/.gstack`. Copy into the repository whatever the pages need.
- The preview predates E4: `build_preview_v2.py` reads `vote_fractions` as the printed counts, and its store and the A3 store have no `listed_party_id`. Pages need the rule under `DESIGN.md` Vote wall, on a store rebuilt with E4. A row with a re-filed Stimme prints both numbers, which goes beyond today's note (`_refiled_note_html` names the members). Put a re-filed vote in the tests. Release identifiers, dates, sizes, the 29 files in the CSV control and the citation in the preview are examples.
- Deferred from the `/gstack-ship` review of this entry (2026-11-07), none of them a wrong statement on a page today:
  - **Gaps to settle in `DESIGN.md` before building the pieces.** Verdict and Vote lead give no wording when `derive.vote_outcome` is None (22 of 556 votes in the A3 store, and it could be the newest), and the Vote lead has no "berechnet" note for a `result_source` that is not official (356 of 534 verdicts there). Sitzungen promises a reason per excluded sitting: since v0.39.0.0 each of the 86 entries in `coverage-exclusions.json` has a reason code and a sentence, so Sitzungen can print them. The word for a verdict comes from the site's labels (`RESULT_BADGE_LABELS`), not from `derive.vote_outcome`, which returns a code.
  - **Wording that disagrees within `DESIGN.md`.** "Generated text" on a slip is undefined, and the inverted vote's key ("Ja (hier: gegen den Antrag)") stands on the slip although Surfaces lists "für" and "gegen" as ground. The log's rows on display size, a third mode and both doors on the first screen are not marked superseded. "Below 760px" and "Between 760 and 1000px" disagree with `max-width: 760px` at exactly 760. The radar row's title size is not in the front matter. The Stand line example says "Release" where visitors read "Stand". "Six small panels" is fixed only in the log, and the Analysen layout depends on the count. CSS variable and family names need a stated mapping to the front-matter tokens. Atkinson Mono 700 has no use in the type scale, and the five-font count depends on it.
  - **References that need another document.** `docs/plans/v1-scope-review.md` and commit cc0b0f7 are only on `claude/strange-germain-01ea7e`, so decisions Q3 to Q16 can't be followed from main until that lands. "Principle 6" is `PRODUCT.md`'s and "stage 2" the plan's Q1; neither is named as such. The log's "Mehr" is "Weitere Bereiche" in today's code.
  - **Figures tied to one store.** The longest title, 642 characters, holds for the preview store; the A3 store has 1,114. The three-month gap behind "date first" also comes from the preview store: on the A3 store the newest vote is in the latest Sitzungswoche. 252 MB is the A3 build's gzipped SQLite.
  - **States the rules leave open, from the adversarial passes. Settle these with the owner before building vote pages, because each can print something false.** (a) Direction unknown: `recommendation_inversion` returns True or None, never False, and None also covers a conflict, a blocked read and no evidence (`validate_dip_protocol.py`), so the store cannot tell "not inverted" from "not known". NULL mostly means not inverted: in the E4 gate store (619 votes, 2026-11-07 fix applied) 95 are inverted and 15 Beschlussempfehlung votes have no established direction ("Vote direction: what the 2026-11-07 fix left open", item 5). The A3 store's "NULL on 529 of 556" predates the interpretation fixes and measures nothing. `DESIGN.md` has no state for "direction not established" on a Beschlussempfehlung; since the fix the site names the Beschlussempfehlung in such a verdict ("Beschlussempfehlung: Angenommen"), which is true either way. (b) "A week without a roll call says so" and "Letzte namentliche Abstimmung" need complete acquisition (`validate_dip_protocol.py` scan states, the partial warning in `features/votes.py`); partial data must not read as "no vote". (c) A count the source did not give is NULL, today "nicht überliefert" (`tests/test_features_votes.py`), and the strip and totals have no form for it. A member's `vote` can be `unknown`, which the wall's four kinds leave out. (d) Release states: no release yet (`local` builds), no stable release, no DOI, a record in stable but gone from main. "Unverändert" needs its unit defined as every figure printed on the page. Two releases can reach the same Sitzung and differ in an aggregate (E4 moved Abweichungen 3,711 → 3,720), which the "counts over many Sitzungen" state can't say. (e) `DESIGN.md`'s Verdict and Vote lead say an inverted vote reads "Antrag abgelehnt". In the E4 gate store 94 of 95 inverted votes read that after the 2026-11-07 fix and one has no result; before it, vote 990 read "Antrag: Angenommen" from a self-contradicting bundestag.de box (`docs/source-errors.md` E6). `derive.vote_outcome` returns accepted when `result_raw` is rejected, so the page reads the outcome and never hard-codes the word. `inversion_source` has four values (protocol, roll-call page, DIP title, DIP Beschlussfassung), and the excerpt can be a whole title, not a sentence. (f) `person_corrections.json` splits a `redner_id` into two people, so "Quelle: Plenarprotokolle" on a person's Reden needs a row that says where the site decided the person. (g) The next Sitzungswoche is written at build, so a late release can name a past week, and the calendar can be empty.
  - **Other points from those passes, not all checked.** A Fragestunde has contributions and no Reden, and the reading component has no place for them. Small multiples ask for neutral ghost lines while "don't overlay" forbids overlaying, and the Analysen door's reasoning relies on that ban. Fraktion order "by size" has no reference date, tie-break or place for Gruppen and Unbekannt. A tally can mix one tick per Rede and one per ten in a view, and has no cap. First-screen figures use a 667 px screen, and mobile Safari's viewport is smaller; fallback fonts move them too. `box-shadow` edges vanish under forced colours, and print drops background-drawn cards and strips. The strip, controls and fields wear the same edge colour the footer explains as "steht so in der Quelle". `overflow-wrap: anywhere` can collapse table columns on long titles.
  - **Component list and tests.** This entry names fewer components than the `DESIGN.md` inventory, which also has Speech with its blocker (`speeches.text` has no paragraphs) and Small multiples. Tests worth naming: no "unverändert" without a comparison, incomplete member rows give a gap and not a wall, an unmapped Fraktion takes `f-none`, no inline hex in markup, and the word check on data lines. Colour values and card geometry are not asserted.

**Settle while applying:**
- **Fonts without a package manager.** The `@fontsource` packages are a one-time download source. Commit the five WOFF2 files (D-DIN Condensed Bold; Atkinson Next variable, latin and latin-ext; Atkinson Mono 400 and 700) and the licence texts, with no `package.json`.
- **How and in what order (decided 2026-11-10).** `docs/plans/render-layer-and-order.md`:
  - L2 settles the shared layer: package `scripts/render/`, a stylesheet whose token blocks are generated from DESIGN.md, hashed asset names (this replaces the stale-stylesheet item that stood here), the page shell and the components.
  - L5 settles tests: `tests/_page.py`, stylesheet tests, the content compare for restyle PRs, and browser checks ported to `data-*` hooks.
  - The pilot (`votes/index.html`) keeps today's content. The strip and counts on vote rows, the per-vote pages and the Vote lead wait for states (a) to (g) above.
  - Until slice 10, the Stand line's release slot reads "lokaler Build".
- **Reviews until this lands.** The `CLAUDE.md` rule to flag UI that does not match `DESIGN.md` means new or changed UI. Existing pages are this entry, not findings.

**Effort:** L
**Priority:** P2
**Depends on:** The shared layer, step 1 of `docs/plans/render-layer-and-order.md`

### Persist or prove the vote outcome and Abweichler count

**What:**
- **Three definitions exist today:**
  - The site computes a vote's outcome (`derive.vote_outcome`) and Abweichler count (`derive.vote_abweichler_count`, `derive.py:784`; `vote_outcome` at `:886`) at render time.
  - The release defines the outcome as SQL (`docs/project-documentation.md`, about `:665`).
  - The release defines the Abweichler count as recipe `r3-abweichler` (`build_dip_pulse_site.py:3664`, tested by `tests/test_mehrheitsvotum.py:163`).
- **Choose one:**
  - Persist both as columns and point the SQL snippet and the recipe at them.
  - Or keep the derive functions and prove on the reference store that they equal the SQL and the recipe on every vote.
- **Never a third definition.** `vote_abweichler_count` returns None unless every group is complete and covers the total, so compare that case first.
- **Report.** Old and new values of any figure that moves.

**Why:** principle 6 and `docs/plans/render-layer-and-order.md` L4. The Vote lead on Home and Aktuell reads the outcome, and the landing page is ported in slice 2.

**Built 2026-11-14** (branch `claude/plan-vote-links-2ed5ac`, `docs/plans/vote-links-and-figures.md` part 2; owner decision 3: persist). `votes.application_result`, `votes.abweichler_count` and `vote_members.abweichung` are written at persist by `derive.vote_outcome`, `derive.vote_abweichler_count` and the new `derive.vote_member_abweichungen`, and rewritten after a `vote_fractions` merge (`persist_dip_pulse_store.rewrite_vote_figures`). Recipe r3, the "meiste-abweichler" Fakt (version 2; the plan missed this fourth definition), the votes archive and its badge read the columns; the dossier panel keeps calling the same derive functions on the report. The store gate checks `abweichler_count = SUM(abweichung)`. Replay of the reference store (718 sittings): nothing moved. 619 outcomes equal the old SQL snippet (330 accepted, 269 rejected, 20 NULL); 3,720 Abweichungen in both, the same (vote, MdB) pairs; `abweichler_count` NULL on 0 votes; r3 identical without its LIMIT (1,390 rows) and all six recipe CSVs byte-identical; 0 of 1,922 Fakt values moved; the archive and all 718 dossiers byte-identical. On inputs no current vote has, r3 and the Fakt now count nobody in a partial group and nobody in Unbekannt, where the old SQL counted them.

**Deferred from the PR A code review (2026-11-15), none a wrong figure today:**
1. ~~**Replay comparer.** `scripts/compare_store_values.py` compares r3's rows but not `votes.application_result`, `votes.abweichler_count` or `vote_members.abweichung`, so the README recipe "Validate a data correction" cannot show these columns moving (PR C, the T4 sittings). Add them, old and new per vote.~~ **Done in v0.46.3.0 (2026-11-17):** the comparison has a section for the three columns (the outcome mix, the Abweichler sum and NULL count, the member flags), then each vote both stores hold whose outcome, count or member Abweichungen moved, old and new, with the members (by `mps.identity_key`) whose flag changed. It follows `--cohort`.
2. **Registry fold.** `persist_vote` counts Abweichler from the report's members keyed by `derive.vote_member_identity`, but `registry.bind` can keep two identity keys on one `mps` record; `ON CONFLICT(vote_id, mp_id)` then folds them into one row and the gate check `abweichler_count_matches_members` refuses the store. The ship's Codex pass (2026-11-15) found the quieter variant: when the folded members all agree, the count is 0 = SUM(abweichung), so the gate passes, yet the stored group no longer adds up to its counts and a re-derive from the stored rows gives NULL. 0 such votes on the replayed store: re-deriving all 619 votes from their stored rows gives every persisted count and flag. Fix: derive the figures from the rows after the fold (or refuse a fold that merges two members of one vote), not in the gate.
3. **Badge source by key presence.** `features.votes.render_result_badge` reads `application_result` only where the dict has the key, else recomputes; a store reader that forgets the column silently recomputes. Pass the source explicitly once the dossier panel reads the store (A4 slice 4).
4. **Two stored-vote readers.** `persist_dip_pulse_store.stored_vote_groups` re-reads totals, fraction rows and members in the derive shape, as `features.votes.stored_votes` does for the archive; share one reader.
5. ~~**Facts fixture.** `tests/_facts_fixture.py` writes `abweichler_count = sum(flag or 0)` even where a member's group has no fraction row (flag None), where `derive.vote_abweichler_count` gives NULL; compute it with the derive function.~~ **Done 2026-11-17:** the fixture writes each group's fraction counts from its seeded members (optional `abstain`/`absent` totals per vote) and `votes.abweichler_count` from `derive.vote_abweichler_count` over the stored rows. `MeisteAbweichlerTests.VOTE` and the thin-count test now carry member lists whose totals add up (they relied on the old sum: a Treue/Abweichler tie has no Mehrheitsvotum in derive, and totals that do not equal the members give NULL). The fixture's `abweichung` flags still come from the spec's `leading`, not from derive; a vote whose `leading` disagrees with its member counts therefore has flags that differ from the stored rows (no test seeds one).
6. ~~**Plan wording.** `docs/plans/vote-links-and-figures.md` part 2 calls 423 / 176 / 20 the "Outcome mix"; that is `result_raw`. The persisted `application_result` is 330 / 269 / 20 (93 of the 94 `proposition` inversions flip; one has no `result_raw`).~~ **Done 2026-11-18:** the plan labels 423 / 176 / 20 as the `result_raw` mix and gives the persisted 330 / 269 / 20.

**Effort:** S
**Priority:** P2
**Depends on:** None. Needed before A4 slice 2

### Design hand-over leftovers

**What:**
- ~~The re-scope review in `docs/plans/a4-site-from-release.md` still reads as approved ("Approval readiness: PASS"). Only the status line at the top says R10 to R16 are not applied. Add a banner under its heading.~~ **Done 2026-11-18:** a banner under the re-scope heading says its PASS and R10 to R16 are not applied. (The PASS the entry cited at `:1054` belongs to the first review, R1 to R9, which stays in force; the re-scope's own PASS is at `:1746`.)
- ~~`docs/designs/gesetzesvorhaben.md:300` names the removed TODO "DESIGN.md, tokens and a typeface decision".~~ **Done 2026-11-17:** it names "Apply DESIGN.md to the site".
- ~~`README.md:509` and `docs/project-documentation.md:21,329` link to `docs/design/bundestag-pulse-design.md`, deleted in ad389bf.~~ **Done 2026-11-17:** both point at `PRODUCT.md` and `DESIGN.md`; the "Builds on:" lines of `docs/designs/puls-wochenradar.md` and `docs/designs/daten-page.md` name `PRODUCT.md` and say the old file was deleted. Still open: the comment above `scripts/render_dip_pulse_html.py:1405` ("The design decision behind this is recorded in docs/design/bundestag-pulse-design.md"), left alone because Stage 2 render work owns that file; point it at `PRODUCT.md` there.

**Why:** none of these moves a figure or misleads a site reader, but each can send a later reader the wrong way.

**Context:** found by the v0.32.1.0 reviews and deferred under CLAUDE.md "Review findings". The `PRODUCT.md` sentence predates that release.

**Effort:** S
**Priority:** P3
**Depends on:** None

## Publication

### Site hosting plan

**What:** Pick the host and make the pages deployable to it. Decided 2026-11-06 (`docs/plans/v1-scope-review.md` Q8): the pages go to a German host with SSH; the data files go to GitHub Releases, and stable releases also to Zenodo. Open: the provider and plan (check prices on the vendor's own page; scope review E16 lists secondary figures only). Pieces:
- (a) Pick the provider.
- (b) The link scheme. `data/` is not deployed wholesale, so every page link into `data/` either points at a release asset or goes. `generation_file_href` changes, because GitHub release assets are flat (see "Write the release script", open decision (b)).
- (c) The deploy step: copy the output without `data/` to the host, plus the deploy gate below.

**Size is no longer the problem.** This item started as fitting a capped static host such as GitHub Pages (1 GB). Measured after A3 (2026-10-29, `~/agent-runs/a3/full`, 716 Sitzungen): 5.4 GB total, `data/` 4.1 GB, and 1.35 GB of pages in 6,750 HTML files (`bills/` 664 MB, `protocols/` 519 MB, `abgeordnete/` 139 MB). Two decisions shrink the pages to about 670 MB (scope review E8): both raw dumps are dropped (Q7, 633 MB) and the restyled pages share one stylesheet instead of inline `<style>` (`docs/plans/render-layer-and-order.md` L2, 96 MB). The only German host the scope review priced, Hetzner Webhosting, offers 10 to 300 GB, with SSH from plan L (E16, secondary figures). So hosting needs no size work, provided the chosen plan has room for about 1 GB.

**Why:** The site cannot go public without a host, and the host decides what the Datenschutz page has to say, so it comes before the Impressum and Datenschutz values (scope review Q8).

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
- ~~Switch on GitHub private vulnerability reporting when the repository goes public.~~ Done 2026-11-06 (owner); the repository is public. SECURITY.md said it was not until 2026-11-14.
- `/.well-known/security.txt` on the site.
- A `config.yml` contact link to the Impressum e-mail for private matters (GDPR, corrections from the people concerned, press).

Done when `security.txt` is served by the preview and the private-matters contact link is in the chooser.

**Why:** Private requests need a non-public channel; vulnerability reports need the GitHub channel SECURITY.md names.

**Context:** Decided 2026-09-29 ([ADR 0003](docs/adr/0003-licences-and-impressum.md), D5, amended 2026-11-01). `security.txt` and the contact link need the final domain and the dedicated e-mail address, both also needed by the Impressum item.

**Effort:** S
**Priority:** P3
**Depends on:** Domain and contact address (Impressum item)

### Contribution governance (batch 8): deferred review findings

**What:** The /gstack-review of `fix/todo-batch-8-governance` (2026-11-01) found three things. (1) The page shows the release notation `Release 2026.10.31`, but the Datenfehler `datenstand` placeholder is `data-2026.10.31`, the tag name. SECURITY.md's `data-<YYYY.MM.DD>` also omits the `.N` same-day suffix. Pick one notation. (2) ~~`tests/test_issue_forms.py` checks only ids, labels, quoting and URL drift. Negative controls passed with these breaks: a missing field `label`, `type: textfield`, `body:` renamed, a label typo, broken `config.yml` indentation, a duplicate field label, and a plain scalar ending in `:` (which Psych rejects). Add dependency-free checks for each.~~ **Done 2026-11-17:** `form_problems`, `config_problems` and `plain_scalar_problems`, each with a negative-control test that breaks the committed file the listed way (and a few more: duplicate or missing id, tab indentation, a markdown item without `value`). (3) ~~`ID_LINE` also matches an `id:` line inside a markdown block. Scope it to field indentation.~~ **Done 2026-11-17:** four spaces. (4) ~~From the v0.28.0.0 /ship red team: the Daten footer link always reads „Datenfehler melden (GitHub)", but `--data-issues-url` also accepts `mailto:` and a site-relative path.~~ **Done 2026-11-17:** `issues_link_label` shows „(GitHub)" only for an `https://github.com` host (look-alike hosts, a host behind userinfo such as `github.com@evil.example`, and `http://` do not; see the Impressum/licence review item 14 for the backslash case); `docs/project-documentation.md` says so. ADR 0003 line 112 and the plans still describe the always-GitHub label as it was decided.

**Why:** These are wording and test hygiene. Real schema validity stays an owner check on GitHub (below).

**Effort:** S
**Priority:** P4
**Depends on:** None

### Owner checks after the v0.28.0.0 merge

**What:** Checks that need main or the real store, accepted as pending at the v0.28.0.0 /ship (2026-11-01):
1. GitHub (needs main): the chooser at `/issues/new/choose` lists Datenfehler first, then „Fehler auf der Seite", plus the security link, and blank issues are off; both forms render with no template error; SECURITY.md shows on the Security tab; a Daten page built with the documented `--data-issues-url` opens the Datenfehler form with `seite` filled and the labels applied (the repository is public). The three labels exist (checked with `gh label list`).
2. ~~Real store (with A3's owed rebuild): batch 5's replay on main vs. the branch (equal `_content_digests`, mode, gid and lock path, no staged leftovers; with `--force-export` identical file hashes except table CSV modes 0600→0644); batch 6's panel hashes on `a3/full` and `b4-local` (expect 0 of 556 and 0 of 217 to change); batch 7's `--offline` build before and after with the same `--today` (differences only in `feeds/`, the cache file and the puls.html line plus script), and one online persisting build logging a single `[sitzungskalender]` line with about 22 weeks for 2026.~~ **Closed 2026-11-12, by the fresh online build of the reference store.**
   - The online check passes. Its bootstrap build logged exactly one line, `[sitzungskalender] angelegt: 43 Sitzungswochen aus 2 Dateien`, and `data/sitzungskalender.json` holds 22 weeks for 2026 and 21 for 2027.
   - The batch 5, 6 and 7 before/after comparisons can no longer run as written. `a3/full` and `b4-local` are not on this machine, and later merges move the same outputs. The fresh store's gate covers the code they checked, all at 28799ac: unchanged replay, export match, link audit and publication. Planner decision D8 in `docs/plans/e4-repersist.md`; the owner can reopen it.
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

**Why:** `parse_protocol_xml` (`scripts/validate_dip_protocol.py:1665`) walks `sitzungsverlauf/tagesordnungspunkt` only; no parser reads the list ("entschuldigt" appears only in the `MISTITLED_ZU_PROTOKOLL` comments, E8). Absent counts already sit in `vote_fractions`, so the page is the Anlage parser plus one query. Plenarwatch states the limit plainly ("weder noch" cannot separate absent from present-but-not-voting); copy that caveat onto the page.

**Context:** Anlage lives under `<anlagen>` in the same XML; verify the exact markup on a live protocol first (same caveat as Zwischenrufe). Sittings without a roll-call vote produce no data point, by design, say so on the page.

**Effort:** M
**Priority:** P3
**Depends on:** Fraktion seat counts in the store, Vote outcome badge

### Muster: agreement matrix, coalition patterns and Geschlossenheit

**What:** Three aggregates over all roll-call votes of WP 21: (1) Fraktion × Fraktion matrix, share of votes where both majorities voted alike (diagonal 100 %); (2) per-vote coalition pattern, which Fraktionen sided with the outcome, with "Koalition" meaning CDU/CSU + SPD; (3) Geschlossenheit per Fraktion, share of votes with a single vote value across all its members (one deviating member = "geteilt"). Ship first as three SQL recipes on the Daten page, then as `muster.html`. Done when the recipes run in the build and the page numbers equal the recipe output.

**Why:** The only adjacent metric is recipe `r3-abweichler` (`scripts/build_dip_pulse_site.py:3664`), per-MP dissent counts. All three aggregates are queries over `vote_fractions`/`vote_members` that already exist; the page is a renderer.

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

Done when no generated page carries `data-operator-missing`. The deploy gate in "Site hosting plan" refuses to publish until then.

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

~~Also: DATA.md's sources paragraph (`_codebook_sources_and_citation`) names the open redistribution question for the roll-call data only; name the MdB-Stammdaten there too until the terms are settled (ship adversarial pass 3).~~ **Done 2026-11-18:** the sentence now reads "der namentlichen Abstimmungsdaten (ADR 0003) und der MdB-Stammdaten" (the ADR is cited for the roll-call data only, since it does not name the MdB-Stammdaten yet); the terms and LICENSE-DATA.md work below stay open.

The answer also reaches two tables outside this layer. Since E4 (2026-11-05), 100 rows of `vote_members.party_id` and 146 rows of `vote_fractions` counts rest partly on the Stammdaten, while the dictionary still tags those columns `bundestag-abstimmungen` alone. If the file can't be redistributed, dropping the seat tables does not remove these rows: decide then whether a correction may stay, and tag the columns to match.

Done when the layer has written terms and DATA.md's attribution names the file.

**Why:** It is a release blocker under track D, not an implementation blocker. The zip itself stays in the private directory, never in OUTPUT (D9).

**Effort:** S
**Priority:** P2
**Depends on:** Settle the roll-call source for redistribution (same e-mail)

### Impressum/licence build: deferred polish (2026-11-01)

**What:** Non-correctness findings from building `docs/plans/impressum-datenschutz-licence.md`: (1) ~~the Datenschutz drift test reads localStorage keys only from `page_head()`/`page_scripts()`; a key written by a page-specific inline script (dossier runtime, Fakt pages) would slip past, so scan the built HTML for `localStorage`/`sessionStorage`/`document.cookie` instead.~~ **Done 2026-11-17:** the test scans every inline `<script>` of the demo build's pages (also `getItem`/`setItem` literals); it covers the 16 demo pages only, so dossier, Fakt and bill-detail runtimes are not in it (see item 4). (2) In the placeholder state the legal pages show doubled punctuation („Angabe folgt.., Anschrift wie oben“); gone once the operator file is complete. (3) On `sources.html#lizenz` the row labels of the licence table inherit the page's uppercase table-header style. (4) The D5 footer comparison covers the 16 pages the demo builds; Abgeordnete detail, Fakt week/month and bill detail footers are checked only by the reference-store footer walk, not by a unit test.

**Why:** Deferred under the CLAUDE.md fix-now-or-defer rule: none changes what a page says today.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Impressum/licence branch: deferred /gstack-review findings (2026-11-01)

**What:** Non-correctness findings from the pre-landing review of `claude/pre-public-items-plan-e8d01d` (specialists, Claude adversarial, red team; Codex found nothing):
1. `test_the_legal_span_is_the_only_footer_change` (`tests/test_demo_site.py`) compares two renders of the same tree, one with `render_legal_links` patched to "". A footer sentence or link lost while editing would be missing from both, so the test cannot catch the regression D5 asked for. Compare against a golden of the pre-change footers (or main's build), or drop the second build and keep the database-unavailable assertions.
2. `previous_manifest_problem` (`scripts/publish_dip_pulse_data.py`): the `protocols`/`votes` shape and `total_rows` branches (bool included) have no test rows, and the docstring says it checks "the fields release_changes reads" although `release_changes` tolerates their absence and reads `tag`, which is not checked.
3. ~~The release gate ties `LICENSE-DATA.md` to the commit but not `manifest["license"]` to its short string.~~ **Done 2026-11-18:** `verify_export` compares the manifest string with `license_short_string` of the commit's blob and refuses any mismatch, a deliberate `--data-license` override included (decision: release strings equal the committed short string); the unreachable "no licence string" refusal and dry-run notice are gone.
4. ~~`--operator-file ""` or an empty `$BUNDESTAG_PULSE_OPERATOR_FILE` (an unset CI secret) is read as "not set" and builds placeholder pages with exit 0; the operator file is also resolved before `--fetch-xml`, so a stale variable blocks runs that render nothing.~~ **Done 2026-11-05:** an empty or blank value is an error (owner decision), and the operator is resolved after the early-exit modes and `--fetch-xml`.
5. ~~The operator e-mail regex accepts `?`, `&`, `%` and `=` in the local part, so `mailto:` can carry header parameters; operator URLs accept whitespace.~~ **Done 2026-11-17:** both refused, with a test row per character and for a space in the path and in the host.
6. Nothing keeps the operator file out of git: ~~no `.gitignore` entry for a conventional name~~ (**done 2026-11-17:** `operator.json` and `operator.local.json`, pinned by `tests/test_repo_hygiene.py`), and `resolve_operator` accepts a path inside the work tree (open).
7. `sources.html#lizenz` states the roll-call layer without the caveat DATA.md and `docs/data-methods.md` carry (redistribution of the named votes is still open, ADR 0003). The four layers are authored in `render_sources_page` beside `LICENSE-DATA.md` with no drift test; „Luca Veh“ is a literal there, in `LICENSE-DATA.md`, the dictionary and `CITATION.cff`.
8. The Impressum says errors are reported publicly via GitHub Issues, but no link renders while `--data-issues-url` is unset. The repository is public now; pass the issues URL when the site is built.
9. ~~A release `--data-tag` with `$BUNDESTAG_PULSE_DATA_MANIFEST` is refused only after `run_facts_engine` wrote the facts tables (idempotent, a wasted pass); move the check before it.~~ **Done 2026-11-05:** refused at the head of `main()`.
10. ~~A blob committed with CRLF is exported as LF, so the shipped `LICENSE-DATA.md` is not byte-identical to "the one that commit holds" (docstring and docs); add `.gitattributes` `eol=lf` for the three codebook inputs or soften the claim.~~ **Done 2026-11-17:** `.gitattributes` sets `text eol=lf` on the three codebook inputs (pinned by `tests/test_repo_hygiene.py`). It governs checkouts and `git add`; a CRLF blob already committed would still be exported as LF (none is).
11. Smaller: `_read_codebook_inputs` normalises CRLF and `text_sha256` normalises again; the `os.chdir` in `test_relative_directories_reach_gh_as_absolute_paths_and_a_hash_is_refused` should be `contextlib.chdir`.
12. ~~Not run in the review: the reference-store export replay.~~ **Done 2026-11-01** in the /gstack-ship run: a clone of the reference store, repersisted with this branch, then offline builds. 290 protocols, every row count, vote, Rede character sum, Sprechrolle and Beitrag count and all 710 stored Fakten unchanged; the store's SQLite hash unchanged by the offline build; a format-12 export listing `LICENSE-DATA.md` with the default short string; a further build on identical inputs printed `export: reused data/exports (unchanged)`.
13. Browser check (375px, dark, 2026-11-01, demo build plus both legal pages rendered from a dummy operator file): no horizontal scroll, dark tokens apply, links and the `cdn.example.net` host sentence correct, no operator marker left when the file is complete. Cosmetic only:
    - ~~the Impressum heading wraps between „§“ and „18“ (use `&nbsp;` after each `§`);~~ done 2026-11-03 (a no-break space after each `§` in the Impressum headings);
    - the placeholder state reads „Angabe folgt., Anschrift wie oben.“ and „Angabe folgt..“ (doubled punctuation; only the deploy gate planned under "Site hosting plan" will refuse these pages: `validate_publication_directory` accepts them, since CI validates the placeholder demo build);
    - Datenschutz grammar breaks on some operator values: „erhält dessen Server“ after a feminine provider („die … GmbH“) and „etwa bei Berliner Beauftragte für …“ (needs a dative article/ending); rephrase so the inserted names stand alone („Server des Hosters“, „Aufsichtsbehörde: …“);
    - the footer Impressum/Datenschutz links are 14px tall, below the 24px touch-target minimum;
    - in `sources.html#lizenz` the intro sentence renders at 16px while the layer texts render at 14px.
    The demo build has no export, so its Daten page lacks the `LICENSE-DATA.md` link that sources.html mentions; a build with an export renders it (`render_daten_downloads`), and the release gate never publishes without one.
14. From the 0.46.19.0 ship review (latent or below the floor): the operator e-mail still accepts `#` in the local part, and `_operator_link` writes `href="mailto:{value}"` unencoded, so a mail client reads the rest as a fragment and writes to the wrong recipient; the item 5 refusal also stops an RFC-valid address such as `contact=legal@example.org` that was accepted before. Percent-encode URI-sensitive characters when building the `mailto:` href instead of refusing them, with positive rows for valid local parts. `issues_link_label` takes the host from `urllib.parse`, so `https://evil.example\@github.com/issues` (a browser treats the backslash as a path separator and goes to evil.example) and a userinfo URL on github.com are labelled GitHub; refuse a backslash or userinfo before the label. The operator-URL error still says "an https:// URL without credentials" though whitespace is refused too. `https://www.github.com/...` gets the plain label. `tests/test_repo_hygiene.py` fails instead of skipping outside a git checkout.

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
5. ~~`verify_export`'s `licence["bytes"] == 0` clause cannot decide the outcome.~~ **Done 2026-11-18:** dropped, message reads "is not the LICENSE-DATA.md of commit X".
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
16. `default_license_text` reads `LICENSE-DATA.md` a second time, apart from `_read_codebook_inputs`; an edit between the two reads gives `manifest["license"]` from another revision than the shipped copy. Derive the default from `CodebookInputs.license` (the consequence is item 3 of the section above). **Partly done 2026-11-18:** `verify_export` now refuses a manifest string that is not the commit blob's short string, so a release can no longer ship the other revision's string; the second read in `default_license_text` itself stays.
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
  - (b) The hosting layout. GitHub release assets are flat, but the site links `<base><generation>/<file>`. So no GitHub release URL works as `--data-base-url` until the site's link scheme (`generation_file_href`) or the host changes. The dry run says so. See "Site hosting plan".
  - (c) `docs/designs/daten-page.md` planned `gh release upload --clobber`, which overwrites. This script creates each version once and never overwrites.
- Only this script enforces immutability. Anyone with write access can still edit a GitHub release.

**Why:** Without a release, "the dataset" is whatever the last local build produced. Nothing can be cited or downloaded twice with the same result. "Scheduled data-release workflow" and the Daten items are blocked on this.

**Effort:** S (the run itself, once the dependencies are settled)
**Priority:** P1
**Depends on:** "Settle the roll-call source for redistribution" (before votes are released); a host from "Site hosting plan"

### Release pipeline: deferred /ship review findings (lane/release, 2026-10-31)

**What:** The v1 release /ship review fixed four defects (dangling „Geändert laut Manifest: .“ in CHANGES.md, tracebacks on a non-object `--previous-manifest`, a non-file in the generation and a missing git/gh or full disk, `--data-tag` accepting any token). These remained, none reached by a current input, deferred under the CLAUDE.md fix-now-or-defer rule. Items 1–5 are done (2026-11-17, branch `claude/cool-jennings-f5dbcb`, one test each in `tests/test_publish_dip_pulse_data.py` / `tests/test_build_revision.py`):
1. ~~Workflow dead ends: …~~ Done: a later run reuses an existing `data-<version>/` only when its files equal the ones it builds (dry run then `--publish` the same day, or the retry after a failed `gh release create`), and otherwise refuses with „remove it or use a fresh --output-dir“ naming the differing files; a failed `gh release create` names the tag and release to check on origin and how to delete what it left. A dry run on another day differs in `changes.json` (`released`) and is refused, by design.
2. ~~Existing remote tag without a release~~ Done: `--publish` asks `git ls-remote --tags origin refs/tags/<tag>` before gh and refuses an existing tag (naming `git push origin :refs/tags/<tag>`) or a failed lookup. It asks `origin`; gh resolves its repository from `gh repo set-default` or an `upstream` remote first, so a clone where that is not `origin` is not covered (this repository has only `origin`); see item 12a.
3. ~~`full_commit` lets a ref named like the digits win~~ Done: `full_commit` lists object ids with `rev-parse --disambiguate=<hex>` and requires exactly one commit among them.
4. ~~`--previous-manifest` not tied to the latest release~~ Done: its `tag` must equal the newest published release, the newest `data-*` tag on origin (`git ls-remote --tags origin`, asked in a dry run too) and under `--publish` also gh's newest release; local tags no longer count (owner decision 2026-11-17, branch `claude/release-script-batch-45ef0a`, which replaced #170's local-tags-plus-gh rule; gh's releases stay in after Codex showed that dropping them lets an older predecessor through when gh publishes to another repository than origin). It is refused when no release is published. Validation stays `previous_manifest_problem` (the fields `release_changes` reads), not `validate_manifest`, per item 10a: `validate_manifest` refuses every export format but the current one, so the first release after a format bump could never name its predecessor.
5. ~~TOCTOU between `verify_export` and the copy~~ Done: `verify_export` returns the sha256 of the `datenstand.json` bytes it checked, and `build_release_directory` re-checks the staged `datenstand.json` and every staged file's size and sha256 before the rename (or before comparing against an existing directory).
6. ~~`LICENSE-DATA.md` is copied from the working tree, not from the manifest commit, and an empty file passes the `--publish` gate.~~ Done 2026-11-01 (branch `claude/pre-public-items-plan-e8d01d`): every export carries `LICENSE-DATA.md` (manifest kind `license`, the codebook input's bytes); the release script copies nothing from the working tree and refuses a listed file that is empty or not the one the manifest commit holds.
7. Release directory mode is 0700 (mkdtemp), which a web host copy cannot read; `SHA256SUMS` lists `g-<hash>/<file>` paths that cannot be checked against flat GitHub assets, and its filter skips any file named SHA256SUMS at any depth; generation files are hard-linked (shared inodes) and symlinks are not refused.
8. ~~`build_revision._PINNED_CONFIG` leaves~~ **Done 2026-11-18, narrowed at ship:** four keys pinned (`diff.suppressBlankEmpty`, `diff.srcPrefix`, `diff.dstPrefix`, `diff.ignoreSubmodules`); release revisions unaffected. `core.fileMode` and `core.autocrlf` stay unpinned: they decide whether a file counts as changed, and git sets them for the checkout's file system, so pinning them made a clean checkout on exFAT/SMB (`fileMode=false`, every file with the exec bit) resolve as `-dirty-` (reproduced in the ship review; `test_a_checkout_that_ignores_exec_bits_stays_clean`). Only `diff.suppressBlankEmpty` has a test row that fails without its pin (checked by mutation): `diff.srcPrefix`, `diff.dstPrefix` and `diff.ignoreSubmodules` are pinned but unproven, because `diff-index` (plumbing) does not read them; their rows in `test_same_edit_same_revision_under_more_diff_settings` stay as cheap guards, drop them with their pins if the file wants trimming. Original: it left `diff.suppressBlankEmpty` (reproduced: another `-dirty-` hash), `diff.srcPrefix`/`dstPrefix`, `core.autocrlf`, `core.fileMode` and `diff.ignoreSubmodules` unpinned, so a dirty revision can differ between machines (release revisions are bare commits, unaffected). Pin them or narrow the docstring.
9. Smaller (done 2026-11-18: Unicode digits, NaN, the Daten page `"-" in commit` test, the duplicated `{12}`, the dead `import subprocess`; the dry-run licence notice is gone with item 3 of the Impressum entry): `_sha256` duplicates `_hash_file`; release files are hashed twice; the export undo uses `rmtree(ignore_errors=True)`, so a partial removal skips the aside restore; tests: `--publish` x staging failure untested, `_link_or_copy` copy fallback, `render_markdown` minor lines, the `docs/data-changelog.md` example not parsed by a test, one long multi-scenario test in `test_build_revision.py` and a duplicated `git()` helper.

10. ~~**P1, fix before the first real `--publish`**~~ **Done 2026-11-01** (branch `claude/pre-public-items-plan-e8d01d`, each with a test): (a) a `--previous-manifest` must be an object with the fields `release_changes` reads (`null`, numbers and lists refused; the site's `validate_manifest` is not used because it refuses every export format but the current one, which the release after a format bump needs); (b) both directories are resolved before gh sees them and an `--output-dir` with `#` is refused; (c) a release `--data-tag` refuses `--data-manifest` in `parse_args` (`--no-persist` no longer exists since 0.29.0.0), and `run_data_pipeline` stops when no export carries it (no store, `DataExportUnavailable`, `$BUNDESTAG_PULSE_DATA_MANIFEST`); (d) the exporter and `blob_sha256` both hash with CRLF read as LF (`build_revision.text_sha256`). Original finding (adversarial review, adjudicated defer 2026-10-31 because `--publish` refuses until LICENSE-DATA.md exists): (a) a `--previous-manifest` file holding JSON `null` passes the object check, so a follow-up release is labelled „Erste Veröffentlichung“, needs no changes file and skips the existing-release check (Codex reproduced it against an existing remote release); require an object whenever the option is given. (b) A relative `--output-dir`/`--exports-dir` run from outside the repository root: gh runs with `cwd=repo_root`, so the asset and `--notes-file` paths point elsewhere and can upload stale same-named files; `.resolve()` them (and refuse `#`, gh's label separator). (c) `--data-tag <version>` with `--data-manifest` (or a missing store / `DataExportUnavailable`) exports nothing yet exits 0, leaving an older release-tagged export for the script; `parser.error` on those combinations and require the export's tag to equal the requested one. (d) With `core.autocrlf=true` the exporter hashes CRLF working-tree bytes while `blob_sha256` hashes the committed LF blob, so a clean checkout builds an export the release script refuses; normalise one side.
11. Cycle-2 and adversarial deferrals: the `main` comment says the release directory „was already rolled back“, true only for failures inside `build_release_directory`; CHANGES.md states „Keine Korrekturen veröffentlichter Werte.“ as fact when the author lists none (say „angegeben“, or check `source_sha256`/`inputs_hash` against the previous manifest); a `--changes` file holding `null` reads as no file; `--next-version` reads local tags only (fetch tags or ask gh); DATA.md of a release export still says no immutable download reference was given; CITATION.cff's title „poliwatch“ differs from the CC BY attribution name „Bundestag-Puls“; CHANGES.md, changes.json and LICENSE-DATA.md are not run through the publication denylist; `ValueError` (lone surrogate, a 5000-digit integer) still escapes `main`; files flagged assume-unchanged/skip-worktree are invisible to the clean-revision and authored-input checks; `committed = True` is set one statement after the manifest rename (interrupt window); the schema-change guard accepts any entry, corrections name unchecked tables/columns, count drops need no note, and a type change („1“ to 1) renders as no change in CHANGES.md; the dry run's `--initial` check sees local tags only; the printed `--data-manifest` path is not shell-quoted.
12. Deferred from the /ship review of items 1–5 (2026-11-17, adversarial pass; none reached by a current input): (a) the origin-tag check asks `git ls-remote origin`, while `gh release create` (no `--repo`) publishes to the repository gh resolves (`GH_REPO`, `gh repo set-default`, then the `upstream`/`github`/`origin` remotes); a tag on that repository but not on origin passes and gh attaches to it, ignoring `--target`. Ask gh itself (`gh api repos/{owner}/{repo}/git/matching-refs/tags/<tag>`, exact ref) or resolve the repository once and pass `--repo` to every gh call; (b) `--previous-manifest` is matched by its `tag` label, not its bytes: a local re-export with the same tag passes; compare its sha256 with the published release's `datenstand.json` asset (`gh release download`); (c) `withheld_export_problem` reads the live export, not the re-verified staging copy (needs two swaps in one run); run it on the staging generation after `staging_problem`; (d) `gh release list` includes drafts, so a draft counts as the latest release (fails closed with a misleading message); read `isDraft`; (e) the `git ls-remote` call has no timeout and `clean_env` drops `GIT_SSH_COMMAND`/`GIT_ASKPASS`; (f) reusing a release directory hashes the existing and the staged copy in full on top of `verify_export`, `staging_problem` and `SHA256SUMS` (about five reads of the SQLite file); reuse the staged digests; (g) from the code-review of PR #170: a tag a failed `gh release create` left on origin (no release behind it) counts as the latest release, so the real latest release's manifest is refused, naming the stray tag (fails closed). Local tags no longer count (item 4 now asks origin); delete the stray tag as the failed run's message says; (h) `full_commit` runs one `git cat-file -t` per `--disambiguate` candidate; one `cat-file --batch-check` would do. (i) from the fix-check of the origin-tag change (branch `claude/release-script-batch-45ef0a`): a dry run of a follow-up release does not warn when its own `data-<version>` tag already exists on origin but not locally (origin's tags no longer count as existing releases, and the origin-tag check runs only under `--publish`, which still refuses it); have the dry run print `--publish would refuse` when `origin_versions` holds the version.
13. Notes from the /ship review of the release hardening (2026-11-20, Codex and adversarial pass; none reached by a current input, all fail closed): (a) `verify_export` reports a `blob_text` failure (git timeout, git missing, a non-UTF-8 blob) as "has no blockquote under ## Short string"; give it its own "cannot read LICENSE-DATA.md at commit X" message. (b) `license_short_string`'s refusal starts "default licence string:" on the release path too; move that prefix into `default_license_text`'s wrapper. (c) `blob_text` folds CRLF only, while `default_license_text` reads with universal newlines, so a LICENSE-DATA.md with lone CR line endings has a short string for the build and none for the release (no committed file has lone CRs; `.gitattributes` keeps the file LF). (d) A short or upper-case `commit` from a `--data-manifest` override gets `REVISION_SUFFIX_NOTE`, which explains only `-dirty-`/`-unverified`. (e) A global `core.attributesFile` marking paths `-diff`/`binary`, or `core.precomposeUnicode`, still moves the `-dirty-` hash across machines; pin `core.attributesFile=/dev/null`. (f) The dry run stops at a licence-string mismatch instead of printing "--publish would refuse" and rehearsing on, unlike the coverage bars; intended by the release-hardening decision, open for the owner to overrule. Pass 2 on the fix: (g) a non-finite count in `--previous-manifest` (read with plain `json.loads`; `previous_manifest_problem` checks only `total_rows` as an int) now stops the run with an uncaught ValueError from the `allow_nan=False` dump, nothing written, instead of a ReleaseError; require ints for `protocols.count`, `votes.count` and `votes.members`. (h) `_finite_float` accepts an underflow: `1e-999` reads as 0.0. (i) Its refusal echoes the whole literal. (j) With `core.fileMode`/`core.autocrlf` unpinned, a dirty tree whose only change is an exec bit or CRLF content hashes differently across machines (dirty revisions only, the accepted trade-off).

**Why:** First release pipeline; the reviewed paths fail closed or need hand-crafted input today. Items 1–6 and 10, the ones that mattered before the first real `--publish`, are done; 7–9, 11 and 12 remain.

**Effort:** M
**Priority:** P2 (items 6 and 10 done 2026-11-01, items 1–5 done 2026-11-17)
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

**Done:** `CITATION.cff` at the repository root (v0.26.0.0, #123), guarded by `tests/test_citation_file.py`. It claims no DOI, version or date. `repository-code` is in since 2026-11-14; `url` waits for the site's host (the rename updates both). The root `LICENSE` (MIT, code only) exists since v0.30.0.0.

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

**How to draw it (2026-11-04):** as SVG from a small Python module with a small tooltip script, per the frontend go/no-go. A working version of this page, on the full store with provisional terms, is in `~/.gstack/projects/LucaAlv-poliwatch/designs/chart-prototype-20261104/arm-a/build.py`. It covers topic and period links, touch tooltips, point-to-Reden pages and a table. It is not the term-list decision, which is still open.

**Context:** Start with a small set of topics (Klimaschutz, Migration, and a few more) and a neutrality review of the term lists before publishing. A term list that uses one side's vocabulary ("Klimakrise" vs. "Klimawandel") frames the result. Also consider filters that Open Discourse offers and the store can support: gender and age group from the abgeordnetenwatch columns.

**Effort:** L
**Priority:** P2
**Depends on:** The Rede-counting items; v1 coverage; stable ids

### Politikfelder over time: which Zusammenschluss emphasises what

**What:** Using the Politikfeld tags, show per Zusammenschluss and per period the share of its Reden (and of its speaking time by characters) that falls under each Politikfeld, and how the share of each Politikfeld in the whole plenary changes over time. Ship as a recipe first, then as a page next to the term series. The page declares a minimum coverage (decision N9, 2026-11-09) and marks a period below it as thin, not drawn as complete. The owner sets the number once the coverage gate has measured the withheld share by words.

**Why:** This answers "which party has which priorities" and "how does attention to a topic change" (PRODUCT.md) from the agenda side, without depending on vocabulary. The term series answers it from the language side. The two complement each other.

**Effort:** M
**Priority:** P2
**Depends on:** Politikfeld tags; the Rede-counting items; v1 coverage

## Abstimmungen

### E4 /gstack-review: deferred findings (2026-11-05)

Pre-landing review of 23629a5 (specialists, red team, Claude adversarial; Codex gpt-6.1-sol on the tree with the first round of doc fixes: gate PASS, one P2, item 3). No figure moves on today's data: the tip's filing equals the replayed store on all 619 votes. These matter when the Stammdaten file changes or goes missing:
1. **Outside a release, no file still means the correction disappears, with only a warning.** A rebuild without `mdb-stammdaten.*` in the private directory puts all 100 Stimmen back under the page's groups. `data-methods.md`, the warning and the Datenstand line say so. A tagged export and `publish_dip_pulse_data.py` refuse this state since the owner's decision of 2026-11-05, so it can't be released, but a local build and its pages stay uncorrected. On the reference store this is settled. The fresh build of 2026-11-12 (`.context/dip-pulse-site`, schema 11, 619 votes) has the file in `.context/.dip-pulse-site.private`: Stand 2026-04-29, sha256 `29ae4ba1…`, fetched 2026-11-10. Its store holds all 100 moves. The schema-8 and A3 stores this item named are not on this machine. Both refusals ran on real files on e7b06f3: a tagged export of a clone without the Stand row refuses, `publish_dip_pulse_data.py` refuses a manifest whose `stammdaten` is null, and a tagged export with the file passes its dry run.
2. **A lag in the file re-files a correct page row to the old group.** `_proved_group`'s only freshness guard is `day > stand_day`, so a group change the file has not recorded yet, or one made on the Stand day after the Stand instant, re-files a correct page row to the old group (0 votes fall on the Stand day today). Treat a window before the Stand as unproven; `stammdaten.py`'s `after_stand` cause uses the same boundary. It needs a window choice (how many days before the Stand count as unproven). **This must land before any Stammdaten refresh,** because a refreshed file is where it bites (`docs/plans/e4-repersist.md`). The other half of this item (a gap counted as proof of fraktionslos) is done: see Completed, 2026-11-17.
3. **One rebuild reads the zip twice.** `refile_entry_votes` and `rebuild_seat_counts` each call `read_cached_stammdaten`, so a refresh landing between them gives the vote moves of one file and the seat tables and `mdb_stammdaten_stand` of another: read it once per rebuild and pass it on. (The offline-render half is fixed in v0.46.15.0: a plain `--offline` render refuses when the cached file's sha256 is not `mdb_stammdaten_stand.sha256`, or one side has a file and the other none, and the refusals name `--offline --repersist`; the reference store passes, 801 dossiers rendered.)
4. **The seat cross-check can't see a wrong Stammdaten row any more.** It compares `vote_fractions.total_count` with seats from the same file the moves came from, so `shift_between_groups` 0 is no independent proof of the moves. It still catches misfilings among the unmatched names. Comparing the page's own counts (read back through `listed_party_id`) would restore the check.
5. **Tests.** `test_hostile_names_end_in_no_key_quickly` asserts a wall-clock bound. The gate still compares only person grouping, so it never sees a re-filed Stimme (E4 leaves grouping alone). Its own replay runs on OUTPUT_DIR, whose private directory the operator clones by hand: a clone without `mdb-stammdaten.zip` beside a store whose `mdb_stammdaten_stand` has a row replays every Stimme back under the page's group with only a warning; the gate could refuse that state before the replay. (`_data_clone` now copies the source's `mdb-stammdaten.*` into each fresh and half clone's private directory and refuses when the copy is missing, 2026-11-17.) The success path of `main`'s offline branch has no test: a readable file marks the entries before the render. The v0.34.0.0 ship covered the other gaps this item listed; reverting `vote_groups_cover_total` is an equivalent mutant, since a move keeps every count's sum.
6. **Small.** `person_name_key` runs three times per member and the zip is parsed per run (measured: 6.3 s and 1.1 s on 425,322 rows). A refused vote shows only on stderr (none today). `filed_fractions` could store a negative `total_count` for a page row whose `total` is under its counts (`parse_fraction_votes` never writes one). The panel note prints "dort None" for a member with no faction (none moved today). `zusammenschluss(faction) or "Unbekannt"` is written out four times; a `listed_group` helper would name it. `refile_entry_votes` loops again only to count what `refile_report_votes` could return. The comment on `vote_fractions.rank` in `persist_dip_pulse_store.py` and the dictionary's `rank` meaning say the source's order, but `filed_fractions` appends a group the page has no row for (none today: every destination row in the TSV already existed).
7. **The online fresh vs incremental comparison is still owed.** Partly superseded by v0.41.0.0: `validate_store_gate.py` now compares a replay with its input store and with a fresh build that reads the roster from the cached DIP person records; the online-roster half is still owed, and the figures below are from the old A3 store. It needs a DIP key, and only an online build fetches the roster. The offline half ran on e7b06f3 (2026-11-05): a store-less `--offline --repersist` against the gate's upgraded clone of `~/agent-runs/a3/full`. Votes, `vote_members`, `vote_fractions`, Reden, Fakten, Abweichungen (3,720) and all r2, r4, r5 and r6 rows are equal. The differences are timestamps; 17,913 Reden keyed `xml:` on one side and `aw:` on the other, and person keys issued anew (84,301 of 523,968 shared bindings have the same key), with the same grouping (1,942 persons on each side over those bindings, 0 split, 0 merged); the retired-only records; the upgraded store's 1,077 extra `mps` rows, which were already in its input (7,457 before the replay), so E4 did not create them; and everything the roster decides: 0 against 589 listed Abgeordnete, 1,577 against 2,005 Personenseiten, the eyebrow on a Personenseite, the display name in r1 and r3, and in 174 protocol pages whether a member's name links to the Personenseite or to bundestag.de. A store-less offline build has no roster by design, so `docs/agents/review-checklist.md`'s "identical CSVs and pages" can't hold for it. That line should say which comparison it means.
8. **Found by the v0.34.0.0 ship reviews (2026-11-06), none reached by today's data.**
   - `refile_entry_votes` only warns about a refused vote, and the release guards check only that the file was loaded. A tagged release could carry a refused vote under the page's group while the Datenstand line and `data-methods.md` describe the correction. Today: 0 refused. Fix: return the refused list and let a tagged export refuse on it.
   - `refile_vote_members` checks that the page's row has a Stimme to give, not that the page's list and chart agreed for that group. If the chart already counted a member in the proved group and only the list misfiled them, the move double-counts. Today: `vote_members` per group equals `vote_fractions` on all 619 votes.
   - `_member_sections_html` (`features/votes.py`) builds its group key from `refiled_to` or the raw `faction`, not `derive.member_group`. A page spelling a group in a variant form would get two headings once a member moves there. All 100 moves land on AfD, SPD or fraktionslos today.
   - ~~`scripts/compare_store_values.py` reads no `vote_members.party_id`, `listed_party_id` or `vote_fractions` counts.~~ Done in v0.46.14.0: a "vote groups" section compares both per (vote, group) and per member.
   - `filed_fractions` trusts a `refiled_to` mark in a cached report; only `refile_vote_members` checks the Stimme is a count. Every loader that feeds persist or render clears and recomputes the marks today, so only a new reader would hit this.
   - `filed_fractions` iterates every member entry, while `vote_abweichler` and `vote_members` dedupe by identity. Two entries with different name text and one identity could both move. Close it with "Persist overwrites a roll-call member row when two members of one vote resolve to one mp".
   - `vote_members.listed_party_id` is `ON DELETE SET NULL`: a party-dedupe path other than `_repoint_party` would make a moved Stimme read as not moved.
9. **Found by the derive-fraktionslos ship review (2026-11-19), none moving a figure today.**
   - `docs/data-methods.md`'s E4 paragraph still gives 100 Stimmen in 55 roll-calls (Stand 2026-11-05, 619 Abstimmungen), and `docs/source-errors.md`'s "Corrected" line the same; since T4 the reference store re-files 157 Stimmen in 87 roll-calls (`docs/source-errors.md`, "Scale after T4"). The figure is dated, so it is not false, but the methods page the site links shows the old scale. Give the post-T4 count with its Stand, or point to the TSV.
   - A gap in the middle or at the end of a Wahlperiode still proves fraktionslos: Fraktion A ends on day X, B starts on X+n, and with no `Fraktionslos` record rule 3 makes X..X+n-1 fraktionslos, so a correct page row on those days moves. The guard covers only the days before the first record. This is the same lag as item 2 (an end date entered before the new group); decide together whether a gap without a `Fraktionslos` record proves anything.
   - `recorded_from` is one day per (Wahlperiode, MdB), the earlier Mandat's when an MdB leaves and comes back. A re-entry Mandat entered before its own Fraktion record has rule-3 fraktionslos lead-in days after that day, so the guard misses them and a correct page row moves into fraktionslos (the case the guard closes for a first Mandat). Before the ship fix the later Mandat's day won and over-guarded the first Mandat; neither keying is right. Key it per Mandat: a (MDBWP_VON, first record day) pair per WAHLPERIODE element, plus a marker for an element with no Fraktion or Gruppe record, and have `_proved_group` check the day against the Mandat covering it (test stub: second Mandat from 01.06.2020, SPD record from 01.09.2020, page SPD on 2020-07-01, no move). No MdB in the Stand 2026-04-29 file has two Mandate in one Wahlperiode.
   - The test helper `source()` in `tests/test_vote_refiling.py` takes `recorded_from` from the earliest `valid_from` of all rows, leading rule-3 fraktionslos rows included, unlike `first_record_days`; tests built through it never reach the new guard (only the `CachedStammdatenTests` ones do). Derive it from the Fraktion and Gruppe rows.

**Effort:** M
**Priority:** P2 (items 1 to 4 and 7 before the first release)
**Depends on:** None

### E4 re-filing: what it leaves open

The rule in `derive.refile_vote_members` moved 100 Stimmen in 55 roll-calls (2026-11-05, `docs/plans/e4-refiled-votes-old-new.tsv`). Nothing here moves a known figure:
1. **`data/bills.json` and a bill page's raw block show the page's `fractions`.** They dump the report's vote as it is, with the `refiled_to` marks beside the counts, so a reader summing `fractions` there gets the Bundestag page's figures, not the store's. No bill page renders group counts. Either give the dump `derive.filed_fractions` or say so in the data docs.
2. **27 member names (3,073 rows) find no Stammdaten name, and 10 (927 rows) match a name only in another Wahlperiode** (measured 2026-11-05 on the E4 replay, 425,322 rows; the same on the fresh reference store, 2026-11-12). Examples: Dagdelen/Dağdelen, Özoguz/Özoğuz, Merkel "Angela Dorothea"; Wadephul and Kemmer in the second group, with Breilmann and Zschau, who joined after the Stand. They keep the page's group. The cross-check would show a misfiling among them as `shift_between_groups`, and shows none today. A stored link from a vote member to the MdB id (via the registry) would replace the name match.
3. **`mps.party_id` keeps the page's group on purpose,** because the registry reads it as name-and-party evidence. Passing the corrected group split Pasemann's Reden from his Stimmen and moved Heßenkemper's page in the first replay. So "Fraktion" on a Personenseite can still rest on a misfiled vote row (Kamann, Bülow). Those pages need the Zugehörigkeit from the Stammdaten, which "Link `mdb_zugehoerigkeiten` to the MP pages" covers.
4. **The panel note is plain body text.** Its look belongs to "Apply DESIGN.md to the site".

**Effort:** S
**Priority:** P3
**Depends on:** None

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

**Remaining:** no population reaches the 90% gate (reference cohort needs 62/68, i.e. two more of: footnote documents `20/9155`, `21/354`, `21/4750`, `21/2553` (fail closed by design); `möge beschließen` `20/10055`; `fordert` without a Bundesregierung object `20/14699`; direct motion to revoke `20/3596`; the others are `20/2345` (source defect) and the two refused mid-period documents). Each is a separate rule with its own fidelity risk; take one at a time with a real fixture and the PDF-layout check used in Run 4. Cloud inverted cases `20/4666`, `19/30983` are still unsupported: their texts are not in the saved corpus and could not be re-checked offline. Not done: step 5 site-level before/after and the store replay (`--offline --repersist`, now with extractor 10). The historical cloud result (32/36, 89%) does not override the local results; do not close this TODO on the description percentage. Owner decision for the hyphen rule: a lowercase line-end hyphen after a 5+ letter part the text itself uses as a word is refused unless the joined word is spelled elsewhere (cost on this corpus: 1 document, 18/2742); recommendation keep, relax only if a larger corpus shows many false refusals.

**Smallest follow-up:** pick the next rule from the list above (footnote removal is the largest group, 4 of the 10 remaining demand-bearing misses), add its real fixture, check every new quote against `pdftotext -layout` as in Run 4, bump `EXTRACTOR_VERSION`, re-audit. Substantial extraction work belongs in that separate session.

**Review findings deferred (lane/correctness /ship, 2026-10-31; none reached by the saved corpus, all under the CLAUDE.md fix-now-or-defer rule):**
1. The imprint drops in `_LAYOUT_LINE` remove any whole line that starts with `Druck:` (with GmbH or www.) or `Vertrieb:` (with Verlag), wherever it stands; a wrapped content line of that shape inside the operative part would vanish from a quote that still ends in a full stop (red team, synthetic repro). Bound the drop to page-foot matter, or refuse the passage when such a label line sits inside a clause.
2. The imprint patterns are single-line: a `Gesamtherstellung:` line wrapped before the address, or `Druck: Bonner Universitäts-Buchdruckerei, 53113 Bonn` (no GmbH or www.), stays inside the demand (not a regression: extractor 7 kept all of it). The Run 4 note's "dropped like running heads" holds for the 19/16794 single-line shape only.
3. `_GLUED_ODER` catches only a capital-led token: `kurzoder` (lowercase truncated part) is quoted; `und` glue is undetectable by this pattern (comment says so). ~~Its comment's "no German word ends in oder after a capital" is false~~ (comment corrected 2026-11-18; Decoder, Encoder stay refused, a safe loss). The lowercase gap is still open.
4. Tests: the "Hintergrund oder" row in `test_a_conjunction_glued_to_a_truncated_compound_is_not_quoted` cannot match the pattern (it has a space), so it proves nothing about real words; no boundary row for `_WHOLE_WORD_LENGTH` (4 vs 5 letters) or the other `_WORD_ENDINGS`; `test_engine_refuses_a_distribution_copy_and_leaves_it_untouched` imports shutil inside its loop.
5. ~~The comment "A word a line-end hyphen leaves standing" now sits above `_WORD_ENDINGS` instead of `_KEEPS_HYPHEN`, and the `_join` docstring has one over-long line.~~ Done 2026-11-18.

**P1 gate before the fallback runs on any Drucksache cache larger than the saved corpus (resumed /ship of v0.25.2.0, 2026-10-31).** Three review sources (red team, Codex adversarial, Claude adversarial) independently found inputs that would publish a wrong verbatim quote. All of them are synthetic: none occurs in the saved 91 documents, and the only cache on the machine (`.context/b4-local-20261029-163417/working/data/dip-drucksache-text-cache.json.gz`) holds those documents alone. The extractor widened in v0.25.2.0 exposes items 1-3 to more openings: Codex reproduced items 2 and 3 under the new „zum Schutz der … auf,“ opening, which the base refused. Before a larger cache (WP 21, A3 backfill) is extracted, fix these or measure them on that cache. Each new quote should be checked against `pdftotext -layout`, as in Run 4. The A3 store (merged-tree gate, 2026-11-01) has no Drucksache text cache yet. 114 of its 619 votes are `not_fetched` (WP 19: 15, WP 20: 63, WP 21: 36) and 505 are `not_applicable`; no vote quotes a passage. That fill is the online build this gate guards.
6. A lowercase line-end hyphen after a part the text never prints elsewhere joins silently (synthetic `türkisch-` + `syrischen` gives „türkischsyrischen“; `deutsch-` + `französischen` gives „deutschfranzösischen“). Absence from the lexicon proves nothing; candidate rule: refuse a 5+ letter adjective-suffix part (-isch, -lich, -ig) without lexicon support, then re-measure coverage.
7. The dropped-bullet refusal in `_lines` fires only after a line ending in „.“ or „;“. Indented items ending in „,“ or „:“ are flattened into one sentence, and the first dropped bullet after „auf,“ is never caught. Fix: widen the predecessor test, or refuse on two or more indented non-item lines.
8. Fail-closed coverage loss: a Vorabfassung watermark after a full stop leaves a leading space after `_WATERMARK.sub("\n", …)`. A line starting with NBSP does the same. The new dropped-bullet check then refuses a passage that extractor 7 quoted. Measured: 0 of 112 replayed texts change with the fix, and the cached texts contain no watermark. ~~Fix before any WP 21 advance-copy cache: make the substitution swallow trailing `[ \t]*`.~~ Done 2026-11-18 (`_WATERMARK` swallows trailing `[ \t]*`, test added; measured 0 of 112 texts change). The v0.46.25.0 ship bumped `EXTRACTOR_VERSION` 9 to 10 (Codex): the fix changes the result for a mid-line watermark followed by a space (refused at 9, quoted at 10), and the version guards every persisted store, not just the measured corpus, so a store persisted at 9 is refused until `--repersist`.
9. The 5+ letter hyphen rule refuses common compounds whose first part the text also prints alone (`Rahmen-` + `bedingungen` with „Rahmen“ elsewhere, `gleich-` + `zeitig`). The saved corpus prices this at 1 document, but the trigger words are frequent, so expect more refusals on a larger cache. The owner note above („relax only if a larger corpus shows many false refusals“) covers this decision.
10. Tests: ~~the clause cap is pinned at 29/31 words, not 30, and `{0,30}` in `_INTERPOSED` is an unnamed literal~~ (done 2026-11-18: `_MAX_CLAUSE_WORDS`, boundary pinned at 29/30/31). `test_rebuild_refuses_a_distribution_copy_and_leaves_it_untouched` covers only the `user_version` marker, not `datenstand`, and does not assert that no staged files are left over. No break row covers a 5+ letter part absent from the text.
11. A watermark followed on the same line by a space and an in-sequence ordinal (`… bis zum <Vorabfassung …> 2. Quartal 2025 vorzulegen;`) starts a new demand mid-sentence: the passage is quoted with demand 1 cut and the real item 2 merged into the new one. Base (extractor 9) splits it the same way, checked 2026-11-20 (v0.46.25.0 ship, Claude adversarial pass); a watermark at a line end followed by such an ordinal did so before too. Fix: refuse when the text after a removed watermark starts an in-sequence marker while the clause before it is unfinished.

**Why:** The local audit found actual errors in quoted older-period texts. The reference population has now been read; fidelity beyond that population remains unproven until the failing sample documents are fixed or safely refused.

**Context:** PR #113, branch `claude/charming-lovelace-4a229o`; `EXTRACTOR_VERSION` 10 (7 at PR #113). The Drucksache cache rides in the in-memory Vorgang cache under `antrag_text.CACHE_NAMESPACE`; A3 coordination was on the former A3 entry (`git show c932255:TODOS.md`).

**Effort:** M (remaining source fidelity and measured anchor follow-ups)
**Priority:** P2
**Depends on:** Saved local corpus; no new backfill required

### Fill the Drucksache text cache for the WP 18–21 store

**What:** The A3 store has no Drucksache text cache, so the Antrag extractor (`EXTRACTOR_VERSION` 10) quotes no passage on it. On the merged-tree gate store (2026-11-01): 114 votes are `not_fetched`, 505 are `not_applicable`, and 0 passages are quoted. Fill the cache through DIP with A3's request pacing (the third stage of `refresh_vorgang_cache`), then repersist and report quoted passages old/new.

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
9. ~~An online Vorgang refetch replaces the cached record whole, so an answer without `titel` or `abstract` drops ones the cache had.~~ Done 2026-11-17: `fetch_ids` merges each refetched record into the cached one, and a field the answer gives as None keeps the cached value (the Sachgebiet and Sachbegriff lists, always lists, are replaced). Left: `resolve_numbers` still writes a number lookup's inline Vorgang records whole (`cache["vorgaenge"][record_id] = ...`), so a lookup answer without `titel` can drop a cached one the same way; it only runs for numbers not yet cached. Reference cache: 6,136 of 15,642 Vorgänge are refetch targets (no Sachgebiet), all with a titel, 3,306 with an abstract; offline replays do not fetch, so nothing moves.
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

### Persist overwrites a roll-call member row when two members of one vote resolve to one mp

**What:** `persist_vote` (`scripts/persist_dip_pulse_store.py`) writes each member with `INSERT … ON CONFLICT(vote_id, mp_id) DO UPDATE`, so when two members of one vote resolve to the same `mps` row the second silently replaces the first: the group loses a Stimme and the surviving row takes the later member's party and vote. Two people of one name in one Zusammenschluss reach this whatever their profile links: `derive.vote_member_key` builds the occurrence id from vote, name and Zusammenschluss alone, so they share one occurrence, and `person_registry.bind` keeps it on the record it is already bound to (reproduced 2026-11-06 through `persist_report`: two "Max Meier"/SPD members with different `/abgeordnete/` links store one row, with the first member's profile URL and the second member's vote). Decide between an occurrence id that tells namesakes apart, which changes a stable id, and a refusal naming the vote and both names, which would stop the build on a real pair of namesakes.

**Why:** The Abstimmung-page fold lost 63 rows in 22 groups of 11 votes this way without any error (Completed, "Store loses roll-call member rows in 22 groups of 11 votes"). v0.21.0.0 stopped new folds; the rows already folded stayed on their records until the store was rebuilt without its registry (review checklist class 3). No input reached it when last measured (2026-11-01, A3 reference store after `--offline --repersist` with that day's main: 425,322 report rows = 425,322 stored rows, 0 duplicate identity or occurrence keys in 619 votes). A real pair of namesakes in one vote would lose a Stimme silently.

**Context:** The same collision is named under "A.2 registry follow-ups from the third review pass" (the `name-party:` clause); close both together. The per-group check in `test_members_linked_to_the_abstimmung_page_stay_one_row_each` compares yes, no and total only, and no group in its fixture has an abstain or absent member; its Value comment cites Completed for the 63 rows, which are in the CHANGELOG for v0.21.0.0.

**Effort:** M
**Priority:** P3
**Depends on:** None

## Architektur

### Audit the or-0 baseline

**What:** `tests/code_rules_baseline.json` froze the 86 `x or 0` expressions (78 entries) that scripts/ had when `tests/test_code_rules.py` arrived on 2026-11-18. For each one, decide what a missing value means. If it was not measured, keep None and let the page say so. If the source leaves zero counts out, use `mapping.get(key, 0)`. If None really means zero, write `0 if value is None else value`. Remove each entry once it's handled. Start with the ones that write into the store, such as `persist_dip_pulse_store` storing `char_count`, `word_count` and `paragraph_count`, and the counts the pages print.

**Why:** Class 5 of the review checklist. `x or 0` publishes an unknown figure as a real 0. The rule stops new ones; the old ones are unchecked.

**Context:** A change that turns a stored 0 into NULL moves figures: replay it with the README recipe "Validate a data correction" and report old and new values.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Code rules: close the detector gaps reviews found

**What:** The detectors in `tests/test_code_rules.py` miss or misread some shapes that `scripts/` does not use today. (1) and (2) are done (2026-11-18): `_ATTACH` also takes `$`, `(`, `@`, a backtick, `[` or a bare name followed by `AS`; the nullable-comparison check and its table references unquote and lowercase identifiers before the schema lookup; `scripts/` had no new hit. (3) `UPDATE t SET a = CASE WHEN … END, b = ?` is misread: `is_comparison` sees the `WHEN` and counts the assignment to `b` as a comparison, a false alarm. (4) Comma joins (`FROM a, b`), a wrapped column (`LOWER(col) = ?`), a reversed comparison (`? = col`), named parameters (`= :p`), `IN (?)` and `BETWEEN` are not checked. (5) An import made through importlib is invisible to the layer rule.

**Why:** Found by the Codex structured review and an adversarial reader of v0.46.16.0 (2026-11-18). A miss lets a new instance of the bug class through; the false alarm in (3) would fail the suite on valid SQL.

**Context:** Each fix goes with a row in `DetectorTests` that shows the miss first. For (3), track the clause while skipping `CASE … END` nesting instead of taking the last keyword. For (2), normalize identifiers before the lookup.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Correct a cached report's XML Drucksache references at the source, not at every reader

**What:** A report cached before `validate_dip_protocol.extract_drucksachen` checked the link host keeps a number read off a quoted URL in `xml_drucksachen` (88/739016 from a syriahr.com link in 20/206), for good: `reparse_report_xml` re-reads Reden and Beiträge from the cached XML but not the Drucksache references. Since v0.23.6.0 every reader filters through `derive.xml_drucksachen` (persist, `item_document_numbers`, the dossier pills, the vote panel's link map), so nothing shows or stores it, but a new reader that reads `item["xml_drucksachen"]` directly brings the bug back. Either refresh `xml_drucksachen` from the cached XML in `--offline --repersist` (then the stored report is right and the filter can go after one replay of every cache), or filter once where reports are loaded (`load_existing_detail_entries`) and drop the per-reader calls.

**Why:** Found by the code review of v0.23.6.0 (2026-10-30). One correction at the source beats a rule every future reader has to remember.

**Context:** Refreshing from XML changes what a repersist writes into the cached reports, and `load_existing_detail_entries` is code `worktree-a3-plan` edits; do it after that branch. Check that `reparse_report_xml` keeps the API's `linked_drucksachen` untouched.

**Effort:** S
**Priority:** P3
**Depends on:** `worktree-a3-plan` merged

### A.2 follow-up ship review: deferred findings

**What:** Findings of the v0.19.0.0 ship review (2026-10-18) deferred by decision, P1 first: (1) **done** (lane/correctness): `run_facts_engine` now applies `pulse_store.require_build_store` (the distribution-copy guard `connect` uses) before computing or staging, so an exported SQLite given as `--database-path` is refused and left byte-identical; the /ship QA of that branch (2026-10-31, probes 004/005) found the rebuild replacing such a file (user_version 1 became 0, new inode), so `_rebuild_database_from_entries` now applies the same guard before staging. The read-only paths are done too (2026-11-18): `open_checked_store` in `build_dip_pulse_site.py` applies `require_build_store` and `require_current_schema` at the online pre-check, the mp-pages read, the post-rebuild read and the export source, so a distribution copy is refused up front. (2)–(4) and (6) are done (Done in v0.28.0.0 (2026-11-01), TODO batch 5): the staged copy gets the store's group before persisting (a group the builder cannot set stops the write), the sweep matches only this store's mkstemp names, a `data` directory directly under `/` keeps its private directory beside the store, and `person_registry.ensure_private_dir` refuses a symlinked, non-directory or foreign-owned private directory before any write or sweep; (5) now fails with a message naming the requirement (OUTPUT's parent writable and on the store's file system, docs/stable-ids.md), no override yet. Was: (2) `_replace_store` keeps the file mode but not the group, so a group-shared web root can lose read access after a rebuild or facts write (staging moved out of `data/`, whose group the old temp file inherited); (3) the staging sweep `glob(f"{name}.*.tmp*")` also matches a prefix-named sibling store's temp files and a lock of a store literally named `<name>.x.tmp`; restrict it to this store's mkstemp names; (4) `private_dir` treats any store whose directory is named `data` as `OUTPUT/data`, so an explicit `--database-path ~/stores/data/x.sqlite` stages in `~/.stores.private` and `/data/x.sqlite` in `/..private`; derive it from the real OUTPUT or fall back to the store's own directory; (5) the private directory needs a writable OUTPUT parent on the same file system, so OUTPUT as a mount point (container bind mount, CI volume) or under a read-only parent fails every rebuild, facts write and export; add an override or a fallback; (6) the private directory and its `exports/` are not checked for symlink or foreign owner before the sweep deletes their contents (shared `/tmp`); (7) the Daten export reads the store by path (schema check, stat, hash, backup) without the writer lock, so a concurrent rebuild can mislabel `datenstand.json` until the next export; (8) a forced same-name re-export killed between `published.replace(aside)` and `gen_dir.replace(published)` loses the published generation, and the next sweep deletes the set-aside copy; restore `replaced` on sweep; (9) `require_applied_partitions` catches a partition removed from the corrections file but not one added after the build (offline pages apply it, the registry does not); (10) a store from before DIP-id canonicalization holding `dip:07` splits that person on replay (new `dip:7` record, two pages; the real store has no such id); (11) `REPRESENTATIVE_SQL` orders `is_mdb DESC, xml_redner_id IS NULL, identity_key` but `collect_abgeordnete` orders `is_mdb` rows by `identity_key` only, so r1/r3 and the Personenseite can name a person with two MdB rows differently (0 such persons in the real store); (12) persist skips XML Drucksachen off the bundestag-xml host without a count or warning (all 4,699 real ones pass); (13) smaller: `_write_new_file` unlinks then creates, so a person page is briefly missing; an href-less date-like "21/09" folds into Drucksache 21/9; `document_issuer` falls back to BT without herausgeber or URL; a legacy `-journal` sidecar beside the store is not removed before the swap; `canonical_dip_person_id` raises on a >4,300-digit id; a local `document_id` in persist shadows the imported `stable_ids.document_id`; `tests/test_facts.py` computes two goldens with `facts._id_sort_key` (accepted, D25A).

**Why:** (1) can modify a downloaded distribution file; (2)-(6) break deployments other than the default layout; the rest are latent on the reference cache.

**Context:** Deferred in the v0.19.0.0 /ship run after three review passes, a red team per pass, a Claude adversarial pass and Codex adversarial and structured passes (structured gate passed, no P0/P1); Step 9 had used two of its three fix cycles. Verified false positive, not to re-file: a case-differing OUTPUT spelling shares one writer lock on macOS (same inode, second writer refused).

**Effort:** M
**Priority:** P2 (the P1 item (1) is done)
**Depends on:** None

### Store staging (batch 5): deferred review findings

**What:** The /gstack-review of `fix/todo-batch-5-store-staging` (2026-11-01) and the v0.28.0.0 /ship (2026-11-01) left three findings open; (1) the export work_dir through `ensure_private_dir` with a 0o077 repair, (2) `_write_csv`'s fchmod inside its cleanup, (3) the unused `import glob`, (4) the cross-file-system refusal test and (5) the chown-patched group-keeping test are done (2026-11-17, `todo/staging-vorgang-cache`). (6) A pre-existing private directory owned by another user (an earlier `sudo` run) is now a hard refusal where it was reused before; the message names the fix. (7) `politikfelder.write_atomic` falls back to staging beside the target in `data/` when `ensure_private_dir` refuses. (8) `_staged_store_path`'s sweep raises if a directory matches `_is_staged_copy`. (9) Follow-up of (1): `ensure_private_dir` now repairs any group/other bit but still refuses only when write bits (0o022) stay after the chmod, so a file system that keeps no POSIX modes may leave a private directory group- or world-readable (file names only; staged copies stay 0600). Refusing on 0o077 would be stricter; left as is because it adds a new hard refusal. (10) From the 0.46.20.0 ship review: the refetch merge cannot tell a field DIP's answer lacks from a Vorgang DIP no longer returns (`fetch_vorgaenge` writes an all-None record for it), so a vanished Vorgang keeps its cached titel, abstract, vorgangstyp and aktualisiert, and an abstract DIP withdrew stays; decide whether a missing id should be dropped or marked. The merge also keeps keys an older cache shape had and the current `vorgang_cache_record` no longer writes (limit to the fresh keys). `ensure_private_dir` tightens a deliberately shared 0750 private directory to 0700 without a message (print one line). `export_distribution_data` and `_export_lock` both run the `ensure_private_dir` pair (drop the one in `_export_lock`).

**Why:** These are latent. No figure moves.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Split the dataset from the site: the site builds from a release alone

**What:** Separate the two halves of the project in the code. On one side: acquisition, the store and the export (the dataset). On the other: the renderers, which read only a store or release. Today `scripts/build_dip_pulse_site.py` (15.2k lines, 2026-11-14) holds both, and the renderers do not read from the store. Checked 2026-09-30:
- **Read from in-memory report JSON (`entries`):** the Dossiers (`protocols/*.html`), `puls.html` and the bills pages. The votes archive reads the store since A4 slice 1 (v0.32.0.0, `votes_archive_rows`).
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
- `build_dip_pulse_site._structural_gap` parses that text back with `text.index("(")` and `_BUDGET_PAGES_RE` to decide whether `--backfill-incomplete` rescans a Sitzung.
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

**What:** Replace the ~680-line `main()` in `build_dip_pulse_site.py` with `build(config, source, clock) -> BuildResult` (pages written, manifest, gaps). DIP access goes behind a source seam with two adapters: HTTP for online builds, and cached reports for `--offline` and tests. Today:
- The offline and online branches repeat the same tail: `run_data_pipeline` returns a 5-tuple that is unpacked into `render_site`'s roughly 20 keyword arguments, in both branches.
- `write_report_and_page` takes 21 parameters, builds a fake `argparse.Namespace` for `dip.build_report`, and returns XML through an out-parameter dict.
- `getattr(args, ...)` appears about 40 times.
- `resolve_today` is called five times while other clocks bypass it, including some in `facts.py`.

**Why:** Orchestration can only be tested by patching module globals: `test_build_dip_pulse_site.py` has about 158 `patch()` calls (2026-11-14). "Some date checks use the wall clock, not `--today`" (item (11) of "Harden the vote acquisition…") is a symptom.

**Context:** Found by the architecture review of 2026-10-03. Easier after "The store owns its schema and its rebuild" and "Delete the feature-selection axis", which remove most of the parameters threaded through `main()`. `validate_dip_protocol.py` (2.6k lines, imported as `dip`: HTTP client, XML parser, roll-call scraping, three LLM providers, report assembly) is the natural home for the source adapter. `enrich_with_llm_summaries` taking the CLI namespace and the `global _namenslisten_entries` cache should go in the same pass.

**Effort:** L
**Priority:** P3
**Depends on:** Best after the store and feature-axis items above

### The pre-gate's `literals` check reads every Wahlperiode 18 as export format 18

**What:** gstack-pregate's `literals` check (installed gstack 1.99.2, `lib/pregate/checks/literals.ts`) searches every test file that names a changed constant or its module for the constant's old value. For a two-digit value it needs no other context, so a format or schema bump flags every Wahlperiode, Drucksache (`18/84`), date and item number holding that value. On the 18 → 19 / 12 → 13 bump (vote PR A, v0.44.0.0) that was about 420 lines in about 40 test files that import `build_dip_pulse_site` or `persist_dip_pulse_store`. It reports one line per file per run, has no config switch, and `gstack-ship-release finish` and the push re-run it. PR A sorted the hits by hand: the real format literals (`tests/test_release_changes.py`'s current manifest) now use `EXPORT_FORMAT`; value cards meaning schema 12 carry `# pregate-literal:` markers; the rest is noise, and the PR was pushed and opened by hand outside `finish`. Vote PR B (schema 13 → 14, format 19 → 20) hits the same, worse with every WP 19 line. Fix upstream (require the constant's name or a version-like key such as `export_format`/`schema` on the line for short numeric values), or add a repo-level allowlist to `.gstack/pregate.json` if gstack offers one.

**Why:** Without it every schema or format bump either fails the pre-gate or needs hundreds of marker comments, so a real stale literal is lost in the noise.

**Effort:** S (upstream heuristic)
**Priority:** P2
**Depends on:** gstack upstream

### Read a Tagesordnungspunkt's turns once

**What:** Give "who speaks in a `<rede>`" one module. It reads each Tagesordnungspunkt once into a sequence of turns that nothing edits afterwards. Each turn's speaker is resolved once: Sitzungsleitung, the Rede's owner, another MdB, someone speaking for the Bundesregierung, or unplaced. Each turn also carries its marker ordinal, label tail, paragraphs, and the Rede or split part it belongs to. Reviewed kinds, the Fraktionsrede role strip and roleless chairs become facts on that sequence instead of tree edits. Today (main ccb0aa0, v0.44.0.0):
- Eight walks over a `<rede>` keep their own chair, marker and continuation state: `speech_kinds.py` 361–371, 497–507, 643–680; `validate_dip_protocol.py` 917–931, 1067–1100, 1179–1355, 1776–1784, 2332–2348.
- "Is this marker the Sitzungsleitung" exists in four forms: a raw role regex (`validate_dip_protocol.py` 1039–1042), a name-stripped test through `derive` (`speech_kinds.py` 244–254), a raw `rolle_lang` Vizepräsident test (`validate_dip_protocol.py` 968–988) and a name match against `<name>` chairs (902–935). `derive.py` 408–420 repeats the test on the report.
- The passes talk to each other by editing the tree: `sitzungsleitung="1"` (934), `reviewed_kind` (964), a removed `<rolle>` (988), `top_source` (1027) and inserted split `<rede>`s (1091–1097). So the pass order in `parse_protocol_xml` (1677–1718) is an unwritten invariant, and `parse_vote_recommendations` (2042) reads the edited tree.

**Why:** The open WP 18/19 work is mostly "who is speaking" cases: "WP 18/19: nested Erwiderung, Erklärung and Geschäftsordnung turns", "20/11: the chair's handover exchange…", the `<name>` speakers in "ADR 0004 follow-ups". Each case has to be taught to every walk, and each walk has its own idea of the chair. Tests reach a rule only through a whole sitting's XML. Six test files write their own XML builders: `test_a3_rule5.py`, `test_a3_round2.py`, `test_presidium_kinds.py`, `test_rede_reconciliation.py`, `test_withholding.py` and `test_rede_text.py`.

**Context:** Found by the architecture review of 2026-11-15 (main 0e6def4). In-process, so no adapter is needed. Chair recognition is then tested once, rule tests feed in turns, and the six builders become one. "Decide each nested turn in one place" takes this sequence as its input. Judged fine and left alone: `reconcile_reden`/`raw_rede_inventory`, `fragestunde_turns`, the annex tables in `written_contributions`, `adopt_reden_outside_tops`. A replay of the reference store must move no figure.

**Effort:** L
**Priority:** P2
**Depends on:** None; best before the next WP 18/19 rule round

### Decide each nested turn in one place

**What:** One module takes one Rede's turns (from "Read a Tagesordnungspunkt's turns once") plus its neighbours' labels. It returns exactly one treatment per turn, with its evidence: a Beitrag Kind, procedural, merged into a named Rede, or withheld with a reason code. `parse_protocol_xml` only stores the result. Today:
- Evidence travels from `speech_segments` (`validate_dip_protocol.py` 1193–1383) as an untyped dict of about 14 keys. Pass 1 decides procedural or merged and sets `unsupported_reply` (1800–1850). Pass 2 combines about nine flags into a Zwischenfrage, a Befragung kind or a `LocatedRefusal` (1918–1935).
- The 20/113 and 20/191 Kurzintervention exceptions are coded twice, with the same regexes: `speech_kinds.py` 511–520 and `validate_dip_protocol.py` 1819–1847. If the two copies drift, the Rede is withheld through `unsupported_reply` without a message.
- Located refusals are stored in one pass (1758, 1764, 1854) and raised in the other (1924, 1933). Nothing lists the refusal sites, so `tests/test_withholding.py` 82–87 counts `reason="…"` strings in the source file.
- `speech_text_and_paragraphs` (1387) is a one-line wrapper over `speech_segments(rede)[0]` with no production caller. Its 8 tests in `test_rede_text.py` check raw own text that pass 1 later blanks or extends (1858, 1864–1868).

**Why:** Each queued rule has to be written into `speech_segments`, pass 1 and pass 2, and an exchange-shaped rule into `classify_reden` as well. This is the code with the most churn since October.

**Context:** Found by the architecture review of 2026-11-15. Each rule then becomes a turns-in, treatment-out test, and the source-grep test becomes an assertion on reason codes. When `speech_text_and_paragraphs` goes, repoint "Zwischenrufe: parse `<kommentar>` and count reactions per Fraktion" to `speech_segments`; it cites the wrapper as the place where `<kommentar>` leaves the Rede text.

**Effort:** L
**Priority:** P2
**Depends on:** "Read a Tagesordnungspunkt's turns once"

### One module for the link between a namentliche Abstimmung and its Tagesordnungspunkt

**What:** The link rule itself is now one module (`scripts/vote_links.py`, PR B, see Status). What is left is the fetch side, which still sits inline in `enrich_with_api` (`validate_dip_protocol.py` 4112–4478):
- The candidate scan (`fetch_roll_call_vote_candidates`, called at 4143) and the detail fetch (`fetch_roll_call_vote_detail`, called at 4297) stay inside it, so link tests keep their patches. Move the fetching behind one local-substitutable seam, so a link test is plain data.
- `find_roll_call_xlsx_url` (3107) has no production caller; only `tests/test_roll_call_scraping.py` calls it. Keep it only if "Take namentliche Abstimmungen from the official XLSX instead of the chart markup" will use it, else delete it with its tests.

**Why:** The rule has no interface, so the tested helper is not the rule that ships, and the P1 "Check that vote links are right" cited the helper until 2026-11-15. Checking one link takes a DIP FakeClient, a parsed agenda, patches of `fetch_html`, `fetch_roll_call_vote_detail`, `fetch_roll_call_vote_candidates` and `overlaps`, and a reset of a module global (`tests/test_vote_acquisition.py` 155, 16 patches).

**Context:** Found by the architecture review of 2026-11-15. In-process; the fetcher is local-substitutable. Link tests become plain data: Tagesordnungspunkte plus candidates give links. With each link's reason returned, the N10 review can sample by reason. The scan-state vocabulary stays with "Typed completeness gaps instead of reason strings".

**Effort:** S
**Priority:** P2
**Depends on:** None; best before or with "Check that vote links are right"

**Status (2026-11-15):** PR B (`claude/vote-link-attribution`) delivers the module: `scripts/vote_links.py` takes the Tagesordnungspunkte and the votes and returns each link with its reason (`agenda_item_votes.basis`); `enrich_with_api`, the replay and the carry-forward call it, and `match_roll_call_votes` with its test is gone. Still open here: the candidate scan and detail fetch stay inside `enrich_with_api`, so its tests keep their patches; the decision on `find_roll_call_xlsx_url`.

### One link scheme for pages and anchors

**What:** One module knows where each page lives (Dossier, Abstimmung, Personenseite, Gesetzesvorhaben), which id each anchor carries (Tagesordnungspunkt, Rede, Beitrag, Abstimmung), and the href from any page depth. Pages emit ids and links through it. Whether a Person has a Personenseite stays with "One Persons module over the person registry". Today five partial helpers each own a piece: `report_paths` (`build_dip_pulse_site.py` 1236), `resolve_entity_link` (5233, depth 0 only), `dossier_href` (6869), `speech_anchor` (`render_dip_pulse_html.py` 1309) and `vote_anchor_id` (`features/votes.py` 429). Around them:
- The Dossier path is written out by hand at 13 places in `build_dip_pulse_site.py` (6159, 6262, 6562, 6648–6649, 7095, 7228, 8011, 9953, 10005, 11159, 11513, 12353), plus `week_radar_feed.py` 93 and `build_demo_site.py` 209.
- `render_dip_pulse_html.py` 3287 writes the anchor `id="top-N"`, and eleven places rebuild `#top-N` by hand: render 2286, 2993, 3171; build 6158, 6648, 6649, 7058, 7095, 8100; `week_radar_feed.py` 93, 102.
- Page depth travels as strings: `mp_prefix`/`site_prefix` (`features/votes.py` 154–156) and `"../"` literals.
- `week_radar_feed.py` 12–13 says the dossier link function is passed in, yet line 93 writes the formula out itself.
- `_bill_event_href` (`build_dip_pulse_site.py` 8868) checks the site's own hrefs against a regex.

**Why:** Renaming a page or an anchor means editing about 30 places in four modules. No test short of a full build proves that an href lands on an id the page emits: `validate_store_gate.audit_links` is the only check. About 77 test lines pin literal link strings.

**Context:** Found by the architecture review of 2026-11-15. A gap in `docs/plans/render-layer-and-order.md`: its `href()` only checks schemes, and `render/common.py` does not name this. Build it before render-layer step 3, or each per-page move copies the formulas into a new module. A round-trip test ("the href for Tagesordnungspunkt X hits the id the Dossier emits") then runs without a build, and `audit_links` stays as the backstop. In-process.

**Effort:** M
**Priority:** P2
**Depends on:** None; before render-layer step 3

### One request module for every outside source

**What:** One module owns outgoing requests per host: pace and budget, which errors are retried, the cut-off after an outage, timeouts and the request log. DIP, bundestag.de, abgeordnetenwatch, the MdB-Stammdaten and the LLM providers ask it for text, bytes or JSON. Production uses a urllib adapter, tests one fake adapter. Today five `urlopen` paths each have their own policy:
- `ApiClient` (`validate_dip_protocol.py` 273): 2 retries, `DipBreaker`, logged.
- `_fetch_page` (363) for bundestag.de and the dserver: 2 retries, logged, no cut-off of its own. The roll-call outage is a `"monotonic|message"` string under `__outage__` in the page-cache dict (352, 3132–3146), and it guards list pages only. Detail and member pages (3299–3300) have no cut-off. The Namenslisten page (2993–2999) is not memoised on failure, so it is requested again for every vote.
- `abgeordnetenwatch.py` `_request`: retries only on 429 (60 s each), does not retry a connection error but counts it, cuts off after 8 failures (`MAX_CONSECUTIVE_FAILURES`), not logged. `measure_aw_match_share.py` 71 has a second cut-off.
- `stammdaten.py` 320: one attempt, not logged.
- `post_json` (`validate_dip_protocol.py` 603) and `build_dip_pulse_site.py` 5200.
- `fetch_html` and `fetch_text` (555, 599) are one-line pass-throughs that exist as patch points.

Tests fake HTTP six ways: the global `urllib.request.urlopen` (`test_abgeordnetenwatch.py` 8 times, `test_stammdaten.py`, `test_measure_aw_match_share.py`), `dip.urllib.request.urlopen`, `dip.fetch_html` (39 patches in 6 files), injected callables (the `sitzungskalender` FakeSource, the `XmlPacer` clock and sleep), and resets of `dip._namenslisten_entries` (3 sites).

**Why:** What "this host stopped answering" means, and whether a request reaches `DIP_REQUEST_LOG`, depends on which module asks. TODOS.md lists the symptoms one source at a time, and each fix lands in one copy: "C1 seat counts: deferred findings" items 1 and 32, "A3 /gstack-ship review: deferred findings (2026-11-01)" adversarial pass (a), "A3 item 1.5 review (2026-11-13): deferred findings" item 1 (its items 5 and 6 were fixed in the abgeordnetenwatch copy on 2026-11-17).

**Context:** Found by the architecture review of 2026-11-15. This is not the source seam in "A build pipeline module behind `main()`", which replays DIP data from cached reports; this one is about requests to every host. Two real adapters, live and fake, justify the seam. A data-level seam for all sources is not justified: each source records a different shape (raw XML and zip, parsed profiles, parsed report JSON), so it would have one adapter. `sitzungskalender` and `XmlPacer` already inject their side effects. Close the symptom items above when this lands.

**Effort:** M
**Priority:** P3
**Depends on:** None

### One reader for a Daten export on disk

**What:** The export module owns its layout in both directions. It opens an exports directory through `datenstand.json`, exposes the generation, its listed files and the SQLite copy, and runs one verification that returns typed problems (missing, extra, size, hash), with a cheap mode for reuse. The release checks (tag, commit, licence) stay in `publish_dip_pulse_data.py`. Today three places check a generation against `datenstand.json`, each differently, and a fourth reads the export by its own route:
- `_manifest_reusable` (`build_dip_pulse_site.py` 4014) checks sizes and hashes only the small files.
- `validate_store_gate.check_export` (224) hashes every listed file and ignores extra files.
- `publish_dip_pulse_data.verify_export` (205) hashes every file and refuses extra or missing ones.
- `compare_store_values._distribution_copy` reads the SQLite copy's name from `datenstand.json` (generation and first file), as the export does.
- "Release pipeline: deferred /ship review findings" item 5 asks for one more check (re-verify staging before the rename).
- The SHA-256 helper is copied at `validate_store_gate.py` 216, `publish_dip_pulse_data.py` 68 and `build_dip_pulse_site.py` 3904.

**Why:** The store gate passes an export with an extra file that the release then refuses. Each consumer knows the layout, and each verifier's tests build a real export and tamper with it on their own (`test_validate_store_gate.py` 525, `test_publish_dip_pulse_data.py` 247–265, `test_daten_export.py` 1635ff).

**Context:** Found by the architecture review of 2026-11-15. This is the reading half of the `export(store, out_dir) -> manifest` module that "Split the dataset from the site" proposes, so build both together. Local-substitutable (a temp directory). The tamper cases are then tested once, and the gate and publish tests keep only their own checks.

**Effort:** M
**Priority:** P2
**Depends on:** None; best with the export move in "Split the dataset from the site"

### The reviewed list applied and checked by its own module

**What:** `reviewed_units.py` decides what `reviewed_units.json` says for a Sitzung's units at both grains (a whole `<rede>` before the split, a withheld unit after it) and raises on a stale entry. It also owns the check that a parse is current under the list, which build and persist call. Today the module only loads, validates and digests the list, and tests inject entries two ways (the global `use()` at 104 and a `reviewed=` parameter):
- Matching sits in the parser, at two grains: whole-`<rede>` entries before the split, each checked against its owner (`validate_dip_protocol.py` 941–965), and withhold entries after it, with a second owner check (1891–1901) and an unmatched check (2028–2033).
- Kind names are string literals in `reviewed_units.py` 36, `derive.py` 325, `speech_kinds.py` 472 and `validate_dip_protocol.py` 1063.
- The currency check is written twice: in `build_dip_pulse_site.stale_causes` (2011–2024) for cached reports and in `persist_dip_pulse_store.require_current_speech_rules` (111–123) for the store. `persist_report` (1949–1954) still stamps the current digest on a report without one, relying on the speech-rule version to refuse such a report.

**Why:** "ADR 0004 follow-ups" still lists a symptom: a candidate flagged on a 6c split part can never be listed, because presidium entries are matched before the split. Listing a split part under a presidium kind today touches five places. PR B of `docs/plans/withheld-before-t4.md` (v0.42/v0.43) closed three more symptoms, the PR 2 ship review P3s in "Coverage gate before the first data release", one at a time, in the parser, in `stale_causes` and in the demo fixture.

**Context:** Found by the architecture review of 2026-11-15. Since PR B made the currency check sound, what remains is mainly the matching at two grains. Local-substitutable. Owner and currency checks become unit tests without XML, and `use()` can go.

**Effort:** M
**Priority:** P4
**Depends on:** None

### One projection from a parsed Plenarprotokoll to its report

**What:** One function owns the report's XML half: protocol stamps, per-Tagesordnungspunkt fields, sitting-level Beiträge, the validation summary and the DIP mismatch warnings. Pre-release, the parser could emit that shape directly. Today:
- The XML half is put together by hand in `build_report` (`validate_dip_protocol.py` 4560–4588, plus 4203, 4364, 4452), in `reparse_report_xml` (4011–4057) and in `extract_demo_fixture.py` 99–153.
- Four test helpers copy it: `test_withholding.py` 46–52, `test_a1_followups.py` 26–31, `test_wp18_19_pipeline.py` 17–24, `test_reden_outside_tops.py` 25–37.
- The parser's shape and the report's shape differ (3830–3874), and readers decode a unit's category from its id prefix (`check_withhold_one.py` 57–125, `render_dip_pulse_html.py` 1887).

**Why:** The copies drift, and each drift has been a separate fix. Reparse skips `xml_drucksache_count` ("Reden outside a TOP: what the ship review left open" item 9). The demo fixture dropped `reviewed_digest` until PR B of `docs/plans/withheld-before-t4.md` added it by hand. `test_withholding.py` now carries it too, but the other three test copies still omit it.

**Context:** Found by the architecture review of 2026-11-15. In-process. "Reparse equals a fresh build's XML half" becomes a test, and the four helpers become one call. This is the write side: "Split the dataset from the site" is the read side, and "Correct a cached report's XML Drucksache references at the source" covers one of its fields.

**Effort:** S
**Priority:** P3
**Depends on:** None

### A Publication domain's page notice from its Presentation state

**What:** `publication_state` maps a Publication domain's facts to the notice a page shows (state, wording, source link), and every page renders that notice. Today each domain dict carries both `acquisition_state` and `presentation_state` (`publication_state.py` 240–241), but only the sources page reads `presentation_state` (`build_dip_pulse_site.py` 12394, defaulting to "unavailable"). Three places read `acquisition_state` instead, default it to "complete" and keep their own wording:
- votes `_STATUS_COPY` (`features/votes.py` 439, 553);
- `_mp_domain_notice` (`build_dip_pulse_site.py` 9749, called at 9859–9860 and 10058–10059);
- the Dossier's profile notice (`render_dip_pulse_html.py` 3340–3348, the same strings as build 9754–9756).

None of them goes through `derive_presentation_state` (`publication_state.py` 96), which folds in the record and rejection counts.

**Why:** CONTEXT.md says a Presentation state is derived and never set directly. Today the meaning of each state and its wording live in four places, and a missing state shows as complete. That is latent: the build always fills the state in (`build_dip_pulse_site.py` 2996–3066), so only direct render callers and tests reach the default.

**Context:** Found by the architecture review of 2026-11-15. A gap in `docs/plans/render-layer-and-order.md`: L2 names a `provenance` gap component but not what feeds it. This is the display side; "Typed completeness gaps instead of reason strings" covers the reasons used by backfill and the manifest. The wording per state is then tested on one function. In-process.

**Effort:** S
**Priority:** P3
**Depends on:** None; fits render-layer L2

### One module for a versioned source cache file

**What:** One module for "a versioned cache file": one load policy for a damaged or old file, an atomic save, a fetch time per entry. Each source supplies only its record shape and expiry rule. Today each cache treats a damaged or old file differently:
- `dip_cache.py` 33–42, 88–108: an unreadable file reads as empty and is overwritten, through `write_text_atomic` (a fixed temp name and no fsync; `validate_dip_protocol.py` 4059).
- `politikfelder.py` 224–372 and `antrag_text.py` 617–671: another version is refused, a corrupt file is moved aside, the save fsyncs.
- `abgeordnetenwatch.py` 236–270: an unreadable or other-version file is dropped silently and overwritten on save.
- `sitzungskalender.py` 200–215: warns and keeps the file.
- `stammdaten.py` 395–420: its own mkstemp and sweep.
- The roll-call page cache travels as `getattr(args, "roll_call_page_cache")` (`validate_dip_protocol.py` 4531), and the Namenslisten cache is a module global (2990).
- `measure_aw_match_share.py` 284–302 keeps a second answers file with its own atomic write, because the abgeordnetenwatch cache records no failures, candidate counts or fetch time.

**Why:** Whether a damaged cache is refused, kept or lost depends on which source wrote it. Losing the abgeordnetenwatch cache costs about 43 minutes of requests ("A3 item 1.5 review (2026-11-13): deferred findings" item 1).

**Context:** Found by the architecture review of 2026-11-15. Latent: no figure is wrong today. Local-substitutable (a temp directory); the corrupt-file, version and atomicity tests are written once. `dip_cache`'s expiry and closed-Wahlperiode rule earn their keep and become its shape and expiry. Related: the gate and prefetch robustness item in "A3 /gstack-ship review: deferred findings (2026-11-01)", where a build and `prefetch_dip_bulk` rewrite the same `data/dip-*-cache.json` without the writer lock.

**Effort:** M
**Priority:** P3
**Depends on:** None

### One reading of a printed MdB name for every source

**What:** Parse each source's name format (the roll-call "surname, given name", the Plenarprotokoll `<redner>`, abgeordnetenwatch) into given name, surname and title words in one place. Each consumer still builds its own key from the parts. Today one roll-call name is read three ways:
- `derive.person_name_key` (`derive.py` 1146), for E4 re-filing: drops every word ending in a full stop and anything in parentheses, and ignores word order.
- `person_registry._normalized_mp_name` and `_name_words` (853–905), for Namensabgleich: 15 title words, leading ones only, and 10 particles including Freiherr and Graf.
- `build_dip_pulse_site._vote_member_name_parts` (1039–1094), for the abgeordnetenwatch name query at 1171: 3 title words, and 23 particles without Freiherr and Graf.
- `measure_aw_match_share.py` 269 imports the private `_name_words`.

**Why:** A title or role rule change lands in one reading only, for example the role words dropped from `_name_words` only (2026-11-17, "Shared Redner-IDs: what the fix leaves open" item 12): `derive.person_name_key` and `_vote_member_name_parts` keep them.

**Context:** Found by the architecture review of 2026-11-15. Speculative: no disagreement between the readings was found in the data. In-process. Test with one table of real spellings across sources.

**Effort:** S
**Priority:** P4
**Depends on:** None

### Architecture review 2026-11-15: smaller findings

**What:**
1. **Page scripts without a home in the render-layer plan.** In `docs/plans/render-layer-and-order.md`, L2 gives `render/assets/site.js` only the theme toggle, the data age and the filter chips. The other inline `<script>` blocks have no target: `render_dip_pulse_html.py` 902, 939, 1128, 1161, 1205, 1231 (the Dossier sidebar among them) and `build_dip_pulse_site.py` 5496, 6441, 7173, 8258, 8417, 9654, 11572. About 30 test lines match their source text, and L5 has no row for them. Add them to the plan before the per-page moves.
2. **Table descriptions have two sources.** `DATABASE_TABLE_DESCRIPTIONS` (`build_dip_pulse_site.py` 144–180, shown on the Daten page at 5591) and the table meanings in `scripts/data_dictionary.json` (DATA.md) describe the same tables in different words. Q10 moves the schema to DATA.md: when the Daten page's schema section goes, merge the richer prose into the dictionary and delete the dict.
3. **`tests/_votes_fixture.panel_for` copies the panel wiring of `render_html`** (`render_dip_pulse_html.py` 3142–3153) and leaves out `vote_passages`, so a fixture panel never shows Antrag passages. Give the page and the fixture one constructor.

**Why:** Found by the architecture review of 2026-11-15. None is a correctness defect.

**Effort:** S each
**Priority:** P3 (1), P4 (2, 3)
**Depends on:** None

### publication-guards review: deferred findings

**What:** Non-correctness findings of the review of `todo/publication-guards` (2026-11-18): (1) `load_existing_detail_entries` skips the vote-shape check for `recorded_exclusions(output_dir)`, but an online run with `--include-document-number N` takes N back while the record still lists it, so a stale report of N loads unchecked and is refused only later by `persist_report`'s `require_vote_shape` (after dossiers and roster are fetched; no figure is wrong). Pass the run's effective exclusion set (record plus `--exclude`, minus `--include`) as the skip set, or keep the check for numbers in `included`. (2) `measure_aw_match_share.py` (~147) calls `load_existing_detail_entries` with a temporary `view` directory that has no `coverage-exclusions.json`, so the skip never applies there and a stale report of an excluded sitting still stops it with a `UsageError` (predates the branch; the cache holds 0 of 246 stale votes). Link the record into the view or run the shape check after `without_recorded_exclusions`. (3) Stale comments: the `# Two paths through this function:` comment of `main` now sits above `open_checked_store` (move the helper above it); the `require_build_store` docstring (`persist_dip_pulse_store.py`, ~169) should name `open_checked_store`; the `sqlite_open.open_readonly` docstring still says a read-only connection "needs none of the build store's refusals", which the build store read paths now apply through `open_checked_store`. (4) Tests: the mp-pages and post-rebuild reads through `open_checked_store` have no test of their own (a patched `open_checked_store` asserted called on the online post-rebuild path would pin them). Ship review (2026-11-19), below the blocking floor: (5) the `local-path` URL token runs to whitespace, a quote or `<`/`>`, so a path glued to a URL by `)`, `]`, `}`, `,`, `;`, `|` or a backtick is hidden (`(https://x.de)/Users/…`); stop the token at those and update the docstring's "bracket". (6) A protocol-relative `//host.tld/…` token is exempt, so `//nas.local/Users/x` passes (base passed it too; `file://` stays caught by `file-url`). (7) Now flagged without a host check: a scheme-less address such as `spd.de/home/news` or a site path `href="/kontakt/home/"` in a quoted speech fails publication (0 such lines in the reference output); exempt `/home/` after a dotted host token. (8) JSON-escaped separators (`\/Users\/`, `\u002fUsers`) in a scanned JSON file are not matched (`json.dumps` writes neither). (9) A single-backslash `C:\Users\` in HTML or DATA.md is not matched, only the JSON-escaped form (predates the branch). (10) `splitlines` also splits on `\x0b`, `\x0c`, `\x85` and U+2028/9, so reported line numbers can drift (predates the branch). (11) Item (1) also holds for `--exclude-document-number`: a sitting excluded in the same run but not yet on the record still raises on a stale shape. (12) `recorded_exclusions` is re-read for every stale report inside the loop, and a malformed record replaces the shape error (`main` refuses a malformed record before any load); read it once, lazily. The comment "no caller reads its shape" is loose: the `--backfill-incomplete` scan gets the unfiltered entry (it computes gaps over the filtered catalog and renders nothing). (13) A refusal at the mp-pages and post-rebuild opens is not caught there and would print a traceback; the main pre-check or the rebuild guard refuses first, as for `require_current_schema` before.

**Why:** Review lenses correctness, spec, standards and checklist; none changes a figure or output.

**Effort:** S
**Priority:** P4
**Depends on:** None

## Completed

One line per finished item, giving the version and PR that shipped it, or the date it closed. When you finish an item, replace its entry with one line here. What changed belongs in CHANGELOG.md and the PR. The full entries up to the 2026-11-02 cleanup are in git history (`git show c932255:TODOS.md`).

- Parser Inhaltsverzeichnis and rede-id guards (Rede reconciliation items 6, 9; Inhaltsverzeichnis block items 1 to 4): v0.46.30.0, 2026-11-20. A source `<rede>` id with ":" and a Rede listed at two pages refuse; adopted runs compare by label, ignore untitled blocks and no longer scan cubically; the pre-gate maps two more parser test files. No figure moved: the 801 cached XMLs parse to identical output. Reconciliation item 8 stays open; the /ship review left Inhaltsverzeichnis block items 7 to 12.
- Profile check rede id and Redner-ID name check edges ("Shared Redner-IDs: what the fix leaves open" items 20, 21, 22; "Redner-ID name check: what the v0.46.10.0 ship review left open" items 2, 3, 4): v0.46.29.0, 2026-11-20. `attach_speaker_profiles` and `redner_id_profiles` look a reviewed occurrence up by the rede id persist keys it by (`profile_rede_id`, a first-five entry by its `xml_speakers` sequence); `_name_words` keeps an office-only name's words and reads Vizekanzler(in), Staatsrat/Staatsrätin, -beauftragte(r) and -bevollmächtigte(r) as offices; `_same_office_surname` links two names sharing only an office-like surname when their given names agree. On the 801-sitting reference store the check compares 53 of 1,591 Redner-ID records before and after and refuses none; no stored name changes its word set. Item 18 stays open (needs the canonical form of a Redner-ID decided); the /ship review left name check items 8 and 9
- Fraktion check items 2 and 7 (an unknown `<fraktion>` names `derive._SPELLINGS` and `docs/source-errors.md` online and on replay; the `_SPELLINGS` comment): v0.46.28.0, 2026-11-18. Message wording only; no figure moved.
- T4 parser rules items 5 and 7 (unspaced Befragung prefixes as a constant; the 18/158 rule removes only the TOPs it emptied): v0.46.28.0, 2026-11-18. No figure moved: the old and new rule give the same TOP list in all 801 cached sittings.
- Withheld-Reden PR B latent items (online sitting check after the parse; empty `dokumentnummer` message): v0.46.28.0, 2026-11-18. `validate_dip_protocol.build_report` compares the XML root's `wahlperiode`/`sitzung-nr` with `dokumentnummer` before `parse_protocol_xml`, so a wrong-sitting file the parser would refuse with `ReviewedUnitsError` is still a `source_rejected` refusal, and `xml_sitting_mismatch` says "the DIP record has no dokumentnummer" instead of "not of ". No figure moved (an online-only path; no cached sitting is a wrong-sitting file).
- compare_cpp_bt and compare_store_values edges: v0.46.27.0, 2026-11-18 (branch `todo/compare-tools`): an `only_theirs` known-differences row without a `rede_id`, a bad deflate stream and a non-UTF-8 known file now exit 2; compare_store_values docstrings, the `unavailable` vote groups row, the narrower `_recipe_rows` catch and the one-sided member list tails. No figure moved.
- Stammdaten download hardening: v0.46.27.0, 2026-11-18 (branch todo/stammdaten-download) (C1 deferred items 28, 32, 40, 42 and two cells of 44): same-host redirects only, a total download deadline, a size cap on the cached zip, and a rebuild pointer for an unreadable store.
- Store-gate tools stop cleanly (v0.46.27.0): `validate_store_gate`, `measure_aw_match_share` and `build_demo_site` load `reviewed_units` at startup and stop with a message when it is missing; the gate turns a clone OSError into exit 2 (C1 item 41); "Registry fix review" (i) found already satisfied and pinned by a test. 2026-11-18. No figure moved
- Vote-link rule cleanups: v0.46.26.0, 2026-11-18. "Check that vote links are right" items 5 and 7 (placement gate also checks `sitting_votes`; printed Drucksachen through `derive.xml_drucksachen`), and "Move title_matches below the parser" (`norm_title`/`title_matches` now live in `vote_links`, the last import cycle and its `KNOWN_CYCLES` entry are gone). No link moved on the 801-sitting reference store.
- B4 extractive fallback validation, items 3 (comment), 5, 8, 10 (clause cap): v0.46.25.0, 2026-11-18. `_WATERMARK` swallows trailing spaces so a watermark mid-text no longer looks like a dropped bullet, `_MAX_CLAUSE_WORDS` named and pinned at 29/30/31, two comments corrected; no measured figure moves; `EXTRACTOR_VERSION` 9 to 10 in v0.46.25.0, so a store persisted at 9 needs `--repersist`.
- Docs status fixes (Design hand-over leftovers item 1; Persist or prove the vote outcome item 6; Settle the MdB-Stammdaten terms, the "Also" sentence; vote-link entry text): v0.46.25.0, 2026-11-18. The A4 re-scope part carries a not-applied banner, the vote-links plan labels the `result_raw` and `application_result` mixes, DATA.md's sources paragraph names the MdB-Stammdaten as an open redistribution question, and the vote-link entry lists only its remaining fetch-side work. No figure moved; DATA.md bytes (export digests) change.
- Code rules detector gaps (1) ATTACH shapes and (2) quoted/uppercase identifiers in the nullable-comparison check: v0.46.25.0, 2026-11-18, `tests/test_code_rules.py`; (3) to (5) stay open.
- Release-script hardening: v0.46.24.0, 2026-11-20. Release pipeline items 8, 11 (numeric commit) and most of 9; Impressum/licence review item 3 and ship items 5 and 16 (the gate half). `verify_export` refuses a licence string that is not the commit blob's short string; versions are ASCII-only; NaN, Infinity and an overflowing number (`1e999`) refused in the changes file and `changes.json` written without them; four more diff settings pinned. No stored figure moved.
- publication-guards: v0.46.23.0, 2026-11-19. `local-path` flags /Users/ and /home/ anywhere except inside a URL token (`https://` in any case, `//host.` or `www.`, read with HTML entities decoded); `open_checked_store` applies `require_build_store` on the read-only paths of A.2 follow-up item (1); `load_existing_detail_entries` skips the vote-shape check for a sitting on the exclusion record. No figure moves.
- WP 18 Einzelplan 21 mapped: v0.46.21.0, 2026-11-19. `EINZELPLAN_TO_POLITIKFELDER` had no `("18", "21")` key, so the Einzelplan 21 items of 18/138 and 18/201 (Bundesbeauftragte für den Datenschutz) were stored `einzelplan_unknown`; now `Digitales` as in WP 19 to 21. WP 18 agenda items with a Politikfeld: 1,443 to 1,445 of 2,381 (60.6% to 60.7%) on a replay of the tagging over the store.
- Puls outward (batch 7) feed and calendar hardening (items 1 partly, 2 partly, 3, 6 RSS date): 2026-11-17. `week_radar_feed` strips XML-illegal control characters from feed text, `valid_site_url` refuses credentials and whitespace, the description parses `datum[:10]`; `sitzungskalender` merges weeks per ISO week before the minimum and the gap count, treats a future `fetched_at` as due, and its docstring records the verified format. No published figure moved.
- Puls outward (batch 7) item 7, feed text: v0.46.25.0, 2026-11-18. `_cut` turns `\x0b`, `\x0c`, `\x1c`-`\x1f` into a space before splitting, `_XML_ILLEGAL` covers lone surrogates and U+FFFE/U+FFFF, the refused SITE_URL warning prints only scheme and host with userinfo masked. No figure moved. Fixes the RSS text only; the JSON write of a lone-surrogate title stays open (item 7).
- Stammdaten reader and store gate hardening: v0.46.15.0, 2026-11-18. C1 deferred items 11 (hash the parsed buffer; the sweep half stays open), 15, 17 and 37; E4 /gstack-review item 3 (offline render refuses a Stammdaten file the store was not built with; the rebuild's double read stays open) and item 5's `_data_clone` part; Registry fix review (c), (g) and (i)'s second half. No figure moved: the reference store's file and `mdb_stammdaten_stand` share sha256 `29ae4ba1…` and an offline render of its clone passes the check (801 dossiers, 157 Stimmen in 87 Abstimmungen re-filed in the panels)
- compare_store_values review notes 1, 4, 5, 7, 8, 9 and the E4 per-(vote, group) comparison: v0.46.14.0, 2026-11-18, `scripts/compare_store_values.py`; items 2, 3, 6 and the ship review's 10 to 15 stay open in their entry. No stored figure moves; the report gains one-sided vote lines, a member-list line and a "vote groups" section.
- abgeordnetenwatch match-share script ("A3 item 1.5 review (2026-11-13)" items 9, 13, 14, 17, 18): v0.46.27.0, 2026-11-18 (`todo/aw-measure`). Offline request count, partial Mandat table, umask and answers-entry checks; item 18 was already done. No stored figure moved.
- abgeordnetenwatch client and match-share script ("A3 item 1.5 review (2026-11-13)" items 4, 5, 6, 8, 11; "what item 1.5 leaves open" item 4): v0.46.13.0, 2026-11-18. Dropped connections and timeouts are counted failures, a disabled resolver never asks, one 60 s wait per 429, unique temporary files, `name_fallback` saves in `finally`, malformed answers entries exit 2, and speakers are looked up by `derive.first_redner_id`. No stored figure moved (the reference store holds no abgeordnetenwatch data); the script's M5 drops the raw-value lookup
- Roster and replay-profile edges ("Shared Redner-IDs" items 6 and 17, registry fix review (f) and (h), A3 roster rule edge (a)): v0.46.12.0, 2026-11-18. On replay a profile found under a shared Redner-ID is taken from and copied to only its profile owner's occurrences (`registry.redner_id_profile_reaches`); `_read_roster_rows` keeps a superseded-DIP-id row only as an "MdB" roster row; `alias_superseded_dip_keys` aliases partitioned successor keys too; `land_office_wahlperioden` reads only lists of ints and cuts nothing otherwise. Offline replay of the 801-sitting store against main: no figure moved, `abgeordnete.json` identical; 0 of 1,949 cached DIP person records change their Land-office cut; all 91,658 speaker units in the 802 cached reports keep their profile. Left open: "Shared Redner-IDs" items 19 and 20
- Shared Redner-IDs: loader checks, role words, one record load ("Shared Redner-IDs: what the fix leaves open" items 6, 7, 9, 10, 14, 15 and 12 in part; "Registry fix review" item (e)): v0.46.10.0, 2026-11-18. `_load_corrections` refuses an own id named twice, a non-canonical `dip:` own id and a `dip:` own id for a profile owner; `_name_words` drops office words and strips `.,()`; `reconcile` loads the records twice, not three times; `dip_successors()` is a read-only map built once. No figure, person or page moved on the offline replay of the 801-sitting store against main, and the name check refused nothing. Left open: "Redner-ID name check: what the v0.46.10.0 ship review left open"
- "Vote direction: what the 2026-11-07 fix left open", items 11, 15 (in part), 17 and the `tally_of` half of 10: v0.46.9.0, 2026-11-18. `_read_contradicted_official_result` re-scopes an official "Antrag angenommen" only on an inversion from the chair (`bundestag-protocol`) or a DIP decision bound to the ballot (also when a title outranks DIP as the recorded source), never on one read from a title alone; a rival vote whose missing count could equal the tally blocks a tally-only bind; `dip_vote_decisions` skips a non-dict position or a non-list `beschlussfassung`, reads only ASCII digits and returns `DipDecision` NamedTuples; `tally_of` reads a missing count as unknown. No vote figure moved on the offline replay of the 801-sitting reference store against main (727 votes: inversions, outcomes, Abweichler identical; 990 stays `proposition`, `result_scope = application` stays 35)
- Stored Fraktion values that are not Fraktionen: v0.46.9.0, 2026-11-18. `derive.printed_fraktion` checks every `<fraktion>` the parser reads: 18/222's "CDU/CSU: Ich glaube, …" (C6) reads as CDU/CSU, 19/60's "Bremen" beside a Bundesrat member (E7) as no Fraktion, anything else unknown refuses the sitting (none of the 801 cached sittings does; "CDU/ CSU" and "BÜNDNIS90/DIE GRÜNEN", printed where no unit is read yet, are known spellings). Contributions naming CDU/CSU 5,713 → 5,714, Bundesrat Reden with no Fraktion 108 → 109, parties 11 → 9 on the offline replay against main; nothing else moved (the Redeanteil holds: the Rede already counted for the Bundesrat by its Sprechrolle). `speech_kinds._fraktion` (classification only, also reads the Rednerliste and Inhaltsverzeichnis, whose values include "zur Geschäftsordnung" and "CDU/ CSU") is unchanged, and `speech_kinds.VERSION` is not bumped: a store persisted before this keeps the two values until its next `--repersist`
- A repeated Inhaltsverzeichnis title loses the page of Reden, with "Reden outside a TOP" items 2, 4, 5 and 6: 2026-11-17, v0.46.8.0. `parse_toc` keeps every block, so the second of two same-titled blocks no longer hides the first one's pages; offline replay of the 801-sitting store: Reden without a page 1,643 (46 sittings) -> 416 (7), TOPs without a page range 1,810 -> 1,740 (with Reden: 106 -> 36), Beiträge without a page 19,792 -> 19,664, nothing else moved (18/44 `ID1804401300` now 3952 B)
- Check that the identity merge joins the MdBs WP 18/19 prints with an initial: 2026-11-17, read-only query on the reference store (801 sittings). All seven (W. Birkwald, G. Lämmel, G. Wöhrl, S. Neu, M. Huber, E. Fischer, A. Lamers) have their speaker `mps` rows (`xml_redner_id`, name "Vorname I. Nachname") and their roll-call `mps` rows (name "Nachname, Vorname I.") under ONE `person_id` each: `SELECT ... FROM mps m WHERE m.display_name GLOB '*[A-Z]. <Nachname>' OR display_name LIKE '<Nachname>, %'`, grouped by `person_id` with `COUNT(speeches.mp_id)` and `COUNT(vote_members.mp_id)`; Birkwald's four roll-call records, Fischer's, Huber's, Lamers's, Lämmel's, Neu's and Wöhrl's all join their speaker, so no count is halved. The roster-record split is separate and already tracked: Lamers's DIP roster record ("Prof. h.c. Dr. Karl A. Lamers, MdB") sits under its own `person_id` and Axel E. Fischer's roster record carries the Wahlkreis in brackets; see "Roster MdB records that never join their speaker" (P1).
- Store staging (batch 5) items 1, 2, 4, 5 and B4 item 9 (a refetched Vorgang keeps cached fields the answer lacks): 2026-11-17, `todo/staging-vorgang-cache`. The export work_dir goes through `ensure_private_dir`, which repairs 0o077; `_write_csv`'s fchmod sits inside its cleanup; tests for the cross-file-system refusal and a single-group chown variant. No figure moved
- E4 deferred item 2, first half (a Mandat day no record covers counted as proof of fraktionslos): 2026-11-17, branch `todo/derive-fraktionslos`. `_proved_group` proves nothing before an MdB's first Fraktion or Gruppe record of the Wahlperiode (`derive.first_record_days`, `Fraktionslos` records included; of two Mandate in one Wahlperiode the earlier record counts, a ship review find), so a Mandat entered before its Fraktion keeps the page's group. No figure moved: the guard bites on 0 of 2,815 MdB-Wahlperioden of the Stand 2026-04-29 file, and the post-T4 reference store's 157 Stimmen in 87 roll-calls (the E4 100 in 55 among them) are the same under the old and the new rule
- Fresh-store record and E8: four sentences that said something false: 2026-11-14, `docs/plans/release-readiness.md`, item 4. `docs/plans/a3-phase4.md` (by-member join, 996's box) and `docs/source-errors.md` E8 "Scale" (802 sittings of WP 18–21: 718 held, 84 excluded; the 799 annex blocks hold). No figure moved; item 4 was closed by #151
- The carried-forward registry diverges from a fresh build, with "Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs": v0.41.0.0, 2026-11-14, `docs/plans/registry-split-koestering-krampe.md`. The fresh store has no Bundesrat `ever_mdb` record; an offline replay keeps preserved roster rows live, and `dip_successors` joins Köstering/Krampe and Jan Wenzel Schmidt. Persons 1,952 (replay 1,956) → 1,946, Stimmen on pages 417,934 (replay 417,707) → 418,104; the gate checks the replay against its input store and against a fresh build that ingests the cached roster
- One Fraktion rule on both sides of the withheld share (PR 2 ship review P3, and Codex's Gruppe Die Linke reproduction): v0.39.0.0, #152, 2026-11-13. `_withheld_coverage` labels a withheld Rede with `derive.speech_zusammenschluss` by the Sitzung, as persist labels stored Reden; the reproduction moves from Die Linke 0 stored words, share 1.0 to Gruppe Die Linke 3 and 0.5.

- The E4 repersist owed since #138: closed 2026-11-12, replaced by the owner's fresh online build from 28799ac (`.context/dip-pulse-site`, 718 Sitzungen, gate `all_passed`). E4, #140 inversions, #141 and #143 match their records, except `result_scope` (34 against 24, "Vote direction: what the 2026-11-07 fix left open", item 18). `docs/plans/e4-repersist.md`, "Outcome"

- Tell official addresses and presidium Reden apart from Fraktionsreden (ADR 0004): v0.40.0.0, 2026-11-13, `docs/plans/adr-0004-presidium-kinds.md`. Ansprache kind, reviewed list of 136 units, oath answers and acceptances procedural: Reden 54,937 → 54,855 in 24 kept sittings. Speech rule 9, export format 18. Open: "ADR 0004 follow-ups".
- Reden the parser drops without refusing: v0.36.0.0, 2026-11-10, `docs/plans/reden-outside-tops.md`. 29 Reden of 18/49 and 18/44 under the item the Inhaltsverzeichnis names, 16 written submissions of 18/133 and 18/134. 21/43 `ID214301700` was never lost: a named rule. The 4 other annex units stay out by rule. Speech rule 7.
- Speaker ids the Bundestag gives to more than one person: v0.35.0.0, 2026-11-09, five ids, 43 units moved to the right person on the A3 store, old and new in `docs/plans/shared-redner-ids-old-new.tsv`; open: "Shared Redner-IDs: what the fix leaves open"
- Correct the WP 19/20 roll-call group misattributions (E4) from the MdB-Stammdaten: v0.34.0.0, 2026-11-06, 100 Stimmen in 55 roll-calls, `shift_between_groups` 55 → 0
- Unmatched roll-call votes never reach the report (`sitting_votes`): fixed by v0.22.0.0 (#109); checked 2026-11-05 on a clone of `~/agent-runs/a3/full` repersisted from main: 619 votes, 63 with no TOP, 41 dossiers with "TOP nicht zugeordnet"
- `documents.url` of BT-Drs. 19/19 is the Bundesrat PDF: closed 2026-11-05, no defect: BT 19/19 (`btd/19/000/1900019.pdf`) and BR 19/19 (`brd/2019/0019-19.pdf`) are two correct rows, 0 rows of either issuer carry the other chamber's url, and `docs/plans/a4-slice1-oracle/t11_measure.py` M2 keyed its lookup on the number alone
- "Validate a data correction" copies no private directory, so `after` loses the seat tables: v0.33.0.0, 2026-11-05
- Textanteil for the r2 Daten recipe, the rest of the ADR 0001 UI half: v0.33.0.0, 2026-11-05: `r2-textanteil-fraktion`, ordered by characters; export format 15; the published rows do not change
- Decide the frontend stack: no-go, the site stays Python-generated HTML; owner, 2026-11-04 ([criteria and measurements](docs/plans/frontend-go-no-go.md); revisit when a real chart cannot reasonably be hand-drawn)
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
