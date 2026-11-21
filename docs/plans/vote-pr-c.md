# Vote PR C: fix the four link patterns, record the review, gate the release

**Status (2026-11-21):** C1 built on this branch (not merged); see "Deviations in the build" at the end. C2 is next. Third PR of [`vote-links-and-figures.md`](vote-links-and-figures.md) ("PR split for part 1", item 3). It carries the outcome of the N10 review ([`vote-links-review-summary.md`](vote-links-review-summary.md), "Outcome of passes 1 and 2") and owner decisions 1, 2 and 6 of 2026-11-14. Main is v0.46.37.0: store schema 14, export format 20, speech rule 10. This branch is cut from `claude/sweet-ellis-983a79`, which holds the review (three commits, not yet merged).

Every figure below was measured offline, read-only, on the 806 cached reports of the reference store `/Users/luca/Projects/poliwatch/.context/dip-pulse-site` (710 links, 736 votes). The scratch harness that measured them is in [`vote-pr-c/`](vote-pr-c/): `harness.py` loads the reports and the sheet, `rules.py` holds every candidate condition, and [`vote-pr-c/expected-links.tsv`](vote-pr-c/expected-links.tsv) lists the 676 links the proposed rule gives. The harness's re-implementation of today's rule reproduces all 710 stored links before any condition is switched on. The decisions only the owner can make are at the end.

## 1. Summary

| | Today | After PR C |
| --- | --- | --- |
| Links (`agenda_item_votes`) | 710 | 676 |
| `drucksache_xml` / `drucksache_vorgang` / `title` | 180 / 510 / 20 | 149 / 485 / 17 |
| `einzelplan` / `drucksache_call` (new) | – | 18 / 7 |
| Votes with no TOP | 70 | 60 |
| Votes linked to 2 or more TOPs | 17 (61 links) | 0 |
| TOPs with 2 or more votes | 107 (297 links) | 95 (264 links) |
| Reviewed wrong links still made | 52 | 0 |
| Reviewed right links lost | – | 0 |

The rule adds 20 links, drops 54 and changes the basis of 5: 79 changed rows in 30 sittings (by Wahlperiode 18: 16, 19: 29, 20: 13, 21: 21). The 54 dropped are the 52 the review found wrong and 2 more wrong links outside the sample (votes 548 and 604, pattern D). Of the 20 added, 8 are the right links the review named for 317, 375, 557 and the five D votes; 10 link Einzelplan votes that have no TOP today; 2 are the moved 548 and 604. The 12 links outside the review's notes were read for this plan (section 3).

## 2. The rule after PR C

`vote_links.top_links` stays one pure function of a report's TOPs and votes, run online, on replay and after carry-forward. It gains one input filter and five steps. Each step looks only at the vote and its sitting, so the result stays independent of order (review checklist class 3).

**Inputs.**
- **B. Procedural motions bring no Drucksachen.** A TOP's DIP numbers no longer follow the `mitberaten` list of a position whose `vorgangsposition` starts with "Geschäftsordnungsantrag" or reads "Antrag zur Geschäftsordnung". Such a motion (to put an item on the agenda or take it off) names the Vorgänge it concerns; the TOP did not deal with them. The TOP keeps its own positions' Vorgänge. Narrower than "Geschäftsordnung": the 18 positions "Beratung über Bericht gemäß § 62 Abs. 2 Geschäftsordnung BT" are debates of a stalled bill and keep their `mitberaten`.
- **Canonical Bundestag numbers.** Every Drucksache number, the vote's, printed, DIP-linked and chair-named, is compared as `derive.canonical_document_number` (the leading-zero item in the TODOS entry), and a DIP-linked number counts only with `herausgeber` BT: 10,955 of the 34,885 linked entries are Bundesrat Drucksachen ("120/15"), which could collide with a Bundestag number once canonical. 0 changes today.
- **The chair's numbers in a section of its own.** A new parse field, `called_drucksachen`, holds the Drucksache numbers the chair names in a TOP section that has no heading and no Rede: paragraphs that are not `T…` heading paragraphs, matched as "Drucksache(n) NN/NNNN[, … und NN/NNNN]" with word boundaries (so a Bundesrat "Drucksache 447/26" does not yield "47/26"). It is filled where the parser builds the report's agenda item, so it follows the report's items, adopted TOPs included, not the XML's section count (18/44, 18/49, 18/89 and 18/158 differ). Every other TOP gets an empty list. 402 sections of the 806 sittings have no heading; 110 of them also hold no Rede, and 85 of those name a Drucksache in the chair's text. The field stays out of `xml_drucksachen` and out of `agenda_item_documents`.

