# A3 Phase 3: the full backfill (started 2026-10-25)

Handoff: [a3-phase3-handoff.md](a3-phase3-handoff.md). Plan: [a3-coverage.md](a3-coverage.md), Phase 3.

## Owner decisions, 2026-10-25 (one question, before step 1)

1. **Clone source:** a fresh `cp -c` of `.context/dip-pulse-site`, then the caches copied in, `--offline --repersist`, and `validate_store_gate.py` as the gate.
2. **WP 20 caches:**
   - allow `--overlap-only` for the current Wahlperiode (test-first);
   - bulk WP 21 as overlap-only;
   - re-merge WP 20 from its staged chunks, right before the WP 20 backfill.
3. **Persons:** `--persons` for WP 18, 19, 20 and 21.
4. **Public-IP logging:** no.

## Step 1: clones (no DIP), 2026-10-25 ~21:36 UTC

- Before the copy, nothing was running and no process had `.context/dip-pulse-site/data` open.
- `~/agent-runs/a3/baseline` and `~/agent-runs/a3/full` are both `cp -c -R` of `.context/dip-pulse-site` (2.3 GB, 291 reports). `baseline` is never written.
- Disk: 20–21 GB free after the clones.

## Step 2: caches copied into `full` (no DIP)

**Copied** from `~/agent-runs/a3/pilot/data/`:
- `dip-vorgang-drucksachen-cache.json`;
- `dip-person-cache.json`;
- `coverage-exclusions.json`;
- `dip-bulk/` (wp17–wp20, 100 MB).

**Checked** with `dip_cache.DipCache.load(full, newest_wahlperiode=21)` (`~/agent-runs/a3/phase3/check_copies.py`):
- **Vorgänge: 77,993**, WP 19 50,702 and WP 18 27,291.
  - The handoff's split (50,693 + 27,284) is the 77,977 from before the 16 later one-at-a-time additions. The total matches.
- **Persons: 1,273,** all loaded. They were fetched 2026-10-24 09:25 to 2026-10-25 11:28 UTC, so they expire from 2026-11-23.
- **Exclusions: 84.**

**Not copied:**
- `abgeordnetenwatch-cache.json`: byte-identical in the pilot and the base.
- `dip-vorgang-cache.json` (the Politikfelder cache), because the pilot's is not a superset of the base's (`~/agent-runs/a3/phase3/cmp_vorgang_cache.py`):

  | | base | pilot |
  |---|---:|---:|
  | Vorgänge | 7,511 | 7,661 (+150) |
  | Drucksache numbers | 2,401 | 2,429 (+28) |
  | shared Vorgänge with `titel` | 4,056 | 0 |

  - The pilot ran on branch code whose `vorgang_cache_record` has no `titel`. Copying its cache would strip `titel` from 4,056 entries, which main's vote "Worum es geht" reads.
  - Every other field is equal. The 150 Vorgänge and 28 numbers cost a few batched requests to fetch again.

## Blocker found before any DIP request: the branch is behind the base's code

- **The base was built by main's code:**
  - `exports/datenstand.json` names commit 54875da, export format 7;
  - the store's `schema_migrations` is version 6;
  - its Politikfelder cache carries `titel`.
- **This branch is behind main:**
  - 14 commits behind, with merge base cfcd249 (v0.20.0.0);
  - `SCHEMA_VERSION = 5` and `EXPORT_FORMAT = 6`;
  - no `titel` in `vorgang_cache_record`.
  - The pilot store is at migration 5.
- **Branch persist does not refuse a newer store.** It does `INSERT OR IGNORE` of its own version. So a `--repersist` or backfill on the branch code would silently rewrite a migration-6 store with the older code. Phase 4's `baseline` vs `full` comparison would then mix code changes with coverage.
- **The bulk cache is not affected.** Main's `validate_dip_protocol.py` changes the shape-error handling and the Vorgang cache record (`titel`), but not the Drucksache positions stored in `dip-vorgang-drucksachen-cache.json`.
- **A trial merge** (`git merge-tree`) conflicts in 5 files:
  - `scripts/build_dip_pulse_site.py`;
  - `scripts/validate_dip_protocol.py`;
  - `TODOS.md`;
  - `tests/test_a1_followups.py`;
  - `tests/test_facts.py`.
- **Next:** the owner decides whether main is merged into `worktree-a3-plan` before any build on `full`. Nothing has been written to `full` beyond the copied caches.

## Main merged into the branch (owner go 2026-10-25): ea049a9

- **Five conflicting files resolved:**
  - `validate_dip_protocol.py`: both new exception classes kept.
  - `build_dip_pulse_site.py`: main's `CachedReportError` guard around every cached-report load, with the branch's exclusion filters kept.
  - `TODOS.md`: the items main moved to Completed stay there.
  - Two test files.
