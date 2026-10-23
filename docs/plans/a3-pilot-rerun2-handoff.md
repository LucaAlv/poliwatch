# Handoff: the A3 pilot re-run, second attempt (next session)

Read this whole file first. Then read:
- in [a3-wp18-19-round2-result.md](a3-wp18-19-round2-result.md): "Owner decisions (round 2 result)", "Built from the owner decisions" and "Exclusion list: 78 → 84";
- in [a3-pilot.md](a3-pilot.md): Finding 2 (all three DIP sections) and "Pilot re-run, 2026-10-22";
- in [a3-coverage.md](a3-coverage.md): Phase 1.

The previous handoff, [a3-pilot-rerun-handoff.md](a3-pilot-rerun-handoff.md), is done except for its steps 3.5 to 4. This file replaces it.

## State (2026-10-22, evening)

- **Worktree:** `/Users/Luca/Projects/poliwatch/.claude/worktrees/a3-plan`, branch `worktree-a3-plan`.
  - It is **not pushed**. 9 commits from 47f584a to 965c046 come on top of the earlier unpushed ones.
  - Push only if the owner says so.
- **Suite:** 1438 tests, OK (2 skipped).
- **Built and committed:**
  - **D2:** a listed `--exclude-document-number` is skipped before acquisition (27a93d5, 965c046). Its reason is `excluded`, and the coverage line reads "nicht erfasst (ausgeschlossen)".
  - **Eight role spellings** (691b4fa).
  - **ADR 0004 rule:** a Vizepräsident(in) who owns a `<rede>` and is printed with a `<fraktion>` speaks for that Fraktion (5cc5982).
- **Exclusion list:** 84 numbers, in the round-2 record and as JSON at `~/agent-runs/a3/round2/final-exclusions-r3.json`. All 400 WP 18/19 sittings off the list parse with every role mapped.
- **Pilot clone:** `~/agent-runs/a3/pilot`.
  - It is a copy-on-write clone (`cp -c`) of `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site`.
  - It has already been repersisted with speech rules v6 at 5cc5982: 665 s, peak RSS 2.36 GB. Don't repersist again.
  - **Its store is untouched by the failed run.**
- **The pilot is prepared:**
  - The arguments are in `~/agent-runs/a3/pilot-args.txt`: 27 sittings, `--sleep 2`, `--vote-scan-pages 90`, and the 84 exclusions. 8 of the 27 are listed, to test the D2 skip.
  - The runner is `~/agent-runs/a3/run-pilot.sh`. It writes `~/agent-runs/a3/pilot-run.log`, wraps the run in `/usr/bin/time -l`, and stops the run (SIGINT) if free disk falls below 1.5 GB.
- **Why it has not run:** the first attempt, at 18:37 UTC, timed out on its very first DIP request (the catalog). About 10 minutes earlier, 43 requests had answered normally.
  - This is the third failure of this shape. The working hypothesis is that DIP stops answering after roughly 40–60 requests in a window of unknown length. That is not established.
  - dserver answered normally at 18:43.

## Progress (2026-10-22, late evening)

- **Step 1 done:** "Owner decisions (round 3)" in the round-2 record. 18/62 and 18/90 stay excluded, the D2 naming is confirmed, the key is renamed to `coverage.excluded` (abd3ddf), and there is no push.
- **Step 2 done:**
  - The nine markers, plus three Lammert markers, were read and committed in 66b45a8. 18/96 and 18/109 are silent misses. Both rule proposals are open, and the owner said "neither yet".
  - The D2 limit is fixed: offline runs and `--fetch-xml` honour `data/coverage-exclusions.json` (517ecee).
- **Step 3.3 done:** `DIP_REQUEST_LOG` (874fa3f). `run-pilot.sh` exports it to `~/agent-runs/a3/pilot-requests.log`.
- **Suite:** 1446 tests, OK (2 skipped).
- **Not logged:** abgeordnetenwatch requests (own client). DIP (`/person` included), dserver and bundestag.de pages are logged.
- **The exclusion record is the list (option A):** every run honours `data/coverage-exclusions.json`, and `--include-document-number` takes a sitting off. The pilot still passes all 84 numbers, which seeds the clone's record.
- **Disk:** 8.4 GB free at 23:16 UTC.
- **Next:** step 3.4, which starts the pilot directly. Do it only on the owner's go. DIP's last request was 2026-10-22 18:40 UTC.

## Your task, in order

One step at a time. Code changes are test-first (the tdd skill), committed with their result in the message. Pre-release: change in place, and report old and new values for any count that moves.

### 1. Owner questions (one AskUserQuestion call), with the recommendation first

1. **18/62 and 18/90.** In both, Pau (Vizepräsidentin, DIE LINKE) asks in the Fragestunde, outside any `<rede>`. The parser reads her as a `fragestunde_antwort` with an unmapped role. In 18/62, Singhammer's chair turn is read the same way. Both are on the list now.
   - Recommended: keep them excluded.
   - Alternative: a Fragestunde rule that reads a presidium marker with a Fraktion as an MdB question.
2. **Three changes made without a decision. Confirm or revert:**
   - the public coverage label "nicht erfasst (Quelle abgelehnt)" → "nicht erfasst (ausgeschlossen)";
   - the new failure code `excluded` in `publication_state.FAILURE_CODES` and in `docs/designs/fixed-public-experience.md`;
   - the manifest key `coverage.source_rejected`, which is kept although it now holds the excluded sittings. Recommended: rename it to `excluded`, which reopens the export contract.