**Steps, per vote, in this order:**
1. **Match (today's rule).** Every TOP sharing a vote number, printed (`drucksache_xml`) or through DIP (`drucksache_vorgang`); with none, the one TOP whose heading or position titles `title_matches` the vote title (`title`).
2. **D. The section where the chair calls the vote.** If exactly one TOP's `called_drucksachen` shares a number with the vote, the vote links to that TOP alone, basis `drucksache_call`. Stop.
3. **A1. The Einzelplan.** If the vote is not an Entschließungsantrag (its description does not begin with "Entschließungsantrag"), its title and description together name exactly one Einzelplan number ("Einzelplan 04", compared as a number, so "Einzelplan 4" matches), the vote is not on the third reading (the text says "zweiten Beratung", or does not say "dritten Beratung"), and exactly one TOP heading of the sitting names that Einzelplan, the vote links to that TOP alone, basis `einzelplan`. Stop. The guard keeps Entschließungsanträge "zu der dritten Beratung" that name one Einzelplan on the third reading: 559 in 19/66 names Einzelplan 11, the sitting has an Einzelplan 11 section, and the guard keeps the vote on TOP II, where it was called.
4. **A2. Drop the umbrella.** With two or more Drucksache matches, drop every TOP whose shared numbers are a proper subset of another matched TOP's.
5. **C. Drop the neighbour.** With two or more left, drop a TOP whose shared numbers come only through DIP positions that touch it on a single page while the same position covers another TOP on more pages. A TOP that prints a shared number keeps it.
6. **A3. The third reading.** With two or more left, if exactly one heading begins (after a list mark "a)", "–" or a Roman numeral) with "Dritte Beratung", keep that TOP. "Zweite und dritte Beratung" does not count.

What is left is the vote's link set. **`top_links` returns, per vote, the set and the step that decided it:** `match` when the set equals step 1's, else `call`, `einzelplan` or `narrowed`; `none` for no TOP. `links()`, `placement_errors`, persist and `enrich_with_api` take the new shape. The release gate keys on every vote whose step is not `match` or `none` (section 5).

**Why no Entschließungsantrag moves to an Einzelplan.** An Entschließungsantrag is usually voted after the Schlussabstimmung, even when it names one Einzelplan and is addressed to the second reading (19/129 defers those to Einzelplan 16 "nach der Schlussabstimmung"). None of the 18 votes step 3 places is one, so the guard changes nothing today.

### Per pattern: the condition, what it fixes, what else it moves

Each condition was run alone and together over all 806 reports (harness `report_diff`; output reproducible with `rules.py`).

| Pattern | Condition | Fixes (reviewed wrong links) | Adds | Moves outside the 408 |
| --- | --- | --- | --- | --- |
| A, 43 links | steps 3, 4 and 6 | all 43: 317, 318, 319, 375, 557, 562–564, 781, 894, 897, 898, 960, 961, 979, 980 | 317 → TOP I (Fortsetzung) occurrence 2, 375 → Einzelplan 12, 557 → Einzelplan 60; and 10 votes with no TOP today: 435, 531, 532, 533, 556, 640, 641, 705, 778, 820 | the 10 added links; basis `title` → `einzelplan` for 279 and 374, `drucksache_xml` → `einzelplan` for the right links of 894, 960 and 979 |
| B, 2 | input filter | 608 and 609 lose Zusatzpunkt 12 | – | none |
| C, 2 | step 5 | 280 loses TOP IV, 493 loses TOP 13 | – | none |
| D, 5 | step 2 + parse field | 476, 477, 480, 579, 588 | each to its own Zusatzpunkt section (10, 11, 3, 10, 14) | 548 (19/59) TOP 30 → Zusatzpunkt 5; 604 (19/102) Zusatzpunkt 11 → Zusatzpunkt 12 |

Step by step alone: A1 drops 16 wrong links and adds 3; A2 drops 26; A3 drops 19 (with the strict "begins with" test; a loose test also dropped 608's Zusatzpunkt 12 by accident, on a later "Dritte Beratung" inside ZP 15's heading); B drops 2; C drops 2; D moves 7. Together: 54 dropped, 20 added, 5 basis changes, nothing else.

**Tested and rejected:**
- **C as the review suggested it** ("refuse a title match in `position_matches_top` when the TOP prints Drucksachen and none belongs to the position's Vorgang"): it fixes neither 280 nor 493. Both are WP 18/19 sittings, where the parser reads printed Drucksachen only from links and every TOP prints none (TODOS "Printed Drucksachen are read only from links"). The page test of step 5 is what separates the two TOPs: the MINUSMA position runs over pages 3725 to 3733, TOP III covers 3725 to 3732, and TOP IV starts on 3733; UNAMID likewise (345–351 against TOP 12's 345–350 and TOP 13's 351–359).
- **A as "keep the TOPs holding a number no other matched TOP holds"** (the review's first suggestion): on this store it gives the same result as the subset test of step 4, but where TOP X holds {a, b}, Y {a, b, c} and Z {c, d}, it drops Y and keeps Z. The subset test drops only X, the one TOP whose evidence another TOP contains.
- **A as "keep the TOP with most shared numbers"**: ties on the same 7 votes, and a count is not evidence that one TOP contains another.
- **A title tiebreak** ("among tied TOPs keep the one whose heading `title_matches` the vote"): fixes 493 and 781 and fails 280, whose two Bundeswehr headings both pass the fuzzy test.
- **D as the review suggested it** ("when a heading lists ZP n, give ZP n's printed Drucksachen to the section with that `top-id`"): the parser drops the `T_ZP_NaS` lines, so no heading in the report holds "ZP 10", and WP 18/19 prints the numbers as plain text. The chair's own words in the section (`18/237`: "Zusatzpunkt 10. Abstimmung über den Antrag der Fraktion Die Linke auf Drucksache 18/12639 …") are the evidence that is there.
- **D without "no Rede"**: would let a Drucksache the chair names in a speaking section pull a vote there. The headingless section filed under "Einzelplan 20" in 19/197, where the owner kept 703 and 704 on the joint "Einzelplan 8" section, holds 15 Reden and names 19/24969; the condition keeps it out.

### Why the rule, not reviewed entries, for every pattern

Owner decision 2 puts a pattern in the rule. Each of the four holds for at least two reviewed links with one cause in the rule's inputs, and the experiment shows each condition touches nothing it should not on 806 sittings. D was the closest call: 5 reviewed links in 4 sittings, and the condition needs a new parse field. It stays a rule because it also found 548 and 604, two wrong links in unreviewed plain links, which entries would never have caught, and because ordinary weeks keep producing joint debates whose votes the chair calls in a section of their own.

## 3. The 12 links outside the review's notes, read

Read against the protocol XML of the reference store: the section the rule now picks, the chair's call of the roll call, and the tally. All 12 are right by the review's standard (the chair calls and takes the roll call in that section, on that Vorlage). An independent reviewer judged them blind from the XML and agreed on all 12 (section 10).

| Vote | Sitting | New TOP | Evidence (protocol) |
| --- | --- | --- | --- |
| 435 | 18/202 | Einzelplan 04 | "Wir kommen jetzt zur Abstimmung über den Einzelplan 04 … Wir stimmen namentlich ab." |
| 531 | 19/45 | Einzelplan 04 | Einzelplan 04 in der Ausschussfassung, namentlich, in that section |
| 532, 533 | 19/45 | Einzelplan 14 | the two Änderungsanträge to Einzelplan 14 (19/3179, 19/3185) called there by name |
| 556 | 19/64 | Einzelplan 04 | "Wir kommen zur Abstimmung über den Einzelplan 04 … Es ist namentliche Abstimmung verlangt." |
| 640 | 19/129 | Einzelplan 16 | Änderungsantrag 19/15464 to Einzelplan 16, roll call opened there |
| 641 | 19/130 | Einzelplan 04 | "Wir kommen zur namentlichen Abstimmung über den Einzelplan 04" |
| 705 | 19/198 | Einzelplan 4 | "Ich eröffne die namentliche Abstimmung über den Einzelplan 04." |
| 778 | 20/40 | Einzelplan 04 | same, section a) Einzelplan 04 / b) Einzelplan 22 |
| 820 | 20/69 | Einzelplan 04 | same |
| 548 | 19/59 | Zusatzpunkt 5 | "Damit kommen wir zum Zusatzpunkt 5 … Die Fraktion der AfD verlangt namentliche Abstimmung." TOP 30 only debated it jointly |
| 604 | 19/102 | Zusatzpunkt 12 | "Zusatzpunkt 12. … Antrag der Fraktion der AfD auf Drucksache 19/9757 … namentlich ab." It was linked to ZP 11, the coalition's Antrag |

