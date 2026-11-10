# Registry: retired-only persons, `ever_mdb` from the exact MdB rule, and the Köstering/Krampe duplicate

Status: **plan, 2026-11-10, eng-reviewed (see the report at the end).** Not built. Roadmap Stage 1, item 2, second bullet: TODOS.md "The carried-forward registry diverges from a fresh build after A3" (the open part) together with "Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs".

## Which "part" this is

TODOS.md numbers the registry item in two parts:
1. **Köstering/Krampe split.** His speeches, votes and DIP records were four persons in the replayed store. Healed at the A3 branch tip (2026-10-31): `p-001037` holds `dip:8257`, `aw:178656`, `xml:11005511` and both bundestag.de profiles, and the replay groups like the fresh build (1,942 = 1,942, same fingerprint; re-measured on 09b7c5d and e7b06f3).
2. **Retired-only persons.** 302 persons hold only bindings that no fresh build produces. 289 render a page with no Reden and no votes, and 281 of the 302 are Bundesrat members.

The brief calls part 2 "the Köstering/Krampe split". That is half right. Part 1's grouping is healed, but one residue was left: the retired DIP record `dip:8054` "Jan Köstering" sits alone on `person-v1-6d527d…` and still renders a page (0 Reden, 0 Abstimmungen). That page is a duplicate of Krampe's. A fresh build does not have it, and it is one of the 302 retired-only persons. So this plan covers part 2 in full: the Bundesrat persons, the Köstering duplicate, and the `ever_mdb` evidence behind both.

## Data available while planning

The machine this plan was written on has no store, no cached reports or XML, no `dip-person-cache.json` and no Python 3.11+ (`docs/plans/e4-repersist.md`, "Blocker found while planning"). So the source check the brief asks for (XML Redner-IDs, DIP person ids, roster rows) rests on:
- the Phase 4 record (`docs/plans/a3-phase4.md`, Step 1 diagnosis and "Gate at the branch tip"), which read `full` and the DIP person cache directly;
- TODOS.md re-measurements on 09b7c5d (2026-11-01) and e7b06f3 (2026-11-05);
- the repository's fixtures: `tests/fixtures/offline-v5/plenarprotokoll-21-15.xml:212` prints Redner-ID `11005511` as "Jan Köstering", and `tests/test_shared_redner_ids.py:191` lists Köstering/Krampe among the name changes that one Redner-ID prints;
- the code at 28799ac.

