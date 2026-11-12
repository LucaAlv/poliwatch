# E4 repersist: bring the A3 store up to main v0.36

Status: **superseded, 2026-11-12.** The repersist was never run: a fresh online build replaced it (see "Outcome" below). The rest of this file is the plan of 2026-11-10, kept as written. Roadmap Stage 1, item 2, first bullet: "Correct the WP 19/20 roll-call group misattributions (E4), merged as #138; the repersist is owed."

## Outcome (2026-11-12)

**Why the plan did not run.** `~/agent-runs/a3/full` never came over from the old machine, so decision D1 (transfer it) fell away. The owner instead built a new store online into `.context/dip-pulse-site`, from main at 28799ac. That commit's data equals v0.36.0.0. The build ran `~/agent-runs/fresh/run.sh` (the a3-phase3 recipe) with the Stand 2026-04-29 Stammdaten in `.context/.dip-pulse-site.private` (D2 held). A fresh build holds E4 and every v0.33 to v0.36 change by construction, so steps 0 to 7 were not needed. The store gate ran on an APFS clone of the store and of its private directory, and all 11 checks pass (step 4). This store is the new reference store. It is recorded in `docs/plans/a3-phase4.md`, "Fresh reference store on main 28799ac", with the receipt in `fresh-store-gate.json`.

**What was checked (step 5, read-only on the store):**
- **E4, by group.** `e4-refiled-votes-old-new.tsv` was regenerated over all 619 votes, with the old columns taken from the cached reports' page `fractions` and the new ones from `vote_fractions`. It equals the committed file byte for byte: 146 rows in 55 votes.
- **E4, by member.** 100 rows have `listed_party_id` ≠ `party_id`: Kamann 38, Bülow 36, Pasemann 10, Witt 7, Huber 7, Heßenkemper 2. No other name appears, and each move falls in its window in `docs/source-errors.md` E4.
- **E4, the other figures.** All match their records:
  - the replay log's `refile: 100 Stimmen in 55 Abstimmungen` line;
  - the seat cross-check, 606 agree and 0 `shift_between_groups`;
  - Abweichungen 3,720 and r3 1,390;
  - unmatched names: 27 with 3,073 rows, and 10 with 927;
  - export format 16 and schema 11.
- **#143, on the 716 sittings the A3 store had.** The store also holds 21/104 and 21/105. Every figure equals its record:
  - Reden 54,747, Beiträge 42,484, zu Protokoll 3,342, Zwischenfragen 3,061;
  - agenda items 7,135 and Politikfeld rows 11,465;
  - Reden per Fraktion: CDU/CSU 14,963, SPD 11,620, Grüne 7,643, Linke 5,616;
  - the `speeches.char_count` sum, 253,528,378;
  - speech rule 7 on all 718 sittings.
- **#141.** All 15 `neu` rows of `shared-redner-ids-old-new.tsv` match, and so do the five `erste-reden` values.
- **#140.** `inverted` is 95 and includes all six votes. 990 is `proposition`.

**Mismatch, recorded as a finding.** `result_scope = application` is 34, not the 24 #140 recorded. This store fetched every roll-call page again, and the scope is read at fetch time. Without the A3 store it is unknown which 10 votes are new and why. See TODOS.md, "Vote direction: what the 2026-11-07 fix left open", item 18, and `docs/source-errors.md` E6.

**Not comparable, re-measured instead.** A fresh build has none of the A3 lineage's carried-forward registry, so these figures differ from the A3 records without a defect: `mps` 6,387 (7,451), Personen after Zusammenführung 2,042 (2,287), Personenseiten 1,661 (1,999), store persons 1,952 (2,244). The gate's replay raises `persons` from 1,952 to 1,956. That belongs to the registry-split plan (TODOS.md, "The carried-forward registry diverges from a fresh build after A3"), not to E4.

