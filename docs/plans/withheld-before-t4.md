# Withheld Reden before T4: facts, the release list, and the guards

**Status:** plan, 2026-11-14. The owner accepted all four decisions on 2026-11-14 (see "Decisions for the owner"). PR A and PR B are being built.
**Parent:** `TODOS.md` "Coverage gate before the first data release", block "Found by PR 2's ship review (2026-11-13)", and item 8 of the same entry (eng review D6).
**Base:** main 0e6def4 (v0.41.0.0): store schema 12 (`persist_dip_pulse_store.py:37`), export format 18 (`build_dip_pulse_site.py:3441`), speech rule 9. Line numbers below are on that commit.
**Out of scope:** two parallel sessions are working on vote links (`match_roll_call_votes`, the vote outcome in `derive.py`) and on release docs (`SECURITY.md`, `CITATION.cff`, the DATA.md Vergleich, `docs/agents/review-checklist.md`). This plan touches none of those files.

## Why now

T4 acquires the 85 excluded sittings online. Once it runs, withheld Reden are stored for the first time: 90 Reden in 71 sittings on W1's XML (`docs/plans/withholding-preflight/report.md`), plus 21/106's one Rede. Every finding below is latent today and becomes reachable at T4, or at the first release after it.

**The reference store today** (`.context/dip-pulse-site`, read-only queries, 2026-11-14):

| Measure | Value |
|---|---|
| Protocols | 718 |
| `withheld_units` rows | 0 |
| Reports that carry `validation_summary.withheld_rede_count` | 718 of 718 |
| Reports that carry `protocol.reviewed_digest` | 718 of 718 |
| `dokumentnummer` equal to the XML header's `wahlperiode/sitzung-nr` | 718 of 718 |
| `coverage-exclusions.json` reasons | 83 `awaiting_acquisition`, 2 `awaiting_rule` (18/62, 18/90), 1 `source_defect` (18/20) |

So no figure of today's store moves except one stored field: `facts.metric_version` for `erste-reden` rows (see PR A). The replay of each PR proves that. The figures these fixes protect move at T4, and T4 measures them.

**What P1 holds at T4.** The 71 sittings fall in 61 ISO weeks and 50 calendar months, counted from the report's per-sitting table. Today those periods are incomplete for every domain because the sittings are `not_persisted`. After T4 without P1, their speech facts would flip to published, on partial data and with no gap note. With P1 they stay `unvollständig erfasst` for speeches, now with a note naming the withheld Reden. Their votes facts become publishable as their votes are acquired, which is the point of T4.

## Each finding against the current code

