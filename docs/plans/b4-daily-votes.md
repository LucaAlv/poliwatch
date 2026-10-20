# B4: Abstimmungen for the daily view (what was decided, by topic, with dissenters)

## Context

Roadmap item B4 (TODOS.md "Abstimmungen for the daily view…"). We want a vote found on `votes/index.html` by topic to answer, on its panel and without leaving the page: what was decided, who voted how, who broke ranks, which committee was responsible, and where the source is. Status of the TODO's four parts:
- Part 2 (topic filter) is done in B3 (v0.20.0.0).
- Parts 1 (description from DIP), 3 (named Abweichler) and 4 (responsible committee) are still open.

**Status (2026-10-19):** this plan passed /plan-eng-review. It replaces the 2026-10-07 snapshot that was in this file before B3 merged. Decisions D1–D17 in the decision ledger below are settled; do not reopen them without new evidence. Implementers should start at "Implementation Tasks".

This plan is based on current main (cfcd249) and settles the open choices with measurements from the reference store (`/Users/Luca/Projects/poliwatch/.context/dip-pulse-site/data`, 217 votes):

| Measurement | Result |
| --- | --- |
| Committee: votes that join to a `documents` row of type `Beschlussempfehlung%` with an Ausschuss in `origin_json` (= DIP `urheber`) | **190 / 217** |
| Vote→Vorgang paths: narrow-tier cache resolution (`politikfelder._vorgaenge_of_numbers`) vs `linked_drucksachen[].vorgang_id` | Agree on 176, differ on 36, cache-only on 5 |
| Votes resolving to more than one Vorgang | 42 via the cache path, 64 via `linked_drucksachen` |
| Votes with an abstract on the narrow cache path | **153 / 217** |

`linked_drucksachen` is the noisier path, and it is missing for sitting-level votes. We therefore use the narrow cache path, the same one B3's tags use, so a vote's abstract and its tags come from the same Vorgänge.

**User decision:** the labelled AI fallback for votes without an abstract is **deferred**. Those votes say "Keine Beschreibung in DIP", and B4's TODO stays open for that one part, behind "Deterministic validators".

## Step 0: refresh the repo plan doc (done: this file)
This file was updated in place:
- B3 is merged.
- State the measurements above.
- The committee line cites the Beschlussempfehlung's issuing committee; drop the mitberatend promise (see Slice 3, D14).
- The AI fallback is deferred.

## Slice 1: named Abweichler on the vote panel (no schema change)

**Predicate.** Add `derive.vote_abweichler(vote) -> dict[zusammenschluss, {"members": [...], "state": "complete"|"partial"|"none"}]` in `scripts/derive.py`.
- Build on `merge_fractions`, `zusammenschluss` and `majority_vote`.
- Take the Mehrheitsvotum from the reported fraction counts, never from a member list.
- A member qualifies only on Ja against a Nein majority, or Nein against a Ja majority.
- Exclude fraktionslos, unknown affiliation, Enthaltung, nicht abgegeben, ties, Enthaltung majorities, and groups with nobody voting.
- **Partial** means the group's member rows (counted by Stimme) don't match its fraction counts. **None** means there are no member rows at all.

**Render.** Change `render_vote_summary` in `scripts/features/votes.py` (tally rows at :133-156):
- Under each qualifying group's tally row, add a compact line with the heading "Anders als die Mehrheit der eigenen Fraktion oder Gruppe" (wording from CONTEXT.md; no Avoid-list terms).
- Show up to 10 names inline (alphabetical). If there are more, a native `<details><summary>alle N anzeigen</summary>` holds the rest (D6; the 2023 Suizidhilfe vote has 62 SPD Abweichler).
- Link names through the existing `derive.vote_member_key` → `html.mp_page_href` → `source_url` fallback (:166-175). Factor that into a helper shared with the Einzelstimmen list.
- Keep three states visibly apart:
  - The group has dissenters: list them.
  - The group has none: show nothing per group, and one "keine Abweichler" line for the vote when every group is complete.
  - Members are missing or partial: "Einzelstimmen unvollständig – Abweichler nicht ermittelbar". This never reads as zero.
- Inversion does not change who dissents, so the predicate has no second inversion.

**Archive.** Add `data-abweichler="N"` and a small "N Abweichler" badge to archive rows in `collect_votes_archive` / `render_votes_archive_index` (`scripts/build_dip_pulse_site.py:4270`, :4329). Show the badge only when the count is complete.

**Tests**, extending `tests/test_features_votes.py`:
- Opposite Ja/Nein.
- Tie, Enthaltung majority, no voters.
- fraktionslos and unknown group.
- Group spelling variants.
- Partial and missing members (fixture `roll_call_1002.json`).
- Profile-link fallback.
- Inverted vote.

**Parity test.** Add one to `tests/test_mehrheitsvotum.py`: the Python (vote, member) set equals a per-vote SQL written in the test with the r3 predicate (`vm.vote IN ('yes','no') AND vf.leading_vote IN ('yes','no') AND vm.vote <> vf.leading_vote AND p.name <> 'fraktionslos'`), on the existing temp-store fixture. `r3-abweichler` itself returns per-MP counts, not pairs (C1). Per-group parity holds only where member counts match fraction counts; the store has 21/1498 groups that don't (see TODOs).

## Slice 2: what the vote is about (DIP abstract)

**Cache first (O9; do this before the schema work).**
- `validate_dip_protocol.vorgang_cache_record` also keeps `titel` (D12).
- `politikfelder.fetch_targets` also wants the narrow-tier Vorgang ids of votes whose record has an empty `abstract` (D11) or lacks the `titel` key (D12). That is ≤ ~100 ids per build once titles are filled, plus about 3 one-time batches [estimated].
- Tests in test_politikfelder.py. After the first online build, report how many of the 64 no-abstract votes gained one (old/new).

**Resolution.** Add `politikfelder.vote_vorgang_ids(vote, cache, *, wahlperiode, linked_vorgang_ids)`.
- Return the narrow tier (`NARROW_NUMBER_FANOUT`) only, narrowed to the TOP's Vorgänge when they intersect. Build it on `_vorgaenge_of_numbers(..., narrow_first=True)`.
- Leave `tags_for_vote` unchanged (D8). Tags may come from the wide tier and context never does, so the two can differ by design. A parity test pins that votes tagged from the narrow tier get the same Vorgänge.
- Never use the wide tier for prose.
- Write the sanitizer with stdlib `html.parser.HTMLParser`, not regex (F7).

**Sanitiser.** Add `politikfelder.abstract_text(raw)` (or a small helper beside it):
- Turn `<br>` into paragraph breaks, strip all other tags, unescape entities, and normalise CRLF and whitespace.
- The caller escapes the result.
- It is a pure function and gets its own tests, including `<strong>` and nested markup.

**Store.**
- `persist_dip_pulse_store.py`: add `proceedings.abstract TEXT` (sanitised; the raw text stays in the cache).
- Add a new junction `vote_proceedings(vote_id, proceeding_id, rank)` holding the resolution above, so the selection can be reproduced from the release.
- Upsert proceedings for vote-only Vorgänge too.
- Add `votes.context_state` in {`resolved`, `none`, `not_fetched`} from the same `vote_vorgang_ids` result, so the export can tell "no Vorgang" from "not fetched", as `vote_politikfelder.source` does (D7).
- Thread `vorgang_cache` into both `dossier_sections` ctx dicts (render_dip_pulse_html.py:3026, :3109). `render_html` already has it (:2921).
- Bump `SCHEMA_VERSION` 5→6. `require_current_schema` already prints the `--offline --repersist` instruction. Add no shim.

**One derivation.**
- Persist and render both call `vote_vorgang_ids` with the same cache snapshot that build loaded.
- The panel takes its context from the same per-vote result the persist writes. A helper in `scripts/features/votes.py` builds `vote_context(vote, report, cache)` once per vote in `iter_report_votes` order. Its linked Vorgang ids are the union over every TOP the vote sits under, the same union `report_politikfelder` builds (politikfelder.py:533-541), so both copies of a multi-TOP vote and `vote_proceedings` agree (D13).
- Fill `proceedings.title` for vote-only Vorgänge from the cached `titel` (D12).
- This does **not** close B3 deferred item 3. Render reads the cache and the export reads the store, so abstracts and `vote_proceedings` share the known drift after a cache refresh without repersist. Extend that TODO to name them (D5).

**Render.**
- Add a block "Worum es geht · Quelle: Deutscher Bundestag/Bundesrat – DIP" above the tallies, clearly separate from the outcome badge. The outcome reading (with inversion) stays in the badge, and the abstract describes the Vorhaben, not the vote's result. This separation is how the TODO's inversion warning is honoured.
- Show the first paragraph inline, or about 300 characters cut at a sentence. The full text goes behind `<details>`.
- Label each block "<titel> · DIP", linked to the DIP Vorgang (D12). With several Vorgänge, each gets its own block.
- Missing or not fetched: "Keine Beschreibung in DIP" or "Vorgang nicht abgerufen". These are two different strings.

**Export.**
- Bump `EXPORT_FORMAT` 5→6 (`build_dip_pulse_site.py:2485`).
- Add `proceedings.abstract` (layer `dip`) and the `vote_proceedings` CSV (layer `derived`).
- Give both a caption (:153) and a provenance tag (`_TABLE_SOURCE_DERIVED` / `_COLUMN_SOURCE_DERIVED`, :2445-2480).
- `docs/data-license.md`: add "HTML stripped, whitespace normalised" to the "What we changed (DIP no. 4b)" list.

**Cache location** (TODOS:890 item 4).
- The "drop abstract until a feature reads it" option is now gone.
- B4 does not move the cache. Rewrite that sub-item to say the cache holds abstracts a feature uses, and that hosting must exclude `data/dip-vorgang-cache.json` or move it.

**Tests:**
- Sanitiser.
- Single, multiple and absent Vorgang.
- not_fetched.
- Bundled TOP with two votes on different Vorgänge.
- A sitting-level vote (`item is None`).
- Fresh-store migration plus the old-schema refusal.
- Export round trip (format 6 columns).
- `tags_for_vote` behaviour unchanged (existing `tests/test_politikfelder.py` must pass untouched).

## Slice 3: responsible committee

**Detector.** Add `derive.vote_committees(vote, report)` in `scripts/derive.py` (D3).
- Build one number→document map from every `agenda_items[].api.linked_drucksachen` of the report. This is sitting-wide, because in 5 of 217 votes the Beschlussempfehlung is linked under another TOP.
- Match the vote's `document_numbers` against that map, keeping entries whose `drucksachetyp` starts with "Beschlussempfehlung". Return their distinct `urheber` strings plus the source Drucksache.
- This is a new structured detector. It does not reuse `recommendation_inversion`'s title regex.
- No store read at render. Sitting-level votes use the same map.
- Expected: 190/217 on the reference store, equal to the store SQL.

**Scope cut.** Cite the Beschlussempfehlung's issuing committee only.
- The Beschlussempfehlung's `urheber` is the issuing committee.
- Mitberatende committees exist only in `ueberweisung` on the 1. Beratung positions, which `compact_position` drops. Note this in the doc.

**Render.**
- "Beschlussempfehlung des <Ausschuss> (Drucksache <link>)". This cites the document and claims no role for this vote, so it stays true for votes on an Entschließungsantrag that list the law's Beschlussempfehlung (D14).
- When nothing matches, show "Ausschuss nicht ermittelt"; never leave the line blank.

**Store/export.**
- No new column: `vote_documents` → `documents.origin_json` already holds it (measured 190/217).
- Join by number, because `vote_documents` rows are number-only (persist :1298-1310). Verify that the join is filled for sitting-level votes too.
- Add a recipe `r-ausschuss` in `RECIPES` (`build_dip_pulse_site.py` near :2572) so the Daten page shows the query. Name its column `beschlussempfehlung_urheber` (D14). Give it a caption, and a test that its rows equal the panel's committee derivation on the temp-store fixture (D1).

**Tests:**
- A Beschlussempfehlung under another TOP of the same sitting (D3).
- An Entschließungsantrag vote whose numbers include the law's Beschlussempfehlung: the wording cites the document (D14).
- A matched Beschlussempfehlung.
- No Beschlussempfehlung (a plain Antrag vote).
- Two urheber.
- A sitting-level vote.

## Slice 4: archive → panel landing and closing

