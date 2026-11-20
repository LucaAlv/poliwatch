# Vote-link review (N10): the sheet and how to read it

The sheet is [`vote-links-review.tsv`](vote-links-review.tsv): 399 links of the 701 on the 801-sitting reference store, in 195 units, written on 2026-11-20. The verdict columns are empty; the review fills them. Plan: [`vote-links-and-figures.md`](vote-links-and-figures.md), "The review", and [`t4-acquire.md`](t4-acquire.md), step 4. Once the review has run, its counts (right, fixed, flagged) go at the end of this file.

## Reviewer's notes

Read these before the first row.

- **What "right" means.** The roll call was taken on a Vorlage this TOP dealt with (the Vorlage, its Beschlussempfehlung, or an Änderungs- or Entschließungsantrag to it). Where the protocol splits a debate into sub-items, only the most specific one is right: the Einzelplan TOP for a vote on an Einzelplan, the third-reading TOP for a Schlussabstimmung. A link need not say that the vote alone settled the TOP.
- **`tally`** says how often the vote's exact Ja/Nein tally occurs in the sitting's protocol text.
  - `unique` (379 rows): once, not counting the table "Endgültiges Ergebnis" the protocol prints right after the chair's announcement. `announced` then lists the Drucksache numbers in the 800 characters before the tally, the chair's announcement. 178 of these rows still show `-`, because no number stands there.
  - `several` (9 rows): the sheet cannot tell whose announcement a match is, so `announced` is always `-`. This says nothing against the link. All 9 are votes that ended with the same tally as another vote of their sitting: 270 and 274 (18/37), 303 and 306 (18/61), 1026, 1027 and 1028 (21/99), 1029 and 1030 (21/99). Search the protocol for the tally ("Mit Ja haben gestimmt N") and tell the announcements apart by the Vorlage they name.
  - `none` (11 rows): the text holds no match for the tally. Find the vote by its title or Drucksache.
- **`shared`** lists the vote's Drucksachen that the TOP holds, separated by commas. An entry has one of two formats, told apart by the number of fields:
  - three fields, `number:type:Vorgang id`: DIP links the Drucksache to a Vorgang of this TOP. Example: `19/4949:Gesetzentwurf:239426`. One special case: `number:xml:-` (29 entries) has `xml` in the type slot and means only the protocol prints the number under the TOP; DIP links it to no Vorgang there.
  - four fields, `number:type:Vorgang id:xml` (175 entries): both. DIP links it, and the protocol prints it under the TOP.
  - `-` means the TOP holds none of the vote's Drucksachen, which is the case for all 20 title links and for no other row. `?` would mean the cached report could not be paired with the stored TOP; no row shows it.
- **`basis`** is the rule's own reason: `drucksache_xml` when a shared number is printed under the TOP, `drucksache_vorgang` when only DIP links it, `title` for the unique title match.
- **`batch`** is `t4` for the 70 rows from the 83 sittings T4 restored, else `-`. No restored row is `drucksache_xml`, because the WP 18 and 19 protocol files carry no linked Drucksachen (`t4-acquire.md`, "Outcome").
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

## Checks on the sheet's inputs (2026-11-20)

- **Cached reports against the store.** The sheet reads `shared` from the cached report JSON, which a replay does not rewrite. No row is affected: no row shows `?`; for all 514 linked TOPs the cached TOP has the store's heading and the store's Drucksache set; and the rule run on the 801 cached reports gives the store's 701 links with the same basis, with 0 placement errors.
- **Leading zeros.** The rule compares Drucksache numbers as strings, so "20/0301" and "20/301" would share nothing. Counted over every vote and every TOP of the 801 cached reports: 0 pairs differ only in form, and no number at all differs from its canonical form. Comparing canonical numbers would add or change no link today.

## What looks wrong at first sight

Not verdicts; places to look first.

- **19/68, votes 562, 563 and 564 (12 links).** Each links to TOPs 6, 8, 17 and 19. All four TOPs hold the Unterrichtung 19/5647 through their own Vorgang, and each vote lists it. 562 (Mietwohnungsneubau) belongs to TOP 6, 563 and 564 (Mietrechtsanpassung) to TOP 8; the other 9 links rest on 19/5647 alone. This looks like pattern A outside the Haushalt.
- **18/42, vote 280 (Mali, MINUSMA).** Linked to TOP III (MINUSMA) and TOP IV (UNIFIL). DIP's MINUSMA position is assigned to both TOPs; this looks like pattern C.
- **Announcement names other Drucksachen.** In 14 Drucksache rows with a unique tally, the announcement names numbers of which none is in `shared`: votes 299 and 300 (18/54, each shows the other's Entschließungsantrag), 367 (18/130), 376 (18/141), 445 (18/209), 494 (19/5), 558 (19/66), 642 (19/132), 676 (19/165), 691 (19/184), 784 (20/42), 886 (20/145), 928 (20/194) and 1024 (21/97). The 800 characters before a tally can also hold the previous vote's numbers or an Änderungsantrag the TOP does not list, so each needs reading.
- **Known from the pilot:** the ten Haushalt votes in S1 (pattern A) and vote 493 (pattern C).

## How to run the review

1. Regenerate only if the store changed, from the main checkout (a worktree needs the store's absolute path): `uv run --python 3.13 python scripts/vote_link_review.py --output-dir .context/dip-pulse-site --out docs/plans/vote-links-review.tsv --batch-protocols docs/plans/t4-acquire/restored-sittings.tsv`. It overwrites the file, so do this before any verdict is filled in.
2. First pass: an agent, or the owner, fills the five verdict columns for all 399 rows from `shared`, `announced` and the protocol section (`data/xml/` of the store), unit by unit. The cached DIP records are the second source. No online request.
3. Second pass, without the first one's verdicts: every `wrong` and `unsure` row and 20 random `right` rows.
4. The owner decides each disagreement, and whether any row still `unsure` gets an online look at the bundestag.de vote page (two requests per vote, with a stated count).
5. Add the counts here: right, wrong by pattern, one-off drops, flags, and S4's error count. PR C starts from them.
