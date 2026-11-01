# Handoff: A3 Phase 4, verify and document (next session)

Read this whole file first. Then read:
- [a3-coverage.md](a3-coverage.md), "Phase 4: verify and document": the steps this session runs.
- [a3-phase3.md](a3-phase3.md), from "Step 4" to the end: what Phase 3 did, per Wahlperiode, and the step 5 report with the open identity finding.
- [source-errors.md](../source-errors.md): the list of errors in the official sources. Add to it when a check finds one.

**Phase 3 finished 2026-10-28.** Phase 4 needs the owner to look at results; stop where this file says so.

## Where things stand (2026-10-29)

- **Branch:** `worktree-a3-plan` in `/Users/Luca/Projects/poliwatch/.claude/worktrees/a3-plan`. Tip 24e60b4 plus this file's commit. **Not pushed;** push only if the owner says so.
- **Suite:** 1,625 tests, OK (2 skipped).
- **Clones under `~/agent-runs/a3/`:**
  - `full` (5.4 GB): the Phase 3 store and site, WP 18–21. **The object of Phase 4.**
  - `baseline` (2.3 GB): the untouched base before Phase 3. **Never write to it.** It is the comparison base.
  - `pilot` (2.5 GB): the 19 pilot sittings (WP 18/19) on pre-merge code, plus the base.
  - Disk: 32 GB free on 2026-10-29.
- **Store in `full`:**

  | WP | protocols | votes |
  |---|---:|---:|
  | 18 | 194 | 127 |
  | 19 | 206 | 179 |
  | 20 | 213 | 171 |
  | 21 | 103 | 79 |

  - Every vote has an agenda-item link.
  - 85 sittings are excluded (`full/data/coverage-exclusions.json`): the reviewed D2 list (WP 18: 51, WP 19: 33) plus **20/11** (owner decision 2026-10-28; diagnostic in a3-phase3.md 4.4).
  - Roster: 1,712 MdBs among 3,724 DIP persons; Abgeordnete: 740 listed, 2,005 profile pages.
  - 529 Fakten; 556 votes in the Abstimmungen archive.
- **Memory:** peak RSS of a full online build is now about 7.9 GB (WP 21), up from 2.9 GB after WP 18. An offline `--repersist` of `pilot` took ~8 min. On 2026-10-26 macOS swap ate the disk down to 3.7 GB free; watch free disk during any full build.
- **Nothing is running.** Check with `pgrep -fl "backfill_drip|build_dip_pulse_site|prefetch_dip_bulk"`.

## Open owner decision: the identity finding

