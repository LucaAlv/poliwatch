# E4 deferred findings 1 to 4: plan

Status: **plan, 2026-11-26, reviewed (Codex, read-only, 2026-11-26; see "Review" at the end); the item 2 window waits for the owner.** Source: TODOS.md, "E4 /gstack-review: deferred findings (2026-11-05)", items 1 to 4 and item 9's second to fourth bullets. The release roadmap needs items 1 to 4 and 7 before the first `--publish`.

Base: main 88d83d3 (v0.46.53.0). Reference store for the replay: `.context/roster-after-52` cloned to `.context/e4-after`, with `.e4-after.private/mdb-stammdaten.zip` (Stand 2026-04-29T08:03:03Z, 4,614 MdB records).

## What the reference store holds today (measured 2026-11-26 on the clone)

- 736 roll-calls, 2013-11-28 to 2026-11-13. 157 `vote_members` rows have a `listed_party_id` (re-filed Stimmen) in 87 roll-calls: Kamann 68, Bülow 60, Pasemann 11, Witt 8, Huber 8, Heßenkemper 2.
- The newest re-filed Stimme lies 1,623 days before the Stand. 11 roll-calls fall in the 90 days before the Stand (2026-01-29 to 2026-04-29) and 44 after it; none of them re-files a Stimme.
- Of the Stammdaten's Mandat days from WP 18 on, none is fraktionslos by rule 3 alone: every fraktionslos day is covered by an explicit `Fraktionslos` record (63 such records). Each of the six re-filed MdBs has one (Kamann from 31.12.2018, Bülow 28.11.2018, Pasemann 15.11.2020, Heßenkemper 29.06.–24.08.2021, Witt and Huber 01.01.2022). So `first_record_days`' guard never fires on this file, and no re-filed Stimme lands on a rule-3 day.
- Seat cross-check (`seat-crosscheck.json`): 736 compared, 720 agree; `after_stand` 1 (1004, 2026-05-22), `change_on_vote_day` 14, `roll_call_short` 1 (440), `shift_between_groups` 0, `unexplained` 0. None of the 16 lies in the 90 days before the Stand.

## Item 2 and item 9 (gap, re-entry): when the Stammdaten prove a group

### The rule (recommended; for the owner's yes)

The Stammdaten prove a member's group on a vote's day only when both hold:

1. **The day is no later than 90 days before the file's Stand** (`last_proved_day` = UTC day of `VERSION` minus 90 days; with today's file 2026-01-29). On later days the page stands. Today's guard is `day > stand_day`.
2. **An explicit Fraktion or Gruppe record of the file covers the day** (`Fraktionslos` records count). A Mandat day no record covers is fraktionslos for the seat counts (rule 3, unchanged), but it proves no group for a Stimme, and neither does the day a record starts right after such a stretch. This one rule replaces `first_record_days` and `RefilingSource.recorded_from`, and covers every case item 9 names: the lead-in before a first record, a gap between two records (A ends on X, B starts on X+n), the tail after a last record that ends before the Mandat, and the lead-in of a re-entry Mandat.

The rest of `_proved_group` stays: one MdB per name in the Wahlperiode, no change on the vote's day, exactly one covering row.

**Why 90 days.** The file says nothing about how late it records a change, and one file is all we have, so no lag can be measured. The window must therefore be generous, and the costs are lopsided. A window too wide only delays a correction: for the newest 90 days of votes before a file's Stand, the Stimme counts for the group the page lists, which is what the site shows without E4, until a later file moves the boundary. A window too narrow lets a lagging file move a correct page row under a wrong group, and the panel then calls the wrong figure a correction. 90 days covers the Bundestag's summer break (eight to ten weeks without sittings, when an entry may wait) with room to spare. On today's file it moves nothing: the newest move is 1,623 days before the Stand.

