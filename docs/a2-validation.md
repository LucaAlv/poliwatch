# A.2 implementation and reference validation

Validated on 2026-09-30 with Python 3.13 and re-validated on 2026-10-01 after the pre-landing review changed the merge model (see the last section; the 2026-09-30 figures below describe the earlier model and a different reference cohort). The implementation keeps the two-module arrangement (`stable_ids.py`, `person_registry.py`), compact source identities, pre-upsert occurrence bindings, explicit upgrade replay and staged database replacement. **T1–T5 are complete.** No outside-review clearance is claimed.

## Automated contracts

The existing Python 3.11–3.13 CI matrix is retained. Locally, `python3.13 -m unittest discover -s tests` ran **947 tests, 2 skipped** on 2026-09-30 and, after the review fixes and the removal of assignments and splits on 2026-10-02, **997 tests, 2 skipped**, with no failures. Tests of the removed pre-A.2 compatibility paths were deleted (pre-release rule). The focused A.2 tests (`tests/test_stable_ids.py`, `tests/test_registry_contracts.py`, and `tests/test_registry_invariants.py` with its shared `tests/_registry_fixture.py`: named regressions plus seeded randomized two-build sequences) cover deterministic/namespaced keys, shared rows after reordering/additional sittings, synthetic source IDs, enrichment continuity, disappearance/reappearance and empty input, roster-independent registry carryover, merge aliases and survivor overrides, malformed and disabled corrections (assignments and splits are refused until their redesign), corrupt registry/alias cycles, writer overlap/crash recovery, failed fact writes, missing evidence, Föhr/Mende links, unchanged export reuse, text PKs, receipt ordering and same-page synthetic speeches, read-only person collection, persisted facts assignments, and the zero-network CLI upgrade through rendering and exports. The review added: rebinding an occurrence when the source names a different Redner-ID or DIP id; evidence re-read per build; name-based guesses recomputed (no alias, a guess moves a whole person and cannot tear a reviewed or hard-ID merge, a guess-merged key keeps a redirect page, guesses independent of arrival order); a dossier written twice keeps its printed speaker in the cached JSON; reserved and case-colliding person keys; unsafe keys refused before page writing; stale temp copies and file mode; the CLI error for an incomplete registry; frozen `stable_key` vectors.

The demo builds without network access and passes `--validate-publication`. Script compilation and `git diff --check` pass. Database checks include `PRAGMA foreign_key_check` and `PRAGMA integrity_check`.

## Reference cohort and method

The supplied live store contains only five sittings, while its real cache contains 290 reports. Comparing only that store to a full replay would mix A.2 with previous extraction/derivation changes and 285 newly restored sittings. Therefore the same real cache/store was copied to two scratch directories, one replayed with the original `HEAD` implementation and one with A.2. The original cache/store was read only. Both replays used the existing compact source-selection and replay-order rules.

The cached catalog predates the authoritative-catalog format, so both real replays correctly withhold all facts. It was not upgraded or declared authoritative. To compare metric arithmetic separately, both read-only stores were computed against the same **controlled report-derived cohort** and completeness evidence. That controlled cohort is an audit input, never published as an authoritative catalog.

| Shared-source contract | Before | After |
|---|---:|---:|
| Protocols | 290 | 290 |
| Agenda items | 2,905 | 2,905 |
| Speeches | 35,239 | 35,239 |
| Speech characters | 121,226,257 | 121,226,257 |
| Documents | 8,070 | 8,070 |
| Votes | 217 | 217 |
| Vote fractions | 1,498 | 1,498 |
| Vote members | 154,015 | 154,015 |
| Bill pages | 556 | 556 |
| Canonical person pages | 1,037 | 1,038 |
| Compact source records | 4,555 | 4,556 |
| Consolidated persons with current records | 3,390 | 3,389 |
| Fact rows in real replay | 684 | 684 |
| Published facts in real replay | 0 | 0 |

Speech rows match exactly by `(protocol_id, rede_id)` for sequence, page/quadrant, paragraph count, text, snippet, character count, speech-time faction, unattributed-character measurement and speaking role. Vote totals, interpretation/provenance fields and fraction tallies/majority positions match exactly. Vote-member printed names, factions, choices and multiplicity match exactly. The unrestricted R3 recipe returns 363 rows in both exports.

The only split in speech-person grouping is Redner-ID `11005304`. No other observed speech or vote groups merge or split. Previously one person held 22 speeches / 93,884 characters; now **Alexander Föhr has 13 / 51,884** and **Dirk-Ulrich Mende has 9 / 42,000**. Six ambiguous cached names are assigned from the printed labels in their official XML URLs recorded in `person_corrections.json`. The correction leaves speech-time faction and role evidence unchanged. The split also joins the two corrected speaker components to their respective existing DIP person records (`7647`, `7648`), which have no vote-member rows; three old components become two, explaining the net consolidated-person count decrease of one. Existing vote-person components remain separate under the conservative matching rules. The shared-ID profile is not used as Mende's biography link.

