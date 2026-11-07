# Reden the parser drops without refusing

Fixes the TODOS.md item of the same name (P1), filed 2026-11-07 on `claude/strange-germain-01ea7e` after the CPP-BT cross-check. Measured on the A3 store's 716 XML files (`~/agent-runs/a3/full/data/xml`).

## What the source shows

**29 Reden directly under `<sitzungsverlauf>`.** A census of all 716 files finds exactly these two sittings [measured: every `<rede>` path counted: 71,748 under `tagesordnungspunkt`, 5,014 under `anlagen-text`, 29 under `sitzungsverlauf`]:

| Sitting | Reden | Inhaltsverzeichnis block | DIP position for the same pages |
|---|---:|---|---|
| 18/49 | 1 | "Tagesordnungspunkt 1:" (`T_NaS` and `T_Drs` in `<sitzungsbeginn>`: 18/2000, 18/2001) | "1. Beratung", 4459–4544 |
| 18/49 | 12 | "Allgemeine Finanzdebatte (einschließ-" + `A_TOP` "lich Einzelpläne 08, 20, 32 und 60)" | "1. Beratung (Einzelpläne)", 4459–4485 |
| 18/49 | 13 | "Einzelplan 06" | "1. Beratung (Einzelpläne)", 4485–4507 |
| 18/44 | 3 | "Zur Geschäftsordnung:" | "Geschäftsordnungsantrag auf Absetzung von der TO", 3927–3931 |

So they are not outside the sitting's agenda. The source lost one wrapper element, and it names each one in the Inhaltsverzeichnis. The same labels are already `top-id`s elsewhere [measured: census of `top-id`]: "Zur Geschäftsordnung" 25 times, "Geschaeftsordnung" 8, "Allgemeine Finanzdebatte" in 20/49, "Allgemeine Finanzdebatte, Einzelplan 08" in 20/183, "Einzelplan NN" 390.

**21/43 `ID214301700` is not lost.** A named rule handles it (`validate_dip_protocol.py:1444-1453`, "summons request"): Brandner's motion to summon the Beauftragte goes to `xml_turn_diagnostics` as `procedural`, Frömming's "Alles gut." too, and Frömming's three resumed turns are `merged_rede` into `ID214301600` [measured: the 21/43 report; "Schön, dass Herr Weimer" is in that Rede's text]. `tests/test_a1_followups.py:254` covers the rule. CPP-BT's 501 tokens are mostly Frömming's resumed speech. No code change; the item's text on `claude/strange-germain-01ea7e` is to be corrected when that branch merges. Counting the motion as a Rede would change what a Rede means, so it stays out unless the owner asks.

**16 zu Protokoll submissions.** Titles "Zu Protokoll gegebene Reden zur Beratung" (18/133, 5) and "…zur Beratung:" (18/134, 11).

**4 annex units:**
- 19/115, 2: §31 declarations. They are the second `anlagen-text` of Anlage 3, whose first says "Erklärungen nach § 31 GO"; the Inhaltsverzeichnis lists both under that title. Stay out under ADR 0002.
- 19/35 and 19/45, 1 each: "Neudruck eines Redebeitrages" of a Rede in the sitting before. Storing them would count that Rede twice. They stay out. The original in 19/34 (`ID193402300`) is held; 19/44 is not in the store. The reprint's text differs a lot from the original (ratio 0.65 on 19/34) [measured: `difflib`]; which text should stand is a separate question, filed as a TODO.

## Plan

### P1. One in-place normalizer, first in `parse_protocol_xml`

`adopt_reden_outside_tops(root)`, before the `mark_*` calls, so the chair readers, `parse_vote_recommendations` and the classifiers all see the same tree:

- Each run of `<rede>` under `<sitzungsverlauf>` in one Inhaltsverzeichnis block is wrapped in a `<tagesordnungspunkt>` in place, with `top_source="inhaltsverzeichnis"`.
- `top-id` is the block title plus its `A_TOP` continuation, line-end hyphen joined, trailing colon dropped.
- `T_` paragraphs of `<sitzungsbeginn>` move into a run that directly follows it, when its block title names a Tagesordnungspunkt or Zusatzpunkt: that is where 18/49 called TOP 1, and it gives the item its heading. "Zur Geschäftsordnung" takes none.
- The lookup reads the blocks directly, not `parse_toc`, whose dict keeps only the last of two blocks with one title.
- **Refuses** with a `ValueError` naming the id: a Rede with no Inhaltsverzeichnis xref, or one after a real TOP. Neither occurs in the 716 files, so each would be new evidence to read, not a guess to make. The 85 excluded sittings have not been scanned.

