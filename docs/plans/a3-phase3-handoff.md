# Handoff: A3 Phase 3, the full backfill, on the option B caches (next session)

Read this whole file first. Then read:
- [a3-coverage.md](a3-coverage.md), "Phase 3: the full backfill" and "Phase 4: verify and document". This handoff replaces Phase 3's clone setup (its `gate` no longer exists) and adds the cache reuse.
- [a3-pilot.md](a3-pilot.md), from "Option B, the bulk prefetch" to the end: how the caches were built and checked, DIP's behaviour, and the per-sitting cost.

**Owner go for Phase 3: 2026-10-25** ("copy the two cache files and get started with phase 3").

## Where things stand (2026-10-25, ~21:30 UTC)

- **Branch:** `worktree-a3-plan` in `/Users/Luca/Projects/poliwatch/.claude/worktrees/a3-plan`. Tip 1bc5797 plus this file's commit. **Not pushed;** push only if the owner says so.
- **Suite:** 1479 tests, OK (2 skipped).
- **Option B is built and verified** (`scripts/prefetch_dip_bulk.py`). The pilot clone `~/agent-runs/a3/pilot/data/` holds:
  - `dip-vorgang-drucksachen-cache.json` (52 MB): 77,993 Vorgänge, WP 19 50,693 and WP 18 27,284. That is the bulk, minus 664 Vorgänge that span two Wahlperioden (17↔18, 18↔19, 19↔20), plus 17 answers fetched one at a time.
  - `dip-person-cache.json`: 1,273 persons. The WP 18/19 bulk lists were fetched 2026-10-24/25 and **expire after 30 days**, around 2026-11-23.
  - `dip-bulk/wp17` … `wp20`: the staged chunks, `total.json` and `vorgaenge.json` per Wahlperiode. A re-merge and the cross-WP overlap drops read these, and copying them avoids about 2,250 requests.
  - `coverage-exclusions.json`: the reviewed D2 list of **84 sittings** (WP 18: 51, WP 19: 33). It is the durable list, and every run leaves these out.
- **Verified:**
  - A cached Vorgang gives exactly the one-at-a-time answer, ids and order: 22/22 reference Vorgänge, and all 5 sittings fetched one at a time before, after the order fix ba52438.
  - Bulk persons equal `/person/{id}` in every field except `aktualisiert`.
- **Cost per sitting with the caches:** about 3 DIP requests for the sitting itself, and about 5 all-in with the Politikfelder `/vorgang` step, against ~26 before option B.
- **DIP behaviour:** since the owner moved to another network on 2026-10-24, DIP answered runs of 450–1,000 requests with no block. Before that it blocked after ~100. The working hypothesis is a per-IP limit, not established. Keep the breaker, the request log and the wall-clock waits anyway.
- **Phase 2 of a3-coverage.md** is built: coverage floor, WP scoping, exclusion list, pacing, summary and exit code, person cache, vote budget, multi-WP roster, Sprechrollen and Einzelplan tables, per-WP Daten recipes, `compare_store_values`. Gaps found 2026-10-25, none blocking:
  - `FRAKTION_WORDING` has no `fraktionslos`. The plan makes this conditional on a Kurzintervention miss, and none is recorded.
  - No evidence of the GitHub issue "Fraktion identity per Wahlperiode". Grep TODOS.md, and open it if it is missing (see `docs/agents/issue-tracker.md`).
  - No test for "a former MdB with no cached speech survives an unchanged offline replay".
- **Known misses the owner accepted** (round-2 decision 4): 18/96 drops one Befragung question, 18/109 drops Bulmahn's closing text. The Vizepräsident rule proposals (a) and (b) are not built.
- **Nothing is running.** The drip and bulk runners have finished. Check with `pgrep -fl "drip.py|bulk_drip|build_dip_pulse_site|prefetch_dip_bulk"`.

## Your task, in order