Why the 10 Einzelplan votes had no TOP: in WP 18, 19 and early WP 20 an Einzelplan section has no DIP position and prints its Drucksachen as plain text, so it shares no number with anything, and the title of a budget vote ("Geschäftsbereich der Bundeskanzlerin …") does not pass `title_matches` against "Einzelplan 04 Bundeskanzlerin und Bundeskanzleramt". Of the 736 votes, 713 name no Einzelplan, 318 names five, and 22 name exactly one: step 3 places 18; 282 (18/42) has no matching section; 559, 643 and 644 are Entschließungsanträge to the third reading, kept there by the guard. Those four keep their links as they are.

**What the S4 estimate means now.** S4 found 0 errors in 64 random plain links. Pattern D's condition found 2 wrong links among the 302 nobody reviewed (548, 604), which fits the bound of 4.6%. The data-methods text reports both.

## 4. The reviewed list: `scripts/reviewed_vote_links.json`

**One file for every reviewed link,** beside `reviewed_units.json` and separate from it, as the plan of 2026-11-14 placed it. It holds the review's verdicts, not only drops and flags, because three consumers need every verdict outside `docs/plans/`: the CI oracle, the store gate and the release gate. The sheet stays the human worksheet.

**Entry:**

```json
{"protocol": "21/45", "vote_id": "980", "top_id": "Tagesordnungspunkt II", "top_occurrence": 1,
 "heading_starts": "Dritte Beratung des von der Bundesregierung",
 "verdict": "right", "pattern": "-", "action": "none", "note": "", "source": "sheet 2026-11-21"}
```

- **Key** `(protocol, vote_id, top_id, top_occurrence)`, as in the sheet. `top_id` is the cleaned id (`derive.clean_text`), and the occurrence is counted over cleaned ids in `item_index` order. The sheet and the store hold cleaned ids already; 168 TOPs of the raw cached reports have a no-break space (`Tagesordnungspunkt\xa026` in 20/64), so the rule's side must clean before it compares.
- **`heading_starts`**: the first 40 characters of the cleaned heading, compared as a prefix, no regex (class 8). Empty for a section without heading.
- **`page_start`**: the TOP's first page. 96 `(protocol, top_id)` pairs occur more than once and a re-parse can adopt a TOP and shift occurrences; with headingless sections and generic prefixes ("Beratung des Antrags der Fraktion der"), the page is what tells a shifted TOP from the reviewed one.
- **`verdict`** `right` or `wrong`; **`pattern`** `A`–`D` or `-`; **`action`** `none` (right), `rule` (wrong, fixed by a pattern), `drop` or `flag` (decision 2); **`note`** required for `drop` and `flag`; **`source`** `sheet <date>` or `plan vote-pr-c` for the 12 links of section 3.

**From the sheet to entries.** `scripts/vote_link_review.py --entries` reads the sheet's five verdict columns and merges them into the file by key. It refuses when an existing entry has another verdict than the sheet (no silent overwrite) and when a sheet row has an empty verdict. PR C commits 428 entries: the 408 rows (356 right, 52 wrong with `rule`), the 8 right links the review's notes name for 317, 375, 557 and the D votes, and the 12 of section 3. Later batches go through the sheet and `--entries` again.

**Deferred item 15 goes with it.** The sheet generator pre-fills the five verdict columns from the entries file by key, so regenerating the sheet no longer erases a verdict.

**How it acts, and how a stale entry shows:**

| Entry | Effect on the data | When it no longer fits |
| --- | --- | --- |
| `right`, `none` | none | the rule stops making the link: oracle test fails; store gate fails; `--publish` refuses |
| `wrong`, `rule` | none (the rule already leaves the link out) | the rule makes the link again: same three |
| `wrong`, `drop` | `vote_links.links` removes the link after the rule | the rule no longer makes it: the loader stops the run, the entry must be deleted |
| `wrong` or `right`, `flag` | the link stays and carries the note | the rule no longer makes it: the loader stops the run |
| any | – | unknown vote or TOP in the sitting, heading not starting with `heading_starts`, other `page_start`, duplicate key, malformed file: the loader stops the run for an acting entry; the store gate and the release refuse for any entry |
| any, sitting not in the store or export | – | skipped and counted (a reviewed exclusion, a sitting not yet released); the gate's summary names them |