`scripts/audit_offline_turns.py` builds its own root, so it calls the normalizer too (one line). The reconciliation of every `<rede>` stays with the coverage gate.

### P2. Replay accepts exactly these items

`replay_top_map` (`:3458`) raises on any change to the item set, so every `--offline --repersist` would stop on 18/44 and 18/49.

- An adopted item that the old report does not hold is new. It is left out of the matching, and the matching over the rest is unchanged. Any other difference still refuses.
- `reparse_report_xml` then rebuilds `agenda_items` in XML order and renumbers `index` to the XML's, as a fresh online build would. Old items keep their `api`, `votes` and `llm_summary`. New items get an empty `api` and no votes.
- `reparse_cached_xml` (`build_dip_pulse_site.py:1982`) keys speaker profiles by `index`, which now moves in these two sittings, so it keys them by item identity.
- `xml_top_fields` carries `top_source`, so a second replay finds the item in the report and stays stable. Not in the store or the export: no schema or format change.

`item_index` feeds ids only where a unit has no `rede_id` (`speech_rede_id`, `contribution_occurrence_id`). The replay reports what moves.

### P3. Annex titles

`validate_dip_protocol.py:1300` matches `zu protokoll gegebene reden?` plus an optional `zur beratung:?`, full match. Deliberately not a prefix: "Technisch bedingter Neudruck der zu Protokoll gegebenen Rede" and "Zu Protokoll gegebene Ergänzung" are other things and hold no `<rede>` in the 716 files. An unseen title falls to the coverage gate's reconciliation.

18/133's "(Tagesordnungspunkt 25 a und b)" matches no single TOP key, so its 5 stay at sitting level, `agenda_item_id` NULL. That is the existing rule for an uncertain TOP (`:1294`).

### P4. Tests, docs, replay

- Tests from real XML cut down to fixtures: 18/49 yields 51 ids and the three named items, 18/44 keeps 7 votes on TOP V and VII after replay, refusal for both shapes, replay refuses any other item-set change, annex titles and the four units that stay out.
- `docs/data-methods.md`: where these Reden sit, and the two rules that keep annex units out.
- Replay on a clone of `~/agent-runs/a3/full`, baseline at 58d343d against the fix, database only. Report Reden per sitting and Fraktion, separately from `zu_protokoll`.

## Limits stated up front

- Offline replay gives adopted items no DIP positions or activities: the report holds no match for them. A fresh online acquisition of 18/49 matches them by page range and title like any TOP. 18/49 holds 0 positions today on its one item, so nothing is lost.
- The 25 Reden of "Einzelplan 07" in 18/49 also hold Einzelplan 15 (Inhaltsverzeichnis: 13 + 12). The source wraps them so; unchanged.
- `parse_toc` overwrites a repeated block title, so 18/44's 13 Reden of "Tagesordnungspunkt II (Fortsetzung)" have no page. Predates this; filed in TODOS.

## Eng review (2026-11-07, short, target: this plan)

Scope Challenge: 8 files or fewer, no new classes or services: `scripts/validate_dip_protocol.py`, `scripts/build_dip_pulse_site.py`, `scripts/audit_offline_turns.py`, one test file, `docs/data-methods.md`, `TODOS.md`, this plan. The complexity gate does not trip. Scope accepted as-is.

## Decision ledger

### R1: where a Rede outside a TOP belongs
Finding: 1, P1, confidence 9/10, `validate_dip_protocol.py:1373` `for index, top in enumerate(root.findall("./sitzungsverlauf/tagesordnungspunkt"), start=1):`, reviewer: this session.
Plan baseline: TODOS asks for the decision; no approved value.
Runtime evidence: 29 Reden in 18/49 and 18/44 have no unit. A bounded probe that wraps them by Inhaltsverzeichnis block and runs today's parser gives 18/49 51 Reden in 4 items, 18/44 44 Reden in 7 items, no refusal.
Comparison grid:
| Choice | Current | A | B | C |
|---|---|---|---|---|
| Home of the 29 Reden | none, dropped | item named by the Inhaltsverzeichnis | NULL agenda item | none, sitting refused |
| `speeches.agenda_item_id` | NOT NULL | NOT NULL | nullable | NOT NULL |
| Schema and export format | 11 / 16 | unchanged | bump both | unchanged |
| 18/49 and 18/44 in the set | counted with half the Reden | counted, all Reden | counted, all Reden | left out |
| TOP count | 1 and 6 | 4 and 7 | 1 and 6 | none |
| DIP link on replay | n/a | none until re-acquired | none | n/a |
State: approved
Actual answer: A, "Items from the IVZ", D1 of 2026-11-07, answered by the owner's adjudicator hook on the evidence above
Accepted scope: P1 to P4 of this plan
History: none