One step at a time. Commit each step's result to `docs/plans/a3-pilot.md`, or to a new `docs/plans/a3-phase3.md` if you prefer, with old and new values for anything that moves. Before step 1, put the decisions below to the owner in **one** AskUserQuestion, with your recommendation first:

1. **Clone source for `full`.**
   - **Recommended:** a fresh `cp -c` of `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site` (the 290 WP 20/21 sittings). Copy the caches in (step 2), then `--offline --repersist` with the current code and run `scripts/validate_store_gate.py` as the gate.
   - **Alternative:** `cp -c` of `~/agent-runs/a3/pilot`. It already has the caches, the exclusion record and 19 acquired WP 18/19 sittings, but it also carries the pilot's narrowed runs.
2. **WP 20 caches.**
   - Phase 3 re-acquires all WP 20/21 sittings, and WP 20 Vorgänge are not cached: WP 20 was staged only to find overlaps. One at a time, that is about 18 requests per WP 20 sitting, about 4,000 for WP 20.
   - **Recommended:**
     - allow `--overlap-only` for the **current** Wahlperiode (code change, test-first: `sitting_span` refuses it today);
     - bulk WP 21 as overlap-only, an unmeasured size of roughly 150–300 requests;
     - re-run WP 20 **without** `--overlap-only`. Its chunks are staged, so that is 1 total request, and it merges minus the 19↔20 and 20↔21 overlaps.
   - **Residual:** a WP 20 Vorgang that gains a WP 21 position after the WP 21 bulk is missed. Take the WP 21 bulk right before the WP 20 backfill.
   - **Alternative:** leave WP 20 one at a time.
3. **Persons.** Recommended: `--persons` for WP 18 and 19 (refresh, ~19 requests) and for WP 20 and 21 (new, ~20). Persons are not closed-WP bound, and the 30-day expiry applies to each.
4. **Network evidence.** Log the public IP once per runner start (one request to an IP-echo service)? The owner has not answered this yet.

### 1. Set up the clones (no DIP)

- `baseline`: `cp -c -R /Users/Luca/Projects/poliwatch/.context/dip-pulse-site ~/agent-runs/a3/baseline`. **Never write to it.** It is Phase 4's comparison base.
- `full`: from the source the owner chose.
- **Never mutate `.context/dip-pulse-site`.** Someone else may be rendering there.
- **Disk:** 20 GB was free on 2026-10-25. The base is 2.3 GB, and APFS clones cost almost nothing until written. Budget about 4–5 GB of growth for ~690 re-acquired sittings (reports, XML, store). Keep a disk watchdog that stops the run below 1.5 GB free, as `drip.py` does.
- **Memory:** the Mac has 16 GB. The pilot peaked at 2.66 GB, and persist and render on the full store will be larger. Measure it; Phase 1 asked for that figure.

### 2. Copy the caches into `full` (no DIP)

From `~/agent-runs/a3/pilot/data/` into `~/agent-runs/a3/full/data/`:
- `dip-vorgang-drucksachen-cache.json` and `dip-person-cache.json`, the two cache files;
- `dip-bulk/`, the whole tree;
- `coverage-exclusions.json`, unless `full` was cloned from the pilot, which already has it. Without it, the 84 rejected sittings abort the backfill (D4).

Then:
- **Check the copies.** Load each with `dip_cache.DipCache.load(full, newest_wahlperiode=21)` and confirm 77,993 Vorgänge, with the persons not yet expired. Confirm `coverage-exclusions.json` lists 84.
- **Optional:** `abgeordnetenwatch-cache.json` and `dip-vorgang-cache.json` (the Politikfelder cache) from the pilot are supersets of the base's for WP 18/19. Copying them saves requests; compare them first and say what you copied.

### 3. Prefetch (DIP, small)

Set `DIP_REQUEST_LOG=~/agent-runs/a3/phase3-requests.log`. Write each request's purpose down before sending it.
- Run the owner-chosen `--persons` refreshes.
- If the owner chose the WP 20 option: the code change, test-first (the tdd skill), then the WP 21 `--overlap-only` bulk and the WP 20 re-merge.
- Report the prefetch's `[bulk]` JSON lines: positions, written, dropped, differing (expected 0).

