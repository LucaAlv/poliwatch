# Handoff: owner decisions, then the A3 pilot re-run (next session)

Read this whole file first. Then read the round-2 result record [a3-wp18-19-round2-result.md](a3-wp18-19-round2-result.md) in full: its questions are step 1 here. Read [a3-pilot.md](a3-pilot.md) for Finding 2, "Known limit of the exclusion list (D2)" and "What is open before Phase 3". Read Phase 1 of [a3-coverage.md](a3-coverage.md) when you reach the pilot.

## State (2026-10-22)

- **Worktree:** `/Users/Luca/Projects/poliwatch/.claude/worktrees/a3-plan`, branch `worktree-a3-plan`. It holds 15 commits since e13f60f and is **not pushed**. Push only if the owner says so.
- **Done:** round 2 is built, test-first, one commit per rule:
  - R2, R4, R3, R1b+R1c;
  - the role-less chair;
  - one Zwischenfrage per exchange (speech rules `VERSION` 6; WP 20/21 Zwischenfragen 1432 → 1246);
  - the R2 follow-up;
  - `XmlPacer` pacing.
- **Also done:** the re-audit (412/484 parse), the review, the 6c DIP check, the exclusion list 73 → 78, and the TODOs. Suite: 1429 tests, OK.
- **Not done:** the pilot re-run.
  - **DIP:** it timed out on the first `/person` probe (2026-10-22 14:01 UTC), about an hour after answering 63 requests normally.
  - **Disk:** it was full. The owner has since freed space: 10 GB free.
- **Gone:** the owner deleted `~/agent-runs/a3/gate` and `~/agent-runs/a3/pilot` to free disk.
  - The 290 WP 20/21 XML files the harness reads from `~/agent-runs/a3/gate/data/xml` are gone with them.
  - The same 290 files are in the reference store `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site/data/xml`.
  - Per [a3-gate-validation.md](a3-gate-validation.md), 21/50 needed no repair, so a fresh copy of the reference store stands in for the gate.
- **Scratch tools:** `~/agent-runs/a3/round2/`: `parse_audit2.py`, `compare.py`, `per_mdb.py`, `merge_scan*.py`, `unit_diff.py`, `split_pages.py`, `person_probe.py`.
  - Each has the gate path hard-coded. Repoint them to the new clone's `data/xml` before use.
  - Reviews are in `~/agent-runs/a3/review/round2/`.

## Your task, in order

One step at a time. Each code change is test-first (the tdd skill) and is committed with its result in the message. Pre-release: change in place, and report old and new values for any count that moves.

### 1. Get the owner's decisions (AskUserQuestion, one call)

These are the open questions of the round-2 record, with the recommended answer first:

1. **D2 semantics.** `--exclude-document-number` acts only on a source rejection, so 6 of the 78 listed sittings parse and would be counted (18/2, 18/29, 18/83, 18/245, 19/1, 19/25).
   - Recommended: a listed number is skipped before acquisition, whatever the parser says.
   - Alternative: a rule per kind.
2. **26 parsing sittings with a role no Sprechrolle rule maps.** Any one of them refuses the whole run at acquisition, listed or not. Recommended, per group:
   - **Official and presidium addresses** (18/178, 18/223, 19/9, 19/19, 19/73): exclude, like 18/245 and 19/1.
   - **A Vizepräsident(in)'s own Fraktionsrede** (18/46, 51, 61, 62, 65, 66, 73, 81, 85, 90, 93, 96, 99, 101, 109, 115, 116): exclude now, with a rule in a later round. The rule would read the `<rede>` as the MdB's Fraktionsrede (ADR 0004). Mapping "Vizepräsidentin" to a side would be wrong.
   - **Role spellings outside R2's six:** extend the closed list in `derive.SPRECHROLLE_RULES`:
     - BMBF, BMG, BMZ (19/67, 19/106, 18/136, 18/173);
     - "Parl. Staatssekretär im Bundesministerium des Innern" (18/124);
     - "… für Verkehr und digitale Infrastruktur" (18/211);
     - "S taatsministerin bei der Bundeskanzlerin" (19/70);
     - "Drogenbeauftragte der Bundesregierung" (18/109).
