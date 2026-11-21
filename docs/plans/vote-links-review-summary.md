# Vote-link review (N10): the sheet and how to read it

The sheet is [`vote-links-review.tsv`](vote-links-review.tsv): 408 links of the 710 on the 806-sitting reference store, in 201 units. It was written on 2026-11-20 on the 801-sitting store (399 links of 701, 195 units) and regenerated on 2026-11-21, after 18/62, 18/90 and 21/107 to 21/109 entered the store: the 399 rows are unchanged and 9 were added ("The sittings added after the sheet was written"). The verdict columns are empty; the review fills them. Plan: [`vote-links-and-figures.md`](vote-links-and-figures.md), "The review", and [`t4-acquire.md`](t4-acquire.md), step 4. Once the review has run, its counts (right, fixed, flagged) go at the end of this file.

## Reviewer's notes

Read these before the first row.

- **What "right" means.** The roll call was taken on a Vorlage this TOP dealt with (the Vorlage, its Beschlussempfehlung, or an Änderungs- or Entschließungsantrag to it). Where the protocol splits a debate into sub-items, only the most specific one is right: the Einzelplan TOP for a vote on an Einzelplan, the third-reading TOP for a Schlussabstimmung. A link need not say that the vote alone settled the TOP.
- **`tally`** says how often the vote's exact Ja/Nein tally occurs in the sitting's protocol text.
  - `unique` (388 rows; the counts in this bullet are those of the 379 rows on the 801-sitting store, and the 9 rows added later are all `unique` with numbers in `announced`): one place in the text carries the tally. In 173 rows that is the chair's announcement; the table "Endgültiges Ergebnis" printed right after it repeats the tally and is not counted again. In 206 rows only that table matches, because the chair worded the result differently or read out a count that differs from the final one. `announced` lists the Drucksache numbers in the 800 characters before the match. That is nearby text, usually the chair's announcement, and it can also hold the previous vote's numbers. 178 of these rows show `-`, because no number stands there.
  - `several` (9 rows): the sheet cannot tell whose announcement a match is, so `announced` is always `-`. This says nothing against the link. All 9 are votes that ended with the same tally as another vote of their sitting: 270 and 274 (18/37), 303 and 306 (18/61), 1026, 1027 and 1028 (21/99), 1029 and 1030 (21/99). Search the protocol for the tally ("Mit Ja haben gestimmt N") and tell the announcements apart by the Vorlage they name.
  - `none` (11 rows): the text holds no match for the tally. Find the vote by its title or Drucksache.
- **`shared`** lists the vote's Drucksachen that the TOP holds, separated by commas. An entry has one of two formats, told apart by the number of fields:
  - three fields, `number:type:Vorgang id`: DIP links the Drucksache to a Vorgang of this TOP. Example: `19/4949:Gesetzentwurf:239426`. One special case: `number:xml:-` (31 entries) has `xml` in the type slot and means only the protocol prints the number under the TOP; DIP links it to no Vorgang there.
  - four fields, `number:type:Vorgang id:xml` (186 entries): both. DIP links it, and the protocol prints it under the TOP.
  - `-` means the TOP holds none of the vote's Drucksachen, which is the case for all 20 title links and for no other row. `?` would mean the cached report could not be paired with the stored TOP; no row shows it.
- **`basis`** is the rule's own reason: `drucksache_xml` when a shared number is printed under the TOP, `drucksache_vorgang` when only DIP links it, `title` for the unique title match.
- **`batch`** is `t4` for the 70 rows from the 83 sittings T4 restored, `nov21` for the 9 rows from the sittings fetched on 2026-11-20 and 2026-11-21, else `-`. No restored row is `drucksache_xml`, because the WP 18 and 19 protocol files carry no linked Drucksachen (`t4-acquire.md`, "Outcome").
- **`top_heading`** is cut at 120 characters. A TOP that the protocol prints as several items under one number can hold the matching item past the cut: vote 251 in 18/11 (Maislinie 1507) is linked by title to a TOP whose visible heading is about the Umverteilungsprämiengesetz. Read the full heading in the dossier or the XML before calling such a row wrong.
- **`other_tops`** lists the vote's other linked TOPs as `top_id#occurrence`. For an S1 vote, judge all its rows together: usually one is right.
- **Fill in** `verdict` (`right`, `wrong`, `unsure`), `pattern` (`A` umbrella Drucksache, `B` one Beschlussempfehlung or Vorgang for several Vorlagen, `C` a DIP position on the neighbouring TOP, a new letter, or `-` for a one-off), `action` (`none`, `rule`, `drop`, `flag`), `evidence` (source and place, one line) and `reviewer`.