- Archive rows link to `#top-N` or `#sitting-votes` (:4305-4309), not to the specific vote. Give the vote's **first** panel on the page (in `iter_report_votes` order) `id="vote-<id>"` and point the archive href at it. 8 of 217 votes render under two TOPs, so later copies get no id (D9). _Amended 2026-10-20 (review fixes, Step 2): the id-less fallback is withdrawn; the reference cache holds 0 of 246 votes without an id, and report loading refuses that shape._
- In TODOS.md:
  - Mark B4 parts 1 (DIP part), 3 and 4 done.
  - Leave the AI fallback as the only open part of B4, with "Depends on: Deterministic validators".
  - Update the roadmap B4 line.
  - Update the B3-deferred item 4 text.
  - Extend the B3-deferred item 3 to name abstracts and `vote_proceedings` (D5).
- Use the reference-store figures for `_vote_procedure_type`: the archive column reads the sitting-wide map too (D4). Report the number of '–' rows old/new.
- CHANGELOG / VERSION come through /gstack-ship as usual. Report moved figures: schema 5→6, export 5→6, the CSV count.

## Critical files
- `scripts/derive.py`: `vote_abweichler`, `vote_committees`.
- `scripts/politikfelder.py`: `vote_vorgang_ids`, `abstract_text`, `fetch_targets` (D11/D12). `tags_for_vote` stays unchanged (D8).
- `scripts/validate_dip_protocol.py`: `vorgang_cache_record` keeps `titel` (D12).
- `scripts/render_dip_pulse_html.py`: `vorgang_cache` and report into the dossier vote ctx (F5); first-panel id bookkeeping (D9).
- `scripts/features/votes.py`: `render_vote_summary`, member-link helper, context and committee blocks, panel id.
- `scripts/persist_dip_pulse_store.py`: schema 6, `proceedings.abstract`, `vote_proceedings`.
- `scripts/build_dip_pulse_site.py`: archive rows (href D9, procedure type D4, Abweichler badge), export format 6, captions and provenance, the `r-ausschuss` recipe (D1).
- `docs/plans/b4-daily-votes.md`, `docs/data-license.md`, `TODOS.md`.
- Tests: `tests/test_features_votes.py`, `tests/test_mehrheitsvotum.py`, `tests/test_politikfelder.py`, `tests/test_build_dip_pulse_site.py`, plus persist/export tests.

## Verification
1. Focused tests per slice, then the full suite: `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests` (run by a subagent; report the verdict).
2. Replay on a copy of the reference store `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site/data` (absolute; that path is not inside the worktree), run with `--offline --repersist` into a scratch output. Never write to the original. Use a 900 s bound.
   - Expect 190 votes with a committee and about 153 with a DIP abstract (more after D11's online refresh).
   - Check that the Abweichler totals match `r3-abweichler` (632).
   - **D10:** diff the before/after Daten CSVs. Only the new columns and tables may differ; tags 0 moved; vote counts identical.
   - **D15:** compare per vote `vote_committees(vote, report)` with the store's Beschlussempfehlung `urheber` set, and list any vote that differs.
   - Report the counts old/new, including the page-only procedure-type '–' rows (D4).
3. Open `votes/index.html` and two dossier pages in Chrome DevTools at desktop and 375px width:
   - The topic filter finds a vote.
   - The archive link lands on that vote's panel.
   - The panel shows the context, outcome, tallies, Abweichler, committee and sources.
   - The `<details>` expands.
   - Gap states read correctly.
   - Dark mode is legible.
4. Run the export manifest check (format 6), and confirm the new CSVs open and the captions render on the Daten page.

---

# /plan-eng-review: B4 plan (target: this file)

Review target: `/Users/Luca/.claude/plans/adaptive-petting-eich.md` (B4: Abstimmungen for the daily view). The design source is `docs/plans/b4-daily-votes.md`. The design-doc finder returned the unrelated `docs/designs/fakt-der-woche.md`; the CEO plan it found belongs to the `expand-database` branch and is not used. Base: `origin/main` cfcd249.

## Scope record
- Feature answers: D1 = "Keep it in B4": the `r-ausschuss` recipe stays, as a definite item rather than an optional one.
- Structure: D2 = A "Original arrangement". `vote_abweichler` and `vote_committees` go in `scripts/derive.py`; `vote_vorgang_ids` and `abstract_text` go in `scripts/politikfelder.py`; 0 new classes.
- Accepted scope: Slices 0–4 as written, with the recipe made definite.
- Pending remedies: none at scope time.
- Scope Challenge result: scope accepted as-is.

## Reality rows
Premise table:

| Premise | Claim | Receipt | Verdict |
|---|---|---|---|
| Committee coverage | 190/217 votes have a Beschlussempfehlung `urheber` | store SQL over `vote_documents`→`documents` [measured: reference store] | TRUE |
| Committee via the item's `linked_drucksachen` | the per-TOP detector gives the same set | report probe: 185/217; a sitting-wide map gives 190 [measured] | **FALSE** → finding A1 |
| Abstract coverage | 153/217 on the narrow cache path | report and cache probe [measured] | TRUE |
| Path agreement | narrow cache vs `linked_drucksachen`: 176 same, 36 differ, 5 cache-only | report probe [measured] | TRUE |
| Partial members detectable | member Stimme counts equal fraction counts per group | 1498/1498 groups match [measured] | TRUE |
| Abweichler parity | Python rule = r3 SQL | 632 = 632 [measured: report probe vs store SQL] | TRUE |
| Avoids B3 deferred item 3 | one derivation means no drift between page and export | render derives from the cache (render_dip_pulse_html.py:2947), export from the store | **OVERCLAIMED** → finding A2 |
| Version constants | schema 5, export 5 | persist_dip_pulse_store.py:33, build_dip_pulse_site.py:2485 | TRUE |
| Archive href | links to `#top-N` / `#sitting-votes` | build_dip_pulse_site.py:4305-4309 | TRUE |

unverified=0

REALITY: premise-table finding 9 premises, 1 false (committee per-TOP detector), 1 overclaimed (B3 item 3) scripts/render_dip_pulse_html.py:2947
REALITY: already-done pass origin/main cfcd249 has no B4 commits since 2026-09-30 (git log --grep abweich/abstract/ausschuss/B4) scripts/features/votes.py:97
REALITY: surface-check pass --offline/--repersist exist; unittest discover command per learning single-test-file-unittest-invocation scripts/build_dip_pulse_site.py:11173
REALITY: binding-decisions pass no branch decisions logged; user decision (AI fallback deferred) and D1/D2 recorded in this file scripts/politikfelder.py:489
REALITY: numbers pass all coverage numbers measured on the reference store 2026-10-19; "~300 chars" teaser is [estimated] scripts/persist_dip_pulse_store.py:33
REALITY: deferred-asks pass TODO parts 1-4: 2 done (B3), 1/3/4 in scope, AI fallback deferred by the user's answer; mitberatend is not in the TODO TODOS.md:868
REALITY: pr-count pass one PR (no ship-policy.json, default) TODOS.md:866
REALITY: transaction-semantics n/a schema/table addition, no driver, pool or protocol change scripts/persist_dip_pulse_store.py:36

## Decision ledger

### F5: thread `vorgang_cache` into the dossier vote context (factual correction)
Finding: 5, P3, 9/10, render_dip_pulse_html.py:3026 and :3109 (ctx `{"item","mp_lookup","mp_prefix"}`), reviewer: Claude eng review.
This is required implementation of the approved Slice 2 behaviour, not a new choice. Pass `vorgang_cache` (already a `render_html` parameter, :2921) into both `dossier_sections` ctx dicts. No question.
State: approved (necessary implementation of the scope record).

### R1: committee lookup scope
Finding: 1, P1, 9/10, plan Slice 3 "Match the vote's `document_numbers` to `item.api.linked_drucksachen`", reviewer: Claude eng review.
Plan baseline: per-TOP `linked_drucksachen` match; sitting-level votes fall back to the store's `documents` row (original proposal, unapproved).
Runtime evidence: per-TOP detector 185/217; sitting-wide number→Beschlussempfehlung map from every `agenda_items[].api.linked_drucksachen` of the same report 190/217 = store SQL 190/217 [measured 2026-10-19]. `_vote_procedure_type` (build_dip_pulse_site.py:4236) has the same per-item scope.
Comparison grid:

| Choice | Current | A | B |
|---|---|---|---|
| R1 committee lookup scope | per-TOP plus store fallback (proposal) | sitting-wide map built from the report, in `derive.vote_committees(vote, report)`; no store read at render | render reads the committee from the store (`vote_documents`→`documents`) |
| Recipe r-ausschuss (D1) | approved, keep | unchanged | unchanged |
| Arrangement (D2) | approved, Original | unchanged | unchanged |
| R2–R5 (R5 = `_vote_procedure_type` scope) | pending | pending | pending |

Question D3:
D3 — Where should the vote panel look up the responsible committee?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: The committee comes from the Beschlussempfehlung Drucksache a vote is about. The plan looks only under the vote's own agenda item. But in 5 of 217 real votes, that Drucksache is listed under a different item of the same sitting, so the panel would say "Ausschuss nicht ermittelt" while the Daten export names the committee. Looking across the whole sitting finds all 190 the store finds.
Stakes if we pick wrong: 5 panels (2.6%) show "not found" for a committee our own download names, so page and data disagree.
Recommendation: A because it matches the store exactly (190 = 190, measured) and keeps render free of store reads.
Completeness: A=10/10, B=9/10
Pros / cons:
A) Sitting-wide lookup (recommended)
  ✅ Measured 190/217, identical to the store, so page and export agree
  ✅ Render needs only the report it already has, no new store dependency
  ❌ A number→document map built once per report, about 15 lines in derive.py
B) Read from the store
  ✅ The store is already right (190), so there is one source of truth
  ❌ Render starts depending on the open store, a new coupling dossier pages lack today
  ❌ Tests need a populated store fixture for every panel test, not just a report dict
Net: a small sitting-wide map, or a new render-time store dependency.
Header: D3 committee
Options:
A) Sitting-wide lookup (recommended)
Build one number→Beschlussempfehlung map from all agenda items' linked_drucksachen in the report; derive.vote_committees(vote, report) reads it. Test: a vote whose BE is linked under another TOP. The procedure-type column is a separate choice (R5). (human: ~2h / CC: ~10 min)
B) Read from the store
Panel reads committee via vote_documents→documents.origin_json at render time; needs a store handle in the dossier ctx. The procedure-type column is a separate choice (R5). (human: ~3h / CC: ~15 min)

State: approved
Actual answer: A) Sitting-wide lookup (D3, user answer 2026-10-19)
Accepted scope: `derive.vote_committees(vote, report)` reads one number→Beschlussempfehlung map built from every `agenda_items[].api.linked_drucksachen` in the report. There is no store read at render. A test covers a vote whose Beschlussempfehlung is linked under another TOP. Expected: 190/217 on the reference store, equal to the store SQL.
History: the first draft bundled the `_vote_procedure_type` fix into A; it was split out as R5 before asking.

### R5: archive procedure-type column scope
Finding: 1 (side effect), P3, 9/10, build_dip_pulse_site.py:4234-4239 `for doc in (item.get("api") or {}).get("linked_drucksachen")`, reviewer: Claude eng review.
Plan baseline: not in the plan. The column stays per-item (current behaviour).
Runtime evidence: the same per-item scope as R1. Votes whose Drucksache is linked under another TOP show "–". The count for this column is not measured; it is at least the 5 votes from R1 (any linked type, not only Beschlussempfehlung).
Comparison grid:

| Choice | Current | A | B |
|---|---|---|---|
| R5 procedure-type scope | per-item | `_vote_procedure_type` reads the R1 sitting-wide number map (all Drucksache types), plus one test | unchanged, per-item |
| R1 (D3) | approved, sitting-wide committee map | unchanged | unchanged |
| D1, D2 | approved | unchanged | unchanged |
| R2–R4 | pending | pending | pending |

Question D4:
D4 — Should the archive's procedure-type column use the same sitting-wide lookup?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: The votes archive shows a 'Vorgangstyp' per vote, looked up the same narrow way the committee was. D3 just made the committee look across the whole sitting. The archive column can reuse that map, or stay as it is.
Stakes if we pick wrong: at least 5 archive rows keep showing '–' for a type the sitting's own documents carry.
Recommendation: A because the map from D3 already exists and the fix is a few lines plus one test.
Completeness: A=10/10, B=8/10
Pros / cons:
A) Reuse the sitting-wide map (recommended)
  ✅ Archive rows and panels read the same document map, so they agree
  ✅ Marginal cost: the map exists after D3, about 5 lines plus one test row
  ❌ Touches the archive builder, which B4 already edits for the panel anchor