Follow-up, owner, 2026-11-09: the store and the export do not mark which items come from the Inhaltsverzeichnis ("Leave unmarked"). `top_source` stays in the report JSON; `docs/data-methods.md` names the items and the rule.

### Sections 1 to 4

**Architecture.**
`[P1] (confidence: 9/10) validate_dip_protocol.py:3462 "raise ValueError("agenda item set changed; reacquire the sitting report")"`: without P2 every offline build stops on these two sittings. Disposition: accepted in P2 under R1.
`[P1] (confidence: 9/10) build_dip_pulse_site.py:1982 "profiles = {item.get("index"): speaker_profiles(item) ...}"`: the index moves in these two sittings, so profiles would attach to the wrong item. Disposition: accepted in P2 under R1.

Flow, `-->` the new part:

    cached report + XML --> adopt_reden_outside_tops(root) --> parse_protocol_xml
       |                       no IVZ entry, or after a TOP: ValueError, sitting refused
       v
    replay_top_map: old items pair by identity; adopted items absent from the old report are new
       v
    reparse_report_xml --> items in XML order, index renumbered, new items empty api and votes
       v
    persist: agenda_items, speeches (agenda_item_id NOT NULL holds)

**Code quality.** No issues found. Reuses `elem_text`, `clean_text` and the existing `mark_*` idiom of changing the tree in place. No shared helper: there is one caller plus the audit's one line.

**Tests.** Coverage plan:

    adopt_reden_outside_tops
      18/49 runs: 3 items, labels, heading from sitzungsbeginn   [GAP -> fixture test]
      18/44 run: "Zur Geschäftsordnung", votes stay put           [GAP -> replay test]
      no IVZ entry / after a real TOP: ValueError                 [GAP -> mutated fixture]
      no orphan: tree untouched                                   [covered by the offline-v5 sources]
    replay_top_map
      adopted item new, replay twice is stable                    [GAP]
      any other item-set change still refuses                     [existing, keep]
    written_contributions
      both long titles stored; 19/115, 19/35, 19/45 not stored    [GAP -> extend test_written_top_association]
    21/43                                                         [covered: test_a1_followups.py:254]

Regression contract, carried from R1: a sitting without orphans parses and replays exactly as before. The replay's per-sitting diff is the proof: only 18/44, 18/49, 18/133 and 18/134 may move.

**Performance.** No issues found: one pass over `<sitzungsverlauf>` per sitting.

### Reality rows

    premise-table: every claim above has a census or report receipt, unverified=0
    already-done: `git log -- validate_dip_protocol.py` has no such fix; the item is not on main
    surface-check: no new CLI surface
    binding-decisions: owner rules kept: no shim, report moved figures, no push; ADR 0002 keeps §31 out
    numbers: all [measured] on the 716 files; the store's old figures are re-measured by the replay
    deferred-asks: per-sitting reconciliation stays with the coverage gate, as the task says
    pr-count: no PR asked for; one commit series, not pushed

### NOT in scope

- Reconciling every `<rede>` per sitting: the coverage gate.
- Offline DIP re-match of adopted items from `api_records`: a re-acquisition does it.
- Which text stands for a Neudruck: filed in TODOS.
- `parse_toc` keeping only the last of two blocks with one title: filed in TODOS, 87 of 716 files repeat a title.

### Outside voice

Unavailable. Codex cannot write `~/.codex` inside this sandbox. The native Plan fallback died on an API network error (`ENOTFOUND`) before it reported, so this plan has no outside coverage. The questions put to it, what the renumbering breaks and whether reports skip the re-parse, were answered here: the replay diff below shows no unit moved TOP, and the second one is why the speech rule went from 6 to 7.

## Replay result (2026-11-07)

Clones of `~/agent-runs/a3/full/data`, database-only `repersist_cached_reports`, `--today 2026-11-07`: baseline at 58d343d (1,110 s), fix (897 s). `full` was not written. Only 18/44, 18/49, 18/133 and 18/134 moved.

| Figure | Old | New |
|---:|---:|---:|
| Reden | 54,718 | 54,747 |
| Reden, 18/49 | 25 | 51 |
| Reden, 18/44 | 41 | 44 |
| Beiträge | 42,465 | 42,484 |
| `zu_protokoll`, 18/133 | 27 | 32 |
| `zu_protokoll`, 18/134 | 0 | 11 |
| Zwischenfragen, 18/49 | 1 | 4 |
| Agenda items | 7,131 | 7,135 |
| Agenda items, 18/49 | 1 | 4 |
| Agenda items, 18/44 | 6 | 7 |
| `agenda_item_politikfelder` | 11,460 | 11,465 |