## Metric arithmetic and deterministic ordering

The controlled comparison computes 684 rows on each store, 488 with numeric values. All metric values, denominators, baselines, ranks and eligibility fields are equal except the following intended effects:

- `erste-reden`, 2023-W13: value and participant count **2 → 3**, percentile **0.11538461538461539 → 0.3076923076923077**, because Mende now has his own debut.
- The changed debut enters later history: `erste-reden` percentile changes in 2023-W38 (**0.45714285714285713 → 0.42857142857142855**) and 2024-W49 (**0.6229508196721312 → 0.6065573770491803**).
- `aktivste-abgeordnete` distinct participant counts increase by one in 2023-03 (**474 → 475**), 2023-07 (**229 → 230**), 2023-11 (**460 → 461**), 2024-04 (**418 → 419**) and 2024-06 (**483 → 484**). Their winner values and all other metric arithmetic stay equal.

Receipts use stable source-entity keys and keep `position` solely for presentation. First-speech selection within a person's first day, row-level ties and grouped receipt order now use stable IDs rather than insertion order. The controlled cohort has 95 changed receipt lists: 49 `aktivste-abgeordnete` lists only reorder; 43 `erste-reden` lists comprise 26 reorderings and 17 changed equally valid first-day representative selections (including the added Mende receipt); three `meistdiskutierter-vorgang` lists choose a different source TOP/page representative. The proceeding metric explicitly selects the minimum stable agenda key, so its source representative is deterministic. These changes do not alter other metric arithmetic.

The 17 first-speech receipt selections occur in 2022-W04, W07, W11, W12, W14, W17, W19, W20, W25; 2023-W06, W13; 2024-W46; and 2025-W21, W23, W26, W28, W48. The three proceeding receipt changes occur in 2024-01, 2025-09 and 2025-11. The unit suite also pins stable-key selection for a longest-speech tie and an active-person tie.

## Final replay and public references

The second unchanged full-cache CLI replay exited successfully and retained the exact store bytes, inode, modification time and export generation. Both the demo and real-cache scratch publication pass `--validate-publication`. The final scratch site has 2,917 HTML pages; all 43,044 generated local person links and all 873 alias pages/targets resolve. `PRAGMA foreign_key_check` returns no violations, `PRAGMA integrity_check` returns `ok`, and the current registry passes validation. Historical eligible person URLs also remain available after empty current input, covered by the focused disappearance test.

Temporary disk space was exhausted during an intermediate scratch page render after database/export success. Redundant task-owned scratch outputs were removed and the same store was rendered again; the original store/cache was unaffected. Database safety does not claim whole-site atomic publication.

## Re-validation after the pre-landing review (2026-10-01)

The review changed the registry: persons carry a durable `home_person_id`; merges that rest on a shared Personenkennung and reviewed corrections are durable aliases, while name-based guesses (corroborated name, unique name+party) are recomputed on every reconcile and applied without an alias; evidence is re-read from the source on a record's first touch in a build; an occurrence moves to a new record when the source names a different Redner-ID or DIP id. These are the figures under the final code. The cohort differs from the one above: a database-only replay of the **285 cached reports** of a sandbox copy of the real cache (34,771 speeches, 119,034,799 speech characters, 154,015 vote members), run from its schema 2 store, without rendering pages.

| Check | Result |
|---|---|
| Upgrade replay of the schema 2 store (full re-mint) | succeeds; schema 3; `PRAGMA integrity_check` ok; `foreign_key_check` empty |
| Source records / issued persons / durable aliases / current persons | 4,252 / 4,252 / 0 / 3,386 (the 866 difference are name-based guesses, recomputed, with no alias; unchanged by the final `_guess_merges` group rules) |
| Occurrence bindings | 189,899 |
| Redner-ID `11005304` | Alexander Föhr 13 speeches / 51,884 characters, Dirk-Ulrich Mende 9 / 42,000 (unchanged) |
| Unchanged replay | keeps the store file (same size and modification time) |
| Order independence | a store built from half of the reports and then replayed with all of them groups records into persons exactly like a fresh replay of all reports (identical grouping fingerprint `6f877bf3d1e92af0`) |

The sandbox store has no DIP roster rows, so roster-dependent figures (and the 2026-09-30 person-page and alias-page counts) were not re-measured. Page rendering was not repeated: the disk was nearly full. Redirect pages are written for retired keys and for keys a guess moved to another person; this is covered by `test_a_guess_merged_key_keeps_a_redirect_page`, not by a full-site count.