The loader stops a run only for entries that act (`drop`, `flag`) and for a malformed file, as `reviewed_units` does: a stale acting entry stops the weekly online build until it is deleted. That is the `reviewed_units` model, kept on purpose; it never fires while no entry acts. A verdict-only entry that no longer holds does not stop a build: it fails the oracle, the store gate and the release, which is where a regression of a checked link belongs. Entries apply after the rule and never stand in for a pattern (decision 2). Today no entry is `drop` or `flag`: the review found no one-off. The file feeds no parse, so a change to it makes no report stale: the attribution at the persist choke point (section 7) applies it on every run, and a test proves that a changed entry reaches the store without a re-read.

## 5. The release gate (owner decision 6, amended 2026-11-21)

**What it reads.** The export's SQLite (`agenda_item_votes`, `votes`) and `scripts/reviewed_vote_links.json` as of the export's commit, read with `build_revision.blob_text` the way `verify_export` already reads the licence file, so the entries are the ones the export was built with.

**What it refuses.** Under `--publish`, every **contested vote** (one linked to two or more TOPs, or whose `top_link_step` is `call`, `einzelplan` or `narrowed`, so a step after the plain match decided it) unless each of its links has an entry with verdict `right` or action `flag`, matching key, `heading_starts` and `page_start`. It also refuses any present link whose entry says `wrong`. A dry run names them all. The export maps to the key by joining `agenda_items.top_id`, `item_index` and `protocols.document_number`, counting occurrences in `item_index` order. It sits beside `awaiting_exclusions` and `unreleased_sittings_problem` in `run_release`, and like them it does not stop `validate_store_gate` or a build, so T4-style and weekly builds still pass (ADR 0005, "The release enforces the bar", D6 precedent).

**Why contested, not only two or more TOPs.** Decision 6 keys on "two or more TOPs" because that is where the review found every error. After PR C no vote is linked to two or more TOPs, so the literal gate would check nothing, while a wrong narrowing, a wrong Einzelplan move or a wrong call-section move would each leave one wrong link that it never sees. Steps 2 and 3 resolved most of the old multi-TOP votes (894, 960 and 979 had 5, 7 and 4 links), so they are gated too. The owner accepted this reading on 2026-11-21; it amends decision 6 (section 13).

**What persist records for it.** `votes.top_link_step` TEXT NOT NULL, one of `none`, `match`, `call`, `einzelplan`, `narrowed`, written from the same `top_links` result as the links, so the two cannot disagree within one store.

**The 17 multi-TOP votes after the rule.** None is linked to two or more TOPs. 15 votes reach two or more TOPs after B: 894, 960 and 979 are placed by their Einzelplan; the other 12 (280, 318, 319, 493, 562, 563, 564, 781, 897, 898, 961, 980) are narrowed. 608 and 609 reach one TOP once B removes the procedural motion's numbers. In all, 35 votes are contested on the reference store (12 narrowed, 18 `einzelplan` minus 279 and 374, whose TOP did not change, and 7 `call`), and every link of each has an entry (sheet row, review note, or section 3). So the gate passes at PR C. A budget week brings about 5 to 10 contested votes to review before its release: the Einzelplan roll calls and the Schlussabstimmung.

**Store gate.** `validate_store_gate.py` gets two checks on the store: every entry's verdict holds (right links present, wrong links absent, drops absent, flags present with their note, keys matching by heading and page), and the release gate's condition, reported but not failing, so a replay shows early what a release would refuse. Making the multi-TOP check fail the store gate, as the 2026-11-14 plan had it, would stop T4-style and weekly builds; it stays a release refusal.

## 6. Regression fixtures

- **One fixture file,** `tests/fixtures/vote_links/reviewed-sittings.json.gz`, for the 156 sittings that hold an entry (147 in the sheet, 9 more for section 3). Per sitting only what the rule reads: per TOP `top_id`, heading, page range, Rede count, printed and `called_drucksachen` numbers, positions (`vorgang_id`, `vorgangsposition`, `titel`, pages, `mitberaten` ids and titles), the DIP-linked numbers with their Vorgang; per vote `id`, `title`, `description`, `document_numbers`. Measured: 4.9 MB as plain JSON, 0.63 MB gzipped; one gzipped file, like `docs/plans/a1-source-baseline.json.gz`.
- **Written by** `vote_link_review.py --fixture`, read-only on the store. A replay never rewrites the cached JSON, so the JSON never gains `called_drucksachen`: `--fixture`, and the sheet generator likewise, run `reparse_cached_xml` in memory on the reports they read before they extract anything. A test runs `--fixture` on a report whose JSON predates the field.
- **`tests/test_vote_link_oracle.py`** runs `vote_links.links` on every fixture sitting with the entries file and asserts every entry: `right` made, `wrong`/`rule` not made, `drop` made by the rule and removed, `flag` made with its note. A later rule change that moves a reviewed link fails here, in CI, without a store. What it cannot see: a change in the rule's inputs (the parser, DIP), because the fixture freezes them, and any sitting outside the 156. Those two are for the replay check below and the store gate.
- **Pattern unit tests** in `tests/test_vote_links.py`, synthetic, one per step and its guard, written first (section 9).
- **Replay check in the PR.** The build's replay compares the new store's links row by row with `docs/plans/vote-pr-c/expected-links.tsv` (676 rows) and runs the gate condition on the whole store. Later PRs that touch the parser or DIP inputs show their link diff through `compare_store_values.py` as every replay does.
- **Parser test on real XML:** `called_drucksachen` of 18/237 Zusatzpunkt 10 is ["18/12639"]; 19/197's headingless section under Einzelplan 20 (15 Reden) stays out of step 2.
- A refresh of the fixtures is a reviewed act: regenerating from a store where DIP or the parser changed can change a sitting's inputs. The test's failure message names the sitting and the step.

## 7. Schema, versions and replay