| # | Finding | Holds on 0e6def4? | Reached by | Where it goes |
|---|---|---|---|---|
| P1 | facts read a sitting with withheld Reden as complete | Yes. `facts.completeness_from_reports` (`facts.py:921`) sets `speeches` from `xml_speech_count` alone (`:940`). `erste-reden` (`facts.py:373`) ranks only `speeches` | T4 | **PR A** |
| P1, sibling | the backfill would re-acquire every sitting with withheld Reden, every run | New, found here. `incomplete_sitting_protocols` (`build_dip_pulse_site.py:597`) selects any sitting with a gap; `_structural_vote_gap` (`:567`) excludes only votes-only gaps | T4 plus P1 | **PR A** |
| P2 | the withheld cap trusts the manifest's own list | Yes. `release_changes.withheld_changes` (`release_changes.py:130`) reads a missing list as `[]`. `verify_export` (`publish_dip_pulse_data.py:132`) never reads the `withheld_units` CSV | first release after T4 | **PR B** |
| D6 | the release does not refuse `awaiting_*` exclusions | Yes. Nothing reads `coverage.excluded[].reason` outside the codebook and the Daten page | first release | **PR B** (recommended), see the D6 section |
| P3a | the stale-digest refusal names the wrong cause | Yes. `require_parsed_reports` (`build_dip_pulse_site.py:1990`) always says "predate the current speech-counting rule"; `warn_unparsed_reports` likewise | every edit of `reviewed_units.json` whose sitting has no cached XML; N8 adds such edits after T4 | **PR B** |
| P3b | a report without `reviewed_digest` is taken as current | Yes. `unparsed_reports` returns "fresh" (`build_dip_pulse_site.py:1981`). `persist_report` stamps the current digest (`persist_dip_pulse_store.py:1880`). The committed demo fixture `tests/fixtures/demo-report-21-84.json` lacks the key; `extract_demo_fixture.extract_report` (`:50`) never copies it | the demo fixture today; any hand-built report | **PR B** |
| P3c | a missing `scripts/reviewed_units.json` reads as empty | Yes. `reviewed_units.load` (`reviewed_units.py:85`) catches `FileNotFoundError` and returns `{"entries": []}` | a rename or delete; the list grows with N7 and N8 | **PR B** |
| P3d | the gate's "withheld also counted" misses nested Beiträge | Yes. `validate_store_gate.withheld_also_counted` (`:307`) compares `rede_id` only | the gate run of step 8, after T4 | **PR B** |
| P3e | pass-1 diagnostics of a withheld Rede stay in `xml_turn_diagnostics` | Yes, but the fix TODOS.md proposes is wrong; see below | nothing: no consumer reads them for a withheld Rede | **stays in TODOS.md**, fix text corrected |
| P3f | the reviewed digest is keyed by two spellings of the sitting | Yes. The parse keys by the XML's `wahlperiode/sitzung-nr` (`validate_dip_protocol.py:1669`). Persist and both checks key by `dokumentnummer`. The online `build_report` (`:4465`) never compares the two, though `--fetch-xml` (`build_dip_pulse_site.py:2107`) and the re-parse (`check_xml_belongs_to_report`, `validate_dip_protocol.py:3913`) do | T4's online acquisition (18/20's file holds sitting 21) | **PR B** |
| P1, new assumption | a withheld Rede with no Redner-ID cannot be tied to a person | New, found here. `withheld_units.xml_redner_id` is nullable | T4 | **PR B** (gate check) |

## PR split

**Two PRs, both before T4.** P1 alone is PR A, as the task suggests: it changes a published rule and an ADR, and its replay and its T4 rehearsal are its own work. PR B collects the rest. Every PR B item is a small guard (an estimated 250 to 350 changed lines with tests), and one ship run costs less than four.

- **PR A, facts on withheld Reden.** Files: `scripts/facts.py`, `scripts/build_dip_pulse_site.py` (only `_structural_vote_gap`, `incomplete_sitting_protocols`, `format_incomplete_report`), `docs/adr/0005-withhold-refused-reden.md`, `CONTEXT.md` ("Sitzung completeness"), `docs/data-methods.md` (the quoted definition), `TODOS.md`, plus tests in `tests/test_facts.py` and `tests/test_build_dip_pulse_site.py`.
- **PR B, the release list and the guards.** Files: `scripts/release_changes.py`, `scripts/publish_dip_pulse_data.py`, `scripts/build_dip_pulse_site.py` (only `unparsed_reports`, `require_parsed_reports`, `warn_unparsed_reports`), `scripts/reviewed_units.py`, `scripts/validate_dip_protocol.py` (only `build_report`), `scripts/validate_store_gate.py`, `scripts/extract_demo_fixture.py`, `tests/fixtures/demo-report-21-84.json`, ADR 0005 (the releases and bar sections), `TODOS.md`.

The two PRs share `build_dip_pulse_site.py`, ADR 0005 and TODOS.md, but in different functions and sections. They can be built in parallel in separate worktrees, with B rebased onto A. Land A first: B's ADR text refers to A's.

**Version numbers.** Neither PR changes a store table or an export column, so neither bumps schema 12 or export format 18. Before ship, check `SCHEMA_VERSION` and `EXPORT_FORMAT` on main again, because the parallel sessions may land first (memory: re-check format numbers before ship). PR A bumps `erste-reden` `version` 2 → 3 because its SQL changes. The speech rule stays 9: nothing the parser emits changes.

---

## PR A: facts treat a sitting with withheld Reden as partial

### A1. Completeness (`facts.completeness_from_reports`, `facts.py:921`)

Rule: a sitting's speeches are complete only when its XML was parsed **and** it withheld no Rede.

- `xml_speech_count` present and `withheld_rede_count == 0` → complete.
- `withheld_rede_count > 0` → not complete. The entry carries reason code `withheld_reden` and the count: `{"speeches": False, "withheld_reden": N, "reasons": {"speeches": "withheld_reden"}}`.
- `xml_speech_count` present but `withheld_rede_count` absent → not complete, reason "no withheld count (report predates it)". Unknown is incomplete, the same rule votes follow (class 5). No current report reaches this branch (718 of 718 carry the key), and `unparsed_reports` refuses a pre-rule-8 report before facts run anyway.
- A non-integer or negative count → not complete with the same "predates it" reason, never a crash. A report from the parser always holds an int, so this branch is defensive only.

Use a reason **code**, not German text, in the map. `period_gaps` (`facts.py:1011`) copies the count into the gap dict (`"withheld_reden": "N"`, since gap dicts hold strings). `incomplete_periods` and `sitting_gaps` pass it through unchanged.

### A2. The gap note (`facts.gap_note`, `facts.py:1133`)

A gap with reason `withheld_reden` reads "Sitzung 18/3: 2 Reden zurückgehalten", and with one Rede "Sitzung 18/26: 1 Rede zurückgehalten". Today any other reason falls through to `_GAP_DOMAIN_TEXT["speeches"]`, "Reden nicht erfasst", which would be false for a sitting whose other Reden are all stored. The card shows it as "unvollständig erfasst: Sitzung 18/3: 2 Reden zurückgehalten" (`build_dip_pulse_site.py:10477`).

### A3. The backfill does not chase withheld Reden (`build_dip_pulse_site.py:567`, `:597`, `:878`)

Without this, P1 makes every sitting with a withheld Rede "acquirable": `_structural_vote_gap` returns False for any gap that is not votes-only, so `incomplete_sitting_protocols` puts it in `acquirable`. Each backfill would then re-download about 72 sittings and leave them exactly as they were. Re-fetching never releases a withheld Rede; only a parser rule or a reviewed-list change does, through `--offline --repersist`.

- Rename `_structural_vote_gap` to `_structural_gap`. First drop a `speeches` reason of `withheld_reden`. If no reason is left, the gap is structural. Otherwise judge what is left with today's votes rule. So a sitting whose only gap is withheld Reden is never selected. One that also has an acquirable votes gap is still selected, for its votes.
- `format_incomplete_report`: a line "N sittings hold withheld Reden (ADR 0005): a parser rule or the reviewed list releases them, not a backfill (18/3, 18/6, …)". The partial-sitting counter keeps the code as its label, so "speeches: withheld_reden (72×)" does not split into one line per count.

### A4. `erste-reden` v3 (`facts.py:373`)

**Rule:** a person's debut is their first Rede in our coverage, stored **or withheld**. When it is a withheld one, the person has no debut row at all. Their real debut falls in a period that A1 already keeps incomplete, and every later Rede of theirs is, by definition, not a first one.

This is the TODOS.md fix "withhold erste-reden for anyone with a withheld Rede on or before their first stored one", made exact. "On or before" means before in the same order the metric already ranks by: sitting number read as WP/number, then `agenda_items.item_index`, then `sequence`. ADR 0005 D3 makes `withheld_units.sequence` and `speeches.sequence` the same source position within a TOP, so the two are comparable. A withheld Rede later on the same day, after the person's stored first Rede, leaves the debut standing.

SQL: extend the `speaker` CTE with a `UNION ALL` of the withheld units, flagged `withheld = 1` and `speech_id = NULL`. Join them `withheld_units → agenda_items` for `item_index` and `→ protocols` for the day and number. The person comes from `mps m ON m.xml_redner_id = w.xml_redner_id → mp_canonical`, the same person key the metric groups by. `first_day` and the `ROW_NUMBER` run over the union. The final `SELECT` keeps `rank = 1 AND withheld = 0`. The tie-break gets the withheld unit's id after `speech_id`, so the order stays total (class 3).

**Partitioned Redner-IDs.** `scripts/person_corrections.json` lists 7 Redner-IDs that are shared by more than one person and partitioned by printed label (`11005304`, `999990108`, `999990124`, `999990127`, `999990141`, `10000`, `999990134`). A withheld Rede with one of them is bound to **every** person who shares it. That can drop a real debutant from a count. It cannot post a false debut, and false debuts are the defect. Resolving the partition by `speaker_name` would reuse `person_registry`'s label logic inside facts SQL, which is too much machinery for at most a handful of cases. T4 measures how many withheld Reden carry a partitioned id: expected 0, because the 99999… ids are guests and government speakers.

**No Redner-ID.** A withheld Rede with NULL `xml_redner_id` binds no one. PR B adds a gate check that fails on any such row (B5), so the rule's one assumption is enforced where the owner reviews the store.

Bump `version` 2 → 3. Every `erste-reden` row's `facts.metric_version` moves 2 → 3. Its `value`, `withheld` and `rank` do not move on today's store, which has no withheld Reden.

### A5. ADR 0005 and the glossary

- **ADR 0005,** a new section "Facts" after "What stays the same": "A Sitzung with a withheld Rede is not complete for speeches. Every Fakt whose basis is speeches, in every week and month that holds it, reads *unvollständig erfasst* and names the Sitzung and the number of withheld Reden. *Erste Reden* counts a person's first Rede in our coverage, stored or withheld. When that first Rede is withheld, the person is not counted in any week. A withheld Rede binds every person who shares its Redner-ID. A backfill does not re-acquire a Sitzung for its withheld Reden." Add a bullet under Consequences: "erste-reden version 3".
- **`CONTEXT.md` "Sitzung completeness"** (`:333`): the speeches clause becomes "a parsed Plenarprotokoll report exists for it and it withheld no Rede (ADR 0005)". The "Completeness basis" entry (`:330`) gets the same words.
- **`docs/data-methods.md:37`** quotes "Period completeness", which refers to Sitzung completeness and does not change. Check it, and change it only if the quote names the speeches rule.

### A6. Tests first (`tests/test_facts.py`, `tests/test_build_dip_pulse_site.py`)

Write each test red first, with the repo's `# Value: protects=…; fails_when=…; why_new=…; seam=…` header.

1. `completeness_from_reports`: a report with `withheld_rede_count: 2` → `speeches` False, reason `withheld_reden`, count 2. With `0` → True. With the key absent and `xml_speech_count` present → False, "predates it". Extend `test_completeness_map_from_cached_reports` (`:1360`).
2. `gap_note`: "Sitzung 18/3: 2 Reden zurückgehalten" and the singular "1 Rede".
3. End to end through `compute`: a complete week whose one sitting withheld one Rede → every speeches metric of that week and its month is incomplete (`complete` 0) and posts nothing. The same week's votes metrics are unaffected.
4. `erste-reden`, using the existing seeding in `tests/_facts_fixture.py`, extended with one `withheld_units` row:
   - Person P has a withheld Rede in week 1 and a stored Rede in week 3 → P is in no week's debut count. Week 3's value drops by one against the same seed without the withheld row.
   - The withheld Rede comes later on the same day as P's stored first Rede (same sitting, higher `sequence`) → P still debuts in that week. This guards the "on or before" edge.
   - A withheld Rede of person Q, while P's debut stands → P is unaffected (no cross-binding).
   - A withheld Rede with a Redner-ID shared by P and Q → neither debuts after it.
5. Backfill (`incomplete_sitting_protocols`): a sitting whose only gap is `withheld_reden` lands in `structural`, not `acquirable`. A sitting with `withheld_reden` plus votes `partial (request_failed)` stays `acquirable`. `format_incomplete_report` prints the withheld line once, with the numbers.
6. The replay test that compares build and replay completeness (`completeness_from_entries` and `load_completeness`) needs no change: both call A1's function. Add one assertion that a report with withheld Reden gives the same map through both.

### A7. Proof on real data

1. **Replay** (README "Validate a data correction"): `cp -cR` the reference store, apply PR A to the copy, run `--offline` facts, then `scripts/compare_store_values.py`. Expected: 0 moved values, except `facts.metric_version` of the `erste-reden` rows (2 → 3). Report it exactly.
2. **T4 rehearsal in a scratch copy**, the one check that shows P1 doing its job before T4. Pick a WP 21 member whose first stored Rede is in the store, and in a scratch worktree add a temporary `withhold` entry for that Rede to `reviewed_units.json`. Run `--offline --repersist` on the copy, then facts. Expected: that week and its month read "unvollständig erfasst: Sitzung 21/N: 1 Rede zurückgehalten" for speeches. The member is in no later `erste-reden` count. The backfill dry run does not select 21/N. Record the old and new values of the facts that moved. Then delete the scratch entry; it must never reach a commit.
3. **Browser:** open that week's page from the rehearsal at 375px and in dark mode, and read the gap note.

### A8. Outcome (built 2026-11-14)

**Built as planned, with one change to A3.** `incomplete_sitting_protocols` returns a fifth list, the sittings held back only by withheld Reden, so `main`'s `[backfill]` line names them on their own instead of calling them roll-call gaps. A sitting with withheld Reden and a votes gap is still acquired for its votes; with votes off it counts as votes-only.

**Replay (A7.1)** of `.context/dip-pulse-site`: `--offline` on main 0e6def4 into one clone, on PR A into another, then `compare_store_values.py` and a direct diff of `facts`, `fact_sources` and `fact_metrics`. Every table count, every value and every Fakt is equal. The only moves: `facts.metric_version` of the 273 `erste-reden` rows, 2 → 3, and that metric's `fact_metrics` row (version 2 → 3, its SQL and hash). The main build on its clone changed no fact against the reference store either.

**Loop cost (class 12):** the `erste-reden` SQL takes 0.24 s as v2 and 0.17 s as v3 on the full store (best of 3, under load), with identical rows.

**T4 rehearsal (A7.2)**, in a scratch copy of the tree and a third clone of the store: a temporary `withhold` entry for Caroline Bosbach's (CDU/CSU) first Rede, 21/20 `ID212014300` (2025-09-10, 2025-W37; her next Rede is 21/34, 2025-W42), then `--offline --repersist`. Speeches 54,855 → 54,854, `withheld_units` 0 → 1.
- 2025-W37 and 2025-09 turn incomplete for every speeches Fakt, with the note "Sitzung 21/20: 1 Rede zurückgehalten". Votes Fakten of the week stay complete. Published before, now *unvollständig erfasst*: `erste-reden` 2025-W37 (9), `aktivste-abgeordnete` 2025-09 (10), `meistdiskutierter-vorgang` 2025-09 (203).
- `erste-reden` 2025-W42: v2 on the same store gives 2 debutants, Bosbach among them, which would be false. v3 gives 1. Bosbach is in no week's count.
- `compare_store_values.py` against the PR A replay: the only stored change is that Rede (21/20 characters 172,272 → 166,555, CDU/CSU Reden 14,996 → 14,995). 117 of 1,922 Fakt values move, all percentiles and baselines of later periods except the six of W37 and 2025-09; publishable weeks 181 → 180, months 58 → 57.
- The week leaves every later baseline, so later percentiles move: `erste-reden` 2025-W38 now publishes (9 debutants), while `laengste-sitzung` 2025-W38, `laengste-debatte` and `laengste-rede` 2025-W45 and `laengste-debatte` 2026-W10 fall below the floor. This is the existing rule for an incomplete week.
- Incomplete periods 102 weeks / 73 months → 103 / 74. The build's report prints "1 sittings hold withheld Reden (ADR 0005): … (21/20)" and its fix still acquires 83 sittings, so 21/20 is not selected.
- The scratch entry lived only in the scratch tree; `scripts/reviewed_units.json` is unchanged.

**Browser (A7.3):** the rehearsal's `fakt/2025-W37.html` in gstack's headless browser at 375 × 812 with `data-theme="dark"`: no console error, no horizontal scroll (scroll width 375), and the four speeches metrics read "unvollständig erfasst: Sitzung 21/20: 1 Rede zurückgehalten", wrapped on two lines. The two votes metrics keep their own reasons.

---

## PR B: the release list, D6 and the guards

### B1. P2: the release reconciles `withheld_reden` with the export

**`release_changes.withheld_changes`** (`release_changes.py:130`):
- The current manifest must carry `withheld_reden` as a list, which may be empty. Absent, `null` or not a list → `ChangesError`. Each entry must be an object with non-blank string `document_number`, `rede_id` and `reason`. A duplicate key (`_withheld_key`) is refused.
- The previous manifest: with `export_format >= 17`, the same requirements. Below 17, an absent list means none. A previous `export_format` that is not an int is refused in `publish_dip_pulse_data.previous_manifest_problem` (class 9: today it only checks the field is present).

**Reconciliation**, a new `withheld_export_problem(manifest, generation_dir)` in `publish_dip_pulse_data.py`, called in `run_release` right after `verify_export` (`:250`) and before `build_release_directory`, so a refusal leaves nothing on disk (class 10):
- Find the one `withheld_units-*.csv.gz` and the one `protocols-*.csv.gz` among `manifest["files"]` (kind `table_csv`). Both are already hash-checked by `verify_export`. A missing one is refused: format 18 always exports the table.
- Map `protocols.id → document_number`. Build `{(document_number, rede_id): reason}` from the withheld CSV and compare it with the manifest list as sets. Name every row that is only in the export, only in the manifest, or has a different reason.
- Key both sides with `release_changes._withheld_key`, so there is one key function (class 4).

The cap and the changelog then read a list that matches the rows a reader downloads. The sqlite file of the same generation comes from the same snapshot (`build_dip_pulse_site.py:4914`), so checking the CSV is enough.

**Tests first:**
1. `test_release_changes.py`: a current manifest without the list, with `null`, or with a non-object entry → `ChangesError`. A previous format-17 manifest without the list → refused. A previous format-16 manifest without it → no Reden released.
2. `test_publish_dip_pulse_data.py`: a manifest list missing an exported row, with an extra row, or with a changed reason → refused, naming the row. A manifest list with all rows removed (the Codex repro) → refused.
3. Update `test_a_release_with_too_many_new_withheld_reden_needs_each_confirmed` (`:560`): today it edits only the manifest (`edit_manifest`, `:122`). After B1 that is refused by reconciliation. The fixture must export three real withheld rows, from a report whose agenda item carries `xml_withheld`, so the test still proves the cap.

### B2. D6: refuse `--publish` while an exclusion awaits

**The case for enforcing now:**
- It is about 15 lines and one test in the one place that publishes: `run_release` before it builds anything.
- Nothing is published, so it blocks nothing that exists. Dry runs stay allowed, so T4 can rehearse releases.
- Item 8's rule is easy to forget at exactly the moment it matters: the first release after T4 is when the last `awaiting_*` code has to go. A refusal written now cannot be forgotten then.
- The bar is a written rule (ADR 0005, "Coverage and the bar"). Every other written rule of the release is enforced by code.

**The case for waiting until after T4:**
- Today all 85 exclusions await, so the check refuses every `--publish` until T4 is done and 18/62 and 18/90 are reclassified.
- The fallback in TODOS.md ("release WP 20 and 21 first as a complete set") would hit this refusal. The exporter writes the whole store's exclusion record, WP 18 and 19 included, so that fallback would need an override flag or an export scoped to its Wahlperioden.

**Recommendation: enforce now, in the release script, not in the gate.** The gate judges a store build. T4's own builds must pass it while 18/62 and 18/90 still read `awaiting_rule`, so a gate refusal would block the work that removes the codes. The fallback is not chosen, and if it ever is, it changes the export's scope anyway and can carry its own rule then. No override flag now.

**Design.** `build_dip_pulse_site.py` gets `FINAL_EXCLUSION_REASONS = ("source_defect", "not_narrowable")`, an allow-list beside `EXCLUSION_REASONS` (`:669`), so a code added later is refused until someone adds it on purpose. `run_release`: when `args.publish` is set and any `manifest["coverage"]["excluded"]` row has a reason outside that set, raise `ReleaseError` with the count, the first 12 numbers and the bar. A missing or malformed `coverage.excluded` is refused as well. A dry run prints "--publish would refuse: 85 exclusions still await acquisition or a rule (ADR 0005)". ADR 0005 "Coverage and the bar" gets "The release refuses `--publish` while any exclusion reads `awaiting_rule` or `awaiting_acquisition`."

**Tests first:** `--publish` with one `awaiting_acquisition` row → refused, naming it. With only `source_defect` and `not_narrowable` → passes this check. A dry run with awaiting rows → succeeds and prints the line. The initial release (`--initial`) is refused too: the bar has no first-release exemption.

### B3. P3a and P3b: stale reports name their cause, and an absent digest is stale

`build_dip_pulse_site.py:1973-2030`:
- Replace the boolean `stale()` with `stale_cause(report) -> "rule" | "reviewed" | None`. "rule" means `speech_kinds_version` differs. "reviewed" means the digest differs **or is absent** (P3b).
- `require_parsed_reports` and `warn_unparsed_reports` print one clause per cause that occurs: "N cached reports predate speech rule 9 (…)" and "M were parsed under other entries of scripts/reviewed_units.json than it holds now (…)". The fix line stays the same; it is right for both.
- `extract_demo_fixture.extract_report` (`:128`) copies `parsed["reviewed_digest"]` into `protocol`. Regenerate the committed fixture from the reference store's `data/xml/plenarprotokoll-21-84.xml` with `scripts/extract_demo_fixture.py`, then diff it: the only change should be the new key. Pin it with a test: the fixture's digest equals `reviewed_units.sitting_digest("21/84")`. That test fails if the fixture and the list drift apart.
- `persist_report`'s fallback (`persist_dip_pulse_store.py:1880`) stays. Every build path reaches persist only through `unparsed_reports` or a fresh parse: online, `--offline --repersist` (re-parse first), and `--persist-only` in the gate's replay. The implementer confirms each caller in the PR (class 1). Making persist refuse would touch about 20 test files that persist hand-built reports, for no reachable input.

**Tests first:** a report with no digest → `unparsed_reports` returns it with cause "reviewed". The refusal text for a digest-only stale report names the reviewed list and not the rule. A report stale for both causes names both. The demo fixture pin.

### B4. P3c: refuse a missing `reviewed_units.json`

`reviewed_units.load` (`:85`): `FileNotFoundError` → `ReviewedUnitsError("scripts/reviewed_units.json is missing; it is checked in, restore it (git checkout -- scripts/reviewed_units.json)")`. Every entry point already turns `ReviewedUnitsError` into a clear stop (`build_dip_pulse_site.py:14560`, `validate_dip_protocol.py:4643`, `extract_demo_fixture.py:172`). Grep the tests for `load(` with a temporary path that does not exist; any such test changes to an explicit empty file.

**Test first:** `load(tmp / "absent.json")` raises `ReviewedUnitsError`. An empty `{"entries": []}` file still loads.

### B5. P3d and the Redner-ID assumption: two store-gate checks (`validate_store_gate.py`)

- `withheld_also_counted` (`:307`) gains `OR EXISTS (SELECT 1 FROM contributions c WHERE c.protocol_id = w.protocol_id AND c.parent_rede_id = w.rede_id)`. Under D4 the outer Rede of a withheld split part `ID…:n` stays stored, so a Beitrag whose parent is the outer `ID…` is legitimate and must not be flagged. Before writing the SQL, the implementer checks what `parent_rede_id` holds for a nested unit inside a split part (`validate_dip_protocol.py:1394`, `:1952`). The 18/10 case `ID1801002600:2` under `check_withhold_one.py` shows it.
- New check `withheld_without_redner_id`: `SELECT COUNT(*) FROM withheld_units WHERE xml_redner_id IS NULL OR xml_redner_id = ''` must be 0. It goes into `checks` beside `no_withheld_rede_counted` (`:530`). It enforces A4's assumption. If T4 ever trips it, the owner looks at that Rede before the gate passes.

**Tests first**, extending `test_flags_a_withheld_rede_that_is_also_counted` (`:341`): a counted `nested:R2:2` with `parent_rede_id = 'R2'` and R2 withheld → flagged. A nested Beitrag of another Rede → not flagged. A Beitrag under the outer `R2` while only `R2:2` is withheld → not flagged. A withheld row with NULL Redner-ID → the new check fails.

### B6. P3f: one sitting key, by refusing a mismatch online

The online `build_report` is the only path that parses without comparing the XML's sitting to `dokumentnummer`. Add the comparison there, with the message `check_xml_belongs_to_report` uses ("it is the XML of 18/21, not of 18/20"), raised as a `DipError` with `source_rejected=True`. After the parse, before enrichment, so no DIP request is spent on the wrong file. Then every report that reaches persist has equal spellings: the parse's key and the checks' key are the same string, with no separate normalizer to keep in step. A padded `dokumentnummer` is refused on fetch, as `--fetch-xml` and the re-parse already refuse it, instead of reading as stale on every run.

This is also the check T4 needs most from PR B: 18/20's file holds sitting 21. Acquired by mistake, it would today be stored as 18/20 with 18/21's Reden.

**Test first:** `build_report` with stubbed fetches, whose XML says 18/21 for protocol 18/20 → `DipError`, `source_rejected`, no enrichment call.

### B7. P3e stays in TODOS.md, with its fix text corrected

The finding holds: `merged_rede`, `merged_erwiderung` and procedural diagnostics that target a withheld Rede stay in `xml_turn_diagnostics` and in the report JSON (`validate_dip_protocol.py:3844`). But "drop them with the Rede" contradicts ADR 0005 D7. The diagnostics are where "partly merged into X, rest withheld" is recorded. The only renderer reader, `reviewed_procedural` (`render_dip_pulse_html.py:1949`), looks for `(reviewed)` presidium evidence, and a withheld Rede cannot carry that: the list allows one entry per (sitting, rede_id). PR B rewrites the TODOS.md item to read: "keep them (D7); mark them `withheld` if they ever reach the store or a page."

### B8. Outcome (built 2026-11-14)

**Built as planned, with three additions found while building:**
- B3's sibling: `build_demo_site.persisted_store` refused every stale fixture as "made under speech rule …". It now names the cause `stale_causes` gives, so a digest-only drift does not blame the rule.
- B6: `--fetch-xml` compared the header on its own. It now uses the same `xml_sitting_mismatch` as the online parse and the re-parse, so one function decides (class 4). Its message for another sitting reads "it is the XML of 21/7, not of 21/6".
- B1: `assemble` validates both withheld lists before it compares the manifests, so a bad list is refused first, not reported as a schema change.

**Test fixtures.** P3b makes a hand-built report without `reviewed_digest` stale. About 15 test helpers built such reports; they now stamp the digest through `_support.stamp_reviewed` (or `_support.shipped_digest` where the CLI runs in a subprocess and reads the shipped list). The demo fixture was regenerated from the reference store's `data/xml/plenarprotokoll-21-84.xml`; its only change is the new key.

**Replay.** `--offline --repersist` with PR B on a fresh clone of `.context/dip-pulse-site` (403 s), compared with PR A's replay by `compare_store_values.py` and the facts diff: every table count and value equal, 0 of 1,922 Fakt values moved, no stale-report warning. PR B changes no figure.

**Real data.** On the reference store, 718 of 718 cached reports have no stale cause under the new rule, and 718 of 718 cached XML headers match their `dokumentnummer`. The D6 check on the replay's real manifest finds the 85 awaiting exclusions (83 `awaiting_acquisition`, 2 `awaiting_rule`), so `--publish` refuses as decided. The reconciliation passes on both real exports (0 rows on the replay, 1 on the rehearsal) and, with the list emptied, names the rehearsal's row: "only in the export: 21/20 ID212014300".

---

## The review checklist applied to this plan

Classes answered per PR. "–" means the PR does not touch it.

| Class | PR A | PR B |
|---|---|---|
| 1 Sibling path | Every completeness reader calls `completeness_from_reports`: the build (`:1914`), offline facts (`:14424`), the site's gap notes (`:10958`), the backfill (`:614`), the facts CLI replay (`facts.py:2834`). The backfill is the sibling that needs its own change (A3). No other code computes a debut (grep `first_speech\|debut` outside `facts.py`: none) | B6 is this class: the online parse lacked the sitting check that `--fetch-xml` and the re-parse have. B3 lists persist's callers. B2 has one publishing entry point, `run_release` |
| 2 Stale beats fresh | Completeness is read from the report a re-parse rewrites, never carried forward | Previous manifest list against current: B1 requires both where they must exist |
| 3 Order and history | A4's ranking gets a total tie-break (unit id after speech id); facts are recomputed every build | – |
| 4 One key, one function | The person key is `mp_canonical`, as v2 already uses | `_withheld_key` for the manifest and the CSV; the sitting key unified by B6 |
| 5 Absent vs zero | An absent `withheld_rede_count` is unknown, so incomplete. NULL Redner-ID is handled by B5's check | An absent list: refused (current, previous ≥ 17), none (previous < 17). An absent digest: stale |
| 6 Derived columns | `facts.complete`, `withheld`, `rank`, `metric_version` are all recomputed each build; the replay (A7) proves only `metric_version` moves | – |
| 7 Neighbour binding | Withheld Rede to person by exact Redner-ID; partitioned ids bind all sharers. Measure at T4 | – |
| 8 Hostile text | No new scanner. A3 reads a reason code, not text | – |
| 9 Input shape | – | Manifest list: null, non-list, non-object, blank fields, duplicates. A previous `export_format` that is not an int. A missing `coverage.excluded`. A missing list file |
| 10 Interrupted run | No new writes | Every refusal comes before `build_release_directory` |
| 11 Claims | ADR 0005 "Facts", CONTEXT.md, the gap-note copy; each cites A1 to A4's lines in the PR body | ADR 0005 releases and bar sections; the refusal texts |
| 12 Loop cost | A4 adds a `UNION ALL` over `withheld_units`, about 91 rows after T4, against 54,855 speeches. Time the metric before and after on the reference store | Reconciliation reads two CSVs of about 800 and 91 rows |
| 13 Last commit | At ship | At ship |

**Checks no diff review replaces:** the figures replay (A7.1; for PR B a replay that shows 0 moves, because B changes no figure), the T4 rehearsal (A7.2), the browser check (A7.3; PR B has no page change), the suite on `uv run --python 3.13.12 python -m unittest discover -s tests` for both, and red team plus Codex on the tip handed to ship if a diff reaches 200 changed lines.

## TODOS.md after both PRs

- P1, P2, P3a, P3b, P3c, P3d and P3f are marked done, with the PR.
- Item 8's sentence "Enforce that in the release (or the gate) when T4 has run" becomes "Enforced by PR B in `publish_dip_pulse_data.run_release`."
- P3e is rewritten as in B7.
- T4's measurement list (item 7) gains two lines: how many withheld Reden carry a partitioned Redner-ID (A4), and confirmation that `withheld_without_redner_id` is 0.

## Decisions for the owner

**Decided 2026-11-14:** the owner accepted all four recommendations below as written. D6 is enforced now, in the release's `--publish` only, with no override flag. A person whose first Rede is withheld is dropped from every week's debut count. A withheld Rede with a shared Redner-ID binds every person who shares it. Two PRs, A (P1) then B (P2, D6, the P3 guards); P3e stays in TODOS.md with its fix text corrected.


1. **D6, when to enforce the bar.** Recommended: now, in the release's `--publish` only, with no override flag. Every `--publish` is refused until T4 is done and 18/62 and 18/90 are reclassified, and the WP 20/21-first fallback would need its own rule if it is ever chosen. The alternative is to write the check after T4.
2. **`erste-reden` for a person whose first Rede is withheld.** Recommended: drop that person from every week's debut count, since the period of the real debut is already incomplete. The alternative is to withhold the whole `erste-reden` fact of every week in which such a person's first stored Rede falls. That costs a whole card for one uncertain row.
3. **A withheld Rede with a shared Redner-ID.** Recommended: bind it to every person who shares the id. This may drop a real debutant and never posts a false one. Expected to affect 0 Reden; T4 measures it.
4. **Split.** Recommended: two PRs, A (P1) then B (P2, D6, the P3 guards), both before T4. P3e stays in TODOS.md with its fix corrected, because dropping the diagnostics would break ADR 0005 D7.
