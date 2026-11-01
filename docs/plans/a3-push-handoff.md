# Handoff: A3 to main (merge main, full gate on the merged tree, ship)

Read this whole file first, then:
- [a3-phase4.md](a3-phase4.md), the whole file, especially the last section, "Gate at the branch tip, 2026-10-31". Its figures are the comparison base for step 3.
- [a3-coverage.md](a3-coverage.md), section "Phase 4: verify and document".
- `TODOS.md` on this branch: "The carried-forward registry diverges from a fresh build after A3" and "Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs".
- Project memory: `v1-push-2026-10-31.md`, `a3-option-b-bulk.md`, `ship-subagent-budget.md`.

**Goal.** Bring A3 (the WP 18–21 backfill and the identity, Bundesrat and replay fixes) into `main` as one PR. First merge current `main` into this branch. Then run the complete store gate on the merged tree. Fix the one known false CHANGELOG claim, record the results, and ship. **Stop for the owner** at the points marked STOP.

## Where things stand (2026-10-31, evening)

- **Branch.** `worktree-a3-plan` at `/Users/Luca/Projects/poliwatch/.claude/worktrees/a3-plan`, tip 497302a, then this file's commit.
  - 120 commits ahead of `origin/main`. The merge base is 1b2df58 (v0.23.7.0).
  - `origin/worktree-a3-plan` holds an older push. **Do not push or open a PR without the owner's go.**
- **`main` has moved.** It is at 6899184 (v0.25.1.0). Two PRs are open and may be merged by the time you start; check with `gh pr view 122 123`:
  - **#122 v0.25.2.0, lane/correctness.**
    - The facts engine and the rebuild refuse a distribution SQLite.
    - Antrag extractor 7 → 9. A store persisted with extractor 7 is refused until `--offline --repersist`; the gate's replay does that.
  - **#123 v0.26.0.0, lane/release.**
    - Release script, `--data-tag` and `build_revision.py`.
    - `publication_state.validate_public_output` also scans `data/exports/**/DATA.md` and `datenstand.json`.
- **Versions.** This branch's VERSION is 0.24.1.0 and its CHANGELOG has entries 0.24.1.0 and 0.24.0.0. Those numbers collide with main, which already used 0.24.0.0 (#113). At ship time, fold this branch's entries into one new entry above main's newest.
- **Last gate (tip, 2026-10-31).** It was a partial run: the disk watchdog stopped it during half-then-full, and no receipt was written.
  - `replayed_store_groups_like_fresh` **passes**: 1,942 = 1,942.
  - Krampe/Köstering is healed.
  - Bundesrat roster rows go 1,712 → 1,360 by repersist alone.
  - 302 persons hold only retired bindings, 281 of them Bundesrat. 289 of them have a page, and 8 of those are linked from the index.
  - Full table: a3-phase4.md.

## Data and machine

- `~/agent-runs/a3/full` (about 5.4 GB) is the Phase 3 store and site. **Never write to it.** Clone it with `cp -cR` (APFS clone, cheap).
- Keep `~/agent-runs/a3/rule-c/`, `phase3/`, `phase3-requests.log` and `phase4/*.sh|*.py`.
  - The gate-tip clone and scratch were deleted on 2026-10-31 with the owner's OK. The `gate-tip-scratch/*.log` files that a3-phase4.md cites are gone; the figures recorded there stand.
  - `phase4/gate-tip.sh` is the template for step 3.
  - `phase4/registry_counts.py` reproduces the retired-only counts (read-only).
  - `phase4/roster-tip.sh` is not needed (no roster refetch).
- **Disk.** About 52 GB free on 2026-10-31. A full gate needs the clone plus about 13 GB of scratch. The watchdog in `gate-tip.sh` stops at 4 GB free.
  - Run nothing else heavy at the same time. The last gate died because other worktrees filled the disk.
  - Close memory-heavy apps: peak RSS is about 7–8 GB, and swap has filled the disk before.
- **Network.** None is needed. The gate is offline. **No DIP or bundestag.de requests** unless the owner says so; the DIP budget and the dserver limits are in `a3-option-b-bulk.md`.
- **Python.** `/opt/miniconda3/bin/python3.13`, the same interpreter as the earlier gates.

## Steps

1. **Orient.** Run `git status` and `git log --oneline -3`, and check `gh pr view 122 123 --json state,mergedAt`. Fetch `origin/main`.

