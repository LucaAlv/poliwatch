# Pre-ship review checklist

The bug classes `/gstack-ship` kept finding after earlier review sessions had passed the branch. Each comes from at least two ship runs (or one wrong public figure) between v0.6 and v0.26. Apply it to the diff before `/gstack-ship`: in the build session when you finish a change, and in every `code-review` of a branch.

Done means every class below is either answered for this diff, with the file and line that answers it, or marked not touched by the diff. A class answered "probably fine" is not answered.

## Diff classes

1. **Sibling path.** A new guard, refusal or invariant was added to one entry point. Grep every other caller and write path that reaches the same state, and state why each is covered: online, `--offline`, `--no-persist`, `--repersist`, facts engine, release script. _Example: `run_facts_engine` skipped the distribution-copy refusal that `persist_dip_pulse_store.connect` applies (PR #91)._

2. **Stale beats fresh.** A carry-forward, cache or merge can restore an old value over a freshly computed one, or a refetch replaces a record whole and drops fields the old one had. When the fresh value is absent or different, decide whether that means missing data or a changed truth. _Example: `carry_forward_vote_provenance` reverted parser fixes (PR #73); `cache["vorgaenge"].update(records)` drops cached titel._

3. **Order and history.** Output must depend only on the current inputs. Look for dict order, first occurrence wins, or a previously stored row (bindings, durable merges) that a fresh build would not have. _Example: order-dependent `person_registry._fold` (PR #89); `registry.bind` kept old bindings, 154,015 vs 154,078 vote_members._

4. **One key, one function.** Every identity key (vote id, person id, document number, profile URL) is defined by exactly one function that parser, persist, SQL and renderer all use. Try blank, `None`, duplicate and URL-shaped values. _Example: `derive.vote_identity` used the raw id, persist the cleaned one, and `None` became `"None"`; a placeholder profile URL folded 63 rows into one person._

5. **Absent vs zero.** For every new query or aggregate, work through NULL, zero rows, a real zero and a missing source. SQL `= ?` never matches NULL (`IS ?`); `x or 0` turns unknown into zero. _Example: NULL `page_quadrant` silently broke citations, and a zero-debut week was dropped from the baseline (9edb6a5)._

6. **Derived columns.** When a merge or migration touches stored counts, list every column and page rule derived from them and recompute each. Page logic and SQL logic must count the same way. _Example: `_repoint_party` merged `vote_fractions` but left `leading_vote` stale._

7. **Neighbour binding.** A matcher that uses text proximity, a normalized title or a tolerance can bind the adjacent vote, Vorgang or document. Name the proof of identity (number, tally) and what happens when it is absent; refuse on a proven mismatch only. Run it over all real votes and the fixtures and report false-positive and false-negative counts. _Example: a tally-less neighbouring decision stealing the official badge (TODOS P1)._

8. **Hostile text.** Every new scanner, regex or truncation of source text gets adversarial strings: unbalanced quotes, partial entities, the cut boundary, very long runs. Time them. This applies to the fix too. _Example: the charref fix e3028b2 crashed `int()` on more than 4,300 zeros._

9. **Input shape.** Every new CLI flag, JSON file, URL or id that reaches a path, a DIP request or a label gets null, wrong type, blank, `..`, backslash, userinfo and over-long values. Each must end in a clear refusal, never a traceback or silent acceptance. _Example: a `--previous-manifest` of JSON `null` labelled the release "Erste Veröffentlichung"._

10. **Interrupted run.** For each write, rename, swap or cleanup, state what is left on disk if the process stops right after it. Check that no cleanup runs in a mode that keeps no new output (`--no-persist`, `--offline`, missing store). _Example: `write_facts_pages` deleted the previous build's pages after a `--no-persist` run._

11. **Claims.** For every new or changed sentence in DATA.md, the codebook, recipe texts, UI copy, the CHANGELOG or the PR body, cite the code line that makes it true. Where the sentence states a figure, also cite the real-store value. Check each table separately; a rule that holds for one table is not proof for another. When DATA.md or `docs/data-methods.md` changed, audit every touched definition against the writing code before any other review. This is what ended the codebook loop: 20 false statements were fixed in one commit, then review converged in 2 cycles.

12. **Loop cost.** Work done per vote, receipt or person inside a render or persist loop gets measured on the real store (about 217 votes, 154k vote_members).

13. **Last commit.** After every fix, diff the fix commit against its tests, TODOS.md and the PR body, and run the sibling-path class on the fix itself. Fixes made during ship have introduced new bugs several times.

## Checks no diff review replaces

Run these before `/gstack-ship` whenever the diff can reach them:

- **Figures:** replay on a `cp -cR` clone of the reference store and report the figures that moved, with old and new values (CLAUDE.md pre-release rule). Every wrong published figure so far was caught this way, never by reading a diff.
- **Fresh vs incremental:** a from-scratch build and an incremental build give identical CSVs and pages.
- **Inline JS and layout:** open the page in a browser and click through it, at 375px and in dark mode. String-assertion tests missed a lost-click bug only DevTools caught.
- **Python patch level:** html.parser behaviour changed in 2025 patches; local `python3` predates them, CI does not. Run the parser tests with `uv run --python 3.13.12` too.
- **Adversarial lenses:** red-team and a Codex review of the branch (`/gstack-codex`) find most of ship's critical findings; run them before ship rather than discovering their findings during it.

## Settled, do not re-file

- DIP plenarprotokoll API order is datum-desc (measured).
- The D10 `protocol_acquisition` completeness gap is known and accepted (TODOS.md).
- A vote's document number need not appear in the outcome text; refuse only on a proven mismatch.
- OUTPUT spellings that differ only in case share one writer lock on macOS (same inode).
- Pregate flags in this repo are mostly false positives: `key` identifiers, bare numbers, `u:p@` test URLs, and the gstack-redact phone rule on large numeric literals. Check the matched text before acting on one.