B) Leave the column as it is
  ✅ Smallest diff; the column is outside B4's four asks
  ✅ No archive regression risk from this change
  ❌ The archive keeps showing '–' where the sitting knows the type
Net: a few lines for consistency, or strict scope.
Header: D4 proc type
Options:
A) Reuse the sitting-wide map (recommended)
_vote_procedure_type looks the vote's numbers up in the R1 report-wide map (all Drucksache types). Extend the archive test with a vote whose Drucksache sits under another TOP. (human: ~30min / CC: ~3 min)
B) Leave the column as it is
No change to _vote_procedure_type; it keeps its per-item lookup. (human: 0 / CC: 0)

State: approved
Actual answer: A) Reuse the sitting-wide map (D4, user answer 2026-10-19)
Accepted scope: `_vote_procedure_type` (build_dip_pulse_site.py:4234) looks the vote's numbers up in the R1 report-wide document map (all Drucksache types). The archive test is extended with a vote whose Drucksache sits under another TOP. Report the moved count (old '–' rows vs new) at implementation.
History: none

### R2: page vs export drift for abstracts (B3 deferred item 3)
Finding: 2, P2, 8/10, plan Slice 2 "This avoids B3 deferred item 3", against render_dip_pulse_html.py:2947 `item_politikfelder, _ = politikfelder.report_politikfelder(report, vorgang_cache or politikfelder.empty_cache())`, reviewer: Claude eng review.
Plan baseline: the plan claims that one derivation function avoids drift (unapproved proposal).
Runtime evidence: pages derive from the cache at render, and the export reads the store snapshot of the last persist. A plain `--offline` build after the cache changed shows different tags than it exports (TODOS.md:891, B3 item 3). Abstracts would inherit exactly this. Render does not read the store (D3 kept it that way).
Comparison grid:

| Choice | Current | A | B |
|---|---|---|---|
| R2 drift handling | claim "avoids item 3" (incorrect) | correct the plan wording: abstracts share B3's known drift. Extend TODOS B3 item 3 to name abstracts and the vote→Vorgang selection, so its fix (cache digest in `datenstand`, or render from store) covers all three | B4 fixes item 3 now: store a cache digest in `datenstand` at persist, and have render print a build warning when the loaded cache digest differs |
| R1 (D3), R5 (D4) | approved | unchanged | unchanged |
| D1, D2 | approved | unchanged | unchanged |
| R3, R4 | pending | pending | pending |

Question D5:
D5 — Abstracts can drift between page and download the same way B3's tags do. Fix it in B4 or track it with the tags?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: Pages read the Vorgang cache when they render; the download reads the database written at the last persist. If someone refreshes the cache and then does a plain offline build without re-persisting, the page can show a newer abstract than the download. Politikfeld tags already have this exact gap (TODOS B3 item 3, P3). The plan wrongly claimed B4 avoids it.
Stakes if we pick wrong: after a cache refresh without repersist, a page and its Daten CSV disagree on a vote's description until the next full build.
Recommendation: A because the gap is shared with tags and needs one fix for both, it never occurs in a normal online build, and B3 already tracks it.
Completeness: A=8/10, B=10/10
Pros / cons:
A) Track with the tags (recommended)
  ✅ One later fix closes drift for tags, abstracts and vote→Vorgang links together
  ✅ Keeps B4 focused; no new build-wide guard inside a feature PR
  ❌ The drift window stays open for abstracts until B3 item 3 ships
B) Fix it now in B4
  ✅ Page and download can never silently disagree after B4 ships
  ✅ Also closes the existing tag drift, a P3 already on the books
  ❌ A build-wide guard (datenstand digest plus a render check) added to a 14-file feature change
Net: one shared fix later, or a build guard now on top of B4.
Header: D5 drift
Options:
A) Track with the tags (recommended)
Remove the 'avoids B3 item 3' claim from Slice 2; edit TODOS B3 deferred item 3 to name abstracts and vote_proceedings too. No code. (human: ~10min / CC: ~2 min)
B) Fix it now in B4
Write a vorgang-cache digest into datenstand at persist; render compares it with the loaded cache and prints a build warning on mismatch; tests for both. (human: ~4h / CC: ~20 min)

State: approved
Actual answer: A) Track with the tags (D5, user answer 2026-10-19)
Accepted scope: remove the "avoids B3 deferred item 3" claim from Slice 2 and state that abstracts and `vote_proceedings` share B3's known render-from-cache vs export-from-store drift. Edit TODOS.md B3 deferred item 3 to name abstracts and `vote_proceedings`. No guard code in B4.
History: before asking, option B's "warns (or refuses publication)" was pinned to "prints a build warning".

### R3: how many Abweichler names show inline
Finding: 3, P2, 9/10, plan Slice 1 "Under each qualifying group's tally row, add a compact line", reviewer: Claude eng review.
Plan baseline: every qualifying name is shown inline under its group's tally row (original proposal, unapproved).
Runtime evidence: 632 Abweichler across 95 of 217 votes (about 6.7 per vote with any). The maximum is 179 in one vote: 2023-07-06 Suizidhilfe, SPD 62, Grüne 46, FDP 28, CDU/CSU 27 [measured: store SQL, matching the report probe].
Comparison grid:

| Choice | Current | A | B |
|---|---|---|---|
| R3 inline cap | unbounded inline | up to 10 names inline per group, alphabetical; the rest behind a native `<details>` "alle N anzeigen" in the same spot | every group's list collapsed behind `<details>` with the count in the summary ("SPD: 3 Abweichler") |
| R1, R5, R2 | approved | unchanged | unchanged |
| D1, D2 | approved | unchanged | unchanged |
| R4 | pending | pending | pending |

Question D6:
D6 — How many Abweichler names should the vote panel show before folding?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: Most votes with dissent have a handful of Abweichler, but free votes have many: the 2023 Suizidhilfe vote has 179, including 62 in the SPD alone. Listing every name inline turns that panel into a wall of text. We can show up to 10 per group and fold the rest, or fold every list behind a count.
Stakes if we pick wrong: either the panel is unreadable on free votes (no cap), or a reader must click to see even one dissenter on a normal vote (always folded).
Recommendation: A because the common case (a few names) stays visible with no click, which is the TODO's 'without leaving the page', and big free votes stay readable.
Completeness: A=10/10, B=9/10
Pros / cons:
A) Up to 10 inline, rest folded (recommended)
  ✅ Typical votes show every dissenter at a glance with no click
  ✅ A free vote's 62-name group folds to 10 plus a native 'alle 62 anzeigen'
  ❌ One more branch to test: exactly 10, 11, and a large group
B) Always folded with counts
  ✅ Uniform compact panel; the count per group is always visible
  ✅ Simplest markup: one <details> per group
  ❌ Even a single dissenter needs a click to see who it is
Net: visible names in the common case, or uniform compactness.
Header: D6 names
Options:
A) Up to 10 inline, rest folded (recommended)
Per qualifying group: first 10 names (alphabetical, linked via the shared member-link helper) inline; if more, a native <details><summary>alle N anzeigen</summary> holds the rest. Tests: 1, 10, 11 and 62 names. (human: ~1h / CC: ~5 min)
B) Always folded with counts
Per qualifying group: <details><summary>{Gruppe}: N Abweichler</summary> with all names inside. Tests: 1 and 62 names. (human: ~45min / CC: ~4 min)

State: approved
Actual answer: A) Up to 10 inline, rest folded (D6, user answer 2026-10-19)
Accepted scope: for each qualifying group, show the first 10 names (alphabetical, linked through the shared member-link helper) inline under the tally row. If there are more, a native `<details><summary>alle N anzeigen</summary>` holds the rest. Tests cover 1, 10, 11 and 62 names.
History: none

### R4: store state for "Vorgang not fetched" on a vote's context
Finding: 4, P2, 7/10, plan Slice 2 "Add a new junction `vote_proceedings(vote_id, proceeding_id, rank)`" vs "Missing or not fetched: 'Keine Beschreibung in DIP' or 'Vorgang nicht abgerufen'", reviewer: Claude eng review.
Plan baseline: `vote_proceedings` holds resolved rows only, so the export cannot tell "no Vorgang" from "not fetched" (original proposal, unapproved).
Runtime evidence: B3 stores that distinction for tags as `vote_politikfelder.source = 'not_fetched'` (persist_dip_pulse_store.py:337 table, TODOS.md:892 item 6). The real store has 0 `not_fetched` today, so no figure moves now.
Comparison grid:

| Choice | Current | A | B |
|---|---|---|---|
| R4 context state in store | none (no row either way) | add `votes.context_state` TEXT in {`resolved`, `none`, `not_fetched`} set at persist from the same `vote_vorgang_ids` result; export column (layer `derived`) with caption; the page derives the same state from the same function at render | keep no state; the `vote_proceedings` caption says "no row = no Vorgang resolved or not fetched" |
| Schema/export bump 5→6 | in plan | unchanged (same bump) | unchanged |
| R1, R5, R2, R3 | approved | unchanged | unchanged |
| D1, D2 | approved | unchanged | unchanged |

Question D7:
D7 — Should the download record when a vote's Vorgang context was not fetched?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: The panel will say either 'Keine Beschreibung in DIP' (DIP has nothing) or 'Vorgang nicht abgerufen' (we failed to fetch). The planned database table only stores links that were found, so the download cannot tell these two apart. The Politikfeld tags already record 'not_fetched' for exactly this reason.
Stakes if we pick wrong: a researcher counting 'votes without a description' silently includes fetch failures, which is a wrong number in a citable dataset.
Recommendation: A because it matches the B3 tag precedent and keeps the download as honest as the page, at the cost of one column inside the schema bump B4 already makes.
Completeness: A=10/10, B=7/10
Pros / cons:
A) Store a context state (recommended)
  ✅ Download distinguishes 'none' from 'not fetched', like vote_politikfelder.source
  ✅ Rides on the 5→6 schema bump B4 already does; no extra migration
  ❌ One more column, caption, provenance tag and round-trip assertion
B) No state, caption only
  ✅ Smallest schema change; vote_proceedings stays a pure junction
  ✅ Zero not_fetched in today's store, so no current figure is wrong
  ❌ After any fetch outage the export conflates two meanings and only the caption warns
Net: an honest download column, or a smaller schema.
Header: D7 state
Options:
A) Store a context state (recommended)
Add votes.context_state ('resolved'|'none'|'not_fetched') at persist from vote_vorgang_ids; export it with caption and derived provenance; tests for all three states and the export round trip. (human: ~2h / CC: ~10 min)
B) No state, caption only
vote_proceedings keeps resolved rows only; its caption explains that a missing row means none or not fetched. (human: ~10min / CC: ~2 min)

State: approved
Actual answer: A) Store a context state (D7, user answer 2026-10-19)
Accepted scope: add `votes.context_state` TEXT in {`resolved`, `none`, `not_fetched`}, set at persist from `vote_vorgang_ids`. The page derives the same state from the same function at render. Export it with a caption and `derived` provenance, inside the 5→6 bump. Tests cover all three states and the export round trip.
History: before asking, the grid wording "the page reads the same state" was corrected to "derives the same state from the same function at render".

### F7: sanitizer mechanism (implementation guidance, no question)
Finding: 7, P3, 8/10, plan Slice 2 "strip all other tags, unescape entities". The approved behaviour is unchanged. Implement it with stdlib `html.parser.HTMLParser` [Layer 1], not regex, so malformed or nested markup in DIP abstracts can't leak tags. The caller still escapes.
State: approved (mechanism for approved behaviour).

### R6: `tags_for_vote` refactor
Finding: 6, P2, 9/10, plan Slice 2 "Refactor `tags_for_vote` to call it, so tags and context cannot diverge" vs politikfelder.py:489-495 `tiers, missing = _vorgaenge_of_numbers(..., narrow_first=True)` … `ordered = [t for t in tiers if linked & set(t)] + [t for t in tiers if not linked & set(t)]`, reviewer: Claude eng review.
Plan baseline: refactor `tags_for_vote` onto the narrow-only `vote_vorgang_ids` (original proposal, unapproved).
Runtime evidence: `tags_for_vote` may take its Vorgänge from the wide tier (fan-out ≤ `MAX_NUMBER_FANOUT`) when only that tier intersects the TOP's Vorgänge. A narrow-only helper therefore cannot be the source of tags without changing tags. How many votes this changes is not measured.
Comparison grid:

| Choice | Current | A | B |
|---|---|---|---|
| R6 tags_for_vote | unchanged code | leave `tags_for_vote` unchanged; `vote_vorgang_ids` is a new sibling over `_vorgaenge_of_numbers` (narrow tier, narrowed to TOP Vorgänge when they intersect); drop the "cannot diverge" claim; a test pins that for votes where tags came from the narrow tier, both pick the same Vorgänge | refactor `tags_for_vote` to try `vote_vorgang_ids` first, then the wide tier; measure the moved tag count on the reference store and report old/new |
| R1–R5 | approved | unchanged | unchanged |
| D1, D2 | approved | unchanged | unchanged |

Question D8:
D8 — Should the Politikfeld tag code be rewired through the new narrow-only Vorgang helper?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: B4 adds a helper that finds the few Vorgänge a vote is clearly about, and uses only those for the description. The plan also wanted the existing tag code to call it 'so they cannot diverge'. But the tag code deliberately also looks at a wider set of Vorgänge, and sometimes prefers that wider set. So the two can't be one function without changing some votes' tags, which B4 doesn't intend.
Stakes if we pick wrong: a silent change to shipped Politikfeld tags (and the votes archive filter) inside a feature PR that isn't about tags.
Recommendation: A because B4 needs a narrower answer than tags do, and keeping tags untouched removes a regression risk for no loss.
Completeness: A=10/10, B=8/10
Pros / cons:
A) Leave tag code alone (recommended)
  ✅ Zero risk to B3's shipped tags and the archive's topic filter
  ✅ The narrow helper shares the same _vorgaenge_of_numbers tiers, so no rule is copied
  ❌ Two entry points over the tiers; a parity test must pin where they should agree
B) Rewire and measure
  ✅ One code path for 'which Vorgänge is this vote about'
  ✅ Any moved tags get counted and reported, per the project's old/new rule
  ❌ Changes shipped tag figures inside a non-tag PR, and needs a tag replay
Net: a safe sibling helper, or one path that moves tag figures.
Header: D8 tags
Options:
A) Leave tag code alone (recommended)
tags_for_vote unchanged; vote_vorgang_ids is a new function over _vorgaenge_of_numbers; plan drops 'cannot diverge'; parity test for narrow-tier-tagged votes. (human: ~1h / CC: ~5 min)
B) Rewire and measure
tags_for_vote tries vote_vorgang_ids first, then the wide tier; replay on the reference store and report moved tag counts old/new; update B3 tests where tags move. (human: ~4h / CC: ~20 min)

State: approved
Actual answer: A) Leave tag code alone (D8, user answer 2026-10-19)
Accepted scope: `tags_for_vote` stays unchanged. `vote_vorgang_ids` is a new function over `_vorgaenge_of_numbers` (narrow tier, narrowed to TOP Vorgänge when they intersect). The plan drops "cannot diverge". A parity test covers votes tagged from the narrow tier.
History: none

### R7: panel anchor for votes listed under several TOPs
Finding: 8, P2, 9/10, plan Slice 4 "Give each vote panel `id="vote-<stable vote id>"`" vs `render_vote_summary` rendering `item.get("votes")` per TOP (votes.py:103), reviewer: Claude eng review.
Plan baseline: one `id="vote-<id>"` on every rendered panel (original proposal, unapproved).
Runtime evidence: 8 of 217 votes are listed under more than one TOP of their sitting, so each would render twice with the same HTML id. All 217 have numeric ids (e.g. `1000`), so no vote lacks an id [measured 2026-10-19].
Comparison grid:

| Choice | Current | A | B |
|---|---|---|---|
| R7 anchor scheme | no vote anchor; the archive links `#top-N` / `#sitting-votes` | `id="vote-<id>"` only on the vote's first rendering in `iter_report_votes` order; the archive links there; later renderings get no id; a vote without id keeps the TOP anchor | an id per rendering, `vote-<id>-top-<n>`; the archive links to the first TOP's |
| R1–R6 | approved | unchanged | unchanged |
| D1, D2 | approved | unchanged | unchanged |

Question D9:
D9 — Which anchor should the archive link to when a vote appears under two agenda items?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: Slice 4 makes each archive row jump straight to its vote panel with an id like vote-1002. But 8 of 217 votes belong to two agenda items, so their panel is drawn twice on the same page, and two elements with the same id are invalid HTML. The browser jumps to the first one anyway, so the id should go on one of them.
Stakes if we pick wrong: duplicate ids on 8 dossier pages (invalid HTML, ambiguous deep links), or links that point at a less relevant copy.
Recommendation: A because it gives one clean, stable URL per vote (vote-1002), matching how iter_report_votes already treats the first occurrence as canonical.
Completeness: A=10/10, B=9/10
Pros / cons:
A) Id on the first panel only (recommended)
  ✅ One stable, citable link per vote: #vote-1002
  ✅ Reuses iter_report_votes' first-occurrence rule, which persist already uses
  ❌ The second copy can't be deep-linked on its own
B) Id per rendering
  ✅ Every copy is addressable, so no panel lacks an anchor
  ✅ No first-occurrence bookkeeping during render
  ❌ Longer, TOP-dependent URLs that change if the TOP number changes
Net: one stable link per vote, or every copy addressable.
Header: D9 anchor
Options:
A) Id on the first panel only (recommended)
render passes a 'seen vote ids' set per page; first rendering gets id="vote-<id>"; archive href = page#vote-<id>; tests: duplicated vote has exactly one id, archive href targets it, id-less legacy vote keeps #top-N. (human: ~1h / CC: ~5 min)
B) Id per rendering
Each panel gets id="vote-<id>-top-<n>" (sitting-level: vote-<id>-sitzung); archive href targets the first TOP's; tests for both copies and the href. (human: ~1h / CC: ~5 min)

State: approved
Actual answer: A) Id on the first panel only (D9, user answer 2026-10-19)
Accepted scope: render passes a per-page set of seen vote ids. The first rendering in `iter_report_votes` order gets `id="vote-<id>"`, and later copies get no id. The archive href becomes `page#vote-<id>`. ~~A vote without an id keeps `#top-N` / `#sitting-votes`.~~ Tests: a duplicated vote has exactly one id and the archive href targets it. _Amended 2026-10-20: "a vote without an id keeps the TOP anchor" is withdrawn, because none exist (0/246) and `require_current_vote_shape` refuses the shape at report loading._
History: none

### R8: regression contract for existing behaviour
Finding: 9, CRITICAL (regression rule), 9/10. B4 rewrites `render_vote_summary` (votes.py:97-224), the archive rows (build_dip_pulse_site.py:4270-4310), persist (schema 6) and export (format 6). Reviewer: Claude eng review.
Plan baseline: "existing tests/test_politikfelder.py must pass untouched", plus focused tests. The rest of the existing behaviour has no stated contract.
Runtime evidence: existing guards are test_features_votes.py (badge, docs, XLSX, fraction merge, 9 member-link tests); test_b1_consumers.py:59 and :91 (the archive's sitting anchors); test_build_dip_pulse_site.py:2377, :2426, :2448 (procedure type, href); test_politikfelder.py:923-950; test_mehrheitsvotum.py:170-202; test_daten_export.py and test_repersist.py.
Comparison grid:

| Choice | Current | A | B |
|---|---|---|---|
| R8 regression contract | none stated | **Preserve:** every existing test in the files above passes unchanged, except the named intentional updates: the archive href `#top-N`→`#vote-<id>` (b1_consumers :59 and :91, build_dip :2448 and :2567 as applicable, D9), procedure type sitting-wide (build_dip :2377 and :2426, D4), and export format/CSV count. **Replay assertion:** on a copy of the reference store, diff the Daten CSVs before and after B4. Only the new columns/tables may differ; tags 0 moved, vote counts and Abweichler totals identical (632). The page-only procedure-type moves (D4) are counted and reported separately | same "Preserve" list; no replay diff, unit tests only |
| R1–R7 | approved | unchanged | unchanged |
| D1, D2 | approved | unchanged | unchanged |

Question D10:
D10 — What must B4 prove it did not break?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: B4 rewrites the vote panel, the archive rows, and the database and download formats. Existing tests guard most of today's behaviour. A few must change on purpose: archive links now jump to the vote (D9), and the procedure-type column looks sitting-wide (D4). Everything else should stay the same. The question is whether a unit-test contract is enough, or whether we also diff the full download before and after on the real reference data.
Stakes if we pick wrong: a figure in the citable download shifts silently (a tag, a count) and nobody notices until after release.
Recommendation: A because the project rule says to report every moved number with old and new values, and a CSV diff on the reference store is the only check that proves 'nothing else moved'.
Completeness: A=10/10, B=7/10
Pros / cons:
A) Tests plus replay diff (recommended)
  ✅ Proves no unintended figure moved in the citable export, per CLAUDE.md's old/new rule
  ✅ Reuses the planned reference replay (Verification step 2); only the diff is new
  ❌ The replay takes about 5 min (b2 learning: a 900 s bound is safe), run once per PR
B) Unit-test contract only
  ✅ Fast and deterministic; no reference-store dependency
  ✅ Existing tests already guard most panel and archive behaviour
  ❌ Can't catch a figure moving through real data shapes the fixtures don't have
Net: proof on real data, or a faster but blinder contract.
Header: D10 regress
Options:
A) Tests plus replay diff (recommended)
Preserve list as in the grid; intentional updates named; then diff before/after Daten CSVs on a reference-store copy, allowing only new columns/tables; count the page-only D4 procedure-type moves separately; report counts. (human: ~2h / CC: ~15 min + ~5 min replay)
B) Unit-test contract only
Preserve list as in the grid with the same intentional updates; no replay diff. (human: ~30min / CC: ~3 min)

State: approved
Actual answer: A) Tests plus replay diff (D10, user answer 2026-10-19)
Accepted scope: every existing test in test_features_votes.py, test_b1_consumers.py, test_build_dip_pulse_site.py (archive), test_politikfelder.py, test_mehrheitsvotum.py, test_daten_export.py and test_repersist.py passes unchanged. The only exceptions are the named intentional updates: the href (D9), the procedure type (D4), and the export format/CSV count. Then, on a reference-store copy, diff the before/after Daten CSVs; only new columns and tables may differ. Tags 0 moved, vote counts identical, Abweichler total 632. Count and report the page-only procedure-type moves separately. Use a 900 s bound for the replay.
History: before asking, "approved moved figures (procedure-type '–' rows)" was corrected, because the procedure type is page-only and not in the CSVs.

## Outside voice (native fallback)
Codex preflight returned `ready`. The run was refused by the worktree-isolation guard (a piped command), and plan mode forbids a temp prompt file, so a native Plan subagent ran within the 5-minute timer and completed. Its findings (O1–O9) and verification:

| # | Sev | Claim | Verified |
|---|---|---|---|
| O1 | High | the cache never re-fetches an abstract once a Sachgebiet exists | **TRUE**: politikfelder.py:560-563 `if (record is None or not record.get("sachgebiet"))`. 1998/7511 records have a Sachgebiet but no abstract; **all 64** no-abstract votes are in that set [measured] |
| O2 | High | no Vorgang title for labels | **TRUE**: validate_dip_protocol.py:298-305 keeps no `titel` |
| O3 | Med | the panel uses one TOP's linked ids, while persist and tags use the union | structurally TRUE (politikfelder.py:533-541); 0 of 8 multi-TOP votes differ today [measured] |
| O4 | Med | r3 SQL returns per-MP counts, not pairs; partial groups differ | TRUE: parity must use a per-vote SQL. Store has 21/1498 groups where `vote_members` ≠ `vote_fractions`; the report JSON matches 1498/1498 [measured] |
| O5 | Low | 190=190 committee parity is per total, not per vote; the store may pull a BE from other sittings | plausible, not measured per vote |
| O6 | Low | an Entschließungsantrag vote inherits the law's committee as "federführend" | partly TRUE: 14/16 Entschließungsantrag-related votes get a BE committee; how many are wrong is not measured |
| O7 | Low | "Critical files" still says `tags_for_vote` refactor | TRUE: contradicts D8 |
| O8 | Low | the reference path must be absolute | TRUE |
| O9 | Low | sequence cache-shape changes before schema 6 | follows from O1/O2 if applied |

### C1: corrections (no question; necessary implementation of approved behaviour)
- O4: the D10/Slice 1 parity test is restated as "Python `vote_abweichler` (vote, member) set == a per-vote SQL written in the test with the r3 predicate". The replay compares totals with r3 (632 = 632 measured). Per-group parity is asserted only where the report's member counts match its fractions. The store's 21 mismatched groups are a pre-existing identity effect, handled under TODOs.
- O7: "Critical files" now says `vote_vorgang_ids` and `abstract_text`, with `tags_for_vote` unchanged (D8).
- O8: Verification uses `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site/data` (absolute; copy it before replay).
State: approved (corrections).

