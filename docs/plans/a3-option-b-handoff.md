# Handoff: DIP option B, bulk downloads per Wahlperiode (next session)

Read this whole file first. Then read in [a3-pilot.md](a3-pilot.md):
- "Pilot re-run, second attempt, 2026-10-23" and its subsections, "DIP request reductions 1–4" and "Workaround while the personal key is pending".

## The problem in one paragraph

DIP (`search.dip.bundestag.de`, the API that links speeches to proceedings and documents) answers roughly 90–100 requests, then goes silent for 3–6 hours. It sends no error: every request times out after 60 s.
- **Measured:** 104 requests on 2026-10-23 morning, then silence. A probe was still silent at +3 h and answered at +6 h. Then 87 requests, then silence again.
- **Per sitting:** after reductions 1–4, a sitting still costs about 26 DIP requests. About 18 of those are one `/vorgangsposition?f.vorgang=ID` per proceeding, and about 4 are `/person/{id}`.
- **Totals:** a WP 18/19 backfill (~400 sittings) is about 10,000 requests, which is about 110 windows.
- **Batching is ruled out.** The DIP OpenAPI spec (1.2) makes only `f.id`, `f.wahlperiode`, `f.dokumentnummer` and `f.frage_nummer` repeatable, so per-sitting requests cannot be batched.

## What option B is (owner approved 2026-10-23: "please write a handoff prompt to implement B")

1. **Bulk Drucksache positions per closed Wahlperiode.**
   - **The query:** `/vorgangsposition?f.wahlperiode=N&f.dokumentart=Drucksache`, paged at 100.
   - **Measured `numFound` (2026-10-23 17:55 UTC):** WP 19 has **73,849**, WP 18 has **40,865**. That is about 1,150 requests for both, against about 7,000 one Vorgang at a time.
   - **Where it goes:** grouped by `vorgang_id`, through `compact_drucksache_position`, into the existing cross-run cache `data/dip-vorgang-drucksachen-cache.json` (`scripts/dip_cache.py`, c7c5d3c).
   - The per-sitting code (`enrich_with_api` → `linked_drucksachen_for_vorgang`, `scripts/validate_dip_protocol.py`) then needs no change: a cached Vorgang costs no request.
2. **Bulk persons per Wahlperiode:** `/person?f.wahlperiode=N`, paged at 100, into `data/dip-person-cache.json`.
   - It replaces about 1,600 single `/person/{id}` lookups with a few dozen requests.
   - `ingest_mdb_roster` (`scripts/build_dip_pulse_site.py`) already lists `/person` this way.
   - Its size is not measured. Its first page gives `numFound`.

Expected total for WP 18/19 with both: about **2,500 DIP requests**, roughly 30 windows instead of 110.

## State (2026-10-23, ~19:00 UTC)

- **Branch:** `worktree-a3-plan` in `/Users/Luca/Projects/poliwatch/.claude/worktrees/a3-plan`.
  - Tip 39ed530 plus this handoff's commit. **Not pushed;** push only if the owner says so.
- **Suite:** 1468 tests, OK (2 skipped).
- **Built today, all test-first:**
  - the exclusion record as the durable list (e71e8ce);
  - `DIP_REQUEST_LOG` (874fa3f, 3c122f2);
  - reductions 1–4 (e0632e3, 33ab996, fa56e27, c7c5d3c, 3e57e98);
  - the run-level DIP stop `DipBreaker` (2921e1c).
- **The drip runner is running:** `~/agent-runs/a3/drip.py`, started detached with `nohup`. Check it with `pgrep -fl drip.py`.
  - It cycles the 27-sitting pilot on the clone `~/agent-runs/a3/pilot`, waits 3 h after DIP goes silent, and resumes.
  - It writes `drip.log`, `drip-state.json`, `pilot-run-<n>.log`, and every request to `pilot-requests.log` (all UTC; the owner is on CEST, UTC+2).
  - Cycle 1 acquired 19/238, with 6 person lookups failed. 18 sittings remain.
  - **Open owner question:** raise `--wait-hours` from 3 to 6. DIP was still silent at +3 h.
- **The drip and any live bulk download share one DIP budget** (same IP, same key). Never run both against DIP at once. See step 5.
- **Saved data for the match checks,** read-only, all in `~/agent-runs/a3/pilot/data/`:
  - `dip-vorgang-drucksachen-cache.json`: the 23 Vorgänge of 19/238, fetched one at a time, 22 with Drucksachen, all WP 19;
  - `dip-person-cache.json`: 12 `/person/{id}` records;
  - `plenarprotokoll-19-238.json`: the sitting's report.

## Your task, in order

One step at a time. Code is test-first (the tdd skill). Confirm the seams with the owner in **one** AskUserQuestion before the first test, with your recommendation first. Commit each step with its result in the message.

### 1. Read and decide the shape (no DIP)