Every figure below is tagged `[measured: source]` or `[estimated]`. Step 0 re-measures each one on the reference store before any code changes. The owed repersists (#141, #143, E4) moved person pages 2,005 → 1,999 (`docs/plans/e4-repersist.md`), so the 2026-11-05 figures are not the baseline.

## Root cause

### A. The Bundesrat persons: a wrong flag that can never clear

1. Before 2026-10-30 the roster took any DIP `funktion` containing "MdB", so "MdBR" and "Stellv. MdBR" counted (352 roster rows over WP 18–21, 151 of them for WP 21) [measured: CHANGELOG, a3-phase4.md].
2. `person_registry.bind` copies that into sticky evidence: `evidence["ever_mdb"] = bool(evidence.get("ever_mdb") or was_mdb)` (`person_registry.py:563-571`). `was_mdb` is read before the first-touch reset, so it survives every later build.
3. `_read_roster_rows` (`build_dip_pulse_site.py:1490-1517`) preserves every `mps` row whose record has `ever_mdb`, even when `is_mdb` is 0. So each `--offline --repersist` upserts the 352 Bundesrat rows again (`:1822-1870`), now with `is_mdb = 0` by the exact rule, and `bind` carries `ever_mdb` forward again. The loop keeps itself going.
4. The preserved rows are taken out of the touched set (`:1867-1869`), so they are stale. A Bundesrat member who never spoke has a person whose only binding is the preserved `roster-v1-…` binding. A store-less build has no such binding: that is the gate's "retired-only" person.
5. `collect_abgeordnete` makes any person with an `ever_mdb` record page-eligible (`build_dip_pulse_site.py:9086-9090`). The person renders "Keine Reden erfasst".
6. An online build with `--enrich mp-roster` does not heal it either. The roster skips Bundesrat members, so their records go untouched and keep the flag.

[measured: TODOS.md, e7b06f3, 2026-11-05]: 302 retired-only persons, 281 of them Bundesrat ("MdBR" in the display name), 289 with a page, 8 linked from the index. Beyond those, 71 live persons hold only a sampled-people roster binding with `ever_mdb` evidence, "many of them Bundesrat or Land office holders". They are live because a cached report's `sampled_people` names them.

### B. Köstering/Krampe: a second DIP record for one person

- DIP keeps two person records for him: 8054 "Jan Köstering" (`aktualisiert` 2025-03-11) and 8257 "Jan Krampe" (2026-10-22, which lists Köstering as an earlier name) [measured: `dip-person-cache.json`, Phase 4 Step 1].
- `dip:8054` is a roster record with an MdB funktion. Its old `mps` row most likely has `is_mdb = 1`.
  - If so, `_read_roster_rows` preserves it through the `row["is_mdb"]` disjunct (`build_dip_pulse_site.py:1515`), not through `ever_mdb`.
  - The page then renders because `mp.is_mdb` short-circuits `has_abgeordnete_page` (`:8974`).
  - Either way, no current input other than that preserved row binds it.
- As a stale record it can join a live person only as a stale roster partner (`_stale_roster_partners`, `person_registry.py:1130-1168`). Two guards there can refuse Krampe: the person already holds a roster record of its own (`:1162`), and the two DIP ids contradict (`:1165`).
  - Which one fires on the real store is **not measured**. In an offline replay `dip:8257` is live only if a cached report samples it.
  - Either refusal is correct as a general rule: two DIP ids normally mean two people. The remedy below does not depend on which one fires.
- `tests/test_registry_contracts.py:165` (`test_preserved_roster_does_not_reactivate_retired_matching_evidence`) pins exactly this outcome for an obsolete DIP id beside a renamed speaker: the obsolete id keeps its own person and an MdB page.
- The fresh store-less build has no `dip:8054`, assuming no cached report samples 8054 (step 0.3 checks).
- An online fresh build whose roster lists both ids would be worse: `dip:8054` would be a live roster record with a hard DIP conflict against Krampe's person, a separate person, listed as a current Abgeordneter. Phase 4 found that with `dip:8054` taking part in matching, "all five stay apart". That was on pre-rule-C code; a test re-checks it on current code.

**The correct partition** has `dip:8054` on Krampe's person. The evidence:
- Redner-ID 11005511 is printed as "Jan Köstering" (21/15) and as "Jan Krampe";
- one bundestag.de member number, 1045564, appears under both slugs (Phase 4, "A name change keeps the number");
- DIP 8257 names Köstering as an earlier name;
- one Fraktion (Die Linke) and one Wahlperiode (21).

`dip:8054` holds one roster binding and no Reden, Beiträge or Stimmen.

### Why replay and fresh disagree, in one line

A replay keeps registry evidence that no current input supports (a Bundesrat `ever_mdb`, a re-issued DIP record's preserved row), and page eligibility and roster preservation trust that evidence. A fresh build never has it.

## Scope

In scope:
1. `ever_mdb` is never true for a record whose roster evidence is a Bundesrat funktion alone. One site, `reconcile`, enforces this before any matching, so the published `person_records.evidence_json` stops saying it.
2. One predicate, `person_registry.roster_member(evidence)`, decides "former roster MdB" for every reader: page eligibility, roster preservation, the stale-partner rule and the gate. It excludes vacated records, Bundesrat-only evidence and re-issued DIP records.
3. A reviewed list of re-issued DIP person records (`dip_successors` in `scripts/person_corrections.json`), with 8054 → 8257 as the first entry.
4. A gate check that proves the replayed and the fresh store render the same person pages, apart from an accounted list of roster-member pages.
5. Docs: `docs/stable-ids.md` (registry paragraph), `CONTEXT.md` (person registry entry), CHANGELOG with old→new figures, and TODOS.md (close both items, file what stays deferred).

Not in scope (each one goes to TODOS.md, see "Deferred"):
- **Pruning registry rows.** Retired-only persons keep their `persons`, `person_records` and `person_bindings` rows (durable keys, `docs/stable-ids.md`). They lose only their page (D3).
- **The MdB-Stammdaten as the authority for `ever_mdb` and name history.** It would settle G3 below and "List MdBs in a government office", but it is a new identity source (A.2 territory).
- **A general rule that joins records across two DIP ids.** Rejected: that is the namesake guard's whole job (`_external_ids_conflict`). Each re-issued record is reviewed (D2).
- **Votes granting a page.** Votes never make a person page-eligible today (`build_dip_pulse_site.py:9081-9090, 8969-8977`). Changing that would mint pages for split WP 18 voter records (TODOS "Apply the voter-link patch"), so it stays out.
- **`is_mdb = not roles or …`** (`build_dip_pulse_site.py:1866`), which makes a preserved row with an empty funktion an MdB forever. Step 0.1 counts such rows. Fix it now only if one is not an MdB.
- **Placeholder Redner-IDs** and **the 187 retired contribution bindings**: different mechanisms, nothing rendered of their own.

## Steps

### 0. Measure on the reference store (read-only, before any code)

Run this on a clone of the reference store as it stands after the E4 repersist (`docs/plans/e4-repersist.md`; the new reference is `full` at main's tip). Run every query against `file:…?mode=ro`, and write the results into this plan's Figures table.

1. **The flag, by funktion class.** Count `person_records` with `ever_mdb` true, grouped by the parsed roster funktion (`roster_bio.function`, else `function`, parsed like `_parse_listish`): exact "MdB", Bundesrat-only ("MdBR"/"Stellv. MdBR", no "MdB"), other, none. Also count `mps.is_mdb = 1` (1,360 [measured: 09b7c5d]) and the `is_mdb = 1` rows with an empty `function`.
2. **Who loses a page.** From `data/abgeordnete.json`, list the persons with a page whose Reden, Beiträge and Stimmen are all 0. Classify each one:
   - Bundesrat-only: loses its page;
   - re-issued DIP record: loses its page;
   - Land office with an exact-MdB funktion: keeps its page;
   - exact-rule roster MdB: keeps its page;
   - other: stops the build and goes to the owner.
3. **Köstering.**
   - Read the `person_records`, `mps` rows (`is_mdb`, `function`) and bindings of `dip:8054` and `dip:8257`, and whether each one is live in a replay.
   - Grep every cached report for 8054 in `sampled_people` and in speaker `dip_person_id`. If a fresh build sees 8054, the fresh fingerprint moves by that binding: record it.
   - Check for any `aw:`-keyed speaker carrying dip 8054. Mapping one to 8257 would collide on `mps.dip_person_id UNIQUE` (`persist_dip_pulse_store.py:192`).
   - Read 8054 and 8257 in `dip-person-cache.json`: funktion, wahlperiode, and the `person_roles` names.
4. **Other re-issued DIP records**, by two searches:
   - (a) Stale roster records (no Redner-ID) whose normalized name+party (`name_party_keys`) a live person with a different DIP id carries.
   - (b) bundestag.de member numbers printed under two name slugs (`bundestag_member_number`, `person_registry.py:680`), the name changes. Check each old name against stale roster records. Five such numbers are known: Köstering/Krampe, Benkstein/Lenk, Cademartori (Dujisin), (Glogowski-)Merten, Santos Firnhaber/Santos-Wintz.

   Each candidate gets Köstering's kind of evidence and becomes a `dip_successors` entry, or stays apart with the reason written down.
5. **G3, the cost of D1.** G3 is a former MdB whose current DIP funktion is Bundesrat-only (for example, now a Land minister).
   - Find them among the Bundesrat-only `ever_mdb` records two ways: a Fraktion role in `person_roles` (`dip-person-cache.json`, read as `land_office_wahlperioden` reads it), and a name match against `mdb_zugehoerigkeiten`.
   - For each one, record what changes. Either a bio-only page with 0/0/0 is removed, or a speaker page loses the roster biography the record supplied as a stale partner.
   - Stimmen never move, because votes give no page and a stale roster record never joins a vote-only person (the partner rule needs a speaker side, `:1159`).
   - See D1 for what happens with the result.
6. **Baseline figures** for the Figures table: person pages, index links, the "Frühere Abgeordnete" section, `abgeordnete.json` entries, `mps` rows, `ever_mdb` records, retired-only persons with and without a page, and Reden, Beiträge and Stimmen per page person (`compare_store_values.py`).

### 1. `ever_mdb` from the exact rule, in one place

- `derive.is_bundesrat_funktion(funktion)`: true when a value is "MdBR" or "Stellv. MdBR". It sits beside `is_mdb_funktion`.
  - Move `_parse_listish` from `build_dip_pulse_site.py:8954` into `derive`, so the registry and the build parse `function` with one function (class 4).
- `person_registry._bundesrat_only(evidence)`: the record's roster funktion (`roster_bio.function`, else `function`) names a Bundesrat office and not exactly "MdB".
- In `reconcile`, right after the touched set is read (`person_registry.py:1248`) and **before the first `_load_rows`**: on every record, touched or not, with `ever_mdb` and `_bundesrat_only`, write `ever_mdb: false`.
  - Running before matching means the stale-partner guard and every later reader see the cleared value in the same replay, so replay 1 converges and replay 2 writes nothing.
  - `bind` is not changed. It still carries `was_mdb`, and the reconcile pass of the same build corrects the result, so the rule has one site.

### 2. One predicate for "former roster MdB"

`person_registry.roster_member(evidence)` returns `(ever_mdb or is_mdb) and not vacated and not _bundesrat_only(evidence) and dip_person_id not in superseded_dip_ids()`. Every reader uses it (class 1):
- `_read_roster_rows`: preserve a row when `roster_member` holds for its record's evidence. This **replaces both disjuncts** at `build_dip_pulse_site.py:1503` and `:1515`. A row without a registry record keeps the `row["is_mdb"]` test, because it has no evidence to read.
- `collect_abgeordnete` page eligibility (`:9089`). Today this ignores `vacated`.
- `has_abgeordnete_page` (`:8974`): `mp.is_mdb` pools the person's `mps` rows. After step 3 no `mps` row exists for a superseded or Bundesrat-only preserved record, so no change is needed. A test pins it.
- `is_stale_roster_partner` (`person_registry.py:1122`) and the "listed again under another roster record" guard (`:1162`).
- `redner_details` stays as it is: it already ignores `ever_mdb` (`:9602`).

Grep `ever_mdb` and `is_mdb` reads of evidence before closing: `build_dip_pulse_site.py:1503, 1515, 8974, 9089`; `person_registry.py:537, 563-571, 1126, 1162`.

### 3. Re-issued DIP records (`dip_successors`)

- **File.** `person_corrections.json` gets a `dip_successors` array. Each entry holds `dip_person_id`, `successor`, `evidence` (non-empty text) and `reviewed` (date).
- **Validation** in `_load_corrections` refuses each of these with a clear message (class 9):
  - an id that does not survive `canonical_dip_person_id`;
  - a self-successor;
  - a successor that is itself superseded (no chains, so no cycles);
  - a duplicate;
  - an unknown key.
- **Lookup.** `person_registry.superseded_dip_ids()` and `person_registry.current_dip_person_id(value)`: canonical id, then the successor.
- **Ingest of DIP person rows skips a superseded id**, counted on stderr like `skipped_no_id`. Three paths do this, each before any `upsert_mp`: `ingest_mdb_roster` (`build_dip_pulse_site.py:8869`), the preserved-roster replay (`:1826`) and `persist_sampled_people` (`persist_dip_pulse_store.py:967`).
  - The successor's own DIP record speaks for the person.
  - Skipping rather than mapping keeps the old name off the roster record: `_representative_pair` prefers the longer "Jan Köstering, MdB" over "Jan Krampe, MdB".
  - `stats["mdb"]` then counts one roster person once.
- **Speaker and vote occurrences** carrying a superseded DIP id map it to the successor inside `upsert_mp`, before `mp_identity` is called on the mapped id. Callers pass raw ids, and `persist_dip_pulse_store.py:718` and `:752` both canonicalize through `current_dip_person_id`. Step 0.3 says whether any such occurrence exists; if one is `aw:`-keyed, a test covers the `UNIQUE` collision.
- **Links.** After `collect_abgeordnete` filters its lookup to unambiguous keys (`build_dip_pulse_site.py:9213-9216`), add `lookup["dip:<superseded>"] = lookup["dip:<successor>"]` when the successor has a page. Speaker links that carry the old id (`render_dip_pulse_html.py:2768`) then resolve.
  - **Not in `mp_keys`**: `mp_keys` feeds pass 1 of `match_rows` (`person_registry.py:892`), whose groups become durable `merge()` calls (`:1257-1258`).
- **The old record.** `dip:8054` stays in the registry with its retired binding. `roster_member` is false for it, so it gets no page, it is not preserved, and it is no stale partner. No alias and no redirect page (D4).

### 4. Gate: prove the replay renders what a fresh build renders

In `scripts/validate_store_gate.py`:
- **New check `replayed_pages_like_fresh`.** Run `build.collect_abgeordnete` on a read-only connection to each store and take the page persons (`has_abgeordnete_page`). Map each page person to its set of live bindings (bindings ∩ the fresh store's binding ids). Then:
  - every fresh page person has a replay page person with the same live-binding set and the same Reden, Beiträge and Stimmen counts;
  - every replay page person without a fresh counterpart holds a record for which `roster_member` is true, the predicate that grants the page. This covers G1/G2 former MdBs and the preserved roster, and it fails on anything else.
  - The receipt lists them as `replay_only_roster_pages`. A store-less fresh build has no roster, so these pages cannot exist there; they are accounted for, not silently allowed.
- **New receipt fields:**
  - `retired_only_persons`, `retired_only_with_page`; each one with a page must pass `roster_member`;
  - `superseded_dip_candidates`: step 0.4's two searches. Reported only, never failing.
- **The existing checks stay:**
  - `replayed_store_groups_like_fresh` on fresh bindings. Same fingerprint, unless step 0.3 finds 8054 in a fresh input; then the receipt names the binding;
  - `half_then_full_groups_like_fresh`;
  - `unchanged_replay_keeps_store`, which proves the reconcile write is idempotent.
- **Cost (class 12):** two `collect_abgeordnete` passes, the same work as one render's MP area: about 7,451 `mps` rows, 54,747 Reden and 425,322 vote members [measured: e4-repersist.md, a3-merged-gate.json]. Time it in the first gate run and record it.

### 5. Tests

New and changed tests, each with the repository's `# Value:` line:
- **`reconcile` clears `ever_mdb`:**
  - on an untouched Bundesrat-only record (the online path) and on a touched one;
  - before matching, so a stale roster partner blocked only by a Bundesrat record joins in the same build;
  - and a second build writes nothing.
- **G1 and G2 keep `ever_mdb` and their page.** G1 is a former MdB the roster no longer lists; G2 is one whose stored funktion is now a federal office. `test_a_former_mdb_keeps_a_page_when_a_later_build_no_longer_lists_them` stays green.
- **Offline replay with a preserved Bundesrat row:** the row is not preserved, its person renders no page, and a second replay keeps the store byte-identical.
- **Vacated records:** a vacated roster record gives its person no page, including when its old `mps` row had `is_mdb = 1`.
- **`dip_successors`:**
  - Replay, rewriting `test_preserved_roster_does_not_reactivate_retired_matching_evidence`. Without an entry the obsolete id keeps its own page; that pin stays and documents the unreviewed case. With an entry, and with the obsolete id's preserved `mps` row at `is_mdb = 1`, the obsolete record renders no page, the successor's page keeps its name, and a speaker link carrying the old id resolves to it.
  - Online: a roster listing both ids gives one person, named after the successor, listed once in the index.
  - A speaker carrying the old id joins the successor without a DIP conflict.
  - Validation: chain, cycle, self-successor, non-canonical id, duplicate and unknown key are each refused.
  - `mp_keys` output is unchanged for a successor's record. This guards matching.
- **Gate** (`tests/test_validate_store_gate.py`), on two small stores:
  - `replayed_pages_like_fresh` passes on equal pages, and passes with a G2 page under `replay_only_roster_pages`;
  - it fails on a replay-only page without a roster member, and on a fresh page missing from the replay.
- Run the suite on 3.13.2 and on the current 3.13 patch (review checklist, "Python patch level").

### 6. Full-data verification

All on clones of the post-E4 reference (`cp -cR`). `full` is never written before the merge.
1. **Figures:** follow the README recipe "Validate a data correction". The baseline is the clone. Apply the change with `--offline --repersist` to a second clone and run `compare_store_values.py`. Fill the Figures table and list every `person_records.person_id` change.
2. **Reden, Beiträge and Stimmen per person are unchanged.** Every removed page holds 0 of each, and every remaining page's counts equal the baseline's. Any difference stops the build.
3. **The gate** (`validate_store_gate.py`, about 2.5 h, 8 GB) on a third clone: `all_passed`, the new check included. Record the receipt beside the A3 receipts.
4. **Browser:** Krampe's page, the index, and one former Bundesrat URL (gone, swept by `write_abgeordnete_pages`, `:9839-9841`) at 375 px and in dark mode.

### 7. Repersist

Yes, the fix needs one. It changes persisted rows:
- `person_records.evidence_json` (`ever_mdb`);
- the `mps` rows of preserved Bundesrat and superseded roster entries, which are gone;
- `person_records.person_id` of any stale partner the corrected guard now lets join;
- the person pages and `abgeordnete.json`.

One in-place `--offline --repersist` of the reference after the merge rewrites all of it, with no DIP fetch.

Sequencing follows decision D3 of `docs/plans/e4-repersist.md`:
1. E4's in-place repersist first. It gives the new reference.
2. This fix measures old→new on a clone of it (steps 0 and 6).
3. After the merge, the reference is repersisted in place once more. That run can be shared with ADR 0004 and W2 when they merge close together. Each item still reports its own old→new from its own clone.

## Figures

Old values are the latest measured ones. Every new value is `[estimated]` until step 6 replaces it.

| Figure | Old | New [estimated] | Why the new one is more correct |
|---|---:|---:|---|
| Person pages (non-redirect) | 1,999 [measured: #141 replay; re-measure before gate] | ≈1,650–1,720 | It loses the Bundesrat-only retired-only pages (≤281), `dip:8054`, and the Bundesrat-only share of the 71 live roster-only persons (0–71). Land-office persons with an exact-MdB funktion keep their pages. For reference, a store-less build has 1,577 [measured: e7b06f3]. |
| Retired-only persons in the registry | 302 [measured: e7b06f3] | 302 | Durable keys stay (D3). |
| Retired-only persons with a page | 289 [measured: e7b06f3] | k ≤ 21, each a `roster_member` | No page rests on Bundesrat evidence or on a re-issued DIP record. |
| … linked from the index | 8 [measured: e7b06f3] | ≤ 8 | |
| `ever_mdb` records | not measured | old − Bundesrat-only records (≈352+) | The evidence no longer calls Bundesrat members former MdBs. |
| `mps.is_mdb = 1` | 1,360 [measured: 09b7c5d] | 1,360 − 1 (`dip:8054`, if its row has `is_mdb = 1`) | |
| `mps` rows | 7,451 [measured: #141] | 7,451 − preserved Bundesrat rows not sampled by any report − 1 | They are no longer preserved. |
| "Jan Köstering"/"Jan Krampe" pages | 2 | 1 | `dip:8054` is the same person as `dip:8257`. |
| Reden, Beiträge, Stimmen per page person | baseline | unchanged | No record holding a speech, contribution or vote binding changes person. |
| Index "Frühere Abgeordnete" | 771 [measured: 09b7c5d] | 771, or minus any entry step 0.4 finds re-issued | |
| Replayed vs fresh live-binding grouping | 1,942 = 1,942 [measured: e7b06f3] | equal, the same fingerprint | Unchanged, unless a fresh input samples 8054. |

Export: no schema or export-format change. The registry tables and `mps` change in content only, and the data changelog lists the moves.

## Risks and failure modes

| Path | Realistic failure | Covered by |
|---|---|---|
| reconcile clear | Runs after `_load_rows`, so replay 2 moves a `person_id` | Step 1 places it first; test "second build writes nothing"; gate `unchanged_replay_keeps_store` |
| `_read_roster_rows` | The `is_mdb` disjunct keeps preserving a superseded or vacated row | Step 2 replaces both disjuncts; test with an `is_mdb = 1` preserved obsolete row |
| G3 | A former MdB now in the Bundesrat loses a bio-only page, or a speaker page loses its roster bio | Step 0.5 counts them before code; D1 |
| Stale partner newly allowed | A page merges unexpectedly | Step 6.1 lists every `person_id` change; Reden and Stimmen cannot move |
| `dip_successors` goes stale | DIP drops the successor, and the person leaves the roster | Gate candidate list; online ingest warns when a superseded id is listed without its successor |
| Mapping a speaker's DIP id | `mps.dip_person_id UNIQUE` collision (`persist_dip_pulse_store.py:192`) | Step 0.3 checks whether the path is reached; a test if it is |
| Gate check | A G2 page fails the gate | Accounting uses `roster_member`, the predicate that grants the page |

Critical gaps: none open after the review fixes. Every row has a test or a step-0 measurement.

File overlap with parallel work:
- `scripts/validate_store_gate.py` may also be edited by W1/W2 or E4: rebase on whichever lands first.
- `scripts/person_corrections.json` is shared with partition work. This plan adds only a top-level array.
- `TODOS.md`: edit only the two registry sections and roadmap line 19.

## Effort

- Code and tests: human ~2 days / CC ~3–4 h [estimated].
- Step 0 queries: ~1–2 h, including the G3 read of `dip-person-cache.json`.
- Full-data verification: one database-only replay (~1 h) and the gate (~2.5 h), unattended [measured: a3-merged-gate timings].
- Repersist after the merge: ~30–60 min.
- One PR.

## Deferred to TODOS.md

- **Re-mint the registry once before the first data release** (P2). This is a store-less online build with `--enrich mp-roster`, about 101 DIP requests.
  - It drops the 302 retired-only persons, the 494 retired bindings and every legacy `p-0000NN` key from the published registry tables. Pre-release, nobody holds them.
  - After the release, orphans can only be pruned with redirects.
- **`ever_mdb` and name history from the MdB-Stammdaten** (P3, A.2 territory). It replaces the Bundesrat rule and the reviewed successor list with source data, and settles G3. It goes with "List MdBs in a government office".
- **The unreviewed re-issued DIP case keeps a duplicate page.** `test_preserved_roster_does_not_reactivate_retired_matching_evidence` keeps pinning it, and the gate lists candidates.
- **`is_mdb = not roles or …`** (`build_dip_pulse_site.py:1866`): an empty preserved funktion is an MdB forever. Latent unless step 0.1 finds a non-MdB.

## Decisions for the owner to confirm

Taken under CLAUDE.md (pre-release: accuracy only, change in place, no shims). Each one stands unless the owner objects.

- **D1. A Bundesrat funktion is never MdB evidence.**
  - `reconcile` enforces it on every record before matching.
  - Rejected alternatives:
    - recomputing `ever_mdb` from the stored funktion loses G2 history;
    - a one-time reset in the upgrade path is a shim;
    - a Stammdaten name-match exception is a new identity source, so it is deferred.
  - It costs G3: a former MdB whose current funktion is Bundesrat-only loses a page that shows 0 Reden, 0 Beiträge and 0 Stimmen, or a speaker page loses a roster biography. No Rede or Stimme moves.
  - Step 0.5 counts G3 before code. If it finds a speaker page that would lose its biography, list it in the PR. The owner may then promote the Stammdaten item.
- **D2. Re-issued DIP records go in a reviewed list (`dip_successors`).** A general join across two DIP ids would defeat the namesake guard. A `merges` entry fails in a fresh build where the old record's person does not exist (`merge` raises "Merge refers to unknown persons"). A superseded id is skipped at DIP-person ingest and mapped for speakers and voters.
- **D3. Retired-only persons render no page unless `roster_member` holds (O2 kept). Their registry rows stay.** Dropping orphan rows is the deferred re-mint, best done before the first release.
- **D4. No alias or redirect for `dip:8054`'s person and the Bundesrat pages.** Pre-release, no reader holds these URLs, and the stale-page sweep removes them.
- **D5. The proof of agreement is a page-level gate check** with replay-only pages accounted for by `roster_member`, not equal person counts. A store-less fresh build has no roster, so equal counts cannot hold by design.
- **D6 (review, structure).** One PR in the original arrangement: about 11 changed files (6 scripts, 3 test files, 4 docs counted together as edits) and no new classes. No smaller arrangement keeps the gate proof and the fix in one reviewable change. Splitting off the gate check would let the fix merge without its proof.

## Eng review (2026-11-10)

Mode: FULL_REVIEW (scope accepted as-is). Plan target: this file. Reviewer: Claude, native. The outside voice was a native Claude subagent, because Codex is not installed. The owner could not be asked, so each choice is auto-decided under CLAUDE.md and listed above.

### Scope Challenge
- **What already exists:**
  - `_stale_roster_partners` and `vacated`;
  - `derive.is_mdb_funktion`;
  - the reviewed-corrections loader (`_load_corrections`, partitions and merges);
  - `validate_store_gate.grouping_fingerprint` and `binding_ids`;
  - `collect_abgeordnete`;
  - the README replay recipe.

  The plan reuses each one. New pieces: one predicate, one corrections array, one gate check.
- **Already done?** No. `git log origin/main --since=2026-11-01` on the touched scripts shows #138, #141 and #143. #141 changed partitions and shared ids in `person_registry.py`, not `ever_mdb` or roster preservation.
- **Complexity:** about 11 files, more than 8, so the structure selector applied. It was auto-decided: original arrangement (D6).
- **TODOS cross-reference:**
  - closes the two registry items;
  - leaves "Placeholder Redner ids" and "Apply the voter-link patch" alone;
  - files four deferred items.
- **Reality rows:**
  - REALITY: premise-table finding. Of 14 claims, 9 are verified in code, 4 rest on measurements in `docs/plans/a3-phase4.md` and TODOS.md, and 1 (which Köstering refusal fires) is unverified, now marked so. unverified=1. Source: this plan, "Root cause B".
  - REALITY: already-done pass. `git log origin/main` shows no overlapping fix (`scripts/person_registry.py` history).
  - REALITY: surface-check pass. `--offline --repersist`, `validate_store_gate.py` and `compare_store_values.py` exist (`scripts/validate_store_gate.py:240-262`).
  - REALITY: binding-decisions pass. No branch decisions recorded. The plan follows E4 plan D3 (`docs/plans/e4-repersist.md`, "Sequencing").
  - REALITY: numbers finding. Every figure is now tagged, and the cited baselines are marked re-measure (Figures table).
  - REALITY: deferred-asks pass. No linked issue. Both TODO asks are covered: "decide whether retired-only persons render a page" is D3, and "re-derive or reset `ever_mdb`" is D1 (TODOS.md:833, :902).
  - REALITY: pr-count pass. One PR (Effort).

### 1. Architecture
- [CRITICAL] (confidence: 9/10) `scripts/validate_store_gate.py` (proposed step 4). Gate accounting used `mps.is_mdb = 1`, but G2 pages are granted by `ever_mdb` (`build_dip_pulse_site.py:9089` `if evidence.get("ever_mdb") or evidence.get("is_mdb"):`). The check would fail on cases step 1 protects. **Accepted:** accounting now uses `roster_member`.
- [CRITICAL] (confidence: 8/10) `build_dip_pulse_site.py:1515` `if row["is_mdb"] or row["id"] in roster_records`. The `is_mdb` disjunct sits outside the predicate, so a superseded or vacated row with `is_mdb = 1` stays preserved. **Accepted:** step 2 replaces both disjuncts.
- [INFORMATIONAL] (confidence: 9/10) `person_registry.py:892` `for key in mp_keys(row):` inside `match_rows`. Putting the alias in `mp_keys` would reach durable merges. **Accepted:** the alias moved to the `collect_abgeordnete` lookup.
- **Two shapes:**
  - A (chosen): a standing Bundesrat rule, one predicate, a reviewed successor list, and a page-level gate proof.
  - B: re-mint the registry once (store-less online build) and drop page eligibility based on stale evidence. B also removes orphan registry rows. But it needs about 101 DIP requests, it still needs the successor list for an online roster that lists both ids, and it leaves the code defect (sticky flag, vacated pages) to recur.
  - A hides more behind less: one predicate owns "former roster MdB" for five readers. B is deferred as a one-off cleanup.
- **Red flags:** two ways to decide "former roster MdB" (four readers today) is fixed by `roster_member`. A hand-synced list (successor ids beside DIP data) is mitigated by the gate's candidate report.

Dispositions: all 3 accepted.

### 2. Code quality
- [INFORMATIONAL] (confidence: 8/10) `build_dip_pulse_site.py:8954` `def _parse_listish`. The registry needs the same parse. **Accepted:** move it to `derive`. Two callers: `_read_roster_rows` and the new `_bundesrat_only`.
- [INFORMATIONAL] (confidence: 7/10) `person_registry.py:563` `was_mdb = …`. A clear in `bind` plus `reconcile` would be two sites for one rule. **Accepted** (from the outside voice): `reconcile` only, before `_load_rows`.

Dispositions: 2 accepted.

### 3. Tests

```
CODE PATHS                                   TEST (step 5)
reconcile ever_mdb clear ─┬ untouched        [new] online-path record
                          ├ touched          [new]
                          ├ before matching  [new] partner joins same build
                          └ idempotent       [new] 2nd build no write
G1 / G2 keep              ─                  [kept] :1071  [new] G2
_read_roster_rows         ─┬ Bundesrat row   [new] not preserved, 2nd replay identical
                           └ is_mdb=1 obsolete [new]
page eligibility          ─┬ vacated         [new]
                           └ Bundesrat-only  [new]
dip_successors            ─┬ replay          [rewritten] :165 (+ unreviewed pin kept)
                           ├ online both ids [new]
                           ├ speaker map     [new]
                           ├ link alias      [new]
                           ├ mp_keys unchanged [new]
                           └ validation x6   [new]
gate replayed_pages_like_fresh ─┬ equal      [new]
                                ├ G2 accounted [new]
                                └ 2 failures [new]
full data                 ─ gate + replay + compare_store_values (step 6)
```

- [INFORMATIONAL] (confidence: 8/10) No test reached a preserved obsolete row with `is_mdb = 1`. **Accepted** (added).
- No tests retire. `:165` is rewritten, and its unreviewed half is kept.

Dispositions: 1 accepted.

### 4. Performance
- [INFORMATIONAL] (confidence: 6/10) Medium confidence, verify. The gate runs `collect_abgeordnete` twice on full stores: one render's MP-area cost per store. **Accepted:** time it in the first run and record it (step 4, cost).
- The `reconcile` pass is one scan of `person_records` (O(records)), negligible beside matching.

Dispositions: 1 accepted.

### Outside voice (native Claude subagent; Codex not installed)

VERDICT: FINDINGS, 8 findings. Each one was checked against the code.
- (1) The gate fails on G2. Folded in, as Architecture 1.
- (2) The G3 premise was false: votes give no page (`build_dip_pulse_site.py:8969-8977`). Folded in:
  - G3 is now measured with `person_roles` and `mdb_zugehoerigkeiten`;
  - D1 now states the real cost: bio-only pages, no Stimmen moved.
- (3) The `dip:8054` page comes through `mps.is_mdb`, not `ever_mdb`. Folded in, as Architecture 2 and Root cause B.
- (4) Ordering of the clear, and one site for it. Folded in, as Code quality 2.
- (5) The alias in `mp_keys` reaches matching. Folded in, as Architecture 3.
- (6) The candidate search should use member numbers. Folded in, as step 0.4(b).
- (7) `UNIQUE dip_person_id` collision. Folded in, as step 0.3 and Risks.
- (8) The Köstering refusal reason is unverified. Folded in: marked not measured.

Plan design review and DX review: not run. No page changes its look (pages are removed, the copy is unchanged), and no CLI flag or operator step changes (the gate gains a check and receipt fields).

Completion summary:
- Scope Challenge: scope accepted as-is, 7 reality rows.
- Architecture: 3 issues. Code quality: 2. Tests: 1 gap. Performance: 1.
- Outside voice: 8 findings, all folded in.
- Failure modes: 0 critical gaps flagged.
- Unresolved decisions: 0. D1–D6 were auto-decided and await owner confirmation.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run | — |
| Outside Review | native Claude subagent (Codex not installed), inside `/plan-eng-review` | Independent 2nd opinion | 1 | completed (native fallback, no outside credit) | 8 findings, 8 folded in |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN (all mapped into the plan) | 7 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | not applicable (no visible page change beyond removed pages) | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not applicable (no CLI or operator change) | — |

- **OUTSIDE COVERAGE:** Codex unavailable (`not_installed`); a native Claude subagent ran the outside-voice prompt and completed with VERDICT: FINDINGS (8). No external-provider coverage.
- **VERDICT:** Eng review complete, with all findings folded into the plan. Step 0's measurements and owner confirmation of D1–D6 come before the build.

NO UNRESOLVED DECISIONS
