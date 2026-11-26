# E4 deferred findings 1 to 4: plan

Status: **plan, 2026-11-26, for review before code.** Source: TODOS.md, "E4 /gstack-review: deferred findings (2026-11-05)", items 1 to 4, item 9's second to fourth bullets, and item 8's second bullet. The release roadmap needs items 1 to 4 and 7 before the first `--publish`.

Base: main 88d83d3 (v0.46.53.0). Reference store for the replay: `.context/roster-after-52` cloned to `.context/e4-after`, with `.e4-after.private/mdb-stammdaten.zip` (Stand 2026-04-29T08:03:03Z, 4,614 MdB records).

## What the reference store holds today (measured 2026-11-26 on the clone)

- 736 roll-calls, 2013-11-28 to 2026-11-13. 157 `vote_members` rows have a `listed_party_id` (re-filed Stimmen) in 87 roll-calls: Kamann 68, Bülow 60, Pasemann 11, Witt 8, Huber 8, Heßenkemper 2.
- The newest re-filed Stimme lies 1,623 days before the Stand. 11 roll-calls fall in the 90 days before the Stand (2026-01-29 to 2026-04-29) and 44 after it; none of them re-files a Stimme.
- Of the Stammdaten's Mandat days from WP 18 on, none is fraktionslos by rule 3 alone: every fraktionslos day is covered by an explicit `Fraktionslos` record (63 such records). So `first_record_days`' guard never fires on this file, and no re-filed Stimme lands on a rule-3 day.
- On every (vote, group), the page's own Ja count (the chart, read back through `listed_party_id`) equals the page's member list. The other three counts are checked in the replay.
- Seat cross-check (`seat-crosscheck.json`): 736 compared, 720 agree; `after_stand` 1 (1004, 2026-05-22), `change_on_vote_day` 14, `roll_call_short` 1 (440), `shift_between_groups` 0, `unexplained` 0. None of the 16 lies in the 90 days before the Stand.

## Item 2 and item 9 (gap, re-entry): when the Stammdaten prove a group

### The rule (recommended; for the owner's yes)

The Stammdaten prove a member's group on a vote's day only when both hold:

1. **The day lies at least 90 days before the file's Stand** (UTC day of `VERSION`). On later days the page stands. Today's guard is `day > stand_day`.
2. **An explicit Fraktion or Gruppe record of the file covers the day** (`Fraktionslos` records count). A Mandat day no record covers is fraktionslos for the seat counts (rule 3, unchanged), but it proves no group for a Stimme, and neither does the day a record starts right after such a stretch. This one rule replaces `first_record_days` and `RefilingSource.recorded_from`, and it covers all three cases item 9 names: the lead-in before a first record, a gap between two records (A ends on X, B starts on X+n), the tail after a last record that ends before the Mandat, and the lead-in of a re-entry Mandat.

The rest of `_proved_group` stays: one MdB per name in the Wahlperiode, no change on the vote's day, exactly one covering row.

**Why 90 days.** The file says nothing about how late it records a change, and one file is all we have, so no lag can be measured. The window must therefore be generous, and the costs are lopsided. A window too wide only delays a correction: for the newest 90 days of votes before a file's Stand, the Stimme counts for the group the page lists, which is what the site shows without E4, until a later file moves the boundary. A window too narrow lets a lagging file move a correct page row under a wrong group, and the panel then calls the wrong figure a correction. 90 days covers the Bundestag's summer break (eight to ten weeks without sittings, when an entry may wait) with room to spare. On today's file it moves nothing: the newest move is 1,623 days before the Stand.