3. **19/25** (the asker owns the `<rede>`, Röttgen's Rede is nested inside it; the parser swaps the two). Recommended: exclude.

Don't build anything the owner declines. Record the answers in the round-2 record under "Owner decisions (round 2 result)", and commit.

### 2. Build what was decided (one commit each)

- **D2 change, if approved.** A listed number is skipped before acquisition: no report, no store row, no fetch. It is recorded in `data/coverage-exclusions.json` the way a source rejection is today, so the coverage notes still name it.
  - Tests:
    - a listed sitting that parses is not counted;
    - a listed sitting with an unmapped role does not raise;
    - an unlisted refusal still stops the run (D4).
- **Spelling extension, if approved:** add a test per spelling, as R2's tests do.
  - Then re-run the parse audit, with `roles_sha` over the 290 WP 20/21 files.
  - The 290 must stay unchanged.
  - 18/124, 18/136 and 18/173 may start to parse. Any sitting that newly parses needs a new-rule unit review before it leaves the list (round-2 method, `~/agent-runs/a3/review/round2/BRIEF.md`: sonnet subagents read, opus decides).
- **Exclusion list:** update it in the round-2 record. Report old (78) and new.
- **The other exclusions** (presidium addresses, Vizepräsident Fraktionsreden, 19/25) need no code once D2 skips before acquisition.

### 3. Pilot re-run (a3-coverage.md, Phase 1)

1. **Clone.** Copy `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site` to `~/agent-runs/a3/pilot`. Never mutate the original.
   - Check `df -h ~` first. The clone is 2.3 GB; the repersist and render need about 3 GB more.
   - Stop if less than about 6 GB would remain free.
2. **Repersist.** `--offline --repersist` on the clone (speech rules v6). Record the time and peak RSS (`/usr/bin/time -l`). The gate took 453 s and 2.6 GB.
3. **Probe.** One request to dserver (`curl -sS -o /dev/null -w '%{http_code} %{time_total}\n' https://dserver.bundestag.de/btp/19/19001.xml`) and one cheap DIP request.
   - If either does not answer, stop and report. Don't retry in a loop.
4. **Measure DIP `/person`.** Use `~/agent-runs/a3/round2/person_probe.py` in small bursts, never below 1 s spacing (for example 20 at 2 s, then 20 at 1 s), with a pause between bursts.
   - Stop on the first failure or answer over 10 s.
   - Record requests, spacing, failures and time of day in a3-pilot.md, Finding 2.
5. **Run the pilot.** The sample is the one from a3-coverage.md Phase 1, about 25 sittings:
   - the 21 of `docs/plans/a1-turn-investigation.md:17`;
   - first and last of each Wahlperiode;
   - one each of Befragung, Fragestunde and Aktuelle Stunde per WP.

   Adjust the sample:
   - **Replace 18/245 and 19/1** with the nearest sittings that parse and have mapped roles, unless the D2 change has landed. Then a listed sitting is skipped, and keeping them tests that.
   - **Format picks must avoid** the 26 unmapped-role sittings, unless those are excluded or fixed.

   Settings:
   - `--document-number` for each sitting;
   - `--sleep 2`, passed explicitly. Without `--backfill-incomplete` the default is 0;
   - the final exclusion list via `--exclude-document-number`;
   - `--vote-scan-pages 90`;
   - through enrichment, votes, persist, render and facts.

   The XML is paced by `XmlPacer`. A `SourceSlowError` stops the run on purpose: report it, and do not resume in a loop.
6. **Record in a3-pilot.md** everything Phase 1 lists:
   - unmapped Sprechrollen (`derive.find_unmapped_sprechrollen`);
   - raw Fraktion strings;
   - WP 18/19 Einzelplan numbers with evidence;
   - the abgeordnetenwatch share;
   - the roll-call match rate;
   - requests per second, seconds per sitting, peak RSS of persist and render;
   - an extrapolation for the full run.

   Then do the deferred identity check (TODOS.md: the 7 initial-printed MdBs, W. Birkwald etc.): does the merge join them across WP 18/19 and 20/21? Report it; don't fix it.

### 4. Stop and report

Report to the owner:
- the decisions as built;
- any moved counts, old and new;
- the final exclusion list;
- the DIP `/person` result;
- the pilot measurements and extrapolation.

**Phase 3 (the full backfill) needs the owner's explicit go. Do not start it.**

## Rules

- Don't put XML in the repo. Never mutate `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site`.
- Don't widen a rule beyond what the owner decides. A new group large enough to need a rule gets a written proposal and a question.
- Keep the main context small: filter every command to failures and counts. Never print whole files, blocker lists or XML.
- Pass `model` on every Agent call: haiku fetches, sonnet reads and judges, opus decides. Stagger Sonnet reviewers; parallel Opus reviewers have hit the account limit before.
- Tests must not touch the network. A test that falls through to a real fetch is a bug: stub `dip.fetch_text` or the pacer.
- Python is `/opt/miniconda3/bin/python3.13`. Run the tests with `-m unittest discover -s tests` (1429 at e7cd09e plus docs).
- The DIP API key is `DIP_API_KEY` in `.env.local`. Never print it.
- The worktree guard refuses compound shell lines that mix git, `cd`, `${=var}` or a heredoc piped to python. Use separate commands or script files.
- The push hook flags `scripts/validate_dip_protocol.py:915` (`key = (…)`) as a MEDIUM env.kv finding. It's a false positive.