Reden per sitting and Fraktion:

| Sitting | CDU/CSU | SPD | Grüne | Linke |
|---|---:|---:|---:|---:|
| 18/49 | 10 → 21 | 6 → 13 | 4 → 8 | 4 → 8 |
| 18/44 | unchanged | 11 → 12 | 7 → 8 | 7 → 8 |

All sittings: CDU/CSU 14,952 → 14,963, SPD 11,612 → 11,620, Grüne 7,638 → 7,643, Linke 5,611 → 5,616.

Written submissions per sitting and Fraktion (they add to no Rede total):

| Sitting | CDU/CSU | SPD | Grüne | Linke | none |
|---|---:|---:|---:|---:|---:|
| 18/133 | 8 → 10 | 7 → 8 | 6 → 7 | 6 → 7 | |
| 18/134 | 0 → 8 | 0 → 1 | 0 → 1 | | 0 → 1 (Bundesminister Schmidt) |

Held by the replay: no speech or contribution id gone; no old Rede changed TOP; 18/44's 7 votes stay on TOP V (6) and VII (1); no Rede without a person; the log's Fakten lines are identical. New Politikfelder rows: "Einzelplan 06" gets Innere Sicherheit and Migration from its Einzelplan rule; the other three adopted items are `untagged`. The 18/133 submissions stay at sitting level; the 18/134 ones join "Tagesordnungspunkt 26".

Also moved, from `scripts/compare_store_values.py` on the two stores:
- `speeches.char_count` sum 253,280,655 → 253,528,378: 18/49 182,864 → 417,749, 18/44 260,942 → 273,780.
- Redeanteil excludes government speech: CDU/CSU 14,822 → 14,831 (+9, not +11), because Schäuble and de Maizière carry Sprechrolle `bundesregierung` (2,836 → 2,838).
- `mps.party_id` NULL → SPD on 3 of 7,457 rows (Carsten Schneider, Eva Högl, Christine Lambrecht): the new Reden print their Fraktion. `mps` row count and the Zusammenführung are unchanged.
- `votes`, `vote_fractions`, `vote_members`, `vote_documents`, `vote_proceedings`, `vote_politikfelder`: identical on every column but the timestamps, so the chair text the 18/44 Geschäftsordnung run now exposes moved no vote.

Agenda item ids are keyed by index, so they move with the renumbering: 6 ids now name another TOP and 4 are new, none gone. 18/44: index 1 "Tagesordnungspunkt V" → "Zur Geschäftsordnung", 2 "II (Fortsetzung)" → "V", 3 "VI" → "II (Fortsetzung)", 4 "II (Fortsetzung)" → "VI", 6 "VII" → "II (Fortsetzung)", new 7 "VII". 18/49: index 1 "Einzelplan 07" → "Tagesordnungspunkt 1", new 2, 3, and 4 "Einzelplan 07". Speech and contribution ids do not move: neither sitting has a unit without a `rede_id`.

Why the new figures are more correct: each new unit is a `<rede>` the source prints, and 18/49 went from 25 to the 51 CPP-BT also finds.

A full `--offline --repersist` on the fixed clone then ran without error and left the store unchanged ("store content unchanged, file kept"), which also shows the replay is stable. The export holds 54,747 speech rows. The 18/49 page holds all 51 Rede ids, with "Einzelplan 06: 13 Reden · 25,5% der Sitzung" and "Einzelplan 07: 25 Reden · 49,0%", where it said 100,0% before. The 18/134 page lists its 11 Zu Protokoll gegebene Beiträge. Plain `--offline` without `--repersist` still renders dossiers from the report files on disk and warns that they predate the rule. That predates this change.

The store's rule version moves from 6 to 7, so an existing store refuses facts, export and rendering until `--offline --repersist` has run once. That is the guard working.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run | |
| Outside Review | Codex, Plan fallback | Independent 2nd opinion | 1 | unavailable | no report |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN, not persisted | 2 issues, both mapped into P2; 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | not run | |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | |

- **OUTSIDE COVERAGE:** Codex, plan review, unavailable in the sandbox; native fallback failed on a network error. No clean-review credit.
- **VERDICT:** no review CLEAR; the two issues are fixed in this change. The review log could not be written from this sandbox (`~/.gstack` is outside it).

NO UNRESOLVED DECISIONS
