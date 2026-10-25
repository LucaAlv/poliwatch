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