### R9: refresh empty abstracts (O1)
Finding: O1, High, 9/10, politikfelder.py:560-563 `if (record is None or not record.get("sachgebiet")) and vorgang_id not in ids`, reviewer: outside voice (Claude subagent), verified by the parent.
Plan baseline: no change to `fetch_targets`; the panel says "Keine Beschreibung in DIP" (approved user decision: AI fallback deferred).
Runtime evidence: all 64 no-abstract votes resolve only to records the refresh rule skips forever.
Comparison grid:

| Choice | Current | A Apply | B Keep | C Investigate | D Defer |
|---|---|---|---|---|---|
| R9 abstract refresh | never refetched | `fetch_targets` also wants ids that a **vote** resolves to (narrow tier) whose cached `abstract` is empty: ≤ ~100 ids, 1–2 batches per online build [estimated]. Panel copy stays "Keine Beschreibung in DIP" | unchanged; panel copy becomes "Keine Beschreibung im DIP-Abruf" (dated by `aktualisiert`) | one bounded online probe: refetch the 64 votes' Vorgänge once and count how many now have an abstract; no code change approved | unchanged; add to the TODOS B3 item 6 refresh list |
| everything else | approved/pending as recorded | unchanged | unchanged | unchanged | unchanged |

Question D11:
D11 — Should online builds re-fetch the Vorgänge of votes that still have no abstract?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: The cache only asks DIP again about a Vorgang if it has no topic area yet. Abstracts often arrive later than topic areas, so the 64 votes without a description will never get one, and the panel would claim 'no description in DIP' when DIP may have one now. Re-asking for just the Vorgänge that votes point at costs one or two extra requests per build.
Stakes if we pick wrong: up to 64 vote panels (30%) state something false about DIP, forever.
Recommendation: A because it makes the panel's claim true at small, bounded cost.
Completeness: A=10/10, B=8/10, C=6/10, D=5/10
Pros / cons:
A) Apply: refetch vote Vorgänge (recommended)
  ✅ 'Keine Beschreibung in DIP' becomes true as of the latest online build
  ✅ Bounded: only vote-resolved ids with an empty abstract, about 1-2 batches per build
  ❌ A few extra DIP requests on every online build until DIP fills them
B) Keep: date the claim instead
  ✅ No change to the fetch path or DIP request volume
  ✅ The panel copy is honest about when we last looked
  ❌ Descriptions DIP added later never appear
C) Investigate first
  ✅ One online probe tells us how many of the 64 DIP has since filled
  ✅ No code approved until we know it matters
  ❌ Costs a session with network, and the decision comes back again
D) Defer to TODOS
  ✅ Keeps B4's diff smaller
  ✅ Groups it with B3's other refresh items
  ❌ B4 ships a claim we know can be false
Net: a tiny fetch change for a true claim, or wording that admits the gap.
Header: D11 refresh
Options:
A) Apply: refetch vote Vorgänge (recommended)
fetch_targets also wants narrow-tier Vorgang ids of votes whose cached abstract is empty; test in test_politikfelder.py; report how many of the 64 gain an abstract on the next online build. (human: ~1h / CC: ~5 min)
B) Keep: date the claim instead
fetch_targets unchanged; panel copy 'Keine Beschreibung im DIP-Abruf (Stand: <aktualisiert>)'. (human: ~20min / CC: ~2 min)
C) Investigate first
One online probe refetching the 64 votes' Vorgänge, counting new abstracts; no code; return to this choice. (human: ~30min / CC: ~5 min + network)
D) Defer to TODOS
fetch_targets unchanged; add 'refresh empty abstracts' to TODOS B3 deferred item 6. (human: ~5min / CC: ~1 min)

State: approved
Actual answer: A) Apply: refetch vote Vorgänge (D11, user answer 2026-10-19)
Accepted scope: `politikfelder.fetch_targets` also wants the narrow-tier Vorgang ids of votes whose cached `abstract` is empty, with a test in test_politikfelder.py. After the next online build, report how many of the 64 votes gained an abstract (old/new). The panel copy "Keine Beschreibung in DIP" stays.
History: none

### R10: Vorgang title for context labels (O2)
Finding: O2, High, 9/10, validate_dip_protocol.py:298-305 `return {"sachgebiet": ..., "deskriptor_sachbegriffe": ..., "abstract": ..., "vorgangstyp": ..., "aktualisiert": ...}` (no `titel`), reviewer: outside voice, verified by the parent.
Plan baseline: Slice 2 "When there are several Vorgänge, label each block with its Vorgang title and link" (unapproved proposal).
Runtime evidence: the cache has no titles; `proceedings.title` exists only for TOP-linked Vorgänge filled from the TOP's API records.
Comparison grid:

| Choice | Current | A Apply | B Keep | C Investigate | D Defer |
|---|---|---|---|---|---|
| R10 label source | the plan names a title with no source | add `titel` to `vorgang_cache_record`; `fetch_targets` also wants vote-resolved ids whose record lacks the `titel` key (a one-time refetch, about 3 batches [estimated]); `proceedings.title` filled for vote-only Vorgänge | label by cached `vorgangstyp` + DIP Vorgang link ("Gesetzgebung · DIP-Vorgang 312345"); no cache change | count how many vote-resolved Vorgänge lack a title in `proceedings` today; no code | single-Vorgang votes unlabelled; multi-Vorgang votes say "Mehrere Vorhaben" with links; title in TODOS |
| R9 (D11) | approved: vote Vorgang refetch for empty abstract | unchanged (the same fetch pass) | unchanged | unchanged | unchanged |

Question D12:
D12 — Where does each 'Worum es geht' block get its Vorgang title?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: 42 votes point at more than one Vorgang, so the panel shows several descriptions, each labelled with what it belongs to. But our cache never stored Vorgang titles, so there's nothing to label them with for Vorgänge only a vote points at. We can start storing the title (one small refetch, riding on D11's fetch pass) or label blocks by type plus a DIP link.
Stakes if we pick wrong: readers see two or three unlabelled descriptions and can't tell which law or motion each one is about.
Recommendation: A because the title is what a reader needs, and D11 already adds the refetch path, so the extra cost is one field and about 3 one-time batches.
Completeness: A=10/10, B=7/10, C=5/10, D=5/10
Pros / cons:
A) Apply: cache the title (recommended)
  ✅ Every context block names its Vorhaben in words, with the DIP link
  ✅ Rides on D11's vote-Vorgang refetch; about 3 one-time batches [estimated]
  ❌ Changes the cache record shape; old records lack titel until refetched
B) Keep: type plus link
  ✅ No cache-shape change; vorgangstyp is already cached
  ✅ Still distinguishes blocks and links to the source
  ❌ 'Gesetzgebung · 312345' twice in a row doesn't tell readers which is which
C) Investigate first
  ✅ Shows how many vote Vorgänge already have a title in proceedings
  ✅ No code approved yet
  ❌ Comes back to the same choice; we already know the cache has none
D) Defer
  ✅ Smallest B4 change
  ✅ Leaves the honest 'Mehrere Vorhaben' note
  ❌ Multi-Vorgang votes lose the per-block label the plan promised
Net: one cached field for readable labels, or type-and-number labels.
Header: D12 title
Options:
A) Apply: cache the title (recommended)
Add titel to vorgang_cache_record; fetch_targets also wants vote-resolved ids lacking the titel key; fill proceedings.title for vote-only Vorgänge; label blocks '<titel> · DIP'; tests for record shape and labels. (human: ~1.5h / CC: ~8 min)
B) Keep: type plus link
Label each block '<vorgangstyp> · DIP-Vorgang <id>' linked to DIP; no cache change; test the label. (human: ~30min / CC: ~3 min)
C) Investigate first
Count vote-resolved Vorgänge with and without proceedings.title on the reference store; no code; return to this choice. (human: ~15min / CC: ~2 min)
D) Defer
Single-Vorgang: no label; several: 'Mehrere Vorhaben' with one DIP link each; titel caching added to TODOS. (human: ~20min / CC: ~2 min)

State: approved
Actual answer: A) Apply: cache the title (D12, user answer 2026-10-19)
Accepted scope:
- Add `titel` to `vorgang_cache_record` (validate_dip_protocol.py:298).
- `fetch_targets` also wants vote-resolved ids whose record lacks the `titel` key, in the same pass as D11.
- Fill `proceedings.title` for vote-only Vorgänge.
- Label context blocks "<titel> · DIP".
- Tests cover the record shape and the labels.
History: none

### R11: combined TOP links for a vote's context (O3)
Finding: O3, Medium, 8/10, politikfelder.py:533-541 (`report_politikfelder` unions `linked_vorgang_ids` over every TOP a vote sits under) vs plan Slice 2 `vote_context(vote, item, cache)`. Reviewer: outside voice, verified by the parent.
Plan baseline: context narrowed by the single rendering TOP's Vorgänge (unapproved proposal).
Runtime evidence: 0 of the 8 multi-TOP votes resolve differently by TOP today [measured]. The divergence is structural and would show as two panels of one vote, or panel vs `vote_proceedings`, disagreeing.
Comparison grid:

| Choice | Current | A Apply | B Keep | C Investigate | D Defer |
|---|---|---|---|---|---|
| R11 linked-id scope | per rendering TOP | build one per-report map vote key → union of linked Vorgang ids (the same union `report_politikfelder` uses), passed to `vote_vorgang_ids` by both persist and render; `vote_context(vote, report, cache)` | per rendering TOP (accept divergence; 0 today) | none useful: already measured at 0 | per TOP now; TODO to unify |
| R7 (D9) | approved: id on the first panel | unchanged | unchanged | unchanged | unchanged |

Question D13:
D13 — Should a vote's context use the Vorgänge of all its agenda items, as tags do?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: To pick the right Vorgang, the helper prefers ones that belong to the vote's agenda item. Tags already combine all agenda items a vote sits under. The plan passed only the one item being drawn, so a vote shown under two items could show two different descriptions, and differ from the download. Today none of the 8 such votes actually differ, but nothing stops it.
Stakes if we pick wrong: a vote's two panels, or panel and download, describe different Vorhaben.
Recommendation: A because it's the same union tags already compute, so it costs little and closes the gap for good.
Completeness: A=10/10, B=7/10, C=5/10, D=6/10
Pros / cons:
A) Apply: one union per vote (recommended)
  ✅ Every panel copy and the download read the same Vorgang selection
  ✅ Mirrors report_politikfelder's existing union, so no new rule
  ❌ Changes vote_context's signature from item to report, so callers need the report
B) Keep per-TOP
  ✅ Simplest: each panel uses the item it already has
  ✅ Measured 0 differing votes on the reference data today
  ❌ Two panels of one vote can drift as data grows
C) Investigate
  ✅ Would re-measure on newer data
  ✅ No code approved yet
  ❌ Already measured at 0; the risk is structural, not a count
D) Defer
  ✅ Smaller B4 diff
  ✅ Tracked for later
  ❌ Leaves a known consistency hole in a new feature
Net: one shared selection, or simpler per-item calls with a latent drift.
Header: D13 union
Options:
A) Apply: one union per vote (recommended)
Per-report map vote key → union of its TOPs' Vorgang ids; persist and render both pass it to vote_vorgang_ids; test a vote under 2 TOPs gets one selection everywhere. (human: ~1h / CC: ~5 min)
B) Keep per-TOP
vote_context(vote, item, cache) as planned; no union. (human: 0 / CC: 0)
C) Investigate
No new probe (already 0/8); return to this choice. (human: 0 / CC: 0)
D) Defer
Per-TOP now; TODOS entry 'unify vote context linked ids with report_politikfelder'. (human: ~5min / CC: ~1 min)

State: approved
Actual answer: A) Apply: one union per vote (D13, user answer 2026-10-19)
Accepted scope:
- Build one per-report map from vote key to the union of its TOPs' Vorgang ids, the same union `report_politikfelder` uses.
- Persist and render both pass it to `vote_vorgang_ids`, so the signature is `vote_context(vote, report, cache)`.
- Test: a vote under 2 TOPs gets one selection on both panels and in `vote_proceedings`.
History: none

### R12: committee wording for votes not on a Beschlussempfehlung (O6)
Finding: O6, Low→Medium, 6/10 (medium confidence: the number of wrong attributions is not measured). Plan Slice 3 renders "Federführender Ausschuss: <name>". Reviewer: outside voice, partly verified by the parent.
Plan baseline: "Federführender Ausschuss: <name> (Beschlussempfehlung <Drucksache link>)" (unapproved proposal).
Runtime evidence: 14 of 16 Entschließungsantrag-related votes get a Beschlussempfehlung committee [measured]. A vote taken directly on an Entschließungsantrag can carry the law's Beschlussempfehlung number, so "federführend" would describe the law, not the motion. How many of the 14 are such cases is not measured.
Comparison grid:

| Choice | Current | A Apply | B Keep | C Investigate | D Defer |
|---|---|---|---|---|---|
| R12 committee line | "Federführender Ausschuss: X" | cite the document instead of claiming a role for this vote: "Beschlussempfehlung des <Ausschuss> (Drucksache <link>)", true for every matched case. The data stays the same (`urheber`, source Drucksache) | wording as planned | read the 16 votes' titles and numbers by hand, count wrong attributions; no code | wording as planned, TODO to special-case Entschließungsanträge |
| R1 (D3), D1 recipe | approved | unchanged; the recipe column is named `beschlussempfehlung_urheber` | unchanged | unchanged | unchanged |

Question D14:
D14 — How should the panel word the committee line so it is never wrong?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: We find the committee by spotting a Beschlussempfehlung among the vote's documents. For a vote on a law, its committee was in charge. But when the Bundestag votes on a side motion (Entschließungsantrag) to that law, the same document is listed, so 'Federführender Ausschuss' would wrongly name the law's committee as in charge of the motion. Saying 'Beschlussempfehlung des Haushaltsausschusses (Drucksache …)' just cites the document, which is true in every case.
Stakes if we pick wrong: some panels (up to 14 measured candidates) name a committee as responsible for a motion it never handled.
Recommendation: A because it states only what the source shows and still answers 'which committee' for a reader.
Completeness: A=10/10, B=6/10, C=7/10, D=6/10
Pros / cons:
A) Apply: cite the document (recommended)
  ✅ True for laws, motions and Entschließungsanträge alike; no special cases
  ✅ Still names the committee and links the source Drucksache
  ❌ Doesn't say 'federführend' in words where it would be correct
B) Keep 'Federführender Ausschuss'
  ✅ Plain role statement readers recognise
  ✅ Correct for the large majority of matched votes
  ❌ Wrong for votes taken directly on a side motion
C) Investigate first
  ✅ Hand count of the 16 Entschließungsantrag votes settles how big the problem is
  ✅ No wording change approved yet
  ❌ Comes back to the same choice, and the answer still needs a rule
D) Defer
  ✅ Smallest change now
  ✅ Tracked as a TODO
  ❌ Ships a wording we know is wrong for some votes
Net: always-true citation, or a familiar role label that's sometimes wrong.
Header: D14 wording
Options:
A) Apply: cite the document (recommended)
Committee line reads 'Beschlussempfehlung des <Ausschuss> (Drucksache <link>)'; recipe column named beschlussempfehlung_urheber; test the wording incl. an Entschließungsantrag fixture. (human: ~20min / CC: ~2 min)
B) Keep 'Federführender Ausschuss'
Wording as planned. (human: 0 / CC: 0)
C) Investigate first
Hand-check the 16 votes' titles and numbers; count wrong attributions; return to this choice. (human: ~30min / CC: ~5 min)
D) Defer
Wording as planned; TODO 'special-case Entschließungsantrag votes in the committee line'. (human: ~5min / CC: ~1 min)

State: approved
Actual answer: A) Apply: cite the document (D14, user answer 2026-10-19)
Accepted scope: the committee line reads "Beschlussempfehlung des <Ausschuss> (Drucksache <link>)", or "Ausschuss nicht ermittelt" when there is no match. The `r-ausschuss` recipe column is named `beschlussempfehlung_urheber`. The wording test includes an Entschließungsantrag fixture.
History: none

### R13: per-vote committee comparison in the replay (O5)
Finding: O5, Low, 6/10. The D10 replay compares Daten CSVs, but the panel committee (from the report map, D3) is checked only as a total against the store (190 = 190). The store `documents` table is store-wide, so a Beschlussempfehlung linked in another sitting can fill the store but not the report map. Reviewer: outside voice; not measured per vote.
Plan baseline: D10 approved the CSV diff and totals (unchanged by this row).
Runtime evidence: totals are equal (190/190) [measured]; per-vote equality is unknown.
Comparison grid:

| Choice | Current | A Apply | B Keep | C Investigate | D Defer |
|---|---|---|---|---|---|
| R13 replay depth | totals only | the replay also asserts, per vote, that the set of `vote_committees(vote, report)` equals the store's Beschlussempfehlung `urheber` set via `vote_documents`→`documents`, and lists any vote that differs | totals only | run that per-vote comparison once now on the reference store (read-only), no code | totals only; TODO |
| R8 (D10) | approved: CSV diff | unchanged | unchanged | unchanged | unchanged |

Question D15:
D15 — Should the replay check committees vote by vote, not just in total?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: The page finds committees within one sitting's documents, and the database finds them across all stored documents. Both total 190, but equal totals could hide one vote gained and another lost. Checking each vote's committee on both sides shows whether they really match.
Stakes if we pick wrong: a few votes could show a different committee on the page than in the download, and the totals would still match.
Recommendation: A because it reuses the replay we already run and turns a coincidental total into a per-vote proof.
Completeness: A=10/10, B=7/10, C=8/10, D=6/10
Pros / cons:
A) Apply: per-vote check in replay (recommended)
  ✅ Proves page and download agree for every vote, not only in sum
  ✅ Rides on the D10 replay; about 20 lines of verification script
  ❌ Slightly longer verification step, run once per PR
B) Keep totals
  ✅ No extra verification work
  ✅ Totals already match (190 = 190)
  ❌ Offsetting differences would go unnoticed
C) Investigate now
  ✅ A one-off read-only comparison answers it today
  ✅ No ongoing check to maintain
  ❌ Doesn't guard future builds
D) Defer
  ✅ Nothing to do now
  ✅ Tracked for later
  ❌ Same blind spot as Keep, plus a TODO
Net: a small proof per vote, or trust in matching totals.
Header: D15 check
Options:
A) Apply: per-vote check in replay (recommended)
Replay step compares per vote vote_committees(vote, report) against store BE urheber via vote_documents→documents; lists differing votes; any difference is reported old/new before ship. (human: ~45min / CC: ~5 min)
B) Keep totals
Replay keeps the totals comparison only. (human: 0 / CC: 0)
C) Investigate now
One read-only per-vote comparison on the reference store now; no code; return to this choice. (human: ~15min / CC: ~3 min)
D) Defer
Totals only; TODO 'per-vote committee parity check'. (human: ~5min / CC: ~1 min)

State: approved
Actual answer: A) Apply: per-vote check in replay (D15, user answer 2026-10-19)
Accepted scope: the replay compares each vote's `vote_committees(vote, report)` with the store's Beschlussempfehlung `urheber` set via `vote_documents`→`documents`, and lists any vote that differs. Any difference is reported old/new before ship.
History: none

## TODO proposals

### T1: store `vote_members` disagree with `vote_fractions` in 21 groups
Finding: found while verifying O4. P2, 8/10, measured on the reference store via a store SQL join of per-group `vote_members` counts to `vote_fractions`.
- **What:** in 21 of 1498 groups across 11 votes, the stored member rows don't add up to the stored fraction counts. Most are off by exactly one member: SPD 188 vs 187 on 2023-06-15, 2023-05-26; Grüne and FDP on 2022-05-20. One fraktionslos group on 2024-02-02 stores 5 members against 40 Ja. The report JSON matches 1498/1498, so rows are lost or re-attributed at persist. Likely causes: namesake occurrence-key collisions (`stable_ids.vote_member_occurrence_id` is built from name + Zusammenschluss), and the party attribution of former Linke/BSW MdBs.
- **Why:** every store-side Abweichler figure (`r3-abweichler`, Fakten `meiste-abweichler`) and the Daten `vote_members` CSV inherit it. The citable dataset is missing Stimmen.
- **Pros:** fixes a silent loss in the export; the B4 parity test then holds per group on the store too.
- **Cons:** touches identity and stable ids (A.2 territory); possibly a stable-id format change.
- **Context:** start from the 11 vote ids in the store query above, and check `vote_member_occurrence_id` collisions for namesakes.
- **Depends on:** none. It is independent of B4.
Question D16:
D16 — Add the 'store loses roll-call member rows' defect to TODOS.md?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: While checking the Abweichler math, the reviewer found that our database drops or misfiles a member's vote in 21 party groups across 11 votes, mostly one MdB at a time. The source files are correct; the loss happens when we save them. It isn't caused by B4, but it makes the downloaded vote records incomplete.
Stakes if we pick wrong: the citable download silently misses individual Stimmen, and store-side Abweichler counts can be off.
Recommendation: A because it's a real data-loss bug in a published table, outside B4's scope, and it needs an identity-focused fix of its own.
Pros / cons:
A) Add to TODOS.md (recommended)
  ✅ Tracks a measured data-loss bug with its 11 vote ids and likely cause
  ✅ Keeps B4 out of identity and stable-id code
  ❌ The bug stays in the store until someone picks it up
B) Skip
  ✅ No TODO noise
  ✅ Nothing to maintain
  ❌ A known loss in the citable dataset goes untracked
C) Build it now in B4
  ✅ Fixed before B4's export format bump, so one format change covers both
  ✅ B4's parity test holds on the store per group
  ❌ Pulls identity and stable-id work into a 14-file feature PR
Net: track a real bug separately, or widen B4 into identity code.
Header: D16 T1
Options:
A) Add to TODOS.md (recommended)
New P2 entry under Daten with What/Why/Context above and the 11 vote ids. (human: ~10min / CC: ~2 min)
B) Skip
No TODO. (human: 0 / CC: 0)
C) Build it now in B4
Diagnose and fix the member-row loss in this PR, report old/new member counts. (human: ~1 day / CC: ~1h)
State: approved
Actual answer: A) Add to TODOS.md (D16, user answer 2026-10-19)
Accepted scope: a new P2 entry under "## Daten" in TODOS.md with the What/Why/Pros/Cons/Context above and the 11 vote ids. It is written during implementation, because host plan mode forbids editing TODOS.md now (not persisted yet).
History: none

### T2: mitberatende committees from `ueberweisung`
- **What:** keep `ueberweisung` (`ausschuss`, `federfuehrung`) from the 1. Beratung positions, which `compact_position` (validate_dip_protocol.py:1205) drops today. Show "mitberatend: …" next to the Beschlussempfehlung line.
- **Why:** abgeordnetenwatch lists the committees involved. B4 cites only the issuing committee of the Beschlussempfehlung (D14).
- **Pros:** completes the "committees involved" picture; the data is already in the cached raw positions (1,650 `federfuehrung: true` entries).
- **Cons:** `ueberweisung` sits on the 1. Beratung, not the vote's TOP, so it needs a Vorgang-level join (`vote_proceedings` from B4 helps); one more stored table.
- **Context:** `api.raw.positions` in cached reports; B4's `vote_proceedings` gives the vote→Vorgang link.
- **Depends on:** B4.
Question D17:
D17 — Add 'show mitberatende committees' as a follow-up TODO?
Project/branch/task: B4 daily-view Abstimmungen plan on worktree-b4-abstimmungen-daily-view.
ELI10: B4 names the committee that wrote the Beschlussempfehlung. Bills are usually also sent to other committees for an opinion (mitberatend). DIP records that on the first reading, and our raw cache already holds it, but B4 doesn't use it. Once B4 links each vote to its Vorgang, this becomes a small follow-up.
Stakes if we pick wrong: either the backlog gains a nice-to-have nobody picks up, or the 'committees involved' gap to abgeordnetenwatch stays unrecorded.
Recommendation: A because the data already exists, B4's vote→Vorgang link makes it cheap, and it closes a named gap to the reference site.
Pros / cons:
A) Add to TODOS.md (recommended)
  ✅ Records a concrete, cheap follow-up with its data source
  ✅ Builds on B4's vote_proceedings link instead of re-deriving it
  ❌ One more P3 item in a long backlog
B) Skip
  ✅ Keeps the backlog focused on v1 roadmap items
  ✅ The B4 TODO never asked for it
  ❌ The gap to abgeordnetenwatch's 'committees involved' stays unrecorded
C) Build it now in B4
  ✅ Panel shows all committees at once
  ✅ Data is already cached
  ❌ Adds a new stored table and join to an already large PR