## The sample, before and after T4

| Stratum | 718 sittings (plan) | 801 sittings | of them `batch = t4` |
| --- | --- | --- | --- |
| S1: votes linked to more than one TOP | 13 votes, 47 links | 17 votes, 61 links | 4 votes, 14 links |
| S2: TOPs with more than one vote | 84 TOPs, 238 links | 105 TOPs, 292 links | 21 TOPs, 54 links |
| S3: title links | 15 | 20 | 5 |
| S4: random plain links | 50 (34 Vorgang-only, 16 printed) | 60 (44, 16) | 10 (all Vorgang-only) |
| Rows (a link in two strata counts once) | 329 | 399 | 70 |
| Units | 155 | 195 | 40 |
| Rows with `tally = several` | 9 | 9 | 0 |

- New in S1: vote 280 in 18/42 (2 TOPs) and votes 562, 563 and 564 in 19/68 (4 TOPs each).
- New in S3: votes 251 (18/11), 279 (18/42), 388 (18/158), 390 (18/161) and 732 (19/227).
- 27 links are in both S1 and S2 (14 before T4); 7 title links are also in S2 (all before T4).
- S4: the generator ran with `--batch-protocols docs/plans/t4-acquire/restored-sittings.tsv`, which keeps the restored sittings out of the first draw. With seed 20261114 that draw picks from the same 212 Vorgang-only and 99 printed plain links as on the 718-sitting store, so the 50 are the ones the plan sized. A second draw takes 10 of the restored sittings' 51 plain links (16% is 9, the minimum is 10).

## The sittings added after the sheet was written

Five sittings entered the store after 2026-11-20: 18/62 and 18/90 (the Fragestunde rule, ADR 0004 "Amendment 2026-11-20") and 21/107 to 21/109 (the online update of 2026-11-21). They are listed in [`vote-links-review-later-sittings.tsv`](vote-links-review-later-sittings.tsv) and carry `batch = nov21`. 18/62, 18/90 and 21/107 have no roll-call vote. 21/108 has 5 votes and 21/109 has 4, each linked to one TOP: 9 links, all in the sheet.

| Stratum | 801 sittings | 806 sittings | of them `batch = nov21` |
| --- | --- | --- | --- |
| S1: votes linked to more than one TOP | 17 votes, 61 links | 17 votes, 61 links | 0 |
| S2: TOPs with more than one vote | 105 TOPs, 292 links | 107 TOPs, 297 links | 2 TOPs, 5 links |
| S3: title links | 20 | 20 | 0 |
| S4: random plain links | 60 (44 Vorgang-only, 16 printed) | 64 (44, 20) | 4 (all printed) |
| Rows | 399 | 408 | 9 |
| Units | 195 | 201 | 6 |

- S2: 21/108 TOP 5 (votes 1038 and 1039, Startchancengesetz and the Entschließungsantrag to it) and 21/109 TOP 26 (votes 1043, 1044 and 1045, two Änderungsanträge and the Gesetzentwurf on the Nachrichtendienstrecht).
- S4: votes 1040, 1041 and 1042 (21/108) and 1046 (21/109). The batch holds 4 plain links, fewer than the minimum of 10, so its draw takes all of them.
- The generator keeps this batch out of the earlier draws like the `t4` batch, so the 60 S4 rows of the 801 sittings are the ones drawn before.
- To look at first: vote 1046 (21/109, Sea Guardian). The text before its tally names 21/9077, and `shared` holds 21/8819 and 21/9152, both printed under the TOP only. It is the fifteenth row under "Announcement names other Drucksachen" below.