### 4. The backfill (DIP and dserver, long)

Follow a3-coverage.md Phase 3, steps 1–3:
1. Refresh the catalog with a normal online build.
2. Run `--backfill-incomplete --protocol-wahlperiode N` for 18, then 19, then 20, then 21.
3. Run the multi-WP roster enrich, then the Vorgang cache fill.

**Run each Wahlperiode in a runner.** Adapt `~/agent-runs/a3/drip.py`:
- **Waits:** wall-clock `sleep_until`, because `time.sleep` does not count the Mac's sleep. Run it under `nohup caffeinate -i`.
- **DIP silent:** rest 6 h and run the **same** command again. A backfill picks up the sittings still missing.
- **Anything else stops it for a human:**
  - a refusal (D4);
  - a crash;
  - the disk watchdog;
  - a network failure (DNS, "nodename nor servname"), which is not a DIP block. On 2026-10-24 the bulk runner rested 6 h for one.
- **After each Wahlperiode, stop and read the `[summary]`.** Fix or re-run before the next Wahlperiode, as the plan says. A newly rejected sitting goes on the exclusion list only after a human has read its diagnostic.

**Expected size (catalog 2026-10-25):**
- WP 18: 245 sittings, 51 excluded, so 194 to acquire.
- WP 19: 239 sittings, 33 excluded, so 206 to acquire.
- WP 20: 214 sittings. WP 21: 103.
- **DIP:** about 5 requests per sitting with the caches, so about 2,000 for WP 18/19. WP 20 adds about 4,000 if it stays one at a time.
- **dserver:** one XML per sitting, paced by `XmlPacer`. It stopped answering after ~150 XML at 1 s spacing on 2026-10-20.
- **www.bundestag.de:** roll-call pages, up to 200 list pages per run.

**Measure per Wahlperiode:**
- DIP requests and windows, from the request log;
- seconds per sitting and peak RSS;
- skipped, `source_unavailable` and quarantined sittings, by reason.

### 5. Report and stop

Report to the owner:
- the clone setup and what was copied;
- the prefetch results;
- per Wahlperiode: acquired, skipped by reason, DIP requests, windows, time and RSS;
- any figure on a WP 18/19 sitting that differs from the pilot's report of the same sitting. The 19 pilot reports are in `~/agent-runs/a3/pilot/data/`, and `~/agent-runs/a3/tools/compare_rerun.py` compares two report sets.

**Phase 4 (verify and document) is the next session's work; don't start it.** Its gate run, value comparison and spot checks need the owner to look at results first.

## Rules

- **Pre-release:** no compatibility shims. Report old and new values for any count that moves. A cache answer must equal a live answer. If a figure moves because of a cache, that is a bug to report.
- **DIP's budget is still the scarce resource:**
  - No probe bursts.
  - Every live request has a written purpose.
  - Tests never touch the network: stub `ApiClient.get_json`/`list_all` or `urlopen`.
- **Never print the API key** (`DIP_API_KEY` in `.env.local`). The request log masks it.
- **Never run a build and a prefetch against the same output dir at once.** A build loads the DIP caches once and rewrites them after every sitting.
- **Python:** `/opt/miniconda3/bin/python3.13`. Tests: `-m unittest discover -s tests`, output filtered to failures and counts. The full suite takes ~80–130 s; run it in the background or with a long timeout.
- **Worktree guard:** it refuses compound shell lines that mix git, `cd` and heredocs piped to python. Use `git -C <path>`, plain commands or script files.
- **Background processes:** a background job of a non-interactive zsh ignores SIGINT; stop builds with SIGTERM.
- **Times:** logs are UTC; the owner reads CEST until 2026-10-25, then CET (UTC+1).
- Pass `model` on every Agent call (haiku fetches, sonnet reads and judges, opus decides).