2. **Merge `origin/main` into `worktree-a3-plan`** (a real merge commit; never rebase 120 commits). Use the `resolving-merge-conflicts` skill. Expected conflict areas:
   - `CHANGELOG.md`, `TODOS.md`, `VERSION`: keep main's version. Keep all entries and interleave the TODOS. This branch's CHANGELOG entries get renumbered at ship.
   - `scripts/publication_state.py` and `tests/test_publication_state.py`: this branch has the `local-path` lookbehind fix (no match on `/home/` inside a URL). #123 adds the scan of `DATA.md` and `datenstand.json`. Keep both.
   - `scripts/build_dip_pulse_site.py`, `scripts/persist_dip_pulse_store.py`, `scripts/person_registry.py`: large files touched on both sides. Resolve hunk by hunk. **STOP and ask the owner** on any conflict where both sides changed the same logic.
   - Then run the full suite: `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`, which must pass. Also run `node tests/run_bills_browser_check.mjs /opt/miniconda3/bin/python3.13`.

3. **Full store gate on the merged tree.**
   - Copy `phase4/gate-tip.sh` to `phase4/gate-merged.sh` and change it in three places:
     - `OUT=$P4/gate-merged`
     - `SCRATCH=$P4/gate-merged-scratch`
     - the log and receipt names
   - Keep `--today 2026-10-28` so the figures stay comparable to Phase 4 and the tip gate.
   - Run it in the background with its watchdog and wait for completion. Don't poll in a loop.
   - **Done when** every gate step finishes and `gate-merged-receipt.json` is written: replay, fresh, half-then-full, unchanged replay, link audit, export, `--validate-publication`.
   - **Then:**
     - Compare every row of the tip table in a3-phase4.md, old against new.
     - Explain each move. Expected sources:
       - extractor 9: `forderung` passages and the 196/217 description count;
       - main's merges up to v0.26.0.0;
       - anything else, which is a finding.
     - Rerun `registry_counts.py` on the gate stores.
   - If the watchdog stops it again, report free disk and what was running. Don't loosen the watchdog.

4. **Fix the known false CHANGELOG claim.** The Bundesrat entry on this branch says „A store built before this keeps those rows until the roster is fetched again (`--enrich mp-roster`)“. Measured: an `--offline --repersist` alone drops the 352 Bundesrat roster rows (1,712 → 1,360). State what actually keeps the rows, if anything, and correct the sentence with that figure.

5. **Record.**
   - Add a section „Gate on the merged tree, <date>“ to a3-phase4.md: command, commit, completion of each step, the comparison table and the explanations.
   - Update the two registry TODOs with the new counts.
   - Add this fact to the TODO „Settle the roll-call source“, bullet 1: 0 of the 232 „Endgültiges Ergebnis“ blocks in the cached WP 20/21 XML list non-voters, so only the XLSX has them. It was found on 2026-10-31 and not yet recorded.
   - Commit (no push).

6. **STOP: report to the owner** with the gate result and these open decisions:
   - (a) The 302 retired-only persons, 289 with a page reachable only by URL: fix the registry `ever_mdb` evidence before the merge, or ship and keep the TODO.
   - (b) `docs/plans/a3-voter-profile-links.patch`: applying it needs a refetch of about 306 roll-call lists from bundestag.de. That needs the owner's go, and it isn't required for the merge.
   - (c) Go to push and open the PR.

7. **Ship, on the owner's go:** run `/gstack-ship`.
   - Reviewers: Sonnet with merged checklists, staggered (`ship-subagent-budget`).
   - Version: MINOR is likely, because of a new data scope and identity rules.
   - The CHANGELOG must report the moved figures, old and new (CLAUDE.md pre-release rule).

## After A3 merges (wave 2, from the v1 push plan)

- The A3-gated TODOs: Dossier count disclosure, r2 Textanteil, the backfill error line, XML Drucksache refs.
- Recipe SQL edges.
- The lost roll-call member rows.
- Seat counts, then Zwischenrufe.
- A Diskursanalyse prototype for the owner.
- Before the first real data release, the P1 items of the TODO „Release pipeline: deferred /ship review findings“ (from #123).

## Rules

- Don't delete anything under `~/agent-runs/a3` except your own `gate-merged*` work, and that only after the results are recorded.
- No DIP or bundestag.de requests and no push without the owner's go.
- CLAUDE.md: report every moved figure, old and new, and why the new one is right. Review findings follow the fix-now-or-defer rule.
- Update the project memory when you stop.