- **README contradiction fixed.** It had auto-merged into two contradictory `--protocol-wahlperiode` rows: main's "default 21, backfill bypasses it" next to the branch's "default 0, scopes the backfill". It now follows the code, which is the branch's.
- **Export format 6/7 → 8.** Both sides had bumped from 5 independently:
  - branch 6: per-WP recipes;
  - main 7: vote context.
  - `docs/stable-ids.md`, `docs/project-documentation.md` and README follow.
- **`r6-ausschuss` (new on main) now carries and groups by the Wahlperiode.** The branch's every-recipe test caught that it pooled committees across Wahlperioden. Its caveat adds "Je Wahlperiode gezählt, die jüngste zuerst."
  - No published figure exists yet. On the base store, which holds WP 20/21 only, r6's rows now split per WP instead of pooling WP 20 and WP 21.
- **Suite:** 1,621 tests OK (2 skipped).

## `--overlap-only` for the current Wahlperiode: 0653cc1

- **Change:** `sitting_span(..., allow_current=overlap_only)`.
  - A Wahlperiode after the catalog's newest is still refused.
  - Without `--overlap-only`, the current one is still refused.
- **Tests (3 new):**
  - the current WP as overlap-only drops the shared Vorgänge and caches none of its own;
  - a closed WP merged after the current overlap leaves the shared ones out, which is the planned WP 21 → WP 20 order;
  - WP 22 is refused.
- **Suite:** 1,624 tests OK.
- **Staleness:** a staged WP 21 chunk is never re-asked. A later WP 21 overlap run therefore reuses the old open newest chunk. To refresh it, delete `dip-bulk/wp21/` first.

## `full` repersisted and gated on the merged code, 2026-10-25 21:50–22:20 UTC (no DIP)

- **Command:** `validate_store_gate.py ~/agent-runs/a3/full`. Its first check is the `--offline --repersist`.
  - Receipt: `~/agent-runs/a3/phase3/gate-receipt.json`. Logs: `phase3/gate-run.log` and `phase3/gate-scratch/*.log`.
- **All checks passed:**
  - replay;
  - integrity and foreign keys;
  - order independence (half-then-full and replayed, each grouping like a fresh build);
  - unchanged replay keeps the store;
  - links;
  - export against the store;
  - publication.
- **The store now has the merged stamps:** migration 6, export format 8, commit 0653cc1.
- **Time and memory:**
  - The gate took 1,781 s, with a peak RSS of 2.57 GB.
  - The replay alone took 446 s, against 453 s for the same store on 2026-10-20.
- **One count moved in the repersist:**

  | | before | after |
  |---|---:|---:|
  | Zwischenfragen | 1,433 | 1,246 |
  | contributions | 16,787 | 16,600 |

  - The cause is the branch's speech rules v6 (d803f96, "one Zwischenfrage per exchange, not per marker"), which reaches the WP 20/21 base for the first time.
  - That is a code change already reviewed in the pilot, not a cache effect.
  - All other counts are unchanged: 290 protocols, 26,267 speeches, 217 votes, 154,078 vote members, 710 facts.
- **Disk:** the 3.3 GB of scratch clones were removed after the receipt was written, and the logs kept. 15 GB is free.

## Step 3: prefetch. Purpose and cost, written before sending

Request log: `~/agent-runs/a3/phase3-requests.log`. Runs only after the gate has finished with `full`. A build and a prefetch never write the same output dir at once.

1. **`--persons` for WP 18 and WP 19:**
   - refreshes the 1,273 cached persons ahead of the 30-day expiry;
   - `differing` compares them with the 2026-10-24/25 answers, and is expected to be empty apart from real changes;
   - about 19 requests.
2. **`--persons` for WP 20 and WP 21:** new, so the WP 20/21 re-acquisition does no `/person/{id}` lookups. Roughly 20 requests.
3. **`--drucksachen --overlap-only` for WP 21:**
   - a count, then month chunks from the first WP 21 sitting;
   - drops from the cache every WP 18/19 Vorgang that also has WP 21 positions, a residual a3-pilot.md left open;
   - stages `wp21/vorgaenge.json` for the WP 20 merge;
   - size unmeasured, roughly 150–300 requests.
4. **`--drucksachen` for WP 20 (no `--overlap-only`), right before the WP 20 backfill, not now:**
   - First delete the open newest `wp21` chunk and re-run step 3. Only that chunk is fetched again, a few requests, so a Vorgang that gained a WP 21 position since then is caught.
   - Then the WP 20 merge: all 44 chunks are staged, so it costs 1 total request.
   - It writes the WP 20 Vorgänge minus the 19↔20 and 20↔21 overlaps.
   - Doing step 3 now and refreshing it then keeps the handoff's residual window (a WP 20 Vorgang gaining a WP 21 position after the WP 21 bulk) at hours, and still protects WP 18/19 now.