**Why rule 2 instead of keying the guard per Mandat (item 9's suggested fix).** A gap without a record is ambiguous in the same way a lead-in is: the file has entered the end of A but not yet the start of B, or the MdB really left and nobody entered `Fraktionslos`. The file enters `Fraktionslos` explicitly 63 times since WP 18 and never leaves a day uncovered, so a missing record is a gap in the entry, not evidence. Keying "the first record day" per Mandat would fix only the re-entry case and leave the gap and tail cases open.

### Change

- `derive.py`:
  - `STAMMDATEN_LAG_DAYS = 90` and `last_proved_day(stand) -> str`. Both `_proved_group` and the cross-check use it, with one comparison: a day after it proves nothing.
  - `_mandate_stretches` builds its stretches once, each tagged recorded (a record) or rule 3, and derives both outputs from that list: the seat rows exactly as today (adjacent stretches of one party merged regardless of the tag, so `mdb_zugehoerigkeiten` and `party_seats` do not change), and the rule-3 stretches with the day a record takes over after each, if any. `mdb_zugehoerigkeiten`'s Nachrücker last-day pass shortens a Mandat's last row; a rule-3 tail it shortens keeps its unshortened end in the evidence, which guards one more day, never one less. A new `stammdaten_evidence(mdbs, since_wahlperiode)` returns the rule-3 stretches per (Wahlperiode, MdB id) from the same traversal.
  - `RefilingSource`: `recorded_from` and `stand_day` go; `unrecorded: Mapping[tuple[int, str], list[tuple[str, str | None]]]` (first day, first day no longer covered, None for an open tail) and `last_proved_day: str` replace them. `first_record_days` is deleted.
  - `_proved_group`: None when `day > source.last_proved_day`; None when `start <= day` and (`end is None` or `day < end`) for a rule-3 stretch of that MdB in the Wahlperiode; None on `day == end` when a record starts on `end` (the takeover day, a change day). A tail stretch's end is the Mandat's end, where no record takes over, so it adds nothing.
  - Behaviour change on inputs today's file does not have: where a rule-3 stretch meets an explicit `Fraktionslos` record, the merged seat row hides the boundary, so today a page row on that day after an earlier Fraktion can move; under rule 2 it does not.
- `stammdaten.crosscheck`: the drift cause uses `last_proved_day` and is renamed `near_stand` (pre-release, no alias); the label and warning say "after <day>, 90 days before the Stand: the file may not record a change yet". `build_dip_pulse_site.log_seat_crosscheck`'s `by_cause["after_stand"]` lookup and the label table change with it.
- `docs/data-methods.md`: the list of cases where the page stands names the 90 days and the uncovered days instead of "nach ihrem Stand" and "vor dem ersten Eintrag".

### Tests (first, red)

In `tests/test_vote_refiling.py`, built from Stammdaten records through `stammdaten_refiling_source` (the `CachedStammdatenTests` way). The `source()` helper is rebuilt to take explicit rule-3 stretches (none by default), so hand-written rows no longer fake a first-record day (item 9, fourth bullet). Every negative case has a paired positive control on the same fixture, and fixtures keep list and chart consistent:
- A vote 91 days before the Stand moves, 90 days before moves, 89 days before keeps the page, and one after the Stand keeps it. Replaces `test_a_vote_after_the_stand_keeps_the_page`.
- Gap: Fraktion A ends 31.03.2019, B starts 01.05.2019, no `Fraktionslos` record; page lists B on 2019-04-15: no move; page lists A on 2019-06-01: moves to B. The same gap with an explicit `Fraktionslos` record: the 2019-04-15 page row under B moves to fraktionslos.
- Tail: A ends before MDBWP_BIS, no record after; page lists A on a tail day: no move. The existing `test_a_fraktionslos_record_or_a_gap_after_a_record_still_proves_fraktionslos` expects the opposite for its second case and is changed in place.
- Re-entry (item 9's stub): second Mandat from 01.06.2020, SPD record from 01.09.2020, page SPD on 2020-07-01: no move; page fraktionslos on 2020-10-01: moves to SPD.
- Takeover day: a rule-3 stretch then an explicit `Fraktionslos` record, after an earlier AfD record; page AfD on the record's first day: no move; the day after: moves.
- `mdb_zugehoerigkeiten` and `party_seats` of each fixture above equal today's output (seat rows unchanged).
- `test_seat_crosscheck.py`: a disagreement 89 days before the Stand is `near_stand`, one 90 days before is filed by shape; end to end through `log_seat_crosscheck`, the warning names the day.

### Figures expected to move

None. Re-filed Stimmen 157 → 157 in 87 → 87 roll-calls; `vote_fractions`, `vote_members`, `party_seats`, `mdb_zugehoerigkeiten` unchanged. Cross-check: `after_stand` 1 becomes `near_stand` 1 (the same vote 1004).

## Item 1: no file must not quietly drop the correction

### Contract

- A rebuild refuses (DatabaseRebuildError, previous store untouched) when the store it would replace has a row in `mdb_stammdaten_stand` and no file is cached. The provenance is read inside `_rebuild_database_from_entries`, under the writer lock, from the read-only probe it already opens; a store whose schema predates the table (the `--offline --repersist` upgrade path) counts as built without a file. The message names the Stand and sha256 the store was built with, the path to restore the file to, and the flag.
- `--without-stammdaten` (keyword `without_stammdaten=True` on `rebuild_database_from_entries` and `repersist_cached_reports`) permits only that: a rebuild with no cached file over a store built with one. It does not hide a cached file: if one is there, it is read and used as without the flag, and an unreadable one still stops the rebuild. Together with `--enrich mdb-stammdaten` it is refused at argument parsing, as the two contradict. The rebuilt store then has no Stand row, empty `mdb_zugehoerigkeiten` and `party_seats`, and every Stimme under the page's group; `rebuild_seat_counts`' warning stays.
- Still allowed with only the warning: a build with no file over a store built without one, or with no store yet (a fresh local build). Nothing is dropped there, the Datenstand line says "MdB-Stammdaten nicht geladen", and a tagged export and `publish_dip_pulse_data.py` refuse that state. Requiring the file for every build would need the flag in about 50 test call sites and in every online build without `--enrich mdb-stammdaten` (an opt-in enrichment), for a state that can't be released anyway. So item 1 closes the accidental downgrade of an existing store; a fresh build still depends on the warning and the release refusals.

### Sibling paths (review checklist class 1)

- The online build, `--backfill-incomplete` included: `main` calls `rebuild_database_from_entries`, and passes the flag.
- `--offline --repersist`: `repersist_cached_reports`, which passes it on.
- `build_demo_site.py`: no file, no Stand row, unaffected.
- `validate_store_gate.py`'s `_data_clone` deletes the cloned store before the rebuild, so the rebuild's own check sees no previous store. `_data_clone` gains the same check against the source: when the source store has a Stand row, the source's private directory must hold a file whose sha256 is that row's, and the copy must arrive; otherwise it refuses before cloning. Today it only checks that a file present at the source was copied.
- The plain `--offline` render writes no store and keeps `stammdaten_store_mismatch`. Its three operator messages that say to remove the file and run `--offline --repersist` (the mismatch text for "no file is cached, but the store was built with one", and the unreadable-file and refile-error messages beside it in `main`) name `--without-stammdaten` where a rebuild without the file is the fix.

### Tests (first, red)

- A store built with a file, the file then removed: `rebuild_database_from_entries` raises, the store's bytes are unchanged; with `without_stammdaten=True` it rebuilds, and the Stand row, `mdb_zugehoerigkeiten`, `party_seats` and every `listed_party_id` are gone.
- A store built without a file, and no store: rebuild without a file as today, with the warning.
- With a file cached and the flag: the file is used (Stand row present).
- CLI: `--offline --repersist` on a store built with a file and no file cached exits 1 with the message and leaves the store; with `--without-stammdaten` it exits 0. `--without-stammdaten --enrich mdb-stammdaten` exits 2 at parsing. The online path passes the flag (a test through `main` with the DIP client stubbed, or the call's keywords asserted).
- `_data_clone`: a source store with a Stand row and no file, or a file with another sha256, is refused.

### Figures expected to move

None on a store with its file.

## Item 3: one read of the zip per rebuild

### Change

`_rebuild_database_from_entries` reads the cached file once, before staging (`read_cached_stammdaten`, the unreadable-file refusal unchanged), and passes the `Stammdaten` object to `refile_entries_from(entries, cached)` (replacing the call to `refile_entry_votes`) and to `rebuild_seat_counts(store, cached)`, and uses it for item 1's check. `refile_entry_votes` loses its only caller and goes; its tests move to the public rebuild entry point. `rebuild_seat_counts` takes the object instead of `database_path`. The offline render already reads once.

### Tests (first, red)

- A rebuild calls `stammdaten.read_zip` exactly once.
- Two valid files that give different Zugehörigkeiten and seat counts: the cache holds the first at the start, and a hook in the persist loop replaces it with the second. The rebuilt store's re-filed Stimmen, `mdb_zugehoerigkeiten`, `party_seats` and `mdb_stammdaten_stand` are all the first file's.
- An unreadable cached file stops `rebuild_database_from_entries` with DatabaseRebuildError and the old store's bytes unchanged.

### Figures expected to move

None.

## Item 4: the seat cross-check compares the page's own counts again

### What the check can and cannot prove

The page's counts come from bundestag.de and the seats from the Stammdaten. Before E4 the cross-check compared these two and listed every E4 case as `shift_between_groups`. Since E4 it compares the re-filed counts, which come from the same file as the seats, so a wrong Stammdaten row moves a Stimme and agrees with itself. No comparison of these two sources tells a wrong Stammdaten row from a wrong page row. What the check can do is keep the page's own disagreement and every move in view, so that a refreshed file that moves a new Stimme, or moves different members on a vote already listed, shows in the report.

### Change

`stammdaten.crosscheck` reads, per roll-call:
- the filed counts, `vote_fractions.total_count`;
- the moves, `vote_members` rows with a `listed_party_id`: member, the page's group, the filed group;
- the page's counts, over the union of the groups in `vote_fractions` and those the moves name: filed count minus the Stimmen moved into the group plus those moved out of it. A group the page listed and every member left has no `vote_fractions` row (`filed_fractions` drops it) and gets its count back from the moves. A page count below zero (the moves and `vote_fractions` disagree) makes the roll-call not comparable, listed under a new `moves_inconsistent`. `Unbekannt` on either side keeps the roll-call out of the comparison, as today.

It compares both sides with the seats and reports them separately:
- **Moves.** A new top-level `refiled` list in the report, one entry per moved member (vote id, date, member, page's group, filed group), whatever the comparison found, so two opposite moves that cancel in the totals still show. The summary line counts them: "N Stimmen re-filed in M roll-calls".
- **Disagreements.** One row per roll-call and group where the page's count or the filed count differs from the seats: `stammdaten_seats`, `roll_call_total` (the page's), `filed_total`, `page_difference` and `filed_difference` (each minus the seats). The old `difference` goes.
- **Cause per roll-call,** tried in this order, which is also `CAUSES`' order: `near_stand` (the day is after `last_proved_day`); `refiled` (the filed counts agree with the seats and the page's do not: the page's groups differ from the seats by exactly the moves); then the shape rules on the filed differences, as today: `change_on_vote_day`, `shift_between_groups`, `roll_call_short`, `unexplained`. A roll-call with moves and a residual is filed by its residual, and its moves are in the `refiled` list. `shift_between_groups` keeps its meaning (the filed totals agree and groups differ); the docs no longer say it means "the unmatched names", since the shape does not show who.

`refiled` is no warning: it is explained, and 87 ids every build would be noise. `docs/project-documentation.md`'s cross-check paragraph and `docs/source-errors.md` E4's "now finds no `shift_between_groups`" sentence say what the check compares.

Known limit, unchanged: persist upserts `vote_members` by (vote, mp), so two page entries resolving to one mp in one vote keep one row and could lose a move from the read-back. That is item 8's sixth bullet ("Persist overwrites a roll-call member row when two members of one vote resolve to one mp"); `moves_inconsistent` catches it where it drives a count below zero. Storing the page's chart counts at persist would remove the read-back, at the cost of a schema change; not done here.

### Tests (first, red)

In `tests/test_seat_crosscheck.py`, on store fixtures with `listed_party_id` set:
- page AfD 86 / fraktionslos 10, one Stimme re-filed fraktionslos → AfD, seats 87 / 9: `refiled`; rows hold page 86, filed 87, seats 87; the `refiled` list names the member.
- the same with seats 88 / 8: filed 87 vs 88 is `shift_between_groups`, page 86 in the row, the move still in the list.
- two opposite moves in one vote, page, filed and seats all agree: no disagreement, both moves in the list.
- the page's group left by its only member (no `vote_fractions` row): its page count comes back from the move.
- no `listed_party_id` anywhere: the same causes as today (regression), empty list.
- a move that breaks an agreement (the page agreed with the seats): filed by shape, not `refiled`.
- a move that would drive a page count below zero: `moves_inconsistent`.
- `log_seat_crosscheck`: the summary line counts the Stimmen and roll-calls re-filed and the `refiled` roll-calls.

### Figures expected to move

Cross-check report only (private, never exported): agree 720 → 633 and `refiled` 0 → 87, if the 87 roll-calls with a move are disjoint from the 16 other disagreements and none has a residual (checked in the replay); `refiled` list 157 Stimmen in 87 roll-calls; the other causes unchanged. No stored figure moves.

## Item 9, first bullet (the dated scale)

`docs/data-methods.md`'s E4 paragraph and `docs/source-errors.md`'s "Corrected" line give the post-T4 scale, 157 Stimmen in 87 namentlichen Abstimmungen, with the date and roll-call count of the measurement (736 on the replay), and point to `docs/source-errors.md` E4 for the list.

## Not taken

- **Item 8, second bullet** (the page's list and chart must agree before a move). Dropped after review: many positive fixtures carry partial member lists with chart-sized counts, so the guard would block their moves and let item 2's "no move" tests pass for the wrong reason, and no vote on the reference store has the defect. It stays in TODOS.md.
- Item 8's other bullets stay in TODOS.md: the refused-vote release refusal needs the refused list stored or recomputed at export; `_member_sections_html`'s group key changes every panel heading's spelling source; the rest are separate code.
- **A store built under older filing rules with the same file** (review finding 1). The offline render accepts a store whose sha256 matches and re-files the panels under the running code, so after a rule change the panels and the store can disagree until a replay; a tagged export checks only that a Stand row exists. Today's filing on the reference store does not change under this plan, and the release replays the store once at the end. A filing-rules version beside `mdb_stammdaten_stand` that the render and the export check, like `require_current_speech_rules`, would close it; recorded in TODOS.md as a new item.

## Item 7 (left to the owner)

The online fresh vs incremental comparison needs a DIP API key and network: an online build of the release tip into an empty OUTPUT with `--enrich mp-roster --enrich mdb-stammdaten` and the same Stammdaten file, then `scripts/compare_store_values.py` against an incremental build (the reference store updated and replayed on the same tip) and a diff of the CSV export and the pages. `docs/agents/review-checklist.md`'s "identical CSVs and pages" line should then say which comparison it means (item 7's last sentence). Nothing in this plan depends on it.

## Replay and checks

1. Tests first for each item, red, then the code, green.
2. `--offline --repersist` on `.context/e4-after` (APFS clone of `roster-after-52` and its private directory), with uv's CPython 3.13; logs in `/private/tmp/claude-501/todo-stores/e4`.
3. `scripts/compare_store_values.py roster-after-52 e4-after`: the "vote groups" section must show no change; every other section no change.
4. The cross-check report before and after: the figures in item 4.
5. Item 1 on the clone: move the zip aside, `--offline --repersist` refuses and the store is unchanged; put it back.
6. `/verify` green; `docs/agents/review-checklist.md` applied.

## Review

Codex (`codex exec`, read-only, plan and code only, 2026-11-26), nine findings, verdict "sound to build after these fixes". Folded in: 2 (moves listed independently, opposite moves), 3 (groups the moves name, `moves_inconsistent`, the collision named as a limit), 4 (`_data_clone` checks the source), 5 (the flag's contract, the other messages, provenance under the lock and on the upgrade path), 6 (one traversal, open tails, the takeover-day fixture, seat-row equality), 7 (consistent fixtures with positive controls; item 8's guard dropped), 8 (one boundary, `CAUSES` order, the logger), 9 (two real files, all four tables). Deferred: 1 (filing-rules version), under "Not taken".
