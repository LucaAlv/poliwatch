# Handoff: WP 18/19 round-2 rule build, then the pilot re-run (A3, next session)

Read this whole file first. Then read the section "Owner decisions, 2026-10-22" and R1–R4 in [a3-rule5-wp18-19-round2.md](a3-rule5-wp18-19-round2.md). Read [a3-wp18-19-audit.md](a3-wp18-19-audit.md) and [a3-rule5-validation.md](a3-rule5-validation.md) for method: how units were reviewed, and how WP 20/21 was proven unchanged. Read [a3-pilot.md](a3-pilot.md) only for Finding 2 and "What is open before Phase 3", and [a3-coverage.md](a3-coverage.md) only for Phase 1 when you reach the pilot.

## State (2026-10-22)

- **Worktree:** `/Users/Luca/Projects/poliwatch/.claude/worktrees/a3-plan`, branch `worktree-a3-plan`, pushed at the decisions commit. Push again only if the owner says so.
- **Done:**
  - rule 5 sub-rules 6a–6d;
  - all 484 WP 18/19 XML downloaded to `~/agent-runs/a3/wp18-19-xml/` (`<wp>-<n>.xml`, sha256 manifest beside it);
  - the counting audit on all of them: 372/484 parse;
  - the 6c DIP check: 7/7 splits confirmed;
  - the owner's decisions on every round-2 question.
- **Not started:** everything below.

## Your task, in order

One step at a time. Each one test-first (the tdd skill applies to every code change) and committed with its result in the message. Pre-release: change in place. Report old and new values for any moved count.

### 1. Build the rules (one commit each, in this order)

1. **R2, role spellings.** Strip U+00AD. Read the "beim/bei der Bundesminister…" long form and the ministry abbreviation as the same side (BMF, BMWi, BMJV, BMI, BMEL, BMUB). When one side is "Minister (Land)" and the other the bare title, take the suffixed one. A real conflict still raises. Add one test per spelling. Target: the 15 conflicting-roles sittings no longer raise. The roles-relaxed audit copy predicts 7 parse.
2. **R4, middle initial.** When matching the chair's named asker, compare against `<nachname>` with a leading initial removed. Do **not** change the stored `last_name` (deferred, decision 4).
3. **R3, 6c floor wording.** Widen `NESTED_REDE_FLOOR` to the forms listed in R3, and add "Sehr verehrte" to `REDE_SALUTATION`. Leave `NESTED_REDE_NOT_FLOOR` unchanged. Must fix 18/17, 18/30, 18/39 and 18/94, which today count a whole Rede as a Zwischenfrage.
4. **R1b + R1c.**
   - R1b: after a valid chair offer, a short Redner turn (about 12 words or fewer) is consent unless it contains a refusal word ("nein", "nee", "nicht", "keine", "später", "lieber nicht"). The following asker must still match the offer, as today.
   - R1c: accept "Darf er/sie (das)?", "Mögen Sie?", "Gestatten Sie?" and "Zusatzfrage" as an offer, but only when the chair's turn names the would-be asker.
   - R1a (a longer closed list) is declined.
5. **Role-less chair** (TODOS.md "Recognize the Sitzungsleitung …"). A role-less `redner` marker inside a member's `<rede>` is Sitzungsleitung when that person chairs the sitting and the text is chair text. Exclude it like 6d. Must fix 21/17 (WP 21, a live miscount) and 18/28. Should unblock 18/95, and 18/10 unless another blocker sits behind it.
6. **Zwischenfrage per exchange.** Consecutive asker markers inside one open exchange, with no new chair offer between them, are one unit. This applies to all Wahlperioden. Known fragments: 18/109 m3, 18/40 m4, 18/124 m5, the 4 in a3-rule5-validation.md, and 20/92 Lötzsch m4. Report the WP 20/21 moves per MdB, old/new.
7. **Backfill pacing.** Build the window logic into the online fetch path, test-first: 2 s spacing, at most about 50 XML per window, a 60-minute pause, and a stop on the first answer over 10 s.
   - Today `--sleep` in `scripts/build_dip_pulse_site.py` defaults to 0, or to `BACKFILL_SLEEP_SECONDS` = 0.5 with `--backfill-incomplete`. Change it in place, and say what you changed in the commit message.
   - `~/agent-runs/a3/tools/fetch_wp18_19.py` is the measured reference.

