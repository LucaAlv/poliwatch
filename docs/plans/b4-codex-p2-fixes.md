# B4: fixes for the Codex review of bfa0e5a, 143a49d, eab8ed5

Source: `/gstack-codex` review on 2026-10-22, 3 × P2, gate PASS. Each finding below
was re-checked against HEAD (eab8ed5) before this plan was written; the "checked"
line says what was run. Branch `worktree-b4-abstimmungen-daily-view`, unpushed.

Order: F1, then F2, then F3. One commit each. F1 is the only one a reader sees today.

## F1. The "geteilt" pill is white text with no background

**Checked:** `scripts/features/votes.py:276-281` renders `<em class="vote-pill">geteilt</em>`
for a tie on an inverted vote (`derive.fraction_position`, `derive.py:608`).
`.vote-pill` (`render_dip_pulse_html.py:3680-3692`) sets `color:white` and no
background; the colour comes only from `.vote-yes` / `.vote-no` / `.vote-abstain`
(`:3676-3678`). So the pill is invisible on the light panel. bfa0e5a fixed the class
string (`vote-pill vote-`) but not the look; the old string was unstyled too.

**Fix:**
1. In `votes.py`, a tie gets its own modifier: `vote-pill vote-split`. Build the class
   from `position == "geteilt"`, or better from `leading is None and position`, so the
   rule doesn't hang on the label text.
2. Add `.vote-split` next to `.vote-abstain` / `.vote-absent` with a neutral background
   that is not the absent grey (`#7a8699` means "nicht abgegeben"; a tie is not
   absence). Check white-on-background contrast ≥ 4.5:1 at 12px/680. Add a
   `:root[data-theme="dark"]` override if the light value fails on the dark panel
   (see the dark rules near `render_dip_pulse_html.py:540`).
3. Update `tests/test_features_votes.py:407` (`test_a_tie_on_an_inverted_vote_gets_a_plain_pill`):
   assert `class="vote-pill vote-split"`, keep the `vote-pill vote-"` negative check,
   and rename the test to match. Add a render test that the stylesheet carries a
   `.vote-split` rule with a `background`, so a class with no rule fails.
4. Look in a browser at a page with an inverted tie, light and dark (or a fixture page
   if the reference data has none; first count how many inverted ties exist, see
   "Measure").

**Not in scope, flag only:** a tie on a non-inverted vote shows no pill at all
(`fraction_position` returns None), an inverted one shows "geteilt". If that asymmetry
looks wrong, raise it with the owner; don't change it here.

## F2. The sanitizer fallback leaks quoted attribute text

**Checked:** `abstract_text('before <a title=">SECRET">visible</a> <![oops]>')` returns
`'before SECRET">visible'`. `_TAG` (`dip_text.py:27`) is `<[!/?a-zA-Z][^>]*>` and stops
at the first `>`, including one inside a quoted attribute value.

Codex also said "comments containing `>` leave comment content behind". Its probe was
wrong: `'x <!-- a > b --> y'` goes through the parser path and returns `'x y'`. The
claim is still worth testing on the **fallback** path, which only runs on markup
html.parser rejects: `'x <!-- a > b --> y <![oops]>'`. If that leaks ` b -->`, fix it
as well.

**Fix (fallback path only; the parser path is correct):**
1. Strip comments before tags: `<!--.*?-->` (DOTALL), then an unclosed `<!--` to the end.
2. Make `_TAG` skip quoted values: `<[!/?a-zA-Z](?:[^>"']|"[^"]*"|'[^']*')*>`. Watch
   for catastrophic backtracking on an unclosed quote. Test that a 100k-char input with
   `<a title="` and no closing quote returns in well under a second. If it doesn't, fall
   back to a small hand-written scanner.
3. Keep eab8ed5's guarantees: `"a < b und c > d"` stays text, and a closed
   `<script>`/`<style>` loses its text.
4. Tests in `tests/test_dip_text.py`, each forced onto the fallback with `<![oops]>`:
   double-quoted `>`, single-quoted `>`, a comment containing `>`, an unclosed comment,
   and the backtracking guard.

**Measure:** run `abstract_text` over all cached abstracts before and after. Expected:
0 of 3,922 change, since none take the fallback today. Report the number either way.

## F3. Abweichler dedupe keys on the name; the store keys on identity