### Step 3 result, 2026-10-25 22:23–22:35 UTC

- **Requests:** 309 DIP requests, all answered, with no failure (`phase3-requests.log`).
- **Persons:** no differing field in any Wahlperiode. The person cache went from 1,273 to 1,943.

  | WP | persons |
  |---|---:|
  | 18 | 871 |
  | 19 | 973 |
  | 20 | 1,036 |
  | 21 | 832 |

- **WP 21 `--overlap-only`:**
  - 20 month chunks, 25,950 positions, equal to DIP's total.
  - **244 Vorgänge are shared with an earlier Wahlperiode:** 1 with WP 18, 25 with WP 19, 218 with WP 20, and none with WP 17.
  - **Vorgang cache: 77,993 → 77,967.** 26 WP 18/19 Vorgänge that run on into WP 21 were dropped (25 WP 19, 1 WP 18).
    - These were cached without their WP 21 positions, the residual a3-pilot.md left open ("a WP 19 Vorgang that runs into WP 21"). They now take the one-at-a-time query.
    - Any of the 19 pilot reports that used one of them may differ in its Drucksache links. The step 5 comparison will show that.
  - The 218 shared with WP 20 are left out at the WP 20 merge (step 3.4, before the WP 20 backfill).

## Step 4: the backfill. Purposes and cost, written before sending

**Runner:** `~/agent-runs/a3/phase3/backfill_drip.py N`, adapted from `drip.py`, run under `nohup caffeinate -i`.
- It runs `build_dip_pulse_site.py --output-dir ~/agent-runs/a3/full --backfill-incomplete --protocol-wahlperiode N --sleep 2`.
- **When DIP goes silent,** it rests 6 h on the wall clock and runs the same command again.
  - Silent means one of two things: the run's last DIP request went unanswered and the run printed a `[summary]` with only `source_unavailable`/`excluded`; or every DIP request of the run went unanswered and there was no traceback.
  - The second case covers a re-run that is still blocked, where the catalog request fails before any summary.
- **It stops for a human on:**
  - any other summary reason;
  - a crash;
  - the disk watchdog (below 1.5 GB);
  - a network error in the request log (DNS, unreachable).
- It logs peak RSS (`/usr/bin/time -l`) and the DIP requests per cycle.

**4.1, catalog refresh:** `build_dip_pulse_site.py --output-dir full --sleep 2 --detail-limit -1`.
- It is online, refreshes the catalog and acquires no sitting, since the backfills acquire everything.
- **DIP cost:**
  - the catalog, a few requests, as on 2026-10-25 (3–4);
  - the Politikfelder `refresh_vorgang_cache`, which re-asks every cached Vorgang with no Sachgebiet that a stored report names. The cache holds 4,086 with an empty Sachgebiet out of 7,511, so up to ~41 batches of 100.
  - That ~41 recurs once per online run, so once per backfill cycle, not per sitting.
- **Other sources:** roll-call list pages at www.bundestag.de, if votes run.

**4.2, WP 18 backfill:**
- The expected scope is 194 sittings to acquire: 245 in the catalog, 51 excluded.
- The run-1 `[backfill]` lines are checked against that before the run is left alone. A different number stops it.
- **DIP:** about 3 per sitting plus the Politikfelder step, so ~600–800 in all.
- **dserver:** 194 XML, paced by `XmlPacer`. It stopped answering after ~150 on 2026-10-20. A `SourceSlowError` stops the runner for a human, and where it hit is recorded.

**After each WP:**
- read the `[summary]`;
- read the `politikfelder: fetched … failed` line and the build's Politikfelder `not_fetched` summary;
- record seconds per sitting, RSS and DIP requests.

**Known cost:** the WP 21 refresh and the WP 20 merge (step 3.4) also drop shared Vorgänge that the WP 18/19 backfills just cached one at a time. That costs requests, not correctness.

### 4.1 result, 2026-10-25 22:38–22:55 UTC

- **Run:** exit 0, 1,012 s, peak RSS 1.53 GB.
- **DIP:** 89 requests, all answered.
  - 47 `/plenarprotokoll`: a full catalog fetch, since the base catalog was past its full-fetch age.
  - 42 `/vorgang` from the Politikfelder step: 4,142 Vorgänge, none failed.
- **Catalog:** WP 18 245, WP 19 239, WP 20 214, WP 21 103, as the handoff expected.
- **Facts:** 710 → 716 rows, in 154 periods (was 153). The refreshed catalog adds a period; the Fakten count is unchanged at 187.
- **`[summary]`:** 84 of 84 not acquired, all `excluded` (the D2 list).

### 4.2 WP 18, started 2026-10-25 ~22:57 UTC

- Runner PID 94401.
- **Scope check passed:** `[backfill] selected per Wahlperiode: WP 18: 194`.