**Versions** (the next free numbers at ship; today):
- **Store schema 14 → 15.** `agenda_item_votes.basis` CHECK gains `einzelplan` and `drucksache_call`; `votes.top_link_step`. A schema-14 store is refused, which forces `--offline --repersist`.
- **Export format 20 → 21.** New basis values and a new column in the exported tables; data dictionary entries.
- **Speech rule unchanged.** The parse output gains `called_drucksachen`, but `speech_kinds.VERSION` is the Reden counting rule: bumping it would mark every Reden fact as rule-changed, touch `speech_rule_inputs`, the demo fixture check and the fact test constants, and clash with the name-tag build, all for a field no Reden figure reads. Instead **`stale_causes` gains a third cause, `votes`**: a report whose `validation_summary.vote_inputs_version` differs from `vote_links.INPUTS_VERSION` (1 in PR C; the parse stamps it) is re-read from its XML. The refusal text names the cause as it names `rule` and `reviewed`.

**Deferred item 1, the trap, closed for good by two changes:**
1. **Attribute at the one place every report passes before persist.** `rebuild_database_from_entries` calls `vote_links.attribute_votes` on every entry right before `persist_report`. Online, offline, backfill and kept reports all pass there, so a rule change can no longer make `placement_errors` refuse a kept sitting, whatever the cached JSON says. `placement_errors` stays in persist as the invariant that the placement equals the rule.
2. **A change of what the rule reads from the XML bumps `vote_links.INPUTS_VERSION`** (above), so `stale_causes` sends kept reports through `reparse_cached_xml` on the next online build. Like the speech rule, the cause stays set until a sitting is re-fetched, because the JSON is not rewritten; every online build re-reads those XMLs, which costs about as much as the replay.
3. **The render that does not persist.** The offline render without `--repersist` loads the cached JSON and only warns about stale reports (`build_dip_pulse_site.py:14997`), and dossier vote panels read `item["votes"]` (`:8138`). It calls `attribute_votes` on load too, so a dossier never shows a placement the store does not hold. Test: a cached report with the old placement renders the rule's.

Online, kept sittings' dossier pages are written before the rebuild; with 3, they are written from the attributed report.

A rule change that reads no new parse field needs neither a schema bump nor a re-read. Rejected: writing the re-attributed report back to the cached JSON. It would make the cache's content depend on the code that last ran, and the replay recipe and the sheet both rely on the JSON being what the acquisition wrote.

**Replay recipe** (README "Validate a data correction", on a copy, never on the reference store):
1. `cp -cR /Users/luca/Projects/poliwatch/.context/dip-pulse-site <scratch>/store` (APFS clone).
2. `uv run --python 3.13 python scripts/build_dip_pulse_site.py --output-dir <scratch>/store --offline --repersist` (`--repersist` re-reads all 806 reports from XML).
3. `scripts/compare_store_values.py` old against new; it compares `agenda_item_votes` already.
4. Compare the new store's links with `docs/plans/vote-pr-c/expected-links.tsv`: they must be equal row for row.
5. `scripts/validate_store_gate.py` on the copy, then the release dry run on its export.

**Expected old → new** (store): the table in section 1. Downstream, which the replay reports and the PR states (class 6):
- The vote panel's place (`features/votes.stored_votes`, lowest `item_index` of the linked TOPs): 980 and 961 from TOP I to TOP II; 898 and 897 from TOP I to TOP III, IV; 894 from TOP I to Einzelplan 04; 318 and 319 from TOP I (Fortsetzung) to TOP II; 563 and 564 from TOP 6 to TOP 8; 608 and 609 from ZP 12 to ZP 15 and ZP 18; 781 from Einzelplan 11 to TOP V; the five D votes and 548, 604 to their Zusatzpunkt sections; the 10 newly linked Einzelplan votes from the sitting panel to their Einzelplan.
- `vote_politikfelder` rows with `source = top`; vote lists on bill pages (`bill["votes"]`); vote facts that join `agenda_item_votes` (`facts.py`); recipes r3 and r4 (no link crosses sittings, so no change expected).
- Not moved: `agenda_item_documents` (B and C act on the vote rule only; `called_drucksachen` stays out of it), Reden, votes, members.
- The Reden figures must not move (the parser change adds one field); the PR says so with the compare output.

## 8. Deferred items of the TODOS entry

| Item | PR C | Reason |
| --- | --- | --- |
| 1 Online run, kept reports | **takes** | section 7; PR C's own rule change would trip it |
| 3 Two rule runs in `enrich_with_api` | **takes** | compute `top_links` once over the list candidates and hand that result to `attribute_votes`, so warnings and placement come from one run. Not "derive the warnings from `placed`": `placed` covers fetched votes only, so a candidate whose detail fetch failed would be reported as matching no TOP, which today counts as matched |
| 4 Carry-forward drops votes of a repeated `top_id` | **takes** | same function as the rule's caller; collect every cached vote (`vote_links.report_votes(existing_report)`) before `attribute_votes`, with a test on a repeated `top_id`. No vote lost today (20/152, 21/25) |
| Leading-zero comparison | **takes** | step inputs; the new chair-text numbers come from free text |
| 6 leftovers (pairing helper, heading check) | leaves | no wrong row; sheet hygiene |
| 8 tests (re-parse adds a TOP; vote id given twice) | **takes** the first | step 2 reads a parse field of re-read TOPs |
| 14 (a) `placement_errors` docstring | **takes** | the function is edited anyway |
| 14 (b)–(f) | leaves | wording and shape checks no input reaches |
| 15 Regenerating the sheet erases verdicts | **takes** | section 4; the entries file becomes the record |
| 16–19 sheet batches, flag, test, header revision | leaves | no figure; the next batch's work |

The Vorgang-level side of B and C is a new follow-up, not PR C: `agenda_item_documents` still gives Zusatzpunkt 12 of 19/105 49 numbers, ZP 5 of 19/37 7 and ZP 14 of 20/109 10 through procedural motions, and 32 TOP–Vorgang assignments in 17 sittings rest on a one-page boundary overlap. Fixing them means making the DIP position assignment replayable (it runs online only; a replay keeps every DIP field) and moves documents, bill pages and Politikfelder. It belongs with "Printed Drucksachen are read only from links", which also moves `agenda_item_documents`. PR C adds a TODOS entry for it.