**Steps that no longer apply:** step 6 (old→new against the 2026-10-28 store, which is not on this machine) and step 7 (the in-place repersist and its determinism check; the gate's unchanged replay kept the store byte for byte). Step 8's browser checks were not run in this docs pass. Step 9 was done as these docs changes, with two exceptions:
- `AGENTS.md`'s interpreter line (D9) was left for the owner, because it is agent configuration.
- `docs/stable-ids.md`'s 2,364 is a dated A3 figure and was not re-measured.

D8 was applied: "Owner checks after the v0.28.0.0 merge", item 2, is closed.

## What "the repersist is owed" means

The A3 store, `~/agent-runs/a3/full` (716 Sitzungen, built on 2026-10-28 on the A3 branch), has never been persisted by main. Every figure since then was measured on clones:

| Change | Persisted effect | Where it was measured |
|---|---|---|
| A3 merge to v0.33.0.0 (#126 to #136) | 63 votes without a TOP kept (556 → 619 votes), schema 9 to 10 (seat tables, stored order), export formats 11 to 15, r2 and r5 recipe changes | merged-tree gate, `a3-merged-gate.json` (2026-11-01); #136 on a schema 10 store |
| E4, v0.34.0.0 (#138) | schema 11, `vote_members.listed_party_id`, 100 Stimmen in 55 roll-calls re-filed, 146 `vote_fractions` rows, Abweichungen 3,711 → 3,720 | gate on e7b06f3 (2026-11-05), `e4-refiled-votes-old-new.tsv` |
| #140, v0.34.2.0 | `votes.inverted` 90 → 95, `result_scope` application 25 → 24 | replay of the E4 gate store |
| #141, v0.35.0.0 | 43 units change person, `mps` 7,457 → 7,451, profile pages 2,005 → 1,999, 5 `erste-reden` Fakten values | replay on `full` against main, `shared-redner-ids-old-new.tsv` |
| #143, v0.36.0.0 | speech rule 7, Reden 54,718 → 54,747, Beiträge 42,465 → 42,484, agenda items 7,131 → 7,135 | database-only replay on clones of `full/data` |

Since #143 main has had only docs commits (#144, #145), so the data of main's tip equals v0.36.0.0.

Three things are owed:
1. **The store itself.** The reference store is at the 2026-10-28 state: 556 votes, no `listed_party_id`, an old speech rule. Offline renders, the export and every release guard refuse it, and each later Stage 1 item (registry split, ADR 0004, W1/W2, vote-link review) would have to replay twice, main and branch, to get a clean old→new.
2. **A whole-store gate on the composed changes.** The last complete gate ran on e7b06f3. #140, #141 and #143 each replayed on their own, but nobody has run them together through order independence, the unchanged replay, the link audit and the export. #141 changed how the registry carries bindings forward, which is the bug class the gate exists for (review checklist class 3).
3. **The E4 precondition.** E4 corrects nothing without the cached MdB-Stammdaten in the store's private directory. `~/agent-runs/a3/.full.private` has no file (TODOS "E4 /gstack-review: deferred findings", item 1).

## Blocker found while planning: the store is not on this machine

The machine this plan was written on was set up on 2026-11-09:
- `~/agent-runs` does not exist. A search of the whole disk finds no `bundestag-pulse.sqlite` and no `mdb-stammdaten.*`. Every receipt names `/Users/Luca/agent-runs/...`, the old machine.
- The main checkout has no `.context/`, so the 290-Sitzungen dev store and its Stammdaten cache are not here either.
- There is no Python 3.11 or newer: `/usr/bin/python3` is 3.9.6, there is no `/opt/miniconda3` (AGENTS.md names it) and no `uv`. The entry scripts refuse 3.9.
- Hardware: Apple M5 Pro, 15 cores, 48 GB RAM, 779 GB free. That is enough: the merged gate peaked at 5.6 GB maxrss and used 17 GB of disk.

So step 0 is the owner's: bring the store over. The W1/W2 agent needs the same files, because W1's raw XML inventory reads `full/data/xml`. One transfer serves both.

## Scope

In scope:
- Python 3.11+ and the store on this machine (owner), checked on arrival.
- The gate on a clone of `full` at main 28799ac, then an in-place `--offline --repersist` of `full`, with the Stand 2026-04-29 Stammdaten in its private directory.
- Reconciling the measured figures against each PR's recorded new values, and attributing every move from the 2026-10-28 store.
- One docs PR: figures, the A3 record, TODOS.md, AGENTS.md.

Not in scope, and why:
- **No code change.** None of the open E4 items moves a persisted row on today's inputs (next section). CLAUDE.md: fix now only what moves a figure.
- **No online fetch.** Re-acquiring sittings, the roster or the Stammdaten is the coverage gate's T4. A refreshed Stammdaten file waits for E4 item 2.
- **The 290-Sitzungen store** (`.context/dip-pulse-site`, schema 8, 217 votes) is not repersisted (decision D7).
- **The online fresh vs incremental comparison** (E4 item 7) needs a DIP key and runs with T4's online rebuild.

## The open E4 items: before the repersist or not

The test is whether an item moves a row that `--offline --repersist` writes. If it does, it has to land first, or the repersist runs twice. If it touches only rendering, it lands any time and needs only a plain `--offline` render afterwards. If it moves nothing, it is independent.

| Item (TODOS) | Moves a persisted row today? | Before? |
|---|---|---|
| Deferred 1: no file, so the correction disappears | yes: without the file all 100 Stimmen go back | **yes, as an operator step:** the file goes into `.full.private` (step 3); no code |
| Deferred 2: a gap counts as fraktionslos; the Stand window | no: the one move into fraktionslos (Pasemann) has an AfD record in WP 19, and all 100 moves fall in 2017–2021, far from the Stand (0 votes on the Stand day, TODOS) | no. **It must land before any Stammdaten refresh**, because a refreshed file is where it bites |
| Deferred 3: offline render against a store from another Stand | no: one file serves both persist and render | no. The operator must not run `--enrich mdb-stammdaten` between steps |
| Deferred 4: the seat cross-check is not independent | no: a report in the private directory | no. Step 5 checks the moves independently instead, by reading the page's counts back |
| Deferred 5, 6: tests, small items | no | no |
| Deferred 7: online fresh vs incremental | no | no, it goes with T4 |
| Deferred 8: refused vote passes a release guard | no: 0 refused; step 4 checks the log | no |
| Deferred 8: `compare_store_values` cannot see a re-filing | no: tooling | no, decision D5. Step 5 queries the moves directly |
| Deferred 8: the other four bullets | no: latent, every check is at 0 today | no |
| Re-filing 1: `data/bills.json` dumps the page's `fractions` | no: render output only | no. Once it lands, a plain `--offline` render |
| Re-filing 2: 27 + 10 names without a Stammdaten match | no | no. Step 5 measures the counts again |
| Re-filing 3, 4 | no | no |

## Sequencing with the parallel work

```
owner: Python 3.11+, store + Stammdaten zip transferred (step 0)
        │
        ▼
E4 repersist (this plan): gate on clone → reconcile → in-place repersist of full
        │       new reference = full @ 28799ac (v0.36 data)
        ├──────────────┬──────────────────┬───────────────────┐
        ▼              ▼                  ▼                   ▼
 registry split   ADR 0004 kinds    plan item 1.5       W1 inventory, W2 withholding
 (persons, pages) (speech rule 8)   (aw-profiles enrich (W2: schema 12)
                                     on a clone)
  each: replay on a clone of the reference, old→new against it, merge,
        then repersist the reference in place (unattended, ~30–60 min)
        │
        ▼
 coverage gate T4: fetch the 85, online rebuild, gate → the release store
```

- **Run now, do not wait (decision D3).** The registry split, ADR 0004 and W2 each change persisted rows, and each has to report its own old→new under CLAUDE.md. That needs a replay per item whatever the order. Against a current reference it takes one replay per item. Against the 2026-10-28 store it takes two (main and branch, as #141 and #143 did), and the cumulative v0.33–v0.36 moves would blur every comparison. Waiting so that "it runs once" saves nothing: T4 rebuilds the store again anyway.
- **W1/W2:** if W1 merges first, this plan's gate also covers W1's reconciliation refusal on all 716 sittings, and that is fine. If W2 (schema 12) merges first, the repersist runs at W2's tip, and the reconciliation table gains W2's withheld units. Either way, run it at main's tip on the day and name the commit.
- **ADR 0004** (`docs/plans/adr-0004-presidium-kinds.md`, speech rule 7 → 8) proposes to fold its own post-merge repersist into this one. That fits this plan. Step 0 gates every replay, and ADR 0004 cannot merge before it, because it needs its own replay on the store first. Whatever persist-affecting PR is merged when step 4 starts is included: its recorded new values join step 5, and its moves get their own rows in step 6's attribution.
- **Plan item 1.5** measures the abgeordnetenwatch match share with `--enrich aw-profiles` on a clone. Measure it on a clone of the new reference.
- **File ownership:** this plan's docs PR edits `PRODUCT.md`, `docs/plans/a3-phase4.md`, `TODOS.md` (the E4, registry and owner-check sections and roadmap line 18 only) and `AGENTS.md`. If another agent's PR touches the same TODOS lines, merge by hand.

## Steps

All commands run from the repository root, on main at the commit named on the day. `PY` is the 3.11+ interpreter from step 0. `A3=~/agent-runs/a3`. Nothing writes to `$A3/full-2026-10-28` after step 2.

### 0. Environment and transfer (owner)

1. Install an interpreter: `brew install python@3.13`, or `brew install uv && uv python install 3.13.12`. Run `$PY -m unittest discover -s tests` and get it green, then the checklist's current-patch run.
2. From the old machine, copy without changing anything:
   - `~/agent-runs/a3/full/` (about 5.4 GB) and `~/agent-runs/a3/.full.private/` if it exists;
   - `<old checkout>/.context/.dip-pulse-site.private/mdb-stammdaten.zip` and `mdb-stammdaten.json`, the Stand 2026-04-29 file that E4 was measured with;
   - optional, for the owner's later inspection: `~/agent-runs/a3/baseline`, `~/agent-runs/a3/phase4/gate-merged`.

   Use `rsync -a --checksum` or a `tar` stream, never a sync tool that skips hidden directories.
3. Check the arrival. Each check is read-only (`sqlite3 'file:…?mode=ro'`), and its result goes in the record:
   - `full/data` holds 716 `plenarprotokoll-*.json` reports plus the catalog, and 716 `data/xml/*.xml`;
   - the store passes `PRAGMA integrity_check`;
   - its counts equal `counts_before` in `a3-merged-gate.json`: protocols 716, votes 556, vote_members 382,441, speeches 54,718, contributions 42,465, persons 4,463. If they differ, someone persisted `full` after 2026-11-01. Record the actual counts and take them as the baseline;
   - the "old" schema and rule. `PRAGMA user_version` cannot give the schema: it is 0 on every build store and marks only distribution copies (`persist_dip_pulse_store.py:142`). Record which of the markers `require_current_schema` tests are present (`party_seats`, `vote_fractions.rank`, `vote_members.listed_party_id`; `persist_dip_pulse_store.py:38`) and the versions in `speech_rule_inputs`;
   - the zip's `VERSION` is 1777449783 (Stand 29.04.2026). Record its sha256.

   If the Stammdaten file cannot be recovered, stop. Land E4 item 2 first, then fetch the current file with `--enrich mdb-stammdaten` (decision D2).

### 1. Freeze the inputs

- **Run every command in this plan from one clean, detached checkout:** `git worktree add --detach <path> <commit>` at main's commit on the day. Record `git -C <path> rev-parse HEAD` and an empty `git status --porcelain` before step 4 and again after step 7. A shared checkout can change between the gate's separate processes, and its receipt records only the first HEAD.
- **Reserve the whole of `$A3/full` from step 2 to the end of step 7,** not just the store. The writer lock covers only the database rebuild (`build_dip_pulse_site.py:1596`). The render after it runs outside the lock and rewrites, file by file:
  - every cached `plenarprotokoll-*.json` report, with its re-parsed content (`rebuild_cached_detail_pages` → `write_report_files`, `:1200`);
  - every page, and the site JSON in `data/` (`bills.json`, `abgeordnete.json`);
  - `data/exports`, `data/a1-classification-diagnostics.json` and the exclusion record.

  Only `data/xml` stays as it was. Parallel agents read `$A3/full-2026-10-28` or a clone of it during the window, never `full`. W1's XML inventory can read `full/data/xml`.

### 2. Pre-copy

`cp -cR $A3/full $A3/full-2026-10-28` (an APFS clone, almost no space). This is the baseline for `compare_store_values` and the rollback. Never write to it.

### 3. Stammdaten into the private directories

```
mkdir -p $A3/.full.private $A3/.gate-v036.private
cp <transfer>/mdb-stammdaten.{zip,json} $A3/.full.private/
cp -cR $A3/full $A3/gate-v036
cp <transfer>/mdb-stammdaten.{zip,json} $A3/.gate-v036.private/
```

The private directory sits beside the output directory: `.<name>.private` (`person_registry.private_dir`). The gate copies only `data/`, so its clone gets the file by hand.

### 4. The gate on the clone

```
/usr/bin/time -l $PY scripts/validate_store_gate.py $A3/gate-v036 \
  --receipt <scratch>/e4-repersist-gate.json --scratch $A3/gate-v036-scratch --today 2026-10-28 \
  > $A3/gate-v036-run.log 2>&1
```

- **Pass:** `checks.all_passed` is true.
- **In `gate-v036-scratch/replay.log`:**
  - the line `refile: 100 Stimmen in 55 Abstimmungen from the MdB-Stammdaten`;
  - no `warning: [refile]`;
  - no `warning: [stammdaten] keine Sitzzahlen`;
  - no Redner-ID refusal.
- **Expected warnings:** the order-independence clones (`fresh`, `half`) run without the Stammdaten and warn about it. They compare person grouping, which E4 leaves alone (E4 item 5). Expect that warning there and nowhere else.
- `--today 2026-10-28` matches the merged gate and #140 (decision D6).
- **Budget:** 1.5 to 2.5 h, at least 20 GB free. Run it unattended. Keep the receipt.

**Stop rules.** Any failed check stops the plan: do not promote, do not touch `full`. Diagnose with the diagnosing-bugs skill. A failure is a correctness defect on main, fixed in place under CLAUDE.md, and the plan resumes at step 3 on a fresh clone. The likeliest candidate is `replayed_store_groups_like_fresh`, after #141's carry-forward.

### 5. Reconcile against the records

Run on `$A3/gate-v036`, read-only. Each row gets the recorded value, the measured value and its source. Queries are kept in the scratch area and quoted in the record. **Any measured value that differs from its recorded value, without a later PR that explains it, stops the plan, as in step 4.**

| Figure | Recorded (v0.36) | Source |
|---|---:|---|
| protocols | 716 | all |
| votes / vote_members | 619 / 425,322 | merged gate, E4 |
| speeches (Reden) | 54,747 | #143 |
| contributions | 42,484 (zu_protokoll 3,342, zwischenfrage 3,061) | #143 |
| agenda_items / agenda_item_politikfelder | 7,135 / 11,465 | #143 |
| Reden per Fraktion: CDU/CSU, SPD, Grüne, Linke | 14,963, 11,620, 7,643, 5,616 | #143 |
| mps | 7,451 | #141 (#143: three rows gain SPD, the count is unchanged) |
| profile pages (non-redirect) | 1,999 | #141 |
| Personen after Zusammenführung (compare tool) | 2,287 | #141 |
| `speech_rule_inputs`, version 7 | 716 of 716 | #143 |
| refile: Stimmen / roll-calls | 100 / 55 | E4 |
| `vote_members` with `listed_party_id <> party_id` | 100 | E4 |
| `vote_fractions` rows that differ from the page | 146 | E4 |
| Abweichungen / r3 rows | 3,720 / 1,390 | E4 |
| seat cross-check `shift_between_groups` / agree | 0 / 606 | E4 (`seat-crosscheck.json`) |
| unmatched names: none / other WP only | 27 names, 3,073 rows / 10 names, 927 rows | E4 re-filing item 2. No build output prints it: a scratch script runs `derive.person_name_key` against the Stammdaten through `stammdaten.py`, never a second name rule |
| `votes.inverted` / application scope | 95 / 24 | #140 |
| Fakten rows / publishable | 1,908 / 530 | merged gate. #141 moves 5 `erste-reden` values (2014-W23 27 → 26, 2015-W12 3 → 2, 2022-W11 49 → 50, 2022-W27 1 → 2, 2023-W50 0 → 1); check those five. Publishable is re-measured, because no record states it after #141 |
| export | format 16, schema 11, 619 votes, 425,322 vote members | E4 |
| broken local links | 0 | gate |

Three per-row checks:
- **E4, by group:** regenerate `e4-refiled-votes-old-new.tsv`. The "new" columns are `vote_fractions` of the repersisted store. The "old" columns come from the page's `fractions`, read straight from the frozen reports in `$A3/full-2026-10-28/data` (a report keeps what the page printed). They are not derived by reversing the moves, which would check the output against itself. `diff` it against the committed TSV: expect 0 lines.
- **E4, by member:** the TSV pins group totals but no member, so moving the wrong person with the same Stimme would pass it. List the 100 rows of `vote_members` whose `listed_party_id` differs from `party_id`, as (vote, member, listed group, filed group, Stimme). Check each against the reviewed evidence in `docs/source-errors.md` E4: six MdBs, in the dated windows of the Textarchiv. Expect Kamann 38, Bülow 36, Pasemann 10, Witt 7, Huber 7 and Heßenkemper 2, which is 100, and no other name. This is the independent check that E4 item 4 says the seat cross-check no longer gives.
- **#141:** regenerate the `neu` rows of `shared-redner-ids-old-new.tsv` (Reden, Beiträge and Stimmen per person, by name; person ids are reissued) and diff them.
- **#140:** votes 990, 638, 695, 774, 777 and 801 have `inverted = 1`, and 990 has `result_scope = proposition`.

Figures no record holds at v0.36 are measured and reported, with the merged gate's value as the old one:
- store persons (2,244);
- persons on fresh bindings (1,942);
- retired-only persons, pages and index links (302, 289, 8);
- retired bindings (494);
- documents (20,596);
- pages and links in the audit (8,970, 874,930);
- export files (37).

These answer "Re-measure" in "The carried-forward registry diverges from a fresh build after A3".

### 6. Old→new against the 2026-10-28 store

```
$PY scripts/compare_store_values.py $A3/full-2026-10-28 $A3/gate-v036                > <scratch>/e4-repersist-compare-shared.txt
$PY scripts/compare_store_values.py $A3/full-2026-10-28 $A3/gate-v036 --cohort all   > <scratch>/e4-repersist-compare-all.txt
```

Every move gets one owner in an attribution table, built from the first table of this plan. Old-schema quantities print `unavailable`, which is not 0 (checklist class 5). **A move no merged PR explains stops the plan.** The compare cannot see re-filings or vote interpretation (E4 item 8); step 5 covers those.

### 7. In-place repersist of `full`

```
/usr/bin/time -l $PY scripts/build_dip_pulse_site.py --offline --repersist \
  --output-dir $A3/full --today 2026-10-28 > $A3/full-repersist.log 2>&1
$PY scripts/build_dip_pulse_site.py --validate-publication $A3/full
$PY scripts/compare_store_values.py $A3/gate-v036 $A3/full --cohort all
```

Expect:
- exit 0, the same `refile:` line, and the store replaced;
- `compare_store_values` reports no move;
- `_content_digests` (`build_dip_pulse_site.py:1521`) gives the same result for both stores. This is the build's own per-table digest without timestamps, the one an unchanged replay uses to keep a store, so no new digest code is written. Run both from the scratch area by importing the module. A digest that differs only in issued person keys is itself a finding (checklist class 3), not noise. This is a second independent run, so it doubles as a determinism check.

Then delete `gate-v036` and its scratch, after the owner's OK (D4). Keep `full-2026-10-28` until T4's store replaces the reference.

### 8. Browser spot checks

Serve `$A3/full` with `python3 -m http.server 8001 --directory $A3/full`. Check with `/browse` at 375 px and in dark mode:
- the dossier panel of vote 750, which should name Witt and Huber as moved;
- vote 990's badge, "Antrag: Abgelehnt";
- Widmann-Mauz's Personenseite, 34 Reden and 82 Beiträge;
- the 18/49 dossier, 51 Reden;
- the Abgeordnete index;
- the Daten page's Stammdaten line, Stand 29.04.2026.

### 9. Docs PR

A docs-only PR with no VERSION bump. Every changed sentence cites its receipt value (checklist class 11):
- `PRODUCT.md:88`: "556 namentliche Abstimmungen (619 when repersisted …)" becomes 619, citing the new receipt and naming the commit.
- `docs/plans/a3-phase4.md`: a new section "Repersist on main v0.36.0.0", with the gate table, the reconciliation table, the attribution table and the timings. Add the receipt (`e4-repersist-gate.json`, `$HOME` as `~`) and both compare outputs under `docs/plans/`.
- `docs/data-methods.md:82` and `docs/source-errors.md` E4: change them only if a figure moved. "Stand 2026-11-05, 619 Abstimmungen" stays true otherwise.
- `docs/stable-ids.md:66` (five flagged ids out of 2,364): re-confirm from the log, and edit only if it moved.
- `README.md`: no figure changes. Line 12 (716 Sitzungen) and line 116 (timings) stay true. The new timing goes in the A3 record.
- `TODOS.md`:
  - roadmap line 18: done;
  - E4 deferred item 1: the file is in `.full.private`, and the store is schema 11;
  - "The carried-forward registry …": "Re-measured on v0.36";
  - "Owner checks after the v0.28.0.0 merge", item 2: its dependency is met (D8);
  - the Completed line.
- `AGENTS.md`: replace the `/opt/miniconda3` interpreter line with the one installed in step 0 (D9).
- **Not changed:**
  - `docs/data-changelog.md`: no release exists, so the first release reads "Erste Veröffentlichung" and carries no corrections (`release_changes.py` rule);
  - `DATA.md`: the export generates it from `data_dictionary.json`. Check that the new export's copy describes `listed_party_id` and format 16;
  - `docs/plans/v1-scope-review.md` and earlier records: they stay dated records.

## Verification summary

| Proof | Step |
|---|---|
| The transfer is complete and is the recorded store | 0.3 |
| Integrity, foreign keys, order independence, replayed = fresh grouping, unchanged replay, links, export, publication | 4 (gate) |
| E4 moves are exactly the committed TSV by group, with the page's counts taken from the frozen reports, and exactly the six reviewed MdBs by member | 5 |
| #140, #141 and #143 compose to their recorded new values | 5 |
| Every move since 2026-10-28 has an owner | 6 |
| A second run gives the same store | 7 |
| The pages show the corrections | 8 |

## Risks

- **The transferred store is not the recorded one,** because it was persisted later or the copy is partial. Step 0.3's counts and integrity check catch it, and the record takes the actual baseline.
- **The Stammdaten file is lost.** A fresh fetch has a newer Stand and can move E4 figures for votes after 29.04.2026. So E4 item 2 lands first, and the moves are reported as a Stand change.
- **The gate fails on the composition of #140, #141 and #143.** That is what the gate is for. Stop, fix on main, rerun.
- **The interpreter differs from the one the records used.** html.parser changed in 2025 patch releases, and the records ran on miniconda 3.13.2. Record the version. A difference in step 5 that only parsing explains gets checked on a second patch level before anything else.
- **An interrupted run.**
  - The store swap is atomic, so a stop before it leaves the store as it was.
  - A stop during the render after the swap leaves a new store, some cached reports already rewritten with re-parsed content and others not, and mixed pages. A plain `--offline` does not repair this: it loads the reports without re-parsing the XML (`build_dip_pulse_site.py:14471`), and it takes the wall-clock date unless pinned. Recover with the complete `--offline --repersist --today 2026-10-28`, then repeat all of step 7's checks.
  - The rollback is `rm -rf $A3/full && cp -cR $A3/full-2026-10-28 $A3/full`, plus removing staged files from `.full.private` (keep the Stammdaten zip). Rollback is the only way back to the old reports, because the run rewrites them.
- **Time.** The repersist took 1,650 s in Phase 4 and 3,640 s inside the merged gate. Plan for the slower figure.
- **A parallel agent writes `full` during the window.** The writer lock refuses the second writer. Step 1 announces the window.

## Effort

| | Human | CC |
|---|---|---|
| Step 0 (owner: install, transfer, checks) | ~1–2 h, plus transfer time | ~15 min of checks |
| Gate | unattended 1.5–2.5 h | ~10 min to start and read |
| Reconciliation, attribution | ~4 h | ~1 h |
| In-place repersist, determinism | unattended 0.5–1 h | ~10 min |
| Browser checks | ~30 min | ~15 min |
| Docs PR | ~2 h | ~30 min |
| **Total** | **~1 day** | **~2.5 h active, ~4 h unattended compute** [estimated] |

## Decisions for the owner to confirm

Taken by the planner under CLAUDE.md, because the owner could not be asked:
- **D1. Source of the store:** transfer `full` and the Stammdaten zip from the old machine, rather than rebuilding online now. A rebuild is T4's job, needs about 2,200 DIP requests for the 85 alone plus the whole roster, and would mix new sittings into the E4 proof.
- **D2. Stammdaten file:** reuse the Stand 2026-04-29 file that every E4 figure was measured with. Refresh it only after E4 item 2 lands.
- **D3. Timing:** run now. Do not wait for the registry split, ADR 0004 or W1/W2. Each of them repersists the reference after its own merge.
- **D4. Where:** gate a clone first, then repersist `full` in place after an APFS pre-copy `full-2026-10-28`. Delete `gate-v036` only after the owner's OK.
- **D5. No code before the run.** The `compare_store_values` per-(vote, group) view (E4 item 8) stays deferred. Step 5's direct queries replace it for this run.
- **D6.** `--today 2026-10-28`, as in the merged gate and #140.
- **D7.** The 290-Sitzungen `.context/dip-pulse-site` store is retired, not repersisted. Releases come from the A3 lineage and, after T4, from its rebuild.
- **D8.** "Owner checks after the v0.28.0.0 merge", item 2: the repersist meets its "A3's owed rebuild" dependency. Its batch-by-batch before/after comparisons can no longer be replayed as written, because later merges move the same outputs. Proposed: close them, keeping only the online `[sitzungskalender]` check for T4.
- **D9.** AGENTS.md names the interpreter installed in step 0.

## Deferred to TODOS.md (no change by this plan)

The E4 items in the table above stay where they are, with one addition to E4 item 2: "must land before any Stammdaten refresh". Also proposed: a standing step that repersists the reference after every persist-affecting merge. That belongs with "Main and stable releases", and is not decided here.

## Eng review (`/plan-eng-review`, 2026-11-10)

The planner ran this review in a spawned session with no owner to ask, so it took every choice itself. Each choice is recorded below and listed under "Decisions for the owner to confirm". The gstack onboarding prompts (upgrade, telemetry) were deferred, not answered.

### Scope Challenge

- **Target:** this file. The plan changes no code. Its docs PR touches 4 existing files (`PRODUCT.md`, `docs/plans/a3-phase4.md`, `TODOS.md`, `AGENTS.md`) and adds 3 records under `docs/plans/` (the receipt and two compare outputs), with no new class. That is under 8 files, so the complexity selectors were skipped. **Scope accepted as-is.**
- **What exists already:** `validate_store_gate.py` (the whole gate), `compare_store_values.py` (old→new), `_content_digests` (store equality), `refile_entry_votes`'s summary line, and `seat-crosscheck.json`. No new tool is planned.
- **Findings:**
  - S1 [P1] (confidence 10/10): the store, the Stammdaten file and a 3.11+ interpreter are all missing on this machine (whole-disk search; `/usr/bin/python3` 3.9.6). Folded in as step 0 and D1.
  - S2 [P2] (8/10): waiting for the registry split, ADR 0004 or W2 would not make this run once. Each needs its own replay under CLAUDE.md, and T4 rebuilds anyway. Decided D3.

```
REALITY: premise-table finding 2 unverified premises: Pasemann has an AfD Stammdaten record in WP 19 (inferred from the TSV direction and source-errors.md:80, the file is not on this machine); the transfer size of full itself (only the 5.4 GB gate-full clone is recorded, a3-phase4.md:66). unverified=2  docs/plans/e4-refiled-votes-old-new.tsv:1
REALITY: already-done pass origin/main fetched, tip 28799ac = HEAD, no repersist or store record after #143; ~/agent-runs absent on this machine  docs/plans/reden-outside-tops.md:155
REALITY: surface-check pass --offline/--repersist/--today/--validate-publication/--enrich mdb-stammdaten exist (scripts/build_dip_pulse_site.py:13577,13628,13634,13649,13666); gate --receipt/--scratch/--today (scripts/validate_store_gate.py:392-396); compare --cohort (scripts/compare_store_values.py:790)  scripts/build_dip_pulse_site.py:13666
REALITY: binding-decisions pass branch decision log empty; the owner's decisions honoured: a tagged export refuses without Stammdaten (2026-11-05), A3 ships with registry part 2 open (2026-11-01), N1-N10  TODOS.md:1446
REALITY: numbers pass every figure carries its source record, figures nobody recorded are marked re-measure, effort is [estimated]  docs/plans/a3-merged-gate.json:1
REALITY: deferred-asks pass no linked issue; every open E4 item is dispositioned in the before/not table  TODOS.md:1443
REALITY: pr-count pass no .gstack/ship-policy.json, so one PR per wave by default; the plan has one docs PR and no code PR  docs/plans/e4-repersist.md:1
```

### 1. Architecture

- **A1 [P1] (confidence 9/10):** the first draft said a repersist leaves the cached reports alone. It does not. The render rewrites every `plenarprotokoll-*.json` outside the writer lock (`build_dip_pulse_site.py:1200`, `:1596`). Found by the outside voice and verified here. **Accepted:** step 1 now reserves the whole output directory, and parallel agents read the pre-copy.
- **A2 [P2] (8/10):** two repersists, the gate's on a clone and then the in-place one. The second costs 0.5–1 h unattended and buys a determinism check from two independent runs. **Accepted** as D4. The alternative, promoting the gated clone with `mv`, saves that hour but renames the private directory and proves nothing new.
- **A3 [P2] (9/10):** the gate copies only `data/`, so its clone has no Stammdaten unless they are placed by hand, and E4 then silently corrects nothing, with only a warning. **Accepted:** step 3, plus a log check in step 4.

Dispositions: A1, A2 and A3 accepted.

### 2. Code quality

- **CQ1 [P2] (9/10):** the first draft read the schema from `PRAGMA user_version`, which is 0 on every build store (`persist_dip_pulse_store.py:142`). **Accepted:** step 0.3 records the column markers `require_current_schema` tests.
- **CQ2 [P2] (8/10):** the first draft proposed a new per-table digest in the scratch area. **Accepted:** reuse `_content_digests` (`build_dip_pulse_site.py:1521`).
- **CQ3 [P3] (7/10):** the unmatched-names counts must reuse `derive.person_name_key`, not a second name rule (checklist class 4). **Accepted.**

Dispositions: all accepted.

### 3. Tests

There is no code, so there are no unit tests to add. The proof is the verification matrix:

```
transfer ──► 0.3 counts/integrity/Stand ──► 4 gate (11 checks) ──► 5 reconcile ──► 6 attribute ──► 7 in-place = gated (_content_digests)
                                               │                    │ by group: TSV from frozen reports
                                               │                    │ by member: 100 rows = 6 MdBs (E4)
                                               │                    │ #140 six votes, #141 per person, #143 per sitting
                                               └ replay.log: refile line, no refused / no-Stammdaten warning
                                                                                        8 browser 375px + dark
```

- **T1 [P1] (8/10):** the group-level TSV cannot catch the wrong member moved with the same Stimme. Found by the outside voice. **Accepted:** step 5 adds the by-member check against the reviewed evidence, and reads the page's counts from the frozen reports.
- **T2 [P2] (8/10):** publishable Fakten after #141 are recorded nowhere. **Accepted:** re-measured, with the five moved `erste-reden` values checked.

The QA test-plan artifact and the task JSONL were not written, because the task allows writes only to this file and to scratch outside the repo. **Not persisted:** their content is the matrix above and "Implementation Tasks" below.

### 4. Performance

- **P1 [P3] (9/10):** the repersist's time is recorded twice and the records disagree: 1,650 s in Phase 4, 3,640 s inside the merged gate. Peak memory was 5.6 GB maxrss, about 7 GB together with the gate (a3-phase4.md:52-66). This machine has 48 GB and 779 GB free, so memory and disk are not limits. **Accepted:** plan for the slower time, record `/usr/bin/time -l`.

Loop cost (checklist class 12): the run is measured on the reference data itself (619 votes, 425,322 vote members), so no extrapolation is needed.

### Outside voice

Codex (`gpt-6-astra`, read-only sandbox) completed with `VERDICT: FINDINGS`, 4 findings, all verified against the code and accepted:
1. High: reports are rewritten outside the lock. Becomes A1.
2. High: a plain `--offline` cannot recover an interrupted render. Becomes the risk entry: rerun the full repersist with `--today`.
3. Medium: the group-level TSV is not a member-level proof. Becomes T1.
4. Medium: run from one clean, detached checkout and check it before and after. Becomes step 1.

No disagreement is left. Cross-model: the native review had not caught 1, 2 or 4. Codex did not raise the store's absence or D3.

### Review checklist applied to the plan

- **Class 1, sibling path:** the Stammdaten must be present for each path that persists or renders: the in-place `full`, the gate's main replay, and the plain `--offline` render. The gate's `fresh`/`half` clones lack it by design (E4 item 5), and their grouping is unaffected.
- **Class 2, stale beats fresh:** the replay carries the 2026-10-28 registry forward. That is checked by `replayed_store_groups_like_fresh`. `preserve_roster` keeps the old roster lists by design, and nothing is refetched.
- **Class 3, order and history:** order independence, plus `_content_digests` equality of two runs.
- **Class 5, absent vs zero:** old-schema columns print `unavailable` in the compare.
- **Class 6, derived columns:** `leading_vote`, Abweichungen, r3 and the Fakten are in the reconciliation.
- **Class 10, interrupted run:** a stop before the swap leaves the store as it was; a stop after it needs the full repersist again; rollback from the pre-copy.
- **Class 11, claims:** each docs edit cites a receipt value.
- **Class 12, loop cost:** measured on the full data.
- **Checks no diff review replaces:**
  - figures: steps 5–6;
  - fresh vs incremental: offline half in the gate, online half deferred with T4;
  - browser: step 8;
  - Python patch level: step 0.1;
  - adversarial lenses: the docs PR is under 200 lines, so class 11 only.

### Failure modes

| Path | Realistic failure | Caught by | Silent? |
|---|---|---|---|
| transfer | partial copy, or a store persisted after 2026-11-01 | 0.3 counts, integrity, report/XML counts | no |
| Stammdaten | file missing from a private dir | step 4 log check (`refile:` line, no `keine Sitzzahlen`) | was silent (a warning only), now checked |
| gate | replayed ≠ fresh after #141 | gate check, stop rule | no |
| render | interrupted after the swap | risk entry: full repersist again | was silent with plain `--offline`, now covered |
| checkout | script edits between gate processes | clean detached worktree, HEAD and status before and after | no |
| E4 | a wrong member moved with the same Stimme | by-member check | no |

Critical gaps: 0 after the folds.

### TODOS.md proposals (taken by the planner)

- **E4 item 2:** add "must land before any Stammdaten refresh". Add, in the docs PR.
- **A standing step to repersist the reference after every persist-affecting merge:** defer to "Main and stable releases". Not added here.
- **`validate_store_gate` copies no Stammdaten into its output clone's private directory,** so a forgotten copy only warns. Already E4 item 5: extend that item to say the gate should refuse when the source's private directory has the file and the clone's does not. Add, in the docs PR.

### DX review

Not run. The plan changes no CLI command, flag or documented operator workflow. It is a one-off operator run of existing commands.

## Implementation Tasks

Synthesized from this review's findings. Each task derives from a specific finding above.

- [ ] **T1 (P1, human ~2 h / CC ~15 min, plus the owner's transfer)**: environment. Install Python 3.11+, transfer `full` and the Stammdaten zip, run the arrival checks.
  - Surfaced by: S1.
  - Files: none.
  - Verify: step 0.3 table; suite green.
- [ ] **T2 (P1, human ~3 h / CC ~20 min, plus ~2.5 h unattended)**: pre-copy, Stammdaten placement, gate on `gate-v036` from a clean detached checkout.
  - Surfaced by: A1, A3, outside voice 4.
  - Files: none.
  - Verify: `all_passed`, the log checks.
- [ ] **T3 (P1, human ~4 h / CC ~1 h)**: reconciliation and attribution.
  - Surfaced by: T1, T2, CQ2, CQ3.
  - Files: scratch only.
  - Verify: TSV diff 0; 100 member rows = six MdBs; every move attributed.
- [ ] **T4 (P1, human ~1 h / CC ~10 min, plus ~1 h unattended)**: in-place repersist of `full`, determinism, browser checks.
  - Surfaced by: A2, outside voice 2.
  - Files: none.
  - Verify: `_content_digests` equal; `--validate-publication`; pages at 375 px and in dark mode.
- [ ] **T5 (P2, human ~2 h / CC ~30 min)**: the docs PR.
  - Surfaced by: step 9 and the TODOS proposals.
  - Files: `PRODUCT.md`, `docs/plans/a3-phase4.md`, `TODOS.md`, `AGENTS.md`, `docs/plans/e4-repersist-gate.json`, `docs/plans/e4-repersist-compare-{shared,all}.txt`.
  - Verify: class 11 audit.

Sequential implementation, no parallelization opportunity.

**Completion summary:**
- Step 0: Scope Challenge, scope accepted as-is.
- Reality rows: 7/7 emitted; 2 unverified premises.
- Architecture: 3 issues.
- Code quality: 3 issues.
- Tests: diagram produced; 2 gaps.
- Performance: 1 issue.
- NOT in scope: written.
- What already exists: written.
- TODOS proposals: 3.
- Failure modes: 0 critical gaps.
- Unresolved decisions: 0. D1–D9 were taken by the planner and are listed for the owner.
- Outside voice: Codex, completed, 4 findings.
- Parallelization: 1 lane, sequential.
- Lake Score: N/A.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run (no scope or strategy change) | |
| Outside Review | Codex (`gpt-6-astra`), default-on outside voice | Independent 2nd opinion | 1 | completed, issues found | 4 findings (2 High, 2 Medium), 4 folded |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN (all folded) | 9 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | not run (no UI change) | |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run (no CLI or workflow change) | |

- **OUTSIDE COVERAGE:** Codex plan-review phase, completed, `VERDICT: FINDINGS`. All 4 findings were verified in the code and folded into steps 1, 5 and the risk entries.
- **CROSS-MODEL:** the two reviews do not overlap. Native found the environment blocker, the schema-marker and digest reuse, and the publishable-Fakten gap. Codex found the report rewriting, the recovery path, the member-level proof and the checkout freeze.
- **VERDICT:** ENG reviewed, with every finding folded into the plan. Ready to run once the owner confirms D1–D9 and completes step 0.

NO UNRESOLVED DECISIONS