Net: a recorded cheap follow-up, or a leaner backlog.
Header: D17 T2
Options:
A) Add to TODOS.md (recommended)
New P3 entry under '## Abstimmungen' with the What/Why/Context above; Depends on: B4. (human: ~5min / CC: ~1 min)
B) Skip
No TODO. (human: 0 / CC: 0)
C) Build it now in B4
Keep ueberweisung in compact_position, store per Vorgang, render 'mitberatend: …'; tests. (human: ~4h / CC: ~25 min)
State: approved
Actual answer: A) Add to TODOS.md (D17, user answer 2026-10-19)
Accepted scope: a new P3 entry under "## Abstimmungen" in TODOS.md with the What/Why/Pros/Cons/Context above; Depends on: B4. It is written during implementation (not persisted yet).
History: none

Approval readiness: PASS. Checked, each with its own answer:
- R1 (D3), R2 (D5), R3 (D6), R4 (D7), R5 (D4), R6 (D8), R7 (D9), R8 (D10), R9 (D11), R10 (D12), R11 (D13), R12 (D14), R13 (D15), T1 (D16), T2 (D17).
- Scope: D1, D2.
- Corrections F5, F7 and C1 are necessary implementation of the approved scope.

## Test review (Section 3)

Framework: unittest, `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`. A single file runs with `-p test_x.py` (prior learning: single-test-file-unittest-invocation, 10/10, 2026-10-08).

```
CODE PATHS (proposed)                                      USER FLOWS
[+] derive.vote_abweichler(vote)                           [+] Archive → panel
  ├── [GAP] Ja vs Nein-Mehrheit / Nein vs Ja-Mehrheit        ├── [GAP] topic chip filters → row → #vote-<id> lands (D9)
  ├── [GAP] tie / Enthaltung-Mehrheit / nobody voted         ├── [GAP] vote under 2 TOPs: one id, link hits first
  ├── [GAP] fraktionslos / unknown faction / spelling var.   └── [GAP] id-less legacy vote keeps #top-N
  ├── [GAP] state: complete / partial / none (1002 fixture)  [+] Panel reading
  └── [GAP] parity with r3 SQL minus LIMIT (632 on ref)      ├── [GAP] 0 / 1 / 10 / 11 / 62 Abweichler (D6)
[+] derive.vote_committees(vote, report)                     ├── [GAP] "keine Abweichler" only when all complete
  ├── [GAP] BE under own TOP                                 ├── [GAP] "Einzelstimmen unvollständig" never reads as 0
  ├── [GAP] BE under another TOP (D3; 5 real cases)          ├── [GAP] abstract teaser + <details> full text
  ├── [GAP] no BE (plain Antrag) → "Ausschuss nicht erm."    ├── [GAP] several Vorgänge labelled separately
  └── [GAP] two urheber (Vermittlungsausschuss case)         └── [GAP] none vs not_fetched wording differs
[+] politikfelder.vote_vorgang_ids                         [+] Error/empty states
  ├── [GAP] narrow tier only; wide never used for prose      ├── [GAP] cache missing → "Vorgang nicht abgerufen"
  ├── [GAP] narrowed to TOP Vorgänge when they intersect     └── [GAP] abstract with <script>/<strong>/CRLF → clean text
  ├── [GAP] missing number → not_fetched
  └── [GAP] parity with tags_for_vote on narrow-tier votes (D8)
[+] politikfelder.abstract_text (HTMLParser, F7)
  └── [GAP] <br>→para, tags stripped, entities, nested/malformed
[+] persist: proceedings.abstract, vote_proceedings, votes.context_state
  ├── [GAP] fresh store schema 6; old store refused w/ repersist msg
  └── [GAP] three context states round-trip to export (D7)
[+] export format 6: captions + provenance for new cols/table
  └── [GAP] round trip; manifest export_format=6
[+] _vote_procedure_type sitting-wide (D4)
  └── [★★ TESTED → UPDATE] build_dip:2377,:2426 + new cross-TOP row
[+] r-ausschuss recipe (D1)
  └── [GAP] rows == vote_committees on temp store
EXISTING (regression contract D10)
  ├── [★★★ TESTED] badge/inversion/docs/XLSX/merge/member links — test_features_votes.py
  ├── [★★ TESTED → UPDATE] archive anchors — test_b1_consumers.py:59,:91 (D9)
  ├── [★★★ TESTED] tags — test_politikfelder.py (must pass untouched, D8)
  └── [★★ TESTED] r3 predicate — test_mehrheitsvotum.py:170-202
[→E2E] replay diff on reference-store copy (D10), 900 s bound

COVERAGE (proposed new paths): 0/31 tested today, all specified below | existing guarded: 4 groups
QUALITY target: ★★★ for derive/politikfelder helpers; ★★ for rendering | GAPS: 31 (1 E2E replay, 0 eval)
```

No LLM or prompt change; the AI fallback is deferred, so no eval scope.

**Tests to add** (extend existing files; every one has a value card in the test plan below):
- `tests/test_features_votes.py`: new `AbweichlerPanelTests` (D6 counts, the three states, links, inversion unchanged) and `VoteContextPanelTests` (abstract, several Vorgänge, none vs not_fetched, committee lines, anchor id once).
- `tests/test_derive.py` (or `test_mehrheitsvotum.py` for parity): `vote_abweichler` table cases plus SQL parity; `vote_committees` cross-TOP, none, two urheber.
- `tests/test_politikfelder.py`: `vote_vorgang_ids` cases, the `abstract_text` table, and the narrow-tier parity with `tags_for_vote`.
- `tests/test_persist_dip_pulse_store.py` / `test_repersist.py`: schema 6 fresh, old refused, context_state persisted.
- `tests/test_daten_export.py`: format 6 round trip, captions and provenance for the new columns and table, the r-ausschuss recipe.
- `tests/test_build_dip_pulse_site.py` and `test_b1_consumers.py`: intentional href and procedure-type updates, plus a cross-TOP row and a duplicated-vote anchor.

**Tests made obsolete:** none. The href assertions are updated, not retired.

### Test plan artifact
Not persisted to `~/.gstack/projects/LucaAlv-poliwatch/` because host plan mode allows writes only to this file. Copy it there when implementation starts.

```markdown
# Test Plan
Generated by /plan-eng-review on 2026-10-19
Branch: worktree-b4-abstimmungen-daily-view
Repo: LucaAlv/poliwatch

## Affected Pages/Routes
- /votes/index.html: rows link to #vote-<id>, Abweichler badge, sitting-wide procedure type
- /protocols/<sitting>.html: vote panel context block, committee line, Abweichler lists, panel id
- Daten page and export: format 6, new captions, r-ausschuss recipe

## Key Interactions to Verify
- Filter by Politikfeld chip, click a row, land on that vote's panel (not just the TOP) on votes/index.html
- Expand "alle N anzeigen" on the 2023-07-06 Suizidhilfe vote panel
- Expand the full DIP abstract <details> on a vote with a long abstract

## Edge Cases
- Vote listed under 2 TOPs: exactly one id="vote-<id>"
  Value: protects=one valid anchor per vote; fails_when=both copies get the id; why_new=no anchor exists today; seam=none; no_claim=browser scroll behaviour (static HTML assert)
- Vote with fractions but no members (roll_call_1002): "Einzelstimmen unvollständig", never "keine Abweichler"
  Value: protects=partial data never reads as zero; fails_when=state check dropped; why_new=no Abweichler code exists; seam=none; no_claim=none beyond protects
- Beschlussempfehlung linked under another TOP: committee still found
  Value: protects=page==store committee (190/217); fails_when=lookup narrowed to item; why_new=new detector; seam=none; no_claim=DIP urheber accuracy
- Abstract with <script>, <strong>, <br />\r\n: rendered as escaped plain paragraphs
  Value: protects=no markup injection from DIP text; fails_when=sanitizer skipped or regex misses nesting; why_new=no abstract rendering today; seam=none; no_claim=none beyond protects
- context_state none vs not_fetched: different panel copy and export value
  Value: protects=export separates absent from unfetched; fails_when=both collapse to no row; why_new=new column; seam=none; no_claim=live DIP outage behaviour (fixture cache)

## Critical Paths
- Python Abweichler set equals r3-abweichler SQL without LIMIT on the temp store
  Value: protects=one Abweichung rule across page, recipe, Fakten; fails_when=Python and SQL predicates drift; why_new=no Python predicate exists; seam=none; no_claim=reference-store parity (that's the replay)
- Replay diff on reference-store copy: only new columns/tables differ; tags 0 moved; Abweichler 632; committees 190; abstracts ~153
  Value: protects=no unintended figure moves in the citable export; fails_when=any existing CSV cell changes; why_new=unit fixtures lack real shapes; seam=none; no_claim=WP coverage beyond the reference store
- tags_for_vote untouched: test_politikfelder.py passes unchanged
  Value: protects=shipped B3 tags; fails_when=refactor leaks into tags; why_new=covered_elsewhere (existing suite is the guard); seam=none; no_claim=none beyond protects

## Tests to Retire
- none

## Pending Decisions
- none
```

Section 3 dispositions: F9 (regression contract) accepted, D10. The test requirements above follow from D3–D10 and need no further question.

## Performance review (Section 4)
No issues found.
- The sitting-wide number map is built once per report: O(linked Drucksachen), about 10–100 per sitting [estimated].
- `vote_vorgang_ids` does dict lookups per vote.
- The sanitizer runs once per vote with an abstract: 153 abstracts, median 451 characters, max 5,111 [measured].
- Persist adds about 217–300 `vote_proceedings` rows on the reference store [estimated], all in the existing persist transaction.
- Implementation note: `collect_votes_archive` must build the map once per entry (report), not once per vote.
- No queries run in loops, since render does not read the store (D3).
- D11/D12 add about 1–3 extra DIP `/vorgang` batches per online build. They go through the existing 0.5 s pacing and the 5-failure breaker (`refresh_vorgang_cache`, build_dip_pulse_site.py:1528).

### Test additions from the outside-voice round (D11–D15)
- test_politikfelder.py:
  - `fetch_targets` wants vote-resolved ids with an empty abstract or no `titel` key, and does not want ones with both.
  - `vorgang_cache_record` keeps `titel`.
- test_features_votes.py:
  - The context label uses `titel`, falling back to "<vorgangstyp> · DIP-Vorgang <id>" when `titel` is absent (F10).
  - A vote under 2 TOPs gets one Vorgang selection on both panels (D13).
  - The committee line wording, including an Entschließungsantrag fixture (D14).
- Replay: the per-vote committee comparison (D15).
- Test-plan artifact addenda (value cards):
  - Value: protects=panel's "Keine Beschreibung in DIP" is current; fails_when=empty-abstract ids are not refetched; why_new=fetch_targets only refetches on empty Sachgebiet; seam=none; no_claim=live DIP timing (fixture cache)
  - Value: protects=committee line never claims a role; fails_when=wording reverts to "Federführender Ausschuss"; why_new=new wording; seam=none; no_claim=none beyond protects

### F10: label fallback when `titel` is absent (necessary implementation, no question)
An offline build, and the reference replay, run on a cache whose records have no `titel` until the next online build (D12). Rendering must fall back to "<vorgangstyp> · DIP-Vorgang <id>" so blocks are still distinguishable. Approved as necessary implementation of D12 for the offline path.

## NOT in scope
- **AI fallback sentence for votes without an abstract:** deferred by the user's answer; it waits for "Deterministic validators". B4's TODO stays open for this one part.
- **Mitberatende committees:** this is TODO T2 (D17); `ueberweisung` sits on the 1. Beratung, not on the vote.
- **Render-vs-export drift guard:** tracked in B3 deferred item 3 together with tags (D5).
- **Moving the Vorgang cache out of published `data/`:** left to "Site hosting plan"; B4 rewrites B3 item 4's text only.
- **The store member-row loss (21 groups):** TODO T1 (D16); it is an identity fix, independent of B4.
- **XLSX ingestion (B5), date filters on the archive, a vote-detail route, the dataset/site split:** outside B4 per the repo plan doc.

## What already exists (reused, not rebuilt)
- Vote figures: `derive.majority_vote`, `merge_fractions`, `zusammenschluss`, `iter_report_votes`, `vote_member_key` (derive.py).
- Member links: `html.mp_page_href` with the `source_url` fallback (votes.py:166-175), factored into one helper for Einzelstimmen and Abweichler.
- Vorgang resolution: `politikfelder._vorgaenge_of_numbers` tiers; `report_politikfelder`'s linked-id union (D13).
- Cache: `vorgang_cache_record` (already keeps `abstract`), `fetch_targets`, `refresh_vorgang_cache` pacing and breaker, `load_cache`/`save_cache` private staging.
- Store/export: `documents.origin_json` already holds `urheber`; `require_current_schema` refusal; the export provenance tags and captions machinery.
- Rendering: `render_html` already receives `vorgang_cache` (render_dip_pulse_html.py:2921); B3's archive chips and filter stay as they are.
- r3 predicate SQL (build_dip_pulse_site.py:2572) as the parity reference.