**A second follow-up: votes that have an obvious TOP and get none.** The second reviewer found about 25 of the 60 votes still without a TOP that have one plainly, from the chair's call: 346–351 (18/115, TOP 13 and TOP 18), 417 and 418 (18/190), 282 (18/42, TOP IV), 298 (18/47), 630 and 631 (19/126), 648 and 650 (19/137), 490 (19/4), 767–770 (20/28), 780 (20/42), 800 (20/54), 840 (20/97), 814 (20/66). None is a wrong link; each is a missing one, mostly where WP 18/19 prints Drucksachen as plain text. It belongs with "Printed Drucksachen are read only from links" and gets its own review rows; PR C adds it to the TODOS entry with this list.

## 9. Build order, tests first

**PR C1: the rule, the record, the gates** (figures move):
1. Unit tests, red: B (a procedural motion's `mitberaten` brings nothing; a § 62 report keeps it); step 2 (a headingless, Rede-free section named by the chair takes the vote; one with a Rede does not; a section that gains a Rede stops taking it; two such sections, none taken; "Drucksache 447/26" yields nothing); step 3 (one Einzelplan, unique heading; "Einzelplan 4" against "Einzelplan 04"; the third-reading guard; an Entschließungsantrag stays; two headings naming it, no move); Bundesrat numbers ignored; step 4 (proper subset dropped, equal sets kept, the X/Y/Z case); step 5 (boundary page dropped, a printed number keeps the TOP); step 6 ("Dritte Beratung" first, not "Zweite und dritte"); canonical numbers; a shuffle test over all steps (class 3).
2. Parser: `called_drucksachen` in `xml_top_fields`, `vote_inputs_version` stamp; parser tests on 18/237 ZP 10 and 19/197 Einzelplan 20 (has Reden, stays empty); the `votes` stale cause with its test.
3. `vote_links`: the filter and steps; the `(set, step)` return shape and its callers; item 3; item 14 (a).
4. Choke-point attribution in `rebuild_database_from_entries` (item 1) with a test: a kept report whose cached placement predates the rule persists with the rule's placement; attribution in the non-persisting render with its test; item 4 with its test; item 8's test.
5. Persist: schema 15 with `basis` values, `votes.top_link_step`, and C2's `agenda_item_votes.review_note` and `vote_link_reviews` table created empty, so C2 needs no second bump; schema refusal test.
6. `reviewed_vote_links.json` loader and its refusals (each row of the table in section 4); `vote_link_review.py --entries` and the verdict pre-fill (item 15); the 428 entries.
7. Fixtures (`--fixture`) and the oracle test; then run the replay and compare with `expected-links.tsv`.
8. Store gate checks; release gate in `run_release` with tests (an unreviewed contested vote refused, for each of `call`, `einzelplan`, `narrowed` and two links; a present link whose entry says `wrong` refused; an entry whose page no longer fits refused; a reviewed vote passes; a dry run names them).
9. Text (section 11), export format 21, data changelog, TODOS.

**PR C2: one-off drops and flags** (no figure moves while the list has no such entry): `drop` and `flag` acting in `vote_links.links`; persist fills `agenda_item_votes.review_note` for a flag and the table `vote_link_reviews(vote_id, protocol, top_id, top_occurrence, heading, action, note, reviewed_on)`, which keeps a dropped link's record for the vote page (both created empty in C1); the vote panel's two lines from decision 2 (component per DESIGN.md, browser check at 375px and in dark mode); no schema bump; tests (a drop removes the link from the TOP and the bill page; a flag shows its note; a stale drop stops the run). Question 2 asks when.

**Size** (estimated): C1 M–L, about 350 lines of code, 450 of tests, 428 generated entries, a 0.6 MB fixture, plus one full replay (minutes) and docs. C2 S–M.

**Why C1 stays one PR.** A reviewer can ask to split "rule, parser, choke point" from "record and gates". The first half alone would move 79 link rows with no oracle and no gate to hold them, and the owner ships one PR at a time; the record is what makes the figure change checkable. The commits follow the build order, so a review can read them in two halves.

## 10. Adversarial review

Two independent Sonnet reviewers attacked the draft on 2026-11-21, with the plan, the code and the read-only store, without this session's reasoning. One reviewed the architecture against the review checklist; the other hunted for a link the rule gets wrong and judged the 12 links of section 3 blind, from the XML, before reading section 3. Both reproduced the 676 links with the harness.

**Folded in:**
1. *The fixtures and the sheet cannot read `called_drucksachen` from the cached JSON*, which a replay never rewrites. `--fixture` and the sheet generator now re-parse in memory first (section 6).
2. *`speech_kinds.VERSION` was the wrong trigger*: it is the Reden rule and would have flagged every Reden fact, touched the demo and fact fixtures and clashed with the name-tag build. Replaced by a `votes` stale cause and `vote_links.INPUTS_VERSION` (section 7). The clash with the name-tag build shrinks to the export format.
3. *The release gate let a present link with a `wrong` entry pass, and never saw votes placed by steps 2 and 3*, which resolved most of the old multi-TOP votes. The gate now requires a `right` or `flag` entry for every link of every contested vote and refuses a present `wrong` link (section 5); owner question 1 is reworded.
4. *Entry keys fail silently when a re-parse shifts occurrences*, and headingless sections have no prefix to check. Entries carry `page_start`, both gates check heading and page, the export-to-key mapping is stated, and entries for sittings outside the store are skipped and counted (section 4).
5. *Deferred item 3 as first written changed behaviour*: warnings from `placed` would call every fetch-failed candidate unmatched. Now one `top_links` run over the candidates feeds both (section 8).
6. *The oracle freezes the rule's inputs and the "no unreviewed narrowed vote" check was vacuous on fixtures chosen for having entries.* Replaced by a whole-store replay comparison with `expected-links.tsv` and a store-gate report of the release condition, plus a parser test on real XML (section 6).
7. *"Closed for good" missed the offline render without `--repersist`*, which renders dossier vote panels from cached placement. It attributes on load too (section 7).
8. *Figures:* 79 changed rows (not 74), per Wahlperiode 16/29/13/21; 110 headingless sections without a Rede, 85 naming a Drucksache; the no-break space is in the raw reports (168 TOPs), not in the sheet. Corrected.
9. *Word boundaries in the chair-text pattern, Bundesrat numbers out of the comparison* (10,955 linked entries are BR), *the item-based keying of the new field*, *a test that a section gaining a Rede stops taking the vote*: added (section 2, build order).
10. *`top_links`' return shape* now carries the deciding step, which `top_link_step` and the gate need (section 2).
11. *C2 needed a second schema bump*: C1 creates C2's column and table empty (section 9).
12. *Step 3 could move an Entschließungsantrag "zu der zweiten Beratung" that the chair takes after the Schlussabstimmung* (the second reviewer's constructed case; 19/129 shows the shape): step 3 now leaves Entschließungsanträge alone. It changes no link today.
13. *About 25 of the 60 votes without a TOP have an obvious one* (second reviewer, from the chair's calls): a new follow-up with the list (section 8), not PR C, because each is a missing link, not a wrong one, and needs its own review rows.

**The blind check:** all 12 links of section 3 right, each with the chair's call quoted. No wrong link found among the 676 after a search the reviewer describes: every vote's call paragraph compared with its linked section, about 40 mismatches read, every unreviewed link whose section prints none of the vote's numbers read, all title links, every Einzelplan vote, every headingless section that names a Drucksache (only the 7 D votes match one; none matches two).

**Rejected, with the reason:**
- *Split C1 into "rule, parser, choke point" and "record, gates"*: the first half would move 79 link rows with nothing to hold them (section 9).
- *A stale acting entry should not stop the weekly build*: kept as in `reviewed_units`; it cannot fire while no entry acts, and an entry that acts on a sitting it no longer fits is exactly what must not ship.
- *Step 5 could drop a right one-page TOP when DIP's position ends a page late*: true in principle; such a vote is `narrowed`, so the release gate stops it for review. No such case on the store.
- *Step 2 could pull a vote to a headingless section that only announces its result with its Drucksache*: such a move is a `call` vote, which the release gate stops for review. *Step 2 does not fire when two sections name the vote*, and the vote then stays on the joint debate TOP, the pattern-D error, as a `match` the gate does not see: a known gap, recorded with the missing-link follow-up. Neither case occurs on the store. A stricter pattern (only paragraphs that open a vote) was not adopted without a case to test it on.
- *Two budget laws in one sitting (a Nachtragshaushalt) could send an Einzelplan vote to the other bill's section*: gated as `einzelplan`; no such sitting on the store.
- *548 could be "right" on TOP 30 under the reading "the TOP that dealt with the Vorlage"* (the second reviewer's note): the owner's pattern-D verdicts and the 703/704 decision settle it as the section where the chair calls the vote when that section is the Zusatzpunkt's own.

## 11. What the user-facing text says afterwards

- **`docs/data-methods.md`, "Abstimmungen und Tagesordnungspunkte"** (DATA.md is generated from it): the six steps in plain German, one sentence each, naming the two new `basis` values; then the review, every figure generated from the store or the entries file at export: "Vor der Veröffentlichung wurden {408} Verknüpfungen von Hand gegen Protokoll und DIP geprüft: {356} richtig, {52} falsch; alle {52} gehen auf vier Muster zurück, die die Regel jetzt behandelt. Die Regeländerung band {20} Verknüpfungen neu, davon {12} außerhalb der Stichprobe, alle gelesen. Unter {64} zufällig gezogenen einfachen Verknüpfungen fand die Prüfung keinen Fehler (Fehlerquote unter 4,6 % bei 95 % Sicherheit); die Regel für Muster D fand außerhalb der Stichprobe {2} weitere." Delete the dictionary's "die Verknüpfungen sind noch nicht von Hand … geprüft", which is false after the review.
- **`scripts/data_dictionary.json`**: `agenda_item_votes` meaning and `basis` values; `votes.top_link_step`.
- **Vote page:** in C1 nothing new (no drop, no flag). In C2 the two lines of decision 2, shown only where an entry acts.
- **`docs/data-changelog.md`**: old → new for links, per basis, votes without a TOP, multi-TOP votes and TOPs with several votes, with one line per pattern on why the new figure is more correct, and the vote panels that move.
- **TODOS.md**: the entry "Check that vote links are right" shrinks to what PR C2 and the follow-ups leave; the new Vorgang-level follow-up (section 8).

## 12. Clash with the name-tag speakers build

The plan on `claude/name-speakers-plan-fff320` bumps the speech rule ("9 → 10", written before 20/25 took 10, so 10 → 11 today) and the export format (20 → 21), and changes no schema. PR C bumps the export format and the schema, not the speech rule (section 7), so the only shared number is the export format.

**Land PR C first.** It is P1 and blocks the first release (N10); the name-tag build was waiting for the stage-direction rule, which has landed, but nothing else waits on it. The second PR re-picks the export format (22), and its replay must show `agenda_item_votes` unchanged at 676 rows and `votes.top_link_step` unchanged. If the name-tag build lands first, PR C re-picks the export format and rebases its parser change onto it. One overlap to check in that replay: wrapping a non-chair `<name>` turn outside any `<rede>` in a Rede could give a headingless section a Rede and switch off step 2 there. None of the 7 sections step 2 uses holds such a turn (all are chair-only), but the replay comparison is the proof, and PR C's unit test (a section that gains a Rede stops taking the vote) states the dependency.

## 13. Owner decisions

**Decided by the owner on 2026-11-21** ("Yes, accept both"), both as picked:

1. **Decided: the release gate checks every contested vote, not only votes still linked to two or more TOPs.** This amends owner decision 6 of 2026-11-14. A vote is contested when a step after the plain Drucksache match decided its TOP (narrowed, moved to its Einzelplan, or moved to the section where the chair called it), or when it is linked to two or more TOPs. Today 35 votes are contested, all reviewed; a budget week adds about 5 to 10 to review before its release.
2. **Decided: C2 is built right after C1, before the first `--publish`.** No entry needs it today, but without it the release gate has no remedy for a one-off wrong link in a new week except a rule change.

Everything else in this plan (the conditions, the file and its keys, the version bumps, the order against the name-tag build) is an engineering choice made here and open to the review below.

## Deviations in the build

C1 was built test-first in the order of section 9. The replay of the reference store (a `cp -cR` copy, `--offline --repersist` with this branch, against a copy replayed with main's code) gives the figures of section 1 exactly and equals `vote-pr-c/expected-links.tsv` link by link (676 rows, 0 added, 0 missing, 0 with another basis):

| | main | C1 |
| --- | --- | --- |
| Links | 710 | 676 |
| `drucksache_xml` / `drucksache_vorgang` / `title` | 180 / 510 / 20 | 149 / 485 / 17 |
| `einzelplan` / `drucksache_call` | – | 18 / 7 |
| Votes with no TOP | 70 | 60 |
| Votes linked to 2 or more TOPs | 17 (61 links) | 0 |
| TOPs with 2 or more votes | 107 (297 links) | 95 (264 links) |
| `votes.top_link_step` none / match / call / einzelplan / narrowed | – | 60 / 641 / 7 / 16 / 12 |
| Entries that no longer hold (store gate) | – | 0 of 428 |
| Contested votes / unreviewed (release condition) | – | 35 / 0 |

`compare_store_values.py` shows nothing else moving: Reden 61,559, Beiträge 45,928, Redeanteil, persons, `agenda_item_documents` (38,147), `vote_politikfelder` (1,264), vote totals, outcomes and Abweichler, and 0 of 1,944 Fakt values. One derived figure the plan did not list moves with the links: `vote_proceedings` 833 → 832, because a vote's Vorgänge are narrowed to those of its TOP. 318 and 319 (18/71) lose "Finanzplan des Bundes 2014 bis 2018", which only the umbrella TOP I (Fortsetzung) held; the Schlussabstimmung and the Entschließungsantrag were on the Haushaltsgesetz, so the new rows are more correct. 375 (18/141) gains "Finanzplan des Bundes 2015 bis 2019", which its new Einzelplan 12 section holds as a jointly debated Vorgang; that follows the existing narrowing rule (`politikfelder`), and whether a jointly debated Finanzplan should count as a vote's context is a question for that rule, not for PR C.

Deviations, each with its reason:

1. **Entries carry `evidence` and `reviewer`.** Item 15 asks the sheet to keep all five verdict columns on regeneration; with only `note` and `source` in the record, a regenerated sheet would lose the reviewers' evidence. `note` stays what the vote page shows for a C2 drop or flag.
2. **The loader refuses `drop` and `flag` until C2.** Accepting them while nothing applies them would let an acting entry sit silently without effect. The store gate, the oracle and the release gate check every entry kind already.
3. **`heading_starts` is at most 40 characters and has no trailing space.** The plan's own example holds 43 characters; a cut at 40 that ends in a space is trimmed, so a cleaned heading still starts with it.
4. **`scripts/reviewed_vote_links.json` is a codebook input.** DATA.md states the review's figures from it at export, and the release reads it as the export's commit holds it; as a codebook input its hash is in the manifest and `verify_export` already matches it against that commit. Generated from the entries: reviewed sample (408), right and wrong (356 / 52), the wrong ones per pattern, and the links the rule change added (20). Written as text in `docs/data-methods.md`, because the entries do not record them: the 64 links of the random stratum with the 4.6 % bound, and the 2 wrong links found outside the sample. The split "12 of the 20 outside the review's notes" is not stated, for the same reason.
5. **`docs/data-changelog.md` is not edited.** It describes the release changelog mechanism; no release exists yet, so there is no release changelog to carry old → new figures. They are in the table above and go into CHANGELOG.md at the ship.
6. **A replay does rewrite the cached JSON.** Section 6 and section 7 assumed it never does; `rebuild_cached_detail_pages` writes every re-read report back. After this replay the cached reports hold `called_drucksachen` and `vote_inputs_version`. `--fixture` still re-reads each sitting from its XML in memory, so it does not depend on a replay having run; the sheet reads no field the replay adds and is left as it was.
7. **`attribute_votes` writes a vote list only where it holds a vote or the report has the key.** Persist now attributes every report, and an attribution that added empty `votes` and `sitting_votes` keys rewrote reports a test proves must stay as they were (`test_registry_contracts`, "the cached source evidence is never rewritten").
8. **Item 4 carries every cached vote when the run fetched none.** A test that asserted the old loss (a re-parse that renamed the TOP lost both votes and the sitting's completeness) now asserts the votes are kept, placed by the rule, and the sitting stays complete.
9. **The release gate reads the exported CSVs**, not the export's SQLite: the CSVs are the rows `verify_export` checked against the manifest, and an in-memory database would need an opener outside `SQLITE_OPENERS`. Both build a `Sitting` through one function (`reviewed_vote_links.sittings_of_rows`), as the store gate does.
10. **Test fixtures that met the new steps.** `vote_interpretation_protocol.xml` has headingless, Rede-free sections whose chair text names the votes' Drucksachen, so step 2 moves vote 811 to TOP 10 alone; the test now expects one copy. The parity test of `test_derive` placed vote 4 (`20/0301`) as a sitting vote because numbers compared as strings; canonical numbers link it to the TOP holding `20/301`.
11. **The Einzelplan pattern has a word boundary in front** (`\bEinzelplan`), and the third-reading test strips leading non-word characters before matching instead of one pattern with overlapping `\W*` and `\s*` (class 8). Neither changes a link on the store.
