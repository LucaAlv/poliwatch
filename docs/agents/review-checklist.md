# Pre-ship review checklist

The bug classes `/gstack-ship` kept finding between v0.6 and v0.26 after earlier review sessions had passed the branch.

## When and how to apply it

- **Build session:** when you finish a change, before handing it to `/gstack-ship`.
- **`code-review`:** run it as a third sub-agent beside Standards and Spec. Paste this file into its prompt and let it report class by class, without the 400-word cap.
- **Start of `/gstack-ship`:** if the "Checks no diff review replaces" below have no result for this branch yet, run them before ship's own steps.
- **`/gstack-review` inside `/gstack-ship`:** apply every class in the first review pass. From the second fix cycle on, apply only class 13 to each fix commit (CLAUDE.md "Review findings: fix now or defer").

Done means every class below is either answered for this diff, with the file and line that answers it, or marked not touched by the diff. A class answered "probably fine" is not answered.

**Small diffs** (under 200 changed lines in `git diff --shortstat`, red team's own threshold) answer only the classes whose trigger the diff hits, with no list of untouched ones, and skip the adversarial lenses below. A diff that changes only documentation answers class 11 alone. Ship's small-fix runs have logged no findings, so the full pass there costs more than it finds.

## Diff classes

1. **Sibling path.** A new guard, refusal or invariant was added to one entry point. Grep every other caller and write path that reaches the same state, and state why each is covered: online, `--offline`, `--no-persist`, `--repersist`, facts engine, release script. _Example: `run_facts_engine` skipped the distribution-copy refusal that `persist_dip_pulse_store.connect` applies (PR #91)._

2. **Stale beats fresh.** A carry-forward, cache or merge can restore an old value over a freshly computed one, or a refetch replaces a record whole and drops fields the old one had. When the fresh value is absent or different, decide whether that means missing data or a changed truth. _Example: `carry_forward_vote_provenance` reverted parser fixes (PR #73). Still open: `cache["vorgaenge"].update(records)` drops cached titel (TODOS.md "B4 review findings: lower-priority edges", item 9)._

3. **Order and history.** Output must depend only on the current inputs. Look for dict order, first occurrence wins, or a previously stored row (bindings, durable merges) that a fresh build would not have. _Example: order-dependent `person_registry._fold` (PR #89); `registry.bind` kept old bindings, so a replay gave 154,015 vote_members where a fresh build gave 154,078._

4. **One key, one function.** Every identity key (vote id, person id, document number, profile URL) is defined by exactly one function that parser, persist, SQL and renderer all use. Try blank, `None`, duplicate and URL-shaped values. _Example: `derive.vote_identity` used the raw id, persist the cleaned one, and `None` became `"None"`; an Abstimmung-page link stored as profile URL folded 63 rows in 11 votes into one person per vote._

5. **Absent vs zero.** For every new query or aggregate, work through NULL, zero rows, a real zero and a missing source. SQL `= ?` never matches NULL (`IS ?`); `x or 0` turns unknown into zero. _Example: NULL `page_quadrant` silently broke citations, and a zero-debut week was dropped from the baseline (9edb6a5)._

6. **Derived columns.** When a merge or migration touches stored counts, list every column and page rule derived from them and recompute each. Page logic and SQL logic must count the same way. _Example: `_repoint_party` merged `vote_fractions` but left `leading_vote` stale (9edb6a5)._

7. **Neighbour binding.** A matcher that uses text proximity, a normalized title or a tolerance can bind the adjacent vote, Vorgang or document. Name the proof of identity (number, tally) and what happens when it is absent; refuse on a proven mismatch only. A vote's document number need not appear in its outcome text, so its absence proves nothing. Run the matcher over all real votes and the fixtures and report false-positive and false-negative counts. _Example: a tally-less neighbouring decision stealing the official badge (TODOS P1)._

8. **Hostile text.** Every new scanner, regex or truncation of source text gets adversarial strings: unbalanced quotes, partial entities, the cut boundary, very long runs. Time them. This applies to the fix too. _Example: the charref fix e3028b2 crashed `int()` on more than 4,300 zeros._

9. **Input shape.** Every new CLI flag, JSON file, URL or id that reaches a path, a DIP request or a label gets null, wrong type, blank, `..`, backslash, userinfo and over-long values. Each must end in a clear refusal, never a traceback or silent acceptance. _Example, still open: a `--previous-manifest` of JSON `null` labels the release "Erste Veröffentlichung" (TODOS.md "Release pipeline: deferred /ship review findings", item 10a)._

10. **Interrupted run.** For each write, rename, swap or cleanup, state what is left on disk if the process stops right after it. Check that no cleanup runs in a mode that keeps no new output (`--no-persist`, `--offline`, missing store). _Example: `write_facts_pages` deleted the previous build's pages after a `--no-persist` run (6578a1a)._

11. **Claims.** For every new or changed sentence in DATA.md, the codebook, recipe texts, UI copy, the CHANGELOG or the PR body, cite the code line that makes it true. Where the sentence states a figure, also cite the real-store value. Check each table separately; a rule that holds for one table is not proof for another. When DATA.md or `docs/data-methods.md` changed, audit every touched definition against the writing code before any other review. _Example: this ended the codebook loop of PR #121, where 20 false statements were fixed in one commit (16a3509) and review then converged in 2 cycles._

12. **Loop cost.** Work done per vote, receipt or person inside a render or persist loop gets measured on the reference store's full data. Count its `votes` and `vote_members` there rather than assuming a size.

13. **Last commit.** After every fix, diff the fix commit against its tests, TODOS.md and the PR body, and run the sibling-path class on the fix itself. _Example: the charref fix in class 8._

## Checks no diff review replaces

Run these before `/gstack-ship` whenever the diff can reach them:

- **Figures:** replay the change with the README recipe "Validate a data correction" (a `cp -cR` baseline of `.context/dip-pulse-site`, the change applied to a second copy, `scripts/compare_store_values.py`) and report the figures that moved, with old and new values (CLAUDE.md pre-release rule). Diff reviews have missed figure bugs that only a replay showed: the stale `registry.bind` bindings in class 3 surfaced as a replay count that differed from a fresh build.
- **Fresh vs incremental:** a from-scratch build and an incremental build give identical CSVs and pages.
- **Inline JS and layout:** open the page in a browser and click through it, at 375px and in dark mode. String-assertion tests missed that a running smooth scroll made Chrome drop 13 of 17 rapid sidebar clicks; a live DevTools check caught it (PR #72).
- **Python patch level:** html.parser behaviour changed in 2025 patch releases. Local `python3` (the miniconda 3.13.2 AGENTS.md names) predates them; CI installs the newest patch of 3.11, 3.12 and 3.13. Run the suite on a current 3.13 patch too: `uv run --python 3.13.12 python -m unittest discover -s tests`, raising the patch when CI's setup-python step reports a newer one.
- **Adversarial lenses:** red team and a Codex review find most of ship's critical findings. Ship runs both again in its own review and never accepts an earlier run in their place, so a run before ship pays only where it saves ship a fix cycle: run both once on the tip you hand to ship, for diffs of 200 changed lines or more, and not again after each fix. Codex: `/gstack-codex review`. Red team: `/gstack-review` dispatches it for diffs over 200 lines or after a CRITICAL security finding; otherwise give a subagent `~/.claude/skills/gstack/review/specialists/red-team.md` as its prompt, plus the diff command and the commit list.

## Settled, do not re-file

- DIP plenarprotokoll API order is datum-desc (measured).
- The D10 `protocol_acquisition` completeness gap is known and tracked as an open item (TODOS.md "Persist per-sitting acquisition state in the store"); it is not a new finding.
- OUTPUT spellings that differ only in case share one writer lock on macOS: `person_registry.private_dir` names the lock directory from the spelling, and the case-insensitive file system resolves both spellings to one directory.
- Pregate flags in this repo are mostly false positives: `key` identifiers, bare numbers, `u:p@` test URLs, and the gstack-redact phone rule on large numeric literals. Check the matched text before acting on one.