From a3-phase3.md step 5, "Finding: voters' bundestag.de links and the identity registry":
- WP 18/19 roll-call members have no bundestag.de link in `full` (filter from #107).
- Restoring the links alone splits 423 persons (pilot measurement, 4,063 → 4,643), because the registry's pass 3 counts differing per-Wahlperiode URLs as different people. The patch is kept unapplied: [a3-voter-profile-links.patch](a3-voter-profile-links.patch).
- WP 20 voters are already split by `/biografien/` against `/biografien20/` URLs (1,558 voter ids, `baseline` 1,555).
- **Recommended order:** finish Phase 4's comparison on today's `full` (so it does not mix a code change with coverage), then fix the registry rule as its own test-first change with its own old/new report.
- **Do not apply the patch** or change the registry before the owner decides.

## Your task, in order

Follow a3-coverage.md Phase 4. What each step needs here:

1. **Gate script.** Run `scripts/validate_store_gate.py` on `~/agent-runs/a3/full`. Commit the receipt (a3-coverage.md: "Gate receipts from Phase 0 and Phase 4 are committed").

2. **Missing count.** Re-measure the per-WP missing table on a fresh catalog.
   - That needs an online run: a few DIP requests for the catalog, plus the Politikfelder batches (~60). Write the purpose down before sending, and set `DIP_REQUEST_LOG=~/agent-runs/a3/phase3-requests.log`.
   - Expected: 0 missing except the 85 excluded, plus any sitting DIP has added since 2026-10-28 (WP 21 is still running). Each non-zero is listed with a reason.

3. **Value comparison.** Run `scripts/compare_store_values.py ~/agent-runs/a3/baseline ~/agent-runs/a3/full` twice:
   - `--cohort shared`: value movement on the same sittings;
   - `--cohort all`: coverage.
   - Report them separately. For each WP 20/21 figure that moved, give old and new values and why, using the reasons the plan lists.
   - Expect the WP 20/21 vote counts to move: WP 20 165 → 171, WP 21 52 → 79, because the re-acquired sittings are now vote-complete.

4. **Spot checks** in Chrome, light and dark:
   - one WP 18 and one WP 19 dossier;
   - a former-MdB profile;
   - `votes/index.html`, the Daten page and `overview.html`.
   - **Also check the roll-call votes that matched no TOP.** These are recorded as backfill warnings (`[N/N] roll-call vote … matched no TOP`) in `~/agent-runs/a3/phase3/backfill-wp*-run-*.log`, including the kept `run-0-*` logs:
     - WP 18: 22 votes in 18/30, 18/33, 18/39, 18/47, 18/115, 18/134, 18/144, 18/170, 18/179, 18/190, 18/199, 18/202, 18/212, 18/240;
     - WP 19: 19 votes in 19/4, 19/29, 19/45, 19/64, 19/126, 19/129, 19/130, 19/137, 19/143, 19/198, 19/230, 19/234, 19/236;
     - WP 20: 16 votes in 20/28, 20/40, 20/42, 20/54, 20/66, 20/69, 20/97, 20/141, 20/210;
     - WP 21: 6 votes in 21/14, 21/37, 21/40, 21/83, 21/99.
     - Many are Bundeswehr mandates, some with no document number at all (source-errors C3). Pick a few per WP: is the vote reachable on the site, and where?
   - Record the size and timing of the store, the site and memory.

5. **Docs.**
   - State the covered range in README, PRODUCT.md:80 and the Daten page.
   - Move A3 to Completed in TODOS with the measured numbers.
   - Add the larger site size to the hosting item in TODOS.
   - Update CONTEXT.md only if a term changed.

6. **Report and stop.** Give the owner the gate result, the missing table, both comparisons and the spot-check findings, then ask about the identity finding.

## Rules

- **DIP:** set `DIP_REQUEST_LOG=~/agent-runs/a3/phase3-requests.log` for every online run.
  - Phase 3 sent about 6,000 DIP requests. Once (2026-10-26, after ~1,200 in 24 h) DIP answered 5 `/vorgang` batches with an HTTP 400 "Enodia Verification" bot-check page.
  - If that appears again, stop and tell the owner; do not retry in a loop.
- **The runner `~/agent-runs/a3/phase3/backfill_drip.py`** (outside the repo) was changed in Phase 3. It now stops for a human on an Enodia page, and it passes `--exclude-document-number` through to the build.
- **A source refusal stops a whole build** before persist. A sitting goes on the exclusion list only after the owner has read its diagnostic.
- **dserver:** `XmlPacer` pauses 60 min after every 50 XML.
- **Keep the Mac on AC power for long runs.** `caffeinate -i` does not hold a Mac on battery awake.
- **Person cache:** the WP 18–21 person lists were fetched 2026-10-25 and expire after 30 days, around 2026-11-24. A backfill after that refetches them (~40 requests with `prefetch_dip_bulk.py --persons`).
- **Write old and new values** whenever a fix moves a number (CLAUDE.md).
- **Open items from Phase 3, in TODOS.md:**
  - "20/11: the chair's handover exchange with the next speaker" (P2): brings 20/11 back.
  - The WP 18/19 nested-turn rules: these keep sittings on the D2 list.