- **Read:** `scripts/dip_cache.py`, `enrich_with_api` (the person loop and `linked_drucksachen_for_vorgang`), `ApiClient.list_all` and `holds_all`, `DipBreaker`, and `fetch_catalog` as a model for count-checked lists.
- **Recommended shape:** a separate prefetch command, `scripts/prefetch_dip_bulk.py --output-dir OUT --wahlperiode N [--persons]`, that fills the two cache files and exits. The build stays unchanged.
- **Chunking:**
  - Split the Drucksache download into date chunks (`f.datum.start`/`f.datum.end`, e.g. one month), so each chunk is fetched in one go, checked against its own `numFound` and saved. A run stopped by the breaker resumes at the first unsaved chunk.
  - Don't rely on a DIP cursor staying valid across hours. Restarting a chunk costs at most its own pages.
  - **Completeness:** the chunks must add up to the Wahlperiode's total (one request). Positions dated outside the WP's span need an open first and last chunk, or a check that the sum matches.
- **Only closed Wahlperioden.** The current one keeps the one-at-a-time path.

### 2. Match check against the saved data (no DIP)

The bulk result must give each Vorgang **exactly** what the one-at-a-time query gave: the same compact Drucksachen, **in the same order**. Order can matter downstream, e.g. `unique_by` keeps the first entry.
- Build the grouping and ordering from fixtures in tests.
- **The real check needs one bulk chunk covering 19/238's Vorgänge.** That costs DIP requests, so it belongs in step 5's first live window. Write the comparison script now, offline, against the saved 23 entries, and run it then.
- **If the order differs:** find DIP's per-Vorgang order (e.g. `datum`, then `id`) from the saved data and reproduce it. If it can't be reproduced, report which downstream values depend on order before going on.

### 3. Fallbacks (test-first)

- **A Vorgang absent from the bulk index** is fetched one at a time, as today, and is never assumed to be empty. 19/238 has one Vorgang with no Drucksache, and a `mitberaten` Vorgang may sit in another Wahlperiode.
  - So the bulk fill writes only Vorgänge it saw.
  - The build must not mark the rest as empty.
- **A person absent from the bulk list** is fetched with `/person/{id}`, as today. Speakers can include Bundesrat members and non-MdB ministers.
- **Bulk entries go into the existing caches with the existing rules:**
  - Vorgänge carry `"wahlperiode": N` and persist only while N is closed.
  - Persons get `fetched_at` and expire after 30 days (`PERSON_MAX_AGE_DAYS`).

### 4. Persons (test-first)

- **The bulk `/person` record must match `/person/{id}`** in the fields the build reads (`compact_person`, and whatever else touches the record), or be made to.
  - Compare the bulk records of the 12 saved persons with the saved records, field by field, in the live window.
  - Volatile fields such as `aktualisiert` may differ. Name any other difference.
- **A 30-day expiry is too short for a backfill spanning weeks.** The bulk list is cheap, though, so re-running it is fine. Decide with the owner whether the prefetch refreshes it.

### 5. Live run: coordinate with the drip

- **Sequence.** Bulk first, then sittings, because every bulk entry saves requests on every later sitting. Recommended:
  1. Stop the drip while it is waiting, never mid-run: check `drip.log` and `pgrep -fl build_dip_pulse_site`.
  2. Run the prefetch in its own drip-style windows (stop on the breaker, rest, resume) until WP 19, then WP 18, are complete.
  3. Restart the drip for the pilot.
  - Ask the owner before stopping the drip.
- **First window:**
  - one small chunk around 19/238's date, then run step 2's comparison;
  - the persons list for WP 19, then step 4's comparison.
  - Go on only if both match.
- **Request log:** set `DIP_REQUEST_LOG` (e.g. `~/agent-runs/a3/bulk-requests.log`), so windows and recovery keep being measured.
- **Paths:** the prefetch writes into the pilot clone (`~/agent-runs/a3/pilot`), never into `.context/dip-pulse-site`.

### 6. Report and stop

Report to the owner:
- the match results: Drucksachen order and content, and the person fields;
- the requests spent per Wahlperiode;
- the windows used;
- the request log's window size and recovery time;
- the new per-sitting cost, measured on the next pilot cycle.

**Phase 3, the full backfill, needs the owner's explicit go. Don't start it.**

## Rules

- **Pre-release:** no compatibility shims. Report old and new values for any count that moves. A cache answer must equal a live answer, so no figure should move. If one does, that is a bug to report.
- **DIP's budget is the scarce resource:**
  - No probe bursts.
  - Every live request has a purpose written down before it is sent.
  - Tests never touch the network: stub `ApiClient.get_json`/`list_all` or `urlopen`.
- **Never print the API key** (`DIP_API_KEY` in `.env.local`, loaded by `dip.load_local_env`). The request log masks it already.
- Never mutate `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site`. Someone else may be running an offline render there.
- **Python:** `/opt/miniconda3/bin/python3.13`. Run the tests with `-m unittest discover -s tests`. Keep output filtered to failures and counts.
- **Worktree guard:** it refuses compound shell lines that mix git, `cd` and heredocs piped to python. Use `git -C <path>`, plain commands or script files.
- **Background processes:** a background job of a non-interactive zsh ignores SIGINT; stop builds with SIGTERM.
- Pass `model` on every Agent call (haiku fetches, sonnet reads and judges, opus decides).
- **Times:** logs are UTC; the owner reads CEST.
