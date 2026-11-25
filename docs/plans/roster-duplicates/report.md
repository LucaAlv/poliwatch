# Roster duplicates: 56 empty Personenseiten joined to their speaker

Built 2026-11-23 on `claude/loving-brattain-e57984` (cut from main 067dd80, v0.46.49.0). TODOS.md "Roster MdB records that never join their speaker: 56 empty duplicate Personenseiten".

Restated 2026-11-25 on main 511e948 (v0.46.52.0, with PRs 215, 216 and 217). Baseline: `.context/leftovers-review-after` (806 sittings, the v0.46.52.0 replay). Result: `.context/roster-after-52`, a clone of it replayed with `--offline --repersist` on this branch. `pairs.tsv` lists every pair with its evidence; its counts are the result's. "Against the first measurement" below names what the restatement moved.

## Why pass 2 left them apart

| Block | Pairs | Fix |
|---|---:|---|
| DIP's `titel` carries the Wahlkreiszusatz ("Achim Post (Minden)"), the parsed speaker name does not | 38 | name rule |
| The XML prints the MdB under two Redner-IDs, so the name+party bucket holds three records | 14 | `same_person` |
| DIP leaves off an accent the XML prints (Glogowski-Merten, Salihović, Dağdelen) | 3 | name rule |
| DIP's `titel` prints "Uda Carmen Freia Heller", the XML "Uda Heller" | 1 | `same_person` |

"Alexander Bartz" and "Bela Bach" are in the second group: a provisional Redner-ID and their own (`docs/source-errors.md` E15). "Heinz Wiese (Ehingen)" is in the first; its twin is "Heinz Wiese".

## Decision

Both, each where it fits.

- **Name rule for 41.** The bracket and the accent are systematic spelling differences between two sources, like academic titles, and a later Wahlperiode brings new ones. `person_registry._bucket_name` drops them from the bucket key only. Printed names, partition labels, the Redner-ID name check and pass 1b read the name as before. Umlauts stay (Müller, Muller).
- **Reviewed list for 15.** No name rule can tell one MdB with two Redner-IDs from two namesakes, or "Uda" from "Uda Carmen Freia". `same_person` in `scripts/person_corrections.json` names the ids, the evidence and the review date; `mp_keys` reads them as one Personenkennung. A `partitions` entry with `own_ids` would also join them, but it rewrites `mps.xml_redner_id`, and `data-methods.md` compares that column with CPP-BT. A `merges` entry names person keys and refuses every store without them.

**Namesake guard** (`person_registry._namesakes`). Pass 2 still needs exactly one roster and one speaker record in the bucket. Where the printed names differ, a join is refused when both sides print a Wahlkreiszusatz and none is shared, or when their known Wahlperioden have none in common. Pass 3 and the stale-roster pass ask the same. The tests use a real case: Dagmar Schmidt (Meschede), SPD, WP 13 to 16, and Dagmar Schmidt (Wetzlar), SPD, WP 18 to 21. A listed Redner-ID the store holds under two names that share no word stops the build (`require_reviewed_redner_ids`); one it holds only under another person's name does not (none of the 806 files prints one).

## Evidence

All 56 pairs are proven beyond the name; none was left alone. For every pair:
- the Redner-ID of the twin is a MdB-Stammdaten id (Stand 2026-04-29), and no other MdB since WP 18 has that name;
- the Fraktion DIP gives is one the XML prints with that Redner-ID;
- the Wahlperioden the speaker spoke in are all in DIP's list, and the Stammdaten mandates since WP 18 are too.

In addition:
- **38 pairs:** DIP's structured `wahlkreiszusatz`, the Stammdaten `ORTSZUSATZ` and the `<ortszusatz>` the XML prints beside that Redner-ID are the same word.
- **14 pairs:** the provisional id stands in the XML for this name and no other, all its sittings lie inside the mandate, and no sitting prints both ids.
- **Heller:** DIP 319 lists "Uda Heller", CDU/CSU, among its own `person_roles`; Stammdaten 11003550 is the only MdB named Heller.

## Figures that move

| Figure | Old | New | Why the new value is more correct |
|---|---:|---:|---|
| Empty MdB persons (0 Reden, 0 Beiträge, 0 Stimmen) | 56 | 0 | each has joined its speaker |
| Persons with at least one record | 1,984 | 1,877 | 107 records of the same people joined |
| `abgeordnete/` pages | 1,676 | 1,605 | 56 empty pages, 14 pages of provisional ids, Trasnea's second page; 84 old page URLs redirect, 13 pages stand under the older of the joined keys |
| Reden on MdB persons | 51,830 | 54,211 | the 56 MdBs' own (2,377) and Trăsnea's 4 |
| Beiträge on MdB persons | 31,238 | 33,469 | the same |
| Stimmen on MdB persons | 420,558 | 441,413 | the same |
| Stimmen of roll-call persons without a page | 8,195 | 4,738 | 3,457 Stimmen of MdBs whose bucket was blocked are on their page |
| Roll-call persons without a page | 81 | 45 | 36 joined |
| `person_aliases` | 3 | 18 | 15 durable `same_person` merges |
| `facts`: `erste-reden` | | | see below |
| `fact_sources` | 3,116 | 3,107 | nine second debuts gone |