## Diagrams

```
online build                                     offline build / render
------------                                     ----------------------
reports ──► fetch_targets ──► DIP /vorgang ──┐   cache (dip-vorgang-cache.json)
  (D11: empty abstract, D12: no titel)       │        │
                                             ▼        ▼
                                vorgang_cache_record {sachgebiet, abstract, titel, ...}
                                             │
       ┌─────────────────────────────────────┴────────────────────────┐
       ▼                                                              ▼
persist_report                                                render_html
  per report: linked-id union (D13) ─► vote_vorgang_ids ◄─ same call, same cache
  ├─ vote_proceedings(vote, proceeding, rank)                  ├─ "Worum es geht" blocks (titel · DIP | fallback F10)
  ├─ votes.context_state (resolved|none|not_fetched, D7)       ├─ committee line from report-wide BE map (D3, D14)
  └─ proceedings.abstract/title                                ├─ Abweichler per group (≤10 + <details>, D6)
       │                                                       └─ id="vote-<id>" on first panel (D9)
       ▼                                                              │
Daten export format 6 (captions, provenance)                  votes/index.html href → #vote-<id>
       ▲ drift vs page after cache refresh w/o repersist: B3 item 3 (D5)
```

```
vote_abweichler state per group:
  members empty ───────────────► none     → "Einzelstimmen unvollständig – Abweichler nicht ermittelbar"
  member counts ≠ fraction counts ► partial → same note, never "keine"
  counts match ─► majority_vote ∈ {yes,no}? ─no─► no Abweichung possible
                                   └─yes─► members with opposite Ja/Nein (not fraktionslos) → list
  all groups complete and empty ─► one "keine Abweichler" line
```

The inline-diagram candidate in code is the `vote_abweichler` docstring, which should carry the state table above.

## Failure modes

| Path | Realistic failure | Handling | Test | User sees |
|---|---|---|---|---|
| D11/D12 refetch | DIP outage or bot challenge | existing breaker; records stay as they were | breaker covered by B3 tests | old text or "Vorgang nicht abgerufen", not silent |
| abstract render | malformed or nested HTML in DIP text | HTMLParser strip then escape (F7) | sanitizer table test | clean text |
| titel absent (offline, old cache) | label missing | F10 fallback label | label fallback test | "Gesetzgebung · DIP-Vorgang N" |
| Abweichler | partial member data | state `partial` | 1002 fixture test | explicit "unvollständig" note |
| committee | Beschlussempfehlung under another TOP | sitting-wide map (D3) | cross-TOP test | correct citation |
| committee | Entschließungsantrag vote | document-citation wording (D14) | wording test | true statement |
| anchor | vote under 2 TOPs | first-panel id (D9) | duplicate-vote test | link lands on the first panel |
| export | cache refreshed, no repersist | none in B4 (D5); tracked in B3 item 3 | none | page and CSV differ until the next persist (**known, tracked; not silent in the TODO**) |
| store member loss | 21 groups short by one | none in B4 (T1) | none | export misses Stimmen (**pre-existing, tracked as T1**) |

Critical gaps (no test, no handling, and silent): **0** inside B4's scope. The two rows with no handling are pre-existing or explicitly deferred, and each is tracked.

## Worktree parallelization strategy

| Step | Modules touched | Depends on |
|---|---|---|
| S1 Abweichler | scripts/derive, scripts/features/votes | — |
| S2a cache shape + refetch | scripts/validate_dip_protocol, scripts/politikfelder | — |
| S2b store/export schema 6 | scripts/persist_dip_pulse_store, scripts/build_dip_pulse_site (export) | S2a |
| S2c context render | scripts/features/votes, scripts/render_dip_pulse_html | S2a, S1 (shared votes.py) |
| S3 committees + recipe | scripts/derive, scripts/features/votes, scripts/build_dip_pulse_site (recipe, archive) | S1 |
| S4 anchors, archive, TODOS/docs | scripts/render_dip_pulse_html, scripts/build_dip_pulse_site, docs, TODOS.md | S2c, S3 |

- **Lane A:** S2a → S2b (cache, store, export).
- **Lane B:** S1 → S3 (derive, votes render).
- **Execution order:** launch A and B together. When both are merged, do S2c, then S4.
- **Conflict flags:** `scripts/features/votes.py` (S1, S2c, S3) and `scripts/build_dip_pulse_site.py` (S2b export, S3 recipe, S4 archive) must be sequenced.

## Implementation Tasks
Synthesized from this review's findings. Each task derives from a specific finding above. Run with Claude Code or Codex; checkbox as you ship.
Effort assumptions: features ~30x, tests ~50x, bug fix ~20x (human ÷ CC).

- [x] **T1 (P1, human: ~2h / CC: ~10min)**: derive: sitting-wide committee map and `vote_committees(vote, report)`
  - Surfaced by: Architecture F1 (D3), 185 vs 190.
  - Files: scripts/derive.py, tests/test_derive.py or test_mehrheitsvotum.py
  - Verify: unittest; replay expects 190/217, plus the per-vote check (D15)
- [x] **T2 (P1, human: ~2h / CC: ~10min)**: cache: keep `titel`; refetch vote Vorgänge with an empty abstract or no titel
  - Surfaced by: Outside voice O1/O2 (D11, D12)
  - Files: scripts/validate_dip_protocol.py, scripts/politikfelder.py, tests/test_politikfelder.py
  - Verify: unittest; the next online build reports old/new abstract count for the 64 votes
- [x] **T3 (P2, human: ~3h / CC: ~15min)**: Abweichler predicate and panel with a 10-name fold and three states
  - Surfaced by: Architecture F3 (D6); the state rule from plan Slice 1
  - Files: scripts/derive.py, scripts/features/votes.py, tests/test_features_votes.py, tests/test_mehrheitsvotum.py (per-vote SQL parity, C1)
  - Verify: unittest; replay total 632
- [x] **T4 (P2, human: ~4h / CC: ~20min)**: store/export schema 6 (`proceedings.abstract`/`title`, `vote_proceedings`, `votes.context_state`)
  - Surfaced by: Architecture F4 (D7); plan Slice 2
  - Files: scripts/persist_dip_pulse_store.py, scripts/build_dip_pulse_site.py, tests/test_persist_dip_pulse_store.py, tests/test_daten_export.py, tests/test_repersist.py, docs/data-license.md
  - Verify: unittest; the export round trip; the old store is refused
- [x] **T5 (P2, human: ~3h / CC: ~15min)**: context render with the union of linked ids, title labels with a fallback, and sanitizer
  - Surfaced by: O3 (D13), D12, F10, F7, F5 (ctx threading)
  - Files: scripts/politikfelder.py, scripts/features/votes.py, scripts/render_dip_pulse_html.py, tests
  - Verify: unittest; DevTools check at desktop and 375px
- [x] **T6 (P2, human: ~1h / CC: ~5min)**: committee wording cites the Beschlussempfehlung; `r-ausschuss` recipe
  - Surfaced by: O6 (D14), D1
  - Done on b4-lane-b: the recipe id is `r6-ausschuss`, numbered like r1–r5.
  - Files: scripts/features/votes.py, scripts/build_dip_pulse_site.py, tests
  - Verify: unittest, including the Entschließungsantrag fixture
- [x] **T7 (P2, human: ~1.5h / CC: ~8min)**: first-panel anchor, archive href, sitting-wide procedure type
  - Surfaced by: Test review F8 (D9), F1 side effect (D4)
  - Files: scripts/render_dip_pulse_html.py, scripts/build_dip_pulse_site.py, tests/test_b1_consumers.py, tests/test_build_dip_pulse_site.py
  - Verify: unittest; report the old/new '–' count
- [x] **T8 (P2, human: ~2h / CC: ~15min + 5min replay)**: regression contract and replay diff
  - Surfaced by: Test review F9 (D10), D15
  - Files: (verification only)
  - Verify: full suite green; the CSV diff shows only new columns and tables
- [x] **T9 (P3, human: ~30min / CC: ~5min)**: docs and TODOS
  - Surfaced by: Step 0, D5, D16, D17, B3 item 4
  - Files: docs/plans/b4-daily-votes.md, TODOS.md (B4 parts done, B3 items 3 and 4 text, T1 P2 entry, T2 P3 entry)
  - Verify: read-through

Task JSONL for /autoplan: not persisted (host plan mode allows writes only to this file).

### Implementation result (2026-10-20, T5/T7/T8/T9 after merging b4-lane-a and b4-lane-b)
Replay on copies of the reference store, `--offline --repersist`, cffa6aa (409 s) vs this branch (423 s):
- D10: the Daten CSVs are 27 → 28 (`vote_proceedings`, 260 rows). The only other differences are the new columns `proceedings.abstract` and `votes.context_state` and the `datenstand` row (export format 5 → 6, hashes). Every other cell is equal: tags 0 moved, 217 votes, and `proceedings` stays at 3,111 rows (no vote-only Vorgang was new to it).
- Store: `context_state` is resolved on 217 of 217, 153 votes have a DIP abstract, and 39 votes resolve to more than one Vorgang (the plan's 42 is reproduced on the narrow tier before narrowing to the TOP union, 42 → 39). The r3 total is 632, the Python total is 632 and the archive `data-abweichler` sum is 632 (95 rows with N > 0).
- D15: the panel and the store both cite a committee on 190 votes, with 0 per-vote differences.
- D4 (page only): the procedure type '–' rows go 5 → 0 (votes 980, 961: Beschlussempfehlung; 898, 894: Gesetzentwurf; 897: Entschließungsantrag), with 0 type→'–' and 0 type→type.
- D9: the 8 votes listed under several TOPs are 8 votes but render 2 to 7 times each (246 panels for 217 votes, not 225); each still has one id.
- D9: all 217 archive links are `#vote-<id>` (before: `#top-N`), and each resolves to exactly one id on its page.
- F10: the reference cache has no `titel` (0 of 7,511), so all 306 context labels on the replay pages are the fallback "<Vorgangstyp> · DIP-Vorgang <id>". The titel path is covered by unit tests only, until an online build.
- The plan's Slice 1 archive badge (`data-abweichler`, "N Abweichler") was missing from lane B and was added with T7.
- Not measured: D11's "how many of the 64 gained an abstract" needs an online build.

## Unresolved decisions
None. D1–D17 were all answered.

## Completion summary
- Step 0: Scope Challenge: scope accepted as-is (D1 kept the recipe; D2 kept the original arrangement)
- Reality rows: 7/7 applicable rows emitted (`PLAN_REALITY: phase=eng rows=7/7 missing=none verdict=complete`), 0 unverified premises
- Architecture Review: 6 issues found (F1, F1 side effect, F2, F3, F4, F5)
- Code Quality Review: 2 issues found (F6, F7)
- Test Review: diagram produced, 31 proposed paths specified, 2 issues (F8 anchor, F9 regression contract)
- Performance Review: 0 issues found
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 2 items proposed to the user (T1 accepted, T2 accepted); written at implementation
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 0 in this review
- Outside voice: Codex preflight was ready, but the run was blocked by the worktree guard. A native Claude subagent fallback completed and found 9 findings: O1, O2, O3, O5 and O6 were resolved through D11–D15; O4, O7 and O8 were corrected (C1); O9 was folded into sequencing. Outside coverage: unavailable.
- Parallelization: 2 lanes, 2 parallel and 2 sequential steps after the merge
- Lake Score: 13/14. 14 answers carried a completeness score (D1, D3–D15), and 13 picked a 10/10 option. D5 chose A (8/10, tracking the drift with B3 item 3).

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Review | codex (blocked by the worktree guard) → native Claude subagent fallback | Independent 2nd opinion | 1 | unavailable (native completed, issues_found) | 9 findings, 5 resolved via D11–D15, 3 corrected, 1 sequencing |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN (not persisted: review log write blocked by plan mode) | 10 issues, 0 critical gaps, all resolved in D3–D10 |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:**
  - Codex was ready, but the plan-review run was not executed: the worktree-isolation guard refused the piped command, and plan mode forbids a temp prompt file.
  - The native Claude Plan subagent completed within its 5-minute bound with 9 findings.
  - External outside coverage: unavailable.
- **VERDICT:** eng review required. This review has no open findings and every decision is answered, but its status is "issues_open" (10 issues found and resolved), and the review log was not persisted.

NO UNRESOLVED DECISIONS