**Checked:** `derive.vote_abweichler` dedupes member rows by `_clean(name)`
(`derive.py:520`). Persist writes `vote_members` keyed `(vote_id, mp_id)`
(`persist_dip_pulse_store.py:377-383`), where `mp_id` comes from
`mp_identity(...)` (`:1390`). That function prefers a trusted abgeordnetenwatch id
(`aw:<id>`), then `profile:<url>`, then `name-party:<name>|<party>`. Then
`registry.bind` may merge records further. So two spellings that share a trusted aw id
are two members to derive and one to the store. Derive says `complete` while the store
holds a different member count. 143a49d's docstring and commit message claim "last row
wins as in the store", which holds only for identical names.

**Limit:** derive has no database, so it can't reproduce registry merges. The goal is
to key on the same identity key persist hands to `upsert_mp`. The docstring should
name the registry as the remaining gap.

**Fix:**
1. Add `derive.vote_member_identity(member) -> str` that returns exactly the string
   `mp_identity` builds for a vote member: `aw:<trusted_aw_id(profile)>`, else
   `profile:<url>` (from `abgeordnetenwatch.url` or `profile_url`), else
   `name-party:<clean name or Unbekannt>|<zusammenschluss or Unbekannt>`. Reuse
   `derive.trusted_aw_id`.
2. In persist's member loop (`:1379-1399`), take `identity_key` from
   `derive.vote_member_identity(member)`, so the two can't drift. Leave `mp_identity`
   itself alone; speeches and the roster use it.
3. In `vote_abweichler`, key `members_by_group[group]` on `vote_member_identity(member)`,
   not the name. Update the docstring: "a member listed twice (same identity key as
   the store binds on) counts once, last row wins; merges the identity registry makes
   later are not seen here".
4. Tests in `tests/test_derive.py` (`VoteAbweichlerTests`):
   - two spellings, one trusted aw id, standing in for a missing member → `partial`,
     nobody named (Codex's case: 3 Ja + 2 Nein rows with one aw id against counts
     3/2 is a mismatch, so not `complete`);
   - two spellings with an untrusted (`match: "name"`) aw id stay two members;
   - a parity test: for a handful of member shapes,
     `derive.vote_member_identity(m) == persist.mp_identity(<the args persist passes>)`.
5. Fix the wording wherever 143a49d made the claim: commit-message history stays, but
   update the CHANGELOG `[Unreleased]` line and any TODOS/plan text that says "as in
   the store".

**Measure (CLAUDE.md: report old → new when a number moves):** replay the reference
store (290 reports) before and after. Count vote groups where two rows share an
identity key but differ in name. Then report Abweichler total (632 before),
`context_state`, `vote_members` (154,015) and any group whose state moves. The expected
move is 0. If anything moves, list each vote and why the new value is more correct.

## Verify

- `python3 -m unittest discover -s tests`: all green, count reported (1,453 before).
- Reference-store replay as in the B4 review-fixes run, `--offline --repersist`, on a
  copy, not the live store. Disk is nearly full, so check free space first (memory
  `b4-ship-run1-result`).
- Browser check for F1 in light and dark.
- `graphify update .` if the graph is initialised.

## Done when

Three commits (F1, F2, F3), each with its test, plus the replay numbers in the last
commit message. Nothing pushed. Next step after this is the re-run of `/gstack-ship`
the B4 ship run 1 note already calls for.

## Handoff prompt

> Implement `docs/plans/b4-codex-p2-fixes.md` on branch
> `worktree-b4-abstimmungen-daily-view` (worktree
> `.claude/worktrees/b4-abstimmungen-daily-view`). It fixes three P2 findings from a
> Codex review of commits bfa0e5a, 143a49d and eab8ed5. Each was re-checked against
> HEAD eab8ed5, and the plan gives the evidence, the fix, the tests and the
> measurement for each.
>
> Do F1 (the invisible "geteilt" tie pill), then F2 (the sanitizer fallback leaking
> quoted attribute text), then F3 (Abweichler dedupe keyed on name instead of the
> store's identity key). One commit each, test-first where it fits. Don't push.
>
> Before you start, read the plan in full, plus `CONTEXT.md` for Abweichler, Mehrheitsvotum
> and Zusammenschluss. The project is pre-release: change things in place, no shims.
> Whenever a figure moves, report old → new and why the new one is more correct.
>
> Stop and ask me before:
> - changing what a tie on a non-inverted vote shows (out of scope, flag only);
> - touching `mp_identity` itself or `registry.bind`;
> - promoting anything into the live reference store (replay on a copy; disk is
>   nearly full, check first).
>
> Finish with: the three commit hashes, the test count, the before/after measurements
> F2 and F3 ask for, the light/dark screenshot verdict for F1, and anything you
> deviated from in the plan, with the reason.