Unchanged: 61,104 Reden, 46,499 Beiträge, 502,697 `vote_members`, `votes`, `vote_fractions`, `withheld_units`, `withheld_turns`, Redeanteil, Abweichler, recipe r3 (1,432 rows; the same counts, 74 of them under the roster's spelling of the name). In `mps` only `person_id` changes (125 rows).

**`erste-reden`.** A person with two Redner-IDs counted a second debut. Values: 2019-W03 1 → 0, 2021-W20 3 → 2, 2021-W23 4 → 1, 2021-W25 2 → 1, 2022-W36 2 → 1, 2023-W13 2 → 1, 2025-W21 58 → 57. Two weeks fall below the floor and are no longer publishable (2021-W23, 2021-W25). In 2021-W20 the fact moves from rank 1 to 2 and `laengste-sitzung` to 1; in 2021-W23 `laengste-sitzung` moves from 2 to 1 and `laengste-debatte` from 3 to 2. 27 further weeks move only in their percentile, because their baseline weeks hold fewer debuts.

## Against the first measurement

First measured on v0.46.49.0 (`.context/ship-after` to `.context/roster-after`). Every old and new value was recounted with one script on both pairs of stores; it gives the first report's figures on the first pair. Three differ:

| Figure | v0.46.49.0 | v0.46.52.0 | Why |
|---|---|---|---|
| Reden | 61,137 | 61,104 | PR 217 joined 13 Reden printed in two halves (one row less each) and made 20 bare motions procedural |
| Reden on MdB persons, old → new | 51,857 → 54,239 | 51,830 → 54,211 | of those 33 Reden 27 are on MdB persons before the join and 28 after it: Dagmar Schmidt's (Wetzlar) of 18/21 `ID1802103000` is the 28th. The other five (Schwesig 18/59, Lange 18/88, Lindholz 18/63, Warken 20/196, Lemke 19/41) are on persons without a plain MdB roster record |
| Reden of Dagmar Schmidt (Wetzlar) in `pairs.tsv` | 90 | 89 | the same Rede |

Everything else is the same in both measurements: the empty persons, persons, pages, redirects, Beiträge, Stimmen, aliases, `fact_sources`, all seven `erste-reden` values, the two weeks below the floor, the four rank moves and the 27 percentiles. The 125 `mps` rows are the same 125, and the 58 joins are the same 58.

## Grouping changes outside the 56

Two persons, both through the accent rule:
- **Adis Ahmetović:** the roll-call record "Ahmetović, Adis" (20/214, 3 Stimmen) joins him: 278 → 281 Stimmen. Its bundestag.de member number 861876 is the one his other WP 20 record carries; Stammdaten 11005005 is the only MdB of the name.
- **Ana-Maria Trăsnea:** two pages become one: the speaker page (4 Reden, 1 Beitrag, 45 Stimmen) and the DIP page (6 Stimmen). Stammdaten 11005306 is the only MdB of the name (mandate 2023-05-16 to 2024-03-04); all 51 Stimmen lie inside it.

No group was torn apart: every new person is a union of old ones. `match_rows` over the replayed store gives exactly the stored grouping, so a second replay is a fixed point.

## Review checklist (docs/agents/review-checklist.md)

1. **Sibling path:** the name match has three entry points, pass 2, pass 3 and `_stale_roster_partners`; each asks `_namesakes`. `compare_store_values.py` runs `match_rows` on raw rows and now passes the spoken Wahlperioden too.
2. **Stale beats fresh:** nothing is carried forward. The guess is recomputed; `same_person` joins are durable like any shared Personenkennung and stay as an alias when the entry is removed (as `merges` do).
3. **Order and history:** tests run every row order; the key sets are order-free; the namesake guard is symmetric.
4. **One key, one function:** `name_party_keys` stays the only bucket key; `_bucket_name` is its only folding.
5. **Absent vs zero:** an unknown Wahlperiode contradicts nothing (tested); `mp_id` NULL rows are skipped.
6. **Derived columns:** `person_id` on `mps`, `person_records` and `person_bindings` goes through `_assign`/`merge` as before; facts and pages are recomputed in the replay.
7. **Neighbour binding:** the proof of identity and the refusal are above. On all 1,358 MdB records: 58 joins made, 58 proven, none wrong, none of the 56 left.
8. **Hostile text:** `_WAHLKREISZUSATZ` is one anchored bracket without nesting; linear.
9. **Input shape:** every `same_person` field is validated and refused with a diagnostic (15 cases).
10. **Interrupted run:** no new write.
11. **Claims:** `docs/stable-ids.md`, `CONTEXT.md` and E15 say what `_bucket_name`, `_namesakes` and `_validate_same_person` do. `docs/data-methods.md` is untouched: `mps.xml_redner_id` keeps the printed id, so its CPP-BT figures stand.
12. **Loop cost:** `_namesakes` runs once per qualifying pair; the two extra queries are one `DISTINCT` per table. The replay took its usual time.
13. **Last commit:** the build commit, the merge of main and the restated figures; no code changed after the build commit, and TODOS.md closes the entry (ship).

Not run here: the full gate and a from-scratch build (one gate run follows at the end of the figure-moving work), and a browser check (no rendering code changed; a page's old URL was checked to redirect).

## Left open

- **Page headings follow DIP's spelling.** The heading prefers the roster name, so joined pages now read "Achim Post (Minden)", and three lose an accent the Bundestag prints: "Aniko Glogowski-Merten", "Zada Salihovic", "Ana-Maria Trasnea" (as "Adis Ahmetovic" already did). A heading rule that prefers the speaker's spelling where the names differ only by accents would fix it, in step with the recipes' `REPRESENTATIVE_SQL`.
- **Other Redner-IDs of the 99999 form** (TODOS.md "Placeholder Redner ids put one speaker on two Personenseiten", "Johanna Wanka is two persons") can use `same_person` once the owner decides on government roles.