## Checks on the sheet's inputs (2026-11-20)

- **Cached reports against the store.** The sheet reads `shared` from the cached report JSON, which a replay does not rewrite. No row is affected: no row shows `?`; for all 514 linked TOPs the cached TOP has the store's heading and the store's Drucksache set; and the rule run on the 801 cached reports gives the store's 701 links with the same basis, with 0 placement errors.
- **Leading zeros.** The rule compares Drucksache numbers as strings, so "20/0301" and "20/301" would share nothing. Counted over every vote and every TOP of the 801 cached reports: 0 pairs differ only in form, and no number at all differs from its canonical form. Comparing canonical numbers would add or change no link today.

## What looks wrong at first sight

Not verdicts; places to look first.

- **19/68, votes 562, 563 and 564 (12 links).** Each links to TOPs 6, 8, 17 and 19. All four TOPs hold the Unterrichtung 19/5647 through their own Vorgang, and each vote lists it. 562 (Mietwohnungsneubau) belongs to TOP 6, 563 and 564 (Mietrechtsanpassung) to TOP 8; the other 9 links rest on 19/5647 alone. This looks like pattern A outside the Haushalt.
- **18/42, vote 280 (Mali, MINUSMA).** Linked to TOP III (MINUSMA) and TOP IV (UNIFIL). DIP's MINUSMA position is assigned to both TOPs; this looks like pattern C.
- **Announcement names other Drucksachen.** In 15 Drucksache rows with a unique tally (14 on the 801-sitting store), the announcement names numbers of which none is in `shared`: votes 299 and 300 (18/54, each shows the other's Entschließungsantrag), 367 (18/130), 376 (18/141), 445 (18/209), 494 (19/5), 558 (19/66), 642 (19/132), 676 (19/165), 691 (19/184), 784 (20/42), 886 (20/145), 928 (20/194), 1024 (21/97) and, with the `nov21` batch, 1046 (21/109). The 800 characters before a tally can also hold the previous vote's numbers or an Änderungsantrag the TOP does not list, so each needs reading.
- **Known from the pilot:** the ten Haushalt votes in S1 (pattern A) and vote 493 (pattern C).

## How to run the review

1. Regenerate only if the store changed, from the main checkout (a worktree needs the store's absolute path): `uv run --python 3.13 python scripts/vote_link_review.py --output-dir .context/dip-pulse-site --out docs/plans/vote-links-review.tsv --batch-protocols docs/plans/t4-acquire/restored-sittings.tsv --batch-name t4 --batch-protocols docs/plans/vote-links-review-later-sittings.tsv --batch-name nov21`. Sittings fetched later still go into a further list with its own name, after these two, so that no earlier draw changes. It overwrites the file, so do this before any verdict is filled in.
2. First pass: an agent, or the owner, fills the five verdict columns for all 408 rows from `shared`, `announced` and the protocol section (`data/xml/` of the store), unit by unit. The cached DIP records are the second source. No online request.
3. Second pass, without the first one's verdicts: every `wrong` and `unsure` row and 20 random `right` rows.
4. The owner decides each disagreement, and whether any row still `unsure` gets an online look at the bundestag.de vote page (two requests per vote, with a stated count).
5. Add the counts here: right, wrong by pattern, one-off drops, flags, and S4's error count. PR C starts from them.

## Outcome of passes 1 and 2 (2026-11-21)

Pass 1 filled the five verdict columns for all 408 rows of the sheet. Pass 2 re-judged every row pass 1 called wrong and 20 random right rows; its verdicts stand beside pass 1's in [`vote-links-review-pass2.tsv`](vote-links-review-pass2.tsv). Both passes ran offline on the 806-sitting reference store. The readers were Sonnet agents, each given a dossier per review unit (an S1 vote with all its links, an S2 TOP with all its votes, or a single S3 or S4 row). A dossier held the vote page fields from the cached report, every TOP of the sitting with its printed Drucksachen and DIP positions, the chair's procedural passages from the protocol XML, the tally announcement and where it stands, and the DIP Vorgänge of the vote's Drucksachen. Readers could grep the protocol XML where a passage was cut. Pass 1 used 36 batches of 4 to 23 rows. Pass 2 used 10 fresh batches in a different grouping, and its readers never saw pass 1's verdicts. A row's verdict is judged by where the chair called and took the roll call and on which Vorlage. Where the result was announced does not count: in most sittings that is a later TOP.

### Counts (the sheet's verdicts: pass 1, with the owner's two decisions below)

| | Rows |
| --- | --- |
| right | 356 |
| wrong, pattern A (umbrella Drucksache) | 43 |
| wrong, pattern B (one Vorgang bundling several Vorlagen) | 2 |
| wrong, pattern C (DIP position on the neighbouring TOP) | 2 |
| wrong, pattern D (vote taken in a separate Zusatzpunkt section) | 5 |
| one-off wrong links (action `drop`) | 0 |
| flagged / unsure | 0 / 0 |

Every wrong row has a cause shared by at least two links, so every action is `rule`; no row is a one-off drop. By stratum: S1 44 of 61 wrong, S2 27 of 297, S3 1 of 20, S4 0 of 64. Pass 1 had 54 wrong rows (S2 29, S3 3); the owner's decision on votes 703 and 704 made two of them right. By batch: `t4` 10 of 70 wrong, `nov21` 0 of 9.

**S4, the random stratum: 0 errors in 64 plain links** (44 Vorgang-only, 20 printed). This is the estimate for the plain links nobody reviewed: at 95% confidence their error rate is below 4.6% (exact binomial bound; the rule of three gives 3/64). Every error the review found sits in a vote linked to several TOPs, in a TOP with several votes, or in a title link.

Pass 2 agreed with pass 1 on 116 of 119 rows it judged: all 20 random right rows, 45 context rows (other rows of the same units) and 51 of the 54 wrong rows. The three exceptions are listed below. Pass 2's verdicts are not merged into the sheet; the three disagreements were decided as below.

### Patterns and what they suggest for PR C

- **A. Umbrella Drucksache: 43 links, 16 votes.** In the Haushalt, these are votes 317 (18/69), 318 and 319 (18/71), 375 (18/141), 557 (19/66), 781 (20/42), 894 (20/150), 897 and 898 (20/152), 960 (21/24), 961 (21/25), 979 (21/43) and 980 (21/45). The Haushaltsgesetz Drucksachen are printed under, or linked through DIP to, the second-reading TOP and every Einzelplan TOP. So an Einzelplan vote reaches the other Einzelplan TOPs, and a Schlussabstimmung, or an Entschließungsantrag zur dritten Beratung, reaches the second-reading and Einzelplan TOPs. Outside the Haushalt, votes 562, 563 and 564 (19/68) reach TOPs 6, 8, 17 and 19 through the Unterrichtung 19/5647, which all four TOPs hold. 28 of the 43 links rest on a printed Drucksache, 14 on DIP alone and 1 on the title. **Rule change:** when a vote's Drucksachen reach several TOPs, keep the TOPs holding a vote Drucksache that no other reached TOP holds. For Haushalt votes, match the Einzelplan number in the vote title against the Einzelplan TOP. Put a Schlussabstimmung, and an Entschließungsantrag zur dritten Beratung, on the third-reading TOP. Put an Änderungsantrag to Einzelplan X on Einzelplan X. Three of these votes lack their right link today and need it added, not only the wrong one dropped: 317 (the Einzelplan 04 section, the second occurrence of "Tagesordnungspunkt I (Fortsetzung)"), 375 (Einzelplan 12) and 557 (Einzelplan 60). Vote 317 is a title link: its title begins with the Haushaltsgesetz title and is cut before the Einzelplan number, so `title_matches` picks the general second-reading section. The fix must therefore also cover the title path, and an Einzelplan-number match must read the vote's description, the only field that carries the number.
- **B. One Vorgang bundling several Vorlagen: 2 links, 2 votes:** 608 and 609 (19/105), both to Zusatzpunkt 12. Zusatzpunkt 12 holds DIP's positions "Geschäftsordnungsantrag auf Absetzung von der TO", whose `mitberaten` list names about thirteen Vorgänge of the day's migration package. The rule's `mitberaten` closure then gives ZP 12 the Drucksachen of the Fachkräfteeinwanderungsgesetz (ZP 15) and of the Asylbewerberleistungsgesetz (ZP 18). Both votes also link to their right TOP. The pilot's doubt about ZP 15 came from the heading cut at 120 characters: ZP 15 a is the government's Fachkräfteeinwanderungsgesetz itself. **Rule change:** do not follow `mitberaten` from Geschäftsordnungsantrag positions.
- **C. DIP position on the neighbouring TOP: 2 links, 2 votes:** 280 (18/42, MINUSMA, to TOP IV, the UNIFIL item) and 493 (19/5, UNAMID, to TOP 13, the UNMISS item). Two adjacent Bundeswehr mandates with near-identical titles. The second TOP prints none of the vote's Drucksachen and holds the Vorgang only through `position_matches_top`. Both votes also link to their right TOP. **Rule change:** in `position_matches_top`, refuse a title match when the TOP prints Drucksachen and none of them belongs to the position's Vorgang. This is review checklist class 7. The fix also moves `agenda_item_documents`.
- **D. Vote taken in a separate Zusatzpunkt section: 5 links, 5 votes:** 476 and 477 (18/237, to TOP 47 occurrence 2; right are Zusatzpunkt 10 and 11), 480 (18/239, to TOP 4; right is Zusatzpunkt 3), 579 (19/83, to Zusatzpunkt 9; right is Zusatzpunkt 10) and 588 (19/87, to TOP 25; right is Zusatzpunkt 14). The protocol prints the Zusatzpunkt's heading and Drucksache inside the heading of the TOP it was debated with. The XML then opens a separate, headingless section with that Zusatzpunkt's `top-id`, and the chair calls the roll call there. That section holds no Drucksache and no DIP position, so the rule cannot reach it. None of the five votes links to its right TOP today. **Rule change, upstream of the vote rule:** when a heading lists "ZP n" and the sitting has a section with `top-id` "Zusatzpunkt n", attribute ZP n's printed Drucksachen (and DIP positions matched by them) to that section.
- **E (withdrawn).** Pass 1 had marked votes 703 and 704 (19/197) wrong because TOP II and Zusatzpunkt 1 have no section of their own. The owner's decision below keeps both links as right, so pattern E has no rows.

### Where the passes disagree

| Vote | Sitting | Row (TOP) | Pass 1 | Pass 2 |
| --- | --- | --- | --- | --- |
| 703 | 19/197 | Einzelplan 8 | wrong, E | right |
| 704 | 19/197 | Einzelplan 8 | wrong, E | right |
| 317 | 18/69 | Tagesordnungspunkt I (Fortsetzung), occurrence 1 | wrong, A | wrong, F (a title match picks the general section over the Einzelplan section) |

**Decided (owner's go, 2026-11-21, after a third reader, a Sonnet agent who saw both readings and the sources but no recommendation, agreed with the recommendation):**
1. Votes 703 and 704 are **right**. The "Einzelplan 8" section is where the chair calls up TOP I.4, TOP II and Zusatzpunkt 1 together, and it is the only section printing their Drucksachen 19/22887, 19/24940 and 19/24969. The headingless section the XML files under Einzelplan 20 continues that joint item. Vote 704 was taken after the Einzelplan 09 debate only because the chair deferred it. Moving either vote to Einzelplan 20 or 9 would put it on another Vorlage's TOP. No rule change.
2. Vote 317 stays **wrong, pattern A**. The cause is the umbrella Haushalt section, reached here by the title rather than by a Drucksache; see A above.

The sheet carries these two decisions; every other row carries pass 1's verdict. The pass 2 file keeps both passes as they were.

### No online look needed

No row is unsure after two passes, so no bundestag.de vote page needs fetching (0 requests). The two disagreements on 703 and 704 are about the protocol's structure, which the vote page does not show.