3. **Push** `worktree-a3-plan`?

Record the answers in the round-2 record under a new heading "Owner decisions (round 3)" and commit. Don't build anything the owner declines.

### 2. Work that needs no DIP (do it while DIP rests)

- **The nine inside markers.** These are Vizepräsident(in) markers that print a `<fraktion>` but sit inside someone else's `<rede>`: 18/60, 18/79, 18/82, 18/85, 18/89, 18/91, 18/96, 18/109, 18/113. They are read as Sitzungsleitung (`presidium_marker`).
  - Five are in sittings that will be counted: 18/79, 18/85, 18/91, 18/96, 18/109.
  - One Sonnet reader checks each with `~/agent-runs/a3/review/round2/dump_rede.py`: is it chair text, or the Vizepräsident(in)'s own Zwischenfrage or Kurzintervention?
  - A wrong reading is a silent miscount. Report it, and propose a rule only with the owner's yes.
  - To list them, scan for `<redner>` markers after the first in a `<rede>` whose `<rolle_lang>` is Vizepräsident(in) and which have a `<fraktion>`. The earlier ad-hoc scan was `vp_scan.py` in the old session's scratchpad, which is gone, so rewrite it.
- **D2 known limit.** `--offline --repersist` and `--fetch-xml` read cached reports and do not consult the list, so a sitting cached before it was listed is still re-persisted.
  - Options: make repersist accept `--exclude-document-number`, or drop the listed reports from the cached entries.
  - Ask the owner only if the change alters a public figure. Otherwise build it test-first.

### 3. Pilot re-run (only after DIP has rested)

1. **Wait.** DIP's last request was 2026-10-22 18:40 UTC. Start no earlier than several hours after that, preferably the next day. If you are unsure, ask the owner; don't probe-burst DIP to find out.
2. **Disk:** check `df -h ~`. The clone shares its blocks with the original, and the run adds about 30 XML files, the staged store (about 350 MB) and the render. Ask the owner if less than about 4 GB is free.
3. **Log every DIP request.** Before the run, add timestamped per-request logging to the DIP client, so the moment DIP stops is known exactly.
   - Do this test-first, and keep it to stderr or a log file. The API key must never be printed.
   - Check whether `dip.ApiClient` already logs. If a flag is needed, keep it small.
4. **Start the run directly:** `~/agent-runs/a3/run-pilot.sh`, in the background.
   - Send **no probe burst** first; the probes spent the budget last time.
   - At most one curl to dserver, which does not count against DIP.
   - The full catalog fetch opens every run and counts against the budget.
   - If DIP or dserver stops answering, or a `SourceSlowError` appears, stop and report. Don't retry in a loop.
5. **Record in a3-pilot.md** everything Phase 1 lists:
   - the unmapped Sprechrollen (`derive.find_unmapped_sprechrollen` over the cached reports);
   - the raw Fraktion strings from the XML, the vote pages and DIP `/person`, mapped through `derive.zusammenschluss`;
   - the WP 18/19 Einzelplan numbers, with evidence;
   - the abgeordnetenwatch share;
   - the roll-call match rate, the TOPs without votes, and the fraction strings on the vote pages;
   - DIP requests per second, seconds per sitting, and peak RSS of persist and render;
   - an extrapolation for the full run;
   - whether the 8 listed sittings were skipped with no fetch and were recorded in `data/coverage-exclusions.json`.
6. **Identity check (TODOS.md):** the 7 MdBs printed with a middle initial (W. Birkwald and others). Does the merge join them across WP 18/19 and 20/21? Report it; don't fix it.

### 4. Stop and report

Report to the owner:
- the decisions;
- any moved counts, old and new;
- the result of the nine-marker read;
- the DIP request log: where DIP stopped, if it did;
- the pilot measurements and the extrapolation.

**Phase 3 (the full backfill) needs the owner's explicit go. Do not start it.**

## Rules

- Never mutate `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site`, and don't put XML in the repo.
- Don't widen a rule beyond what the owner decides. A new group gets a written proposal and a question.
- Keep the main context small: filter every command to failures and counts. Never print whole files, logs or XML.
  - The pilot log is full of `[redner-id]` warnings, so grep it.
- Pass `model` on every Agent call: haiku fetches, sonnet reads and judges, opus decides. Stagger the Sonnet readers.
- Tests must not touch the network. Stub `dip.fetch_text`, `ApiClient` or the pacer.
- Python is `/opt/miniconda3/bin/python3.13`. Run the tests with `-m unittest discover -s tests` (1438 at 965c046).
- **Parse audit:**
  - Use `~/agent-runs/a3/round2/parse_audit2.py SCRIPTS_DIR OUT.json`. It is already repointed to the reference store's `data/xml`, read-only, and takes about 8 minutes.
  - Its latest run, at 5cc5982, is `parse-vp.json`.
  - WP 20/21 must stay unchanged by any parser change.
- The DIP API key is `DIP_API_KEY` in `.env.local` and is loaded by `dip.load_local_env`. Never print it.
- **Worktree guard:** it refuses compound shell lines that mix git, `cd`, `${=var}` or a heredoc piped to python. Use `git -C <path>`, plain commands or script files.
- The push hook flags `scripts/validate_dip_protocol.py:915` (`key = (…)`) as a MEDIUM env.kv finding. It's a false positive.
