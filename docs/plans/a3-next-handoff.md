# Handoff: WP 18/19 download, counting audit, pilot re-run (A3, next session)

Read this whole file first, then [a3-rule5-validation.md](a3-rule5-validation.md). Read [a3-pilot.md](a3-pilot.md) only for Finding 2 (request rate) and "What is open before Phase 3", and [a3-coverage.md](a3-coverage.md) only for Phase 1 when you reach the pilot re-run.

## State (2026-10-20)

- **Worktree:** `/Users/Luca/Projects/poliwatch/.claude/worktrees/a3-plan`, branch `worktree-a3-plan`. Check with `git log origin/worktree-a3-plan..HEAD` whether the rule-5 commits (d2e33c2 … 4de20ab) are pushed. Push only if the owner says so.
- **Done:** speech rule 5 sub-rules 6a–6d for WP 18/19 XML. On the 175 downloaded WP 18/19 files the refusals fell from 37 to 20; the 290 WP 20/21 files are unchanged.
- **Not started:**
  - the full WP 18/19 download (about 309 files missing of 484);
  - the counting audit on all WP 18/19 files;
  - the 6c DIP cross-check;
  - the pilot re-run;
  - Phase 3.

## Your task, in order

### 1. Probe before anything else

- **Probe:** send one request to dserver (`curl -sS -o /dev/null -w '%{http_code} %{time_total}\n' https://dserver.bundestag.de/btp/19/19001.xml`) and one cheap DIP request, the way the pilot did. The DIP API key comes from the project `.env` (see `load_local_env`).
- **If either does not answer**, stop. Report to the owner, and don't retry in a loop. Both servers stopped answering after a few hundred requests on 2026-10-20 (a3-pilot.md, Finding 2).

### 2. Measure a sustainable rate (a3-pilot.md, open item 2)

- **How:** small bursts, for example 20 dserver files at 3 s spacing, then 20 at 2 s. Stop at the first timeout or non-200 and back off. Never go below 1 s spacing; 1 s was already enough to get cut off after about 150 files.
- **Record** the result in a3-pilot.md under Finding 2: requests, spacing, failures and time of day.
- **Then** propose the backfill default `--sleep` from it. Do not change the code default without the owner.

### 3. Download the rest of WP 18/19

- **Where to:** `~/agent-runs/a3/wp18-19-xml/`, named `<wp>-<n>.xml` like the existing 175, from `https://dserver.bundestag.de/btp/<wp>/<wp><nnn>.xml` (WP 18 has 245 sittings, WP 19 has 239).
- **How:**
  - Write a small resumable script under `~/agent-runs/a3/tools/` that skips existing files.
  - Use the measured spacing and stop after 3 consecutive failures.
  - Run it in the background.
  - Record the sha256 of each file in a manifest beside them.
- **Don't** put the XML in the repo.

### 4. Counting audit on every WP 18/19 file

- **Tools:** the tools are in `~/agent-runs/a3/tools/` and `~/agent-runs/a3/tools/rule5/`.
  - `parse_audit.py SCRIPTS_DIR OUT.json` parses all WP 20/21 and WP 18/19 files.
  - `rule5/diff_audit.py NEW [BASE]` gives a compact diff.
  - `rule5/record_counts.py FINAL` gives the count tables.
  - The last run is `~/agent-runs/a3/parse-rule5.json`. Diff the new run against it: the 175 old files and all WP 20/21 files must be unchanged, because the parser did not change.
- **The check the plan names:** run `scripts/audit_offline_turns.py` on the whole WP 18/19 directory as well. It lists every refused marker, not only the first.
- **Group each refusal:**
  - **exclusion:** 18/1 and 19/1;
  - **6e and 6f:** the reviewed one-off cases;
  - **near 6a/6b:** a grant, consent or addressed-turn wording the approved rules do not cover;
  - **role-less chair marker:** the chair printed as a speaker marker without a role, see TODOS.md;
  - **new**.

  Delegate the reading of refused exchanges to `sonnet` subagents in batches. `dump_rede.py STEM REDE_ID [FROM TO]` prints one `<rede>` between two markers.
- **Also check the units the rules let through**, as the last session did ("Review of the units the new rules admit" in a3-rule5-validation.md). An instrumented copy of the parser logs every unit that exists only because of 6a–6d, and someone reads each one in the source.
- **Write it up** as `docs/plans/a3-wp18-19-audit.md`, a counting record like `offline-v5-validation.md`:
  - files and refusals per WP;
  - counts per kind;
  - remaining blockers by group;
  - the review of new-rule units;
  - a proposed exclusion list for the owner.
- **Do not** add or widen a parser rule in this step. If a group is large enough to need one, write a proposal like [a3-rule5-wp18-19.md](a3-rule5-wp18-19.md) and ask the owner.

### 5. The 6c cross-check (ADR 0002)

- **When:** once DIP answers.
- **What:** for every split Rede (`<outer id>:<marker>`, for example 18/70 Binder and 18/10 Bartz, plus any new ones), check that DIP's Aktivitäten for the sitting list that speaker's Rede.
- **Record** the result in the audit record.

### 6. Stop and report to the owner

The owner must decide these before the pilot re-run:
- the exclusion list. Only 18/1 and 19/1 are approved so far; they go through `--exclude-document-number`.
- rules for any large new group, or exclusions for those sittings;
- the TODO "Tell official addresses and presidium Reden apart from Fraktionsreden (ADR 0004)". 18/245 and 19/1 count presidium `<rede>` elements as Reden.
- the TODO "A chair printed as a speaker marker without a role". 21/17 is a miscount in current WP 21 data.
- per marker or per exchange for a Zwischenfrage split across two markers. There are four such fragments in WP 18/19, and the same convention applies in WP 20/21.
- the backfill `--sleep` default.

### 7. Pilot re-run (only after the owner's answers)

- **Spec:** Phase 1 of a3-coverage.md, on the clone `~/agent-runs/a3/pilot`, with `counted_build.py` to count requests.
- **Measure:** seconds per sitting, peak RSS of persist and render, and the abgeordnetenwatch share.
- **Record** the results in a3-pilot.md.

**Phase 3 (the full backfill) needs the owner's explicit go.** Do not start it.

## Work efficiently (owner's request)

- **Delegate by the CLAUDE.md tiers:**
  - `haiku` runs the suite and the harness, and reports pass/fail plus the diff only.
  - `sonnet` reads exchanges and judges them.
  - Pass `model` on every Agent call.
- **Keep the main context small:**
  - Filter every command to failures and counts.
  - Never print whole files, blocker lists or XML.
- **The worktree guard** refuses compound shell lines that mix git, `cd`, `${=var}` or a heredoc piped to python. Use separate plain commands, `git -C <worktree>`, and helper scripts written to `$CLAUDE_JOB_DIR/tmp`.

## Rules of the project

- The tdd skill applies to every code change.
- Pre-release: change in place. Report old and new values for any moved count.
- One step at a time, each committed with its result in the message.
- Python `/opt/miniconda3/bin/python3.13`. Tests: `-m unittest discover -s tests` from the worktree (1397 tests, OK).
- Never mutate `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site`.

## Done when

- The rate is measured and recorded.
- All WP 18/19 XML is downloaded with a sha256 manifest.
- `docs/plans/a3-wp18-19-audit.md` is committed with counts, grouped blockers, the new-rule review and a proposed exclusion list.
- The 6c cross-check is recorded, or recorded as still blocked.
- The owner has the decision list from step 6. The pilot re-run follows only after their answers, and Phase 3 only after their go.