**WP 20/21 must stay unchanged after steps 1–5,** apart from 21/17 in step 5. Prove it per commit with `units_sha` over the 290 gate files, as a3-rule5-validation.md did, with the harness at `~/agent-runs/a3/tools/parse_audit.py`. Step 6 is expected to move WP 20/21: report the moves, don't hide them.

### 2. Re-audit and review

- Re-run the audit on all 484 WP 18/19 files (`~/agent-runs/a3/tools/rule5/audit_all.py`, `blocker_list.py`, the new-rule probe `make_newrule_parser.py`). Compare against `docs/plans/a3-wp18-19-blockers.tsv`.
- **Unit review:** review every unit a new rule admits, as in the last two rounds (`~/agent-runs/a3/review/BRIEF.md`; sonnet subagents read, opus decides). A wrong unit means fix the rule or put the sitting back on the list.
- **DIP check:** every new 6c split gets the DIP Aktivitäten check (`~/agent-runs/a3/tools/rule5/dip_6c_check.py`, 2 s spacing, cached).
- **The list:** the exclusion list starts at the 73 sittings in the decisions section. Take a sitting off only when it parses and its units pass review. Add one back if its review fails. Report the final number, old (73) and new.
- Write the results into a new record, `docs/plans/a3-wp18-19-round2-result.md`, and commit.

### 3. TODOs to file (one commit)

Add TODOs to TODOS.md for:
- erwiderung-nested, erklaerung-nested, go-debate (a rule each, in a later round);
- the `last_name` initial: after the pilot, check whether the identity merge joins the 7 initial-printed MdBs (W. Birkwald, G. Lämmel, G. Wöhrl, S. Neu, M. Huber, E. Fischer, A. Lamers) across WP 18/19 and WP 20/21;
- `audit_offline_turns.py` stopping on a non-locator ValueError.

Grep first, and update an existing entry rather than adding a duplicate. The presidium-Reden TODO (ADR 0004) stays as it is.

### 4. Pilot re-run

Follow Phase 1 of a3-coverage.md, with the approved exclusions passed via `--exclude-document-number`.
- **First, measure DIP `/person`** in small bursts, never below 1 s spacing. Stop on the first block; don't loop on retries. Record it in a3-pilot.md Finding 2.
- If dserver or DIP doesn't answer the first probe, stop and report.
- Record the pilot result in a3-pilot.md.

### 5. Stop and report

Report the moved counts, the final exclusion list and the pilot result to the owner. **Phase 3 (the full backfill) needs the owner's explicit go. Do not start it.**

## Rules

- Don't put XML in the repo. Never mutate `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site`.
- Don't widen a rule beyond what the decisions say. A new group large enough to need a rule gets a written proposal and a question to the owner.
- Keep the main context small: filter every command to failures and counts. Never print whole files, blocker lists or XML. Pass `model` on every Agent call: haiku fetches, sonnet reads and judges, opus decides.
- Python is `/opt/miniconda3/bin/python3.13`. Run the tests with `-m unittest discover -s tests`. There were 1397 at the decisions commit.
- The DIP API key is `DIP_API_KEY` in `.env.local`. Never print it.
- The worktree guard refuses compound shell lines that mix git, `cd`, `${=var}` or a heredoc piped to python. Use separate commands or script files.
- The push hook flags `scripts/validate_dip_protocol.py:915` (`key = (…)`) as a MEDIUM env.kv finding. It's a false positive.