**Why rule 2 instead of keying the guard per Mandat (item 9's suggested fix).** A gap without a record is ambiguous in the same way a lead-in is: the file has entered the end of A but not yet the start of B, or the MdB really left and nobody entered `Fraktionslos`. The file enters `Fraktionslos` explicitly 63 times since WP 18 and never leaves a day uncovered, so a missing record is a gap in the entry, not evidence. Keying "the first record day" per Mandat would fix only the re-entry case and keep the gap and tail cases open.

### Change

- `derive.py`:
  - `STAMMDATEN_LAG_DAYS = 90` and one function, `last_proved_day(stand) -> str`, the UTC day of the Stand minus 90 days. Both `_proved_group` and the cross-check use it.
  - `_mandate_stretches` keeps producing the same rows (the seat tables do not change) and also reports its rule-3 stretches, each as (first day, first day no longer covered). `mdb_zugehoerigkeiten` stays as it is; a new `unrecorded_stretches(mdbs, since_wahlperiode)` returns them per (Wahlperiode, MdB id), from the same code path, so the two can't disagree.
  - `RefilingSource`: `recorded_from` goes; `unrecorded: Mapping[tuple[int, str], list[tuple[str, str | None]]]` and `last_proved_day: str` replace it and `stand_day`. `first_record_days` is deleted.
  - `_proved_group`: None when `day > source.last_proved_day`, or when `start <= day <= end` for an unrecorded stretch of that MdB (inclusive of `end`, the day a record takes over, as a change day).
- `stammdaten.crosscheck`: the drift cause uses `last_proved_day` too and is renamed `near_stand` (pre-release, no alias); its label and warning say "on or after <day>, 90 days before the Stand: the file may not record a change yet".
- `docs/data-methods.md`: the list of cases where the page stands names the 90 days and the uncovered days instead of "nach ihrem Stand" and "vor dem ersten Eintrag".

### Tests (first, red)

In `tests/test_vote_refiling.py`, built from real-shaped Stammdaten records through `stammdaten_refiling_source` (the `CachedStammdatenTests` way), not from the `source()` helper; the helper is rebuilt to derive `unrecorded` from rows the same way (item 9, fourth bullet):
- A vote 89 days before the Stand keeps the page; 90 days before it moves. Replaces `test_a_vote_after_the_stand_keeps_the_page`.
- Gap: Fraktion A ends 2019-03-31, B starts 2019-05-01, no `Fraktionslos` record; page lists B on 2019-04-15: no move. The same with an explicit `Fraktionslos` record for the gap: moves to fraktionslos.
- Tail: A ends before MDBWP_BIS, no record after; page lists A on a tail day: no move.
- Re-entry (item 9's stub): second Mandat from 2020-06-01, SPD record from 2020-09-01, page SPD on 2020-07-01: no move; page fraktionslos on 2020-10-01: moves to SPD.
- The boundary day a record starts after an uncovered stretch: no move.
- `test_seat_crosscheck.py`: a disagreement 30 days before the Stand is `near_stand`, one 120 days before is filed by shape.

### Figures expected to move

None. Re-filed Stimmen 157 → 157 in 87 → 87 roll-calls; `vote_fractions`, `vote_members`, `party_seats`, `mdb_zugehoerigkeiten` unchanged. Cross-check: `after_stand` 1 becomes `near_stand` 1 (the same vote 1004).

## Item 1: no file must not quietly drop the correction

### Change

`_rebuild_database_from_entries` refuses (DatabaseRebuildError, previous store untouched) when the store it would replace was built with a Stammdaten file (`mdb_stammdaten_stand` has a row) and no file is cached now. The message names the Stand and sha256 the store was built with, the path to restore the file to, and the opt-out. A new CLI flag `--without-stammdaten` (and keyword `without_stammdaten=True` on `rebuild_database_from_entries`) lets that rebuild go ahead; the warning in `rebuild_seat_counts` stays. The offline render's `stammdaten_store_mismatch` text, which today says "run --offline --repersist without it", names the flag.

Not changed: a store built without a file, or no store yet, still builds without a file with the warning. Nothing is dropped there, the Datenstand line says "MdB-Stammdaten nicht geladen", and a tagged export and `publish_dip_pulse_data.py` already refuse that state. Requiring the file for every build would need the opt-out in about 50 test call sites and in every online build that does not pass `--enrich mdb-stammdaten` (an opt-in enrichment), for a state that can't be released anyway.

**Sibling paths** (review checklist class 1): the check sits in `_rebuild_database_from_entries`, which every store write reaches: the online build, `--backfill-incomplete` included (`main`, `rebuild_database_from_entries` at the end of the update), `--offline --repersist` (`repersist_cached_reports`), `build_demo_site.py` (no file, no Stand row: unaffected) and `validate_store_gate.py`'s clones (`_data_clone` already copies the file and refuses without it). `--offline` without `--repersist` writes no store and keeps its own mismatch refusal.

### Tests (first, red)

- A store built with a file, the file then removed: `rebuild_database_from_entries` raises, the store's bytes are unchanged; with `without_stammdaten=True` it rebuilds, the Stand row is gone and the Stimmen are back under the page's groups.
- A store built without a file, still no file: rebuilds as today (the warning).
- CLI: `--offline --repersist` on such a store exits 1 with the message; with `--without-stammdaten` it exits 0.

### Figures expected to move

None on a store with its file.

## Item 3: one read of the zip per rebuild

### Change

`_rebuild_database_from_entries` reads the cached file once, at the start (`read_cached_stammdaten`, the unreadable-file refusal unchanged), and passes the `Stammdaten` object to `refile_entries_from(entries, cached)` (replacing the call to `refile_entry_votes`) and to `rebuild_seat_counts(store, cached)`, and uses it for item 1's check. `refile_entry_votes` loses its only caller and goes. `rebuild_seat_counts` takes the object instead of `database_path`. The offline render already reads once.

### Tests (first, red)

- A rebuild calls `stammdaten.read_zip` exactly once (counting wrapper).
- The file is replaced between the start of the rebuild and the seat step (patched hook in `persist_report`'s loop): the store's `mdb_stammdaten_stand.sha256` is the first file's, and the moves are the first file's.

### Figures expected to move

None.

## Item 4: the seat cross-check compares the page's own counts again

### What the check can and cannot prove

The page's counts (`vote_fractions` minus the Stimmen re-filed into a group plus those re-filed out of it, read back through `vote_members.listed_party_id`) come from bundestag.de; the seats come from the Stammdaten. Before E4 the cross-check compared these two and listed every E4 case as `shift_between_groups`; since E4 it compares the re-filed counts, which come from the same file as the seats, so a wrong Stammdaten row moves a Stimme and agrees with itself. No comparison of these two sources can tell a wrong Stammdaten row from a wrong page row. What it can do is keep every re-filed roll-call in view, so a refreshed file that moves a new Stimme shows as a new roll-call in the report and a changed count in the summary line.

### Change

`stammdaten.crosscheck` reads, per roll-call, both the filed counts (`vote_fractions.total_count`) and the page's counts, and compares the page's counts with the seats:

- page and seats agree, and filed and seats agree: agree.
- the day is after `last_proved_day`: `near_stand` (item 2).
- the filed counts agree with the seats and the page's do not: new cause **`refiled`**, "the page's groups differ from the seats by exactly the re-filed Stimmen".
- otherwise the existing shape rules run on the filed differences (what is left after the moves): `change_on_vote_day`, `shift_between_groups` (now misfilings among the unmatched names only), `roll_call_short`, `unexplained`.

Each disagreement row carries `roll_call_total` (the page's), a new `filed_total`, `stammdaten_seats` and `difference` (page minus seats). `CAUSES` becomes `("near_stand", "change_on_vote_day", "refiled", "shift_between_groups", "roll_call_short", "unexplained")` in the order tried (`refiled` before the shape rules, after `near_stand`). The summary line counts `refiled`; it is no warning (it is explained, and 87 ids every build would be noise). `docs/project-documentation.md`'s cross-check paragraph and `docs/source-errors.md` E4's "now finds no `shift_between_groups`" sentence say what the check compares.

### Tests (first, red)

In `tests/test_seat_crosscheck.py`, on a store fixture with one re-filed Stimme (`listed_party_id` set):
- the page's AfD 86 / fraktionslos 10 against seats 87 / 9, one Stimme re-filed fraktionslos → AfD: `refiled`, the row holds page 86, filed 87, seats 87.
- the same, but the file's seats 88 / 8 (a second, unmatched misfiling): filed 87 vs 88 is a `shift_between_groups`, page 86 in the row.
- no `listed_party_id` anywhere: results exactly as today (regression).
- a re-filed Stimme whose filed counts disagree with the seats where the page agreed (the move broke an agreement): filed by shape, not `refiled`.

### Figures expected to move

Cross-check report only (private, never exported): agree 720 → 633; `refiled` 0 → 87 (exactly the 87 roll-calls with a re-filed Stimme, to be confirmed disjoint from the 16 other disagreements in the replay); the other causes unchanged. No stored figure moves.

## Item 8, second bullet (taken: it is in `refile_vote_members`)

`refile_vote_members` moves a Stimme only when, for the moved member's Stimme, the page's member list and chart agree on both the group the page lists and the proved group; otherwise the vote stays as the page has it and is reported refused (the existing warning). This stops a double count where the chart already counted the member in the proved group and only the list misfiled them. Test: chart AfD yes 87 / fraktionslos yes 9, list AfD 86 / fraktionslos 10 (the list alone misfiles one member the Stammdaten place in the AfD): refused, no mark. Expected moves on the reference store: none (checked in the replay on all four counts).

Not taken from item 8: the refused-vote release refusal (first bullet) needs the refused list stored or recomputed at export, a store or export change of its own; `_member_sections_html`'s group key (third bullet) changes every panel heading's spelling source, a render change; the rest are separate code. They stay in TODOS.md.

## Item 9, first bullet (the dated scale)

`docs/data-methods.md`'s E4 paragraph and `docs/source-errors.md`'s "Corrected" line give the post-T4 scale, 157 Stimmen in 87 namentlichen Abstimmungen, with the date and roll-call count of the measurement (736 on the replay), and point to `docs/source-errors.md` E4 for the list.

## Item 7 (left to the owner)

The online fresh vs incremental comparison needs a DIP API key and network: an online build of the release tip into an empty OUTPUT with `--enrich mp-roster --enrich mdb-stammdaten` and the same Stammdaten file, then `scripts/compare_store_values.py` against an incremental build (the reference store updated and replayed on the same tip) and a diff of the CSV export and the pages. `docs/agents/review-checklist.md`'s "identical CSVs and pages" line should then say which comparison it means (item 7's last sentence). Nothing in this plan depends on it.

## Replay and checks

1. Tests first for each item, red, then the code, green.
2. `--offline --repersist` on `.context/e4-after` (APFS clone of `roster-after-52` and its private directory), with uv's CPython 3.13; logs in `/private/tmp/claude-501/todo-stores/e4`.
3. `scripts/compare_store_values.py roster-after-52 e4-after`: the "vote groups" section must show no change; every other section no change.
4. The cross-check report before and after: the figures in item 4.
5. Item 1 on the clone: move the zip aside, `--offline --repersist` refuses and the store is unchanged; put it back.
6. `/verify` green; `docs/agents/review-checklist.md` applied.
