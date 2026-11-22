# Changelog

All notable changes to this project will be documented in this file.

## [0.46.47.0] - 2026-11-22

Speakers the protocol prints with a speaker marker directly in an agenda item, outside any Rede, are now counted. Before, these 74 markers in 31 sittings (19,686 words) were read by nothing, among them 23 whole WP 18 Reden. Reden go from 61,637 to 61,660 (all WP 18, 18,383 words), Beiträge from 45,991 to 45,999, and existing Reden gain 533 words. Fact values move in 27 of 1,944 (period, metric) pairs, and the week 2017-W20 loses its longest-Rede fact. A store built before this version owes one `--offline --repersist`; the speech rule goes from 11 to 12, the export format stays at 22.

### Changed

- **Reden the protocol prints without a Rede around them count.** Jan Korte's Rede in 18/7, Golze's, Bär's and Brantner's in 18/6 and 19 more WP 18 Reden are stored for their speakers (Die Linke +10, CDU/CSU +6, SPD +3, BÜNDNIS 90/DIE GRÜNEN +3, Bundesregierung +1). Each gets the id `M` plus its marker's position in the sitting, for example `M159` in 18/7. Seven of them are oral Erklärungen nach § 31; whether such a statement is a Rede at all is still open.
- **Short turns next to a Rede join it.** A speaker's first sentence before the chair interrupts, or the last words after it, now count in that speaker's Rede. Two Zwischenfragen (18/10, 18/83) and six Befragung questions and answers (19/114, 19/201) count as the Beiträge they are. Bartels' acceptance of his election (18/76) and two ministers' thanks after their oath are procedural steps; Oppermann chairing under a speaker marker (19/14) and three replies to the chair are stored nowhere.
- **A speaker marker outside any Rede is never counted unread.** Each of the 74 is listed by sitting, position and speaker in the reviewed list; a marker the list does not name stops the sitting, and the build says to add an entry. None of the 806 held sittings has one.
- The data notes replace the old estimate of these words ("about 1,750") with the rule; ADR 0004's amendment and the source error E14 describe it.

### Fixed

- **The architecture diagram says the site keeps only sessionStorage.** The Browser node still read "localStorage only" after v0.46.39.0.

## [0.46.44.0] - 2026-11-22

The research on the open legal questions of ADR 0003 and a draft packet for the Cyber Law Clinic of Universität Hamburg are in the repository. Documentation only: no stored value, export, page or figure changes.

### Added

- **A research note on the open licence and data-protection questions.** `docs/research/adr-0003-legal-questions-2026-11.md` works through ADR 0003's questions 1–4 and 6–8 from statutes, the DIP terms, official guidance and court decisions, with an independent second read. It is research, not legal advice. Where the repository changed after it was written, an *Update 2026-11-22* line says what is now true.
- **A draft packet for the Cyber Law Clinic (question 4), in German.** `docs/legal/clinic-2026-11/` holds a cover letter with the proposed legal bases (Art. 6 Abs. 1 lit. f, Art. 9 Abs. 2 lit. e, Art. 85 DSGVO with § 23 MStV), a record of processing (Art. 30), a DPIA threshold note (Art. 35) and an erasure and objection process. The owner sends it after settling every `OFFEN:` line; no contact address is in the repository.
- **What the packet found.** A withheld Rede keeps its words in `withheld_units.text` and `withheld_turns.text`, which the export ships, so today an erasure request cannot be met. A text-free kind of withholding, which also covers text moved into a neighbouring Rede, has to be built before the process is offered as existing.

## [0.46.43.0] - 2026-11-22

The comparison with CPP-BT in the data notes is restated on the reference store replayed with v0.46.42.0. No stored value or export changes; only documented figures move.

### Changed

- **The CPP-BT figures match the current store.** 81,446 Rede-IDs are on both sides (was 81,444) and 2,313 only in CPP-BT (was 2,315), because the two Reden released in v0.46.42.0 are no longer withheld (withheld 95 → 93). Split Reden (`ID…:N`) in `speeches` go from 65 to 131 rows, `nested:` ids from 4,000 to 4,056, Fragestunde rows from 19,893 to 19,899, surnames compared from 81,438 to 81,440 and Fraktionen from 71,346 to 71,348. The Redner-ID agreement now reads 81,372 of 81,430, 58 differing; it is counted over shared ids without `:N` with an id on both sides, which gives 81,428 rather than the 81,429 counted by hand on the store before.
- **The record of the speaker rule's effect is exact.** ADR 0004 now says that stored rows change in 48 sittings, as planned, and that the 50 it counted before includes 18/4 and 18/223, where only an oath answer's diagnostic changes.

## [0.46.42.0] - 2026-11-22

Speeches and questions that the WP 18 and 19 protocols print in the chair's element, although someone else speaks, are now stored for the person who spoke. Before, these 170 turns in 51 sittings (80,381 words) were read as chair text and counted nowhere. Reden go from 61,555 to 61,637 (WP 18 +80 with 73,265 words, WP 19 +2), Beiträge from 45,928 to 45,991, and withheld Reden from 102 to 100. Fact values move in 330 of 1,944 (period, metric) pairs, and 2 more weeks become publishable (211 → 213). A store built before this version owes one `--offline --repersist`; the speech rule goes from 10 to 11 and the export format from 21 to 22.

### Changed

- **A speaker the protocol prints like the chair is counted as who they are.** Sylvia Pantel's, Gülistan Yüksel's and Alois Rainer's first Reden in 18/30, Alexander S. Neu's Rede in 18/10, Johanna Wanka's Befragung reports and answers, and 160 more turns now count as the Reden, Zwischenfragen, Befragung questions and answers or Fragestunde questions they are. Each one is listed by person and kind in the reviewed list (145 entries). Oath answers stay procedural steps, Wolf Biermann's address at the 18/64 Gedenkstunde is stored as an Ansprache with no Redner-ID, and Dietmar Bartsch's remark in 18/181 is stored nowhere.
- **Two Reden are no longer withheld.** 18/6 `ID1800602300` and 18/36 `ID1803601400` were held back because a turn inside them was lost; they now count (3,054 words). 18/104 `ID1810402200`, stored before as an empty Rede with no speaker, now holds Christian Kühn's Rede.
- **Ids that move.** Converting a tag into a speaker marker shifts the marker numbers after it, which renames 6 nested Beiträge and the withheld unit `ID1802902700:2`, now `ID1802902700:2:2:2`. A Rede printed outside any `<rede>` gets the id `N` plus its tag's position in the sitting, for example `N39` in 18/10.
- **A speaker printed this way that the list does not name is never counted unread.** Inside a Rede it withholds that Rede with the new reason `unreviewed_name_speaker`; outside any Rede it stops the sitting, and the build and the fetch now say to add a reviewed-list entry instead of calling the XML corrupt. None of the 806 held sittings has one.
- Blankau-Rosenfeldt, whom the Bundestag gave no Redner-ID, is bound to her DIP person (1828). The method, ADR 0004's amendment and the source error (E13) describe the rule.

## [0.46.41.0] - 2026-11-22

A Fraktion's nomination for the Bundestagspräsident's election no longer counts as a Rede where the protocol prints it as the nominating MdB's own speech. Four nominations leave the Reden: Volker Kauder's in 18/1 and 19/1, Rolf Mützenich's in 20/1 and Friedrich Merz's in 21/1. Reden go from 61,559 to 61,555 (CDU/CSU −3, SPD −1) and speech characters drop by 474. A store built before this version owes one `--offline --repersist`, which re-reads these four sittings from their cached XML.

### Changed

- **A nomination in the Präsident's election is a procedural step, not a Rede.** "Die CDU/CSU-Bundestagsfraktion schlägt Herrn Dr. Wolfgang Schäuble vor." is a motion in the election, like the acceptance that follows it. The four are listed in `scripts/reviewed_units.json` as `procedural`: no row in `speeches`, `contributions` or `withheld_units`, one diagnostic in the sitting report.
- **What moves.** Each of the four sittings has one Rede fewer (18/1 5 → 4, 19/1 7 → 6, 20/1 8 → 7, 21/1 12 → 11), and each nomination's agenda item now shows "Keine Reden: Was das Protokoll hier als Rede druckt, sind Verfahrensschritte (Wahlvorschlag, Annahme einer Wahl, Eid, Sitzungsleitung) …". On their person pages Kauder loses two Reden (57 → 55, the nominations in 18/1 and 19/1), Mützenich (61 → 60) and Merz (63 → 62) one each. Kauder's first stored Rede is now his 18/2 Rede of 2013-11-18. The Fakt "meistdiskutierter Vorgang" has no value for 2017-10 and 2025-03, whose most discussed Vorgang was the election with the nomination as its one Rede. In later months 29 percentiles move and 6 more months change only their comparison window; no published flag, rank or winner changes.
- The Methodik and Quellen pages, the sitting page's no-Reden lines and the data notes now name the nomination among the steps that are no Rede. The comparison with CPP-BT is restated from a run on the 806-sitting store: 81,444 shared Rede-IDs, 2,315 that only CPP-BT lists, with the four nominations explained.

## [0.46.40.0] - 2026-11-22

A reviewed vote link can now be removed or marked as unsure one case at a time, and the vote's panel on its sitting page says so. The shipped review list has no such case yet, so no stored figure, vote link or export row changes.

### Added

- **A single wrong vote link can be removed, and an unsure one marked, by a dated review entry.** An entry with `action: drop` in `scripts/reviewed_vote_links.json` takes the vote off that agenda item: a vote left with no agenda item becomes a sitting vote with `top_link_step = none`, and leaves the bill page of that item's Vorgang. An entry with `action: flag` keeps the link and stores its note in `agenda_item_votes.review_note`. Each applied entry is kept in `vote_link_reviews` with its note and review date.
- **The vote's panel on the sitting page names each such review**: "Ein Abgleich verband diese Abstimmung (auch) mit TOP …; die Prüfung vom … ergab, dass sie nicht dazu gehört: …" for a removed link, "Die Zuordnung zu TOP … ist nicht sicher geprüft (Prüfung vom …): …" for a marked one.

### Changed

- **An entry that no longer fits its sitting stops the run** with the entry and the fix named: its vote or agenda item is gone, the item's heading or first page differs, or the link rule no longer makes the link. An online refresh whose vote list was skipped or could not be fetched checks the entries only once the cached votes are back.
- **The store check and the release check cover removed and marked links**: a removed link must be absent and recorded, a marked one present with the entry's note, both with the entry's note and review date, and a note or record no entry names is refused. A removed link on one of a vote's two agenda items leaves the other link under review.

## [0.46.39.0] - 2026-11-22

The owner's ten open decisions before the first data release are recorded, and three legal gaps the research on ADR 0003 found are closed. No stored figure, vote link or export row changes.

### Changed

- The dark-theme choice and the AI-summary collapse state are stored in `sessionStorage` instead of `localStorage`. They hold in the tab where the switch was used, not in a new tab, and end with it unless the browser restores the tab or the last session.
- **The Datenschutz page names its legal bases.** For the people in the data it gives Art. 6 Abs. 1 lit. f and Art. 9 Abs. 2 lit. e DSGVO and, for the published protocol text, Art. 85 DSGVO with § 23 MStV; it names the recipients, the permanent versioned archive and how an objection under Art. 21 is handled. The storage section names § 25 Abs. 2 Nr. 2 TDDDG.
- **The data notes say what the speech text leaves out.** `LICENSE-DATA.md` and the codebook entries for `speeches.text` and `contributions.text` now say they hold only the speaker's own words: applause, Zwischenrufe and chair remarks the protocol prints as their own element, and other speakers' turns, are not in them.
- The root `LICENSE` says that the Plenarprotokoll XML, roll-call pages and MdB-Stammdaten excerpt kept as test fixtures, and the protocol-derived data under `scripts/` and `docs/` are not under MIT and carry the Bundestag's source line and the DIP terms.

### For contributors

- The owner's decisions of 2026-11-21 are recorded in TODOS.md, ADR 0003, 0004 and 0005, `docs/release-review.md` and `docs/plans/v1-scope-review.md`: the e-mail on the roll-call and Stammdaten terms (sent, answer awaited), the name-tag speakers stored as Reden or Beiträge, nominations no longer counted as Reden (O13), ADR 0004 confirmed, the CPP-BT thresholds signed off, a 98% minimum coverage per analysis period, the trademark check, Zenodo set up, GitHub secret scanning on, and the legal questions answered by research with question 4 sent to a free law clinic.

## [0.46.38.0] - 2026-11-21

A namentliche Abstimmung is now linked to the Tagesordnungspunkt where it was actually called, not to every agenda item that shares one of its Drucksachen. 408 of the 710 links were checked one by one against the Plenarprotokoll and DIP, read by AI agents in two passes, with the owner deciding the three cases where the passes disagreed: 356 were right and 52 wrong, and all 52 come from four patterns that the link rule now handles. On the 806 stored sittings the links go from 710 to 676. All 52 wrong links are gone and all 356 right ones stay. A store built before this version owes one `--offline --repersist`, which re-reads every sitting from its cached XML.

### Changed

- **A vote is linked to the section where it was taken, in six steps.** Step 1 is the existing match: a shared Drucksache, printed under the agenda item or linked through DIP, or else a unique title. Then:
  - the section without heading and Rede in which the chair names the vote's Drucksache wins (`basis = drucksache_call`);
  - a vote on one Einzelplan goes to that Einzelplan's section (`einzelplan`);
  - an agenda item whose shared Drucksachen all sit inside another match's is dropped;
  - an item reached only through a DIP position that touches it on one page is dropped;
  - among the rest, the "Dritte Beratung" section is kept.
  
  A Geschäftsordnungsantrag no longer lends an agenda item the Drucksachen of the Vorlagen it only names, and Drucksache numbers compare without leading zeros, with Bundesrat numbers left out.
- **The figures that move** on the 806 stored sittings, each from the old value to the new one:
  - links (`agenda_item_votes`): from 710 to 676;
  - by basis: `drucksache_xml` from 180 to 149, `drucksache_vorgang` from 510 to 485, `title` from 20 to 17, plus the new `einzelplan` 18 and `drucksache_call` 7;
  - votes linked to two or more agenda items: from 17 (61 links) to 0;
  - votes linked to no agenda item went from 70 to 60;
  - agenda items with two or more votes: from 107 (297 links) to 95 (264 links);
  - `vote_proceedings`: from 833 to 832.
  
  Each new value is more correct, for these reasons:
  - The 34 links fewer are the wrong links of the review. A budget vote reached every Einzelplan through the Haushaltsgesetz (pattern A). A procedural motion lent its Drucksachen (B). A neighbouring Bundeswehr mandate shared a boundary page (C). A Zusatzpunkt called in a section of its own was linked to the debate it was taken with (D).
  - The links in the new categories, and the 10 votes that now have an agenda item, were each read in the protocol and checked right.
  - `vote_proceedings` follows the narrower links. Votes 318 and 319 (18/71) lose the Finanzplan they were not on, and vote 375 (18/141) gains the one its Einzelplan section debated.
  
  Nothing else moves: Reden, Beiträge, persons, vote totals, outcomes, Abweichler and every Fakt value are unchanged.
- **The vote panel moves with the link.** For example, votes 980 and 961 now show under TOP II instead of TOP I. The five Zusatzpunkt votes 476, 477, 480, 579 and 588 now show under their own Zusatzpunkt.

### Added

- **`votes.top_link_step` says which step decided a vote's agenda items** (`none`, `match`, `call`, `einzelplan`, `narrowed`). `agenda_item_votes.basis` takes the two new values. The store schema is 15 and the export format 21. The empty column `agenda_item_votes.review_note` and the empty table `vote_link_reviews` are reserved for the next step, in which single reviewed links are dropped or flagged on the vote page.
- **`scripts/reviewed_vote_links.json` records every reviewed link with its verdict.** It holds 428 entries: the 408 of the sample, 8 right links the review named, and 12 links the new rule made, each read. DATA.md states the review's figures from this file at export.
  - A test checks every entry against a frozen copy of the 156 reviewed sittings.
  - The store gate checks every entry against the store.
  - A data release (`--publish`) refuses any vote that a later step decided, or that is linked to two or more agenda items, unless each of its links has a matching `right` entry. It also refuses any link whose entry says `wrong`.
- **`scripts/vote_link_review.py --entries` merges a filled review sheet into that file**, refusing an empty or changed verdict. A regenerated sheet keeps the verdicts it already holds.

### Fixed

- **A rule change now reaches every stored report.** Every report, kept or fresh, is placed by the current rule right before it is stored. The offline render places every report it loads by the same rule. A sitting cached before the parser read the chair's Drucksache numbers is re-read from its XML.
- **A carried-forward sitting keeps all its cached votes.** This includes two agenda items with the same id.

## [0.46.37.0] - 2026-11-21

A stage direction the Plenarprotokoll prints in the chair's element no longer cuts a speech short. In sitting 20/25 the source prints "(Vizepräsident Wolfgang Kubicki räuspert sich)" as if the chair took the floor, and Lamya Kaddor's closing words after it were read as chair text and stored nowhere. They now count to her Rede. One figure moves: her Rede `ID202506700` goes from 783 to 835 words, 16 to 18 paragraphs and 5,317 to 5,661 characters. No other Rede, Beitrag or withheld Rede changes in any of the 806 sittings held, and the number of Reden stays the same everywhere (20/25: 115). The speech-counting rule goes from version 9 to 10, so a store built before this version owes one `--offline --repersist`; until then the facts, export and offline render refuse it.

### Fixed

- **A `<name>` element whose whole text is one pair of parentheses, with no parenthesis inside, is read as a stage direction, not a chair turn.** The speaker before it goes on. A chair label that holds a parenthesis, such as a constituency in "Norbert Müller (Potsdam) (DIE LINKE):", is read as before. The rule is an amendment to ADR 0004; the source fault is listed as E12 in `docs/source-errors.md`, and `docs/data-methods.md` describes it for readers of the data.

## [0.46.36.0] - 2026-11-21

The sheet for checking vote links by hand now covers the 806-sitting reference store, and the store refuses a few more ways a report could place a vote wrongly. No stored figure, vote link, page or export changes. Running the new checks on all 806 cached reports of the reference store refuses none of them.

### Added

- **The review sheet takes the sittings fetched since it was written.** 18/62, 18/90 and 21/107 to 21/109 entered the store on 2026-11-20 and 2026-11-21. Their 9 links join the sheet as batch `nov21`, so it now lists 408 of the 710 links in 201 review units. The 399 rows written before are unchanged, and the reviewer notes name vote 1046 (21/109) as one to read first.
- **`scripts/vote_link_review.py` takes several later batches.** `--batch-protocols` and `--batch-name` can be given more than once, one name per list. Each batch is drawn on its own, in the order given, so a batch added later changes no earlier draw. Two batches with one name, or one sitting in two batches, are refused.

### Changed

- **The store refuses a vote that sits both under an agenda item and among the sitting's unattached votes.** A reader of the unattached votes would have shown it twice.
- **A misplaced vote gives one error instead of two.** A vote the rule attaches to no agenda item, held under one anyway, used to be named twice, which could push a third fault out of the three errors shown.
- **A vote without an id in the DIP records is refused when the report is loaded, with the protocol number.** Before, the store refused it later, with an error that named no sitting.
- **The parser and the vote links read printed Drucksachen through one host check,** so they cannot disagree about which link counts as a Drucksache.

## [0.46.35.0] - 2026-11-20

The sheet for checking the links between roll-call votes and agenda items by hand is written for the 801-sitting reference store. It lists 399 of the 701 links in 195 review units, with notes for the reviewer beside it. No link, figure, page or export changes. The rule that makes the links is untouched, and the verdict columns of the sheet are still empty. On the 718 sittings held before the restored ones came back, the sheet picks the same 329 links the plan sized; the 83 restored sittings add 70.

### Added

- **The review sheet and its notes.** `docs/plans/vote-links-review.tsv` holds every vote linked to more than one agenda item (17 votes, 61 links), every agenda item with more than one vote (105 items, 292 links), all 20 links made by title, and 60 randomly drawn plain links. `docs/plans/vote-links-review-summary.md` explains each column, lists the rows that look wrong at first sight and says how to run the review.
- **Rows from the restored sittings are marked and sampled on their own.** `scripts/vote_link_review.py --batch-protocols` takes a list of sittings; their rows carry `t4` in a new `batch` column, and the random draw takes 10 of their 51 plain links after drawing the same 50 as before from the other sittings.

### Changed

- **The sheet settles the tally for 172 more rows.** A protocol prints the result table after the chair reads the result, so the same tally stood twice in the text and the sheet gave up on it. The table no longer counts as a second match: 379 rows now show one place for the tally (209 before), 9 show several and 11 none.
- **Two votes of one sitting with the same tally show no announcement.** The text cannot say which vote an announcement belongs to, so the sheet marks both as ambiguous instead of showing one vote's numbers on the other's row. This applies to 9 rows.

## [0.46.34.0] - 2026-11-20

The dataset's codebook now says how this dataset relates to four others and how to join it to one of them. DATA.md gains the section "Vergleich mit anderen Datensätzen und Verknüpfung": a table for this dataset, CPP-BT, GermaParl, ParlLawSpeech and BTVote, read from each project's own pages on 2026-11-20, and the rules for joining by the Bundestag's own Rede and Redner ids. A second document says what main and stable data releases are. No figure, page or stored value changes; this is text only.

### Added

- **A comparison table in DATA.md.** It gives version, coverage, unit, links, identifiers and licence for the five datasets, with the sources and the date read. A cell nobody could check says so: ParlLawSpeech's codebook was not read. The section states that the projects are independent and not affiliated.
- **Join rules for `rede_id` and `xml_redner_id`.** `rede_id` is the Bundestag's `<rede>` id, and CPP-BT carries the same ids. The section explains the forms that are not Bundestag ids (`ID…:N` for a part the parser split off, `nested:…` for a Zwischenfrage, `annex:…`, and the Fragestunde without an id), the ` (neu)` suffix on five CPP-BT protocol numbers, and why a person is better joined by Rede id and surname than by Redner-ID alone.
- **What CPP-BT lists as a Rede and this dataset does not.** Measured on the 801-sitting reference store against CPP-BT 2026-09-19: 81,354 ids are on both sides in the 789 shared sittings, none of ours is missing there, and 2,311 are only there. 2,092 of those are declarations under § 31 GO, which this dataset leaves out by rule; the rest are 121 procedural units, 95 withheld Reden, 2 reprints and one motion. The Redner-ID agrees on 81,280 of 81,338 shared ids.
- **`docs/release-policy.md`.** A main release is every published data release; a stable release is a main release the owner reviewed, marked by a `stable-<version>` tag and a review record. The document lists what a release fixes (a release never changes, every moved figure is recorded, ids keep their meaning, withheld Reden are listed) and holds the text that replaces the pre-release section of `CLAUDE.md` after the first release.
- **A template for the review record,** `docs/release-reviews/TEMPLATE.md`, with one part per step of the release review checklist.

### Changed

- **Step 5 of the release review checklist checks the new section:** the table when its date is older than six months or CPP-BT has a newer version, and the measured figures against the comparison's own output.
## [0.46.33.0] - 2026-11-20

The parser can now read sittings 18/62 and 18/90, the last two that waited for a parser rule. In both, Vizepräsidentin Petra Pau asks follow-up questions in the Fragestunde and the protocol prints her with her office, which no counting rule covers, so each sitting stopped at the role check. Her questions now count as questions of her Fraktion. No stored figure, page or export changes. Parsing all 801 cached sittings of the reference store with the old and the new parser gives identical output. The two sittings are not in the store yet; they still need one online run to acquire their agenda and document links.

### Added

- **A Vizepräsidentin or Vizepräsident printed with a Fraktion at a Fragestunde speaker line asks for that Fraktion.** The turn is stored as a `fragestunde_frage` without a Sprechrolle. This is Petra Pau's three follow-up questions in 18/62 and one in 18/90. A Präsident, an Alterspräsident and a presidium member printed without a Fraktion are still not read there, and such a sitting still stops.
- **The same line is Sitzungsleitung when that person presides.** If the last chair line before it names the same first and last name, the words are the chair's and are not stored. This is one line in 18/62, where the protocol prints a turn of Vizepräsident Johannes Singhammer as "Johannes Singhammer (CDU/CSU):" between two of his chair lines. It is listed as source error E11 in `docs/source-errors.md`.
- **Measured on the two sittings' XML, without any online request:** 18/62 gives 11 Reden and 160 Beiträge (Fragestunde: 65 questions and 65 answers, where the old reading gave 62 and 69), 18/90 gives 13 Reden and 120 Beiträge (40 and 38, before 39 and 39). Neither has a withheld Rede, and neither day has a roll-call vote.

## [0.46.32.0] - 2026-11-20

The store no longer records an unknown length as zero. When a Rede, a Beitrag, a withheld Rede or one of its turns reaches the store without its paragraph, character or word count, the sitting now stops with an error, and the store stays as it was. Before, the store wrote 0, which reads as a real empty text. No figure, page or export changes. The parser sets every one of these counts, and re-persisting all 801 sittings of the reference store with the old and the new rule gives the same rows: 61,284 Reden, 45,389 Beiträge, 102 withheld Reden and 170 of their turns. Every count column is equal by id, and 0 of 1,944 fact values moved.

### Fixed

- **A missing Rede, Beitrag or withheld count stops the sitting instead of being stored as 0.** This covers `paragraph_count` and `char_count` of a Rede, `char_count` of a Beitrag, `char_count`, `word_count` and `nested_word_count` of a withheld Rede, and `char_count` and `word_count` of its turns. A count of 0 that the parser really measured is still stored as 0.

## [0.46.31.0] - 2026-11-20

The source cited under a Fakt der Woche is now found by the id stored with the fact, so an agenda item or speech the protocol prints without a page number is cited like any other. Two notes that could print the word "None" now say what they mean. No published figure, page or export changes. On the 801-sitting reference store, 316 of 317 agenda-item citations resolved before and all 317 resolve now; every one that resolved before resolves to the same agenda item. The one that changes belongs to a fact held back below its floor (20/97, week 2023-W16), so no page shows it. All 1,555 speech citations resolve as before.

### Fixed

- **A fact citing an agenda item or speech without a printed page keeps its source.** The citation used to be looked up by page, and a page the protocol does not print never matched, so the card was left out with "Quelle nicht mehr auffindbar". It is now looked up by the cited row's own id, still checked against the sitting.
- **A gap note handed no count of withheld Reden says "Sitzung N: Reden zurückgehalten"** instead of "None Reden zurückgehalten". No build reaches this today: every withheld-Reden gap carries its count.
- **The vote panel's note on a re-filed member reads "dort Unbekannt"** instead of "dort None" when the linked Bundestag page gives that member no group.

## [0.46.30.0] - 2026-11-20

The parser now refuses two source shapes it used to read by guess, and it places Reden printed outside any agenda item by one rule. No figure, page or export changes. Parsing all 801 cached sittings of the reference store with the old and the new parser gives identical output, and neither refuses any of them.

### Fixed

- **A source Rede id containing a colon stops the sitting.** The parser names the parts of a split Rede "id:1", "id:2", so a source id already shaped like that could hide an unread Rede from the check that every Rede in the XML is accounted for. Such a sitting is now refused as a source error with its number in the message.
- **A Rede that two Inhaltsverzeichnis blocks list at different pages stops the sitting.** The later page used to win silently, so a Rede's page citation could depend on block order. Now the sitting is refused, and the message names both pages.
- **Reden printed outside any agenda item are grouped by their Inhaltsverzeichnis title.** In 18/44, 18/49 and 18/89 the source prints Reden directly in the Sitzungsverlauf. Consecutive Reden listed under one title now share one agenda item even when the title appears in two blocks, and an untitled block beside a titled one no longer counts as a second title and refuses the sitting.

## [0.46.29.0] - 2026-11-20

The check that stops two people printed under one Redner-ID from being filed as one person now catches cases it skipped, and a reviewed speaker is honoured wherever the build attaches an abgeordnetenwatch profile. No figure, page or export changes. On the 801-sitting reference store the check still compares 53 of 1,591 Redner-ID records and refuses none, and no stored speaker name is read differently.

### Fixed

- **A name printed as an office alone is compared with the other names under its Redner-ID.** "Bürgermeister" or "Senatorin" used to be skipped, so it could never show that a Redner-ID covers two people; the build now stops and asks for a review when such a name shares no word with the others.
- **More offices count as offices, not as names.** Vizekanzler(in), Staatsrat and Staatsrätin, and titles ending in -beauftragte(r) or -bevollmächtigte(r) ("Wehrbeauftragter", "Landesbevollmächtigte") no longer make two different people look like one because both hold the office. Bundeskanzler(in) stays a whole word, since Kanzler is a real surname.
- **An office-like surname still links a person's own spellings, but never two different people.** "Karl Bürgermeister" and "K. Bürgermeister" are one person; "Sieling Bürgermeister" and "Bovenschulte Bürgermeister", or "Karl Bürgermeister" and "Anna Bürgermeister", stop the build for review.
- **A reviewed speaker is found by the same Rede id the store uses.** When an abgeordnetenwatch profile is found under a Redner-ID two people share, the build looks up who spoke by the Rede id as stored (spaces tidied, or the generated id of a Rede printed without one), including in the list of an agenda item's first five speeches, so a profile the review gives to someone else is no longer attached.

## [0.46.28.0] - 2026-11-20

A build that is handed the wrong sitting's XML now refuses it as a source error every time, and an unknown `<fraktion>` spelling points to the spelling list instead of telling the operator to delete or re-fetch a good file. These are refusal paths and messages; no stored figure, page or export changes. Parsing all 801 cached sittings of the reference store with the old and the new agenda rule gives the same agenda items in every sitting.

### Fixed

- **An online build checks which sitting an XML belongs to before it parses it.** A file whose root names another Wahlperiode or Sitzung is refused as a rejected source naming both sittings, even where the parser would have stopped first on the reviewed list or the Rede reconciliation of the wrong sitting. A DIP record without a dokumentnummer is refused by name instead of with a half-empty sentence, and a body that is not well-formed XML is still a source refusal.
- **An unknown `<fraktion>` spelling names its fix,** online and on an offline replay: add the spelling to `derive._SPELLINGS` if it names a known Zusammenschluss, and record the source error in `docs/source-errors.md`. Before, a replay called the file corrupt and said to delete it and run `--fetch-xml`, and the replay's fix line said to re-fetch the sitting; both bring back the same XML.
- **The rule that moves annex Reden out of the Sitzungsverlauf removes only the agenda items it emptied.** An agenda item the protocol prints without content stays, as in 21/18, 21/28, 21/42, 21/45 and 21/93; only 18/158 triggers the rule, and its agenda is unchanged.

## [0.46.27.0] - 2026-11-20

The operator tools refuse bad input with a message instead of a traceback or a quietly wrong report, and the MdB-Stammdaten download can no longer be redirected off bundestag.de and has a total time limit. These are scripts run by hand around a build; no stored figure, page or export changes.

### Fixed

- **The MdB-Stammdaten download stays on bundestag.de and gives up after five minutes.** A redirect is followed only to `https://www.bundestag.de/`; plain http or another host is refused and the cached file kept. A body of declared length must arrive within five minutes, also when the server sends one byte per read just inside the 60-second socket timeout; a chunked body or a slow header phase can still run past the limit. A cached zip larger than the 32 MiB download cap is refused before it is read.
- **The store gate, the demo site builder and the abgeordnetenwatch match-share script stop at startup when `scripts/reviewed_units.json` is missing or malformed,** naming the file to repair, instead of failing halfway through a replay. A failed clone in the store gate ends with `ERROR [gate]` and exit 2 instead of a traceback.
- **The CPP-BT comparison refuses a known-differences file that would hide real differences.** An `only_theirs` row without a `rede_id` would have marked every Rede only CPP-BT holds as known; it is now refused. A known-differences file that is not UTF-8 and an export whose deflate stream is corrupt also stop with exit 2.
- **The store value comparison reports a missing side honestly.** Its vote groups section shows a store as unavailable when it lacks the vote figures as well as when it lacks the group counts, and a disk error while unpacking a recipe copy is no longer read as "no copy".
- **The abgeordnetenwatch match-share script measures what an online run would do.** The offline estimate counts only the Redner-IDs without an answer in the answers file. A store whose Mandat table holds no Wahlperiode 18 and 19 rows (built with a narrower `--roster-wahlperiode`) falls back to the MdB-Stammdaten zip, or stops when there is none, instead of moving every WP 18/19 MdB out of the first match tier. A hand-edited answers entry without the fields a rerun reuses is refused. Its cache files follow the umask instead of being world-readable.
- **An unreadable store now says how to rebuild it:** run `--offline --repersist`.

## [0.46.26.0] - 2026-11-20

The rule that links a roll-call vote to its agenda item now reads the Drucksachen printed under an agenda item the same way the store and the dossier do, and the store refuses a report that would silently lose a vote. No link, page or stored figure moves. Over the 801 cached reports of the reference store, 0 of 8,189 agenda items get a different set of printed Drucksachen and 0 reports fail the new check.

### Fixed

- **A number read off a quoted news-site link no longer counts as a Drucksache printed under an agenda item.** A report cached before the parser checked the link's host can still hold such a number. The vote-link rule and the vote-link review sheet now skip it, as persist and the dossier already did, so it can neither link a vote nor show in the sheet's shared column.
- **A report that would drop a vote is refused.** A fetched vote that belongs to no agenda item has to be listed among the sitting's other votes, because those two places are all the store keeps. A report that holds it in neither is now refused with the vote's id, instead of being stored without it. An `--offline --repersist` places the vote correctly.

### Changed

- **The title comparison behind the vote-link rule lives in the vote-link module.** It matches exactly the same titles as before. The vote linker no longer imports the protocol parser, which removes the last import cycle in `scripts/`.

## [0.46.25.0] - 2026-11-20

The week radar's RSS titles keep their words apart and drop characters that make a feed unreadable, the build warning about a refused site address no longer prints any part of a password, and an Antrag passage that the advance-copy watermark interrupts mid-line is quoted instead of refused. The Antrag extractor moves from version 9 to 10, so a store persisted with version 9 is refused until `--offline --repersist`; on the saved corpus of 112 Antrag texts no quote changes. DATA.md now names the MdB-Stammdaten beside the roll-call data as data whose redistribution is still an open question: the DATA.md bytes of every export change, no figure does.

### Fixed

- **RSS item titles keep their words apart.** A vertical tab, a form feed or one of the separator characters U+001C to U+001F between two words of a title was deleted, so the words ran together ("Titelmit"); it now becomes a space. A lone surrogate and U+FFFE or U+FFFF are dropped from the RSS text like the other characters XML forbids.
- **The warning for a refused site address shows only the scheme and the host.** A `BUNDESTAG_PULSE_SITE_URL` that fails the check was printed whole, or hidden whole when it held an "@". The build log now shows `scheme://host/`, `***@host` when the value carries a user and password, `***` as the host when an "@" sits after the host part (the host read from such a value can be part of the password), and `ungueltig` for a value that cannot be read. The query, fragment and path are never shown.
- **An advance-copy watermark in the middle of a line no longer stops an Antrag passage from being quoted.** After "Vorabfassung – wird durch die lektorierte Fassung ersetzt." and a space, the next text started with a blank, which reads as a list item whose marker the text lost, and the passage was refused. The watermark now goes together with the blanks after it.

### Changed

- **DATA.md names the MdB-Stammdaten as an open redistribution question.** Its sources paragraph named only the roll-call data. It now names both, and cites ADR 0003 for the roll-call data only, since the ADR does not cover the MdB-Stammdaten yet.

## [0.46.24.0] - 2026-11-20

The data release script is stricter before its first real publication. A release now carries exactly the licence string its commit's `LICENSE-DATA.md` states, and a few inputs that could slip through are refused. No stored figure, page or export value changes, and no release has been made yet.

### Changed

- **A release refuses any licence string other than the committed one.** The dry run and `--publish` compare the export's licence string with the short string under "## Short string" in `LICENSE-DATA.md` at the export's commit, and refuse a mismatch. This includes a deliberate `--data-license` override and a leftover `$BUNDESTAG_PULSE_DATA_LICENSE`. Builds and exports still accept the override; only a release refuses it. The older "the export carries no licence string" refusal and its dry-run notice are gone, because the new check covers them.

### Fixed

- **A release version written with non-ASCII digits is refused.** Arabic-Indic or full-width digits no longer pass as a calendar version.
- **The changes file of a release refuses numbers JSON cannot hold.** `NaN`, `Infinity` and a number past the float range such as `1e999` are refused when the file is read. `changes.json` is written with no non-finite value.
- **The Daten page explains every revision that is not a bare 12-digit commit.** It used to add the "local changes" note only when the revision held a hyphen. A short or upper-case revision from a hand-given manifest now gets the note too. A revision that is not text no longer crashes the page.
- **The `-dirty-` revision no longer depends on four more of the reader's git diff settings** (blank-line, prefix and submodule settings). The settings that decide whether a file counts as changed at all (`core.fileMode`, `core.autocrlf`) are left to the checkout. A clean checkout on a file system without exec bits therefore keeps its bare commit.
## [0.46.23.0] - 2026-11-19

The check that keeps local file paths out of a published site now catches paths under a mount point, a downloaded release given as the build store is refused before anything is read from it, and a stale cached report of an excluded sitting no longer stops every build. No stored figure, page or export changes. The path check flags 0 lines of the 10,639 files of the reference site, before and after.

### Fixed

- **A local path under a mount point stops publication.** `/Volumes/Data/Users/…`, `/mnt/c/Users/…` and `/System/Volumes/Data/home/…` passed the check before. `/Users/` and `/home/` are now flagged anywhere in a line except inside a web address (`https://` in any case, a protocol-relative `//host.` link or `www.`). The address ends at a space, a quote or an angle bracket, also when the space or quote is written as `&nbsp;` or `&quot;`, so a path after a link is still caught. `www.sr.de/sr/home/…` in a quoted speech stays allowed.
- **A downloaded release given as `--database-path` is refused up front on every read.** The offline render, the online pre-check, the Abgeordnete pages, the read after a rebuild and the Daten export now refuse an exported distribution SQLite with the "distribution copy" message, as the rebuild already did. An offline render of such a file stops before any page is written, earlier than before.
- **A stale cached report of a sitting on the exclusion record no longer stops the build.** A report of an excluded sitting with an old vote shape stopped online, backfill and offline runs with "ERROR [cached input]", whose suggested re-fetch could acquire nothing for an excluded sitting. It now loads and is dropped with the exclusion as before. The same report of a sitting not on the record still stops the build.

## [0.46.22.0] - 2026-11-19

When an MdB's Mandat appears in the MdB-Stammdaten before their Fraktion does, a roll-call vote on those first days keeps the group the Bundestag page gives instead of being moved to fraktionslos. No figure moves on today's file. An offline replay of the reference store against main gives the same 157 re-filed Stimmen in 87 roll-calls, and no group count, member Fraktion or stored fact changes.

### Fixed

- **A Mandat the Stammdaten list before any Fraktion or Gruppe record no longer proves fraktionslos.** The correction of misfiled roll-call members moved a member to fraktionslos on any Mandat day no membership covered, including the days before the file entered their Fraktion. It now moves nobody before an MdB's first Fraktion or Gruppe record in that Wahlperiode, an explicit "Fraktionslos" record included. Leaving a Fraktion still proves fraktionslos, as for the six MdBs corrected so far.
- **An MdB with two Mandate in one Wahlperiode keeps the proof of the first one.**

## [0.46.21.0] - 2026-11-19

Two budget debates of Wahlperiode 18 on the data protection commissioner's Einzelplan now carry the Politikfeld Digitales, as the same debates do in Wahlperiode 19 to 21. On the 801-sitting reference store, the agenda items of Wahlperiode 18 with a Politikfeld go from 1,443 to 1,445 of 2,381 (60.60% to 60.69%). The schema and the export format stay as they are.

### Fixed

- **Einzelplan 21 of Wahlperiode 18 is tagged Digitales.** The items "b) Einzelplan 21 Bundesbeauftragte für den Datenschutz …" of the sittings 18/138 and 18/201 had no Politikfeld (stored as `untagged` with source `einzelplan_unknown`), because the budget table had no entry for that Einzelplan in Wahlperiode 18. They now read `Digitales` with source `einzelplan`. The two sitting pages show the tag on the next render; the stored table `agenda_item_politikfelder` and its CSV export show it after the next `--offline --repersist`. The two items hold 25 Reden with 192,790 characters.
- **No other tag moves.** A replay of the tagging over all 801 sittings changes these two rows and nothing else: no vote tag, and Wahlperiode 19, 20 and 21 stay at 2,045 of 2,629, 1,750 of 2,109 and 903 of 1,070 agenda items with a Politikfeld.

## [0.46.20.0] - 2026-11-18

An online build that asks DIP again for a Vorgang no longer loses the title and summary it had cached, and the private directory beside a published site is no longer listable by other users. No stored figure moves, because offline replays do not ask DIP. An offline build of the reference store whose private directory was left world-readable still exports and ends with that directory closed to others.

### Fixed

- **A Vorgang asked for again keeps the cached fields DIP's answer leaves empty.** A vote's "Worum es geht" kept losing its title and summary when an online build refetched a Vorgang still without a Sachgebiet and the answer lacked them. The Sachgebiet and Sachbegriff lists are still replaced by the fresh answer.
- **The private directory beside a published site is closed to other users.** A directory left readable by group or others (an export run under the usual umask made it so) is set back to owner-only, so the names of the staged store copies inside are not listed to others. A symlinked or foreign private directory is refused before the export creates anything in it.
- **A CSV export that cannot set its file permissions leaves no half-written temporary file behind.**

## [0.46.19.0] - 2026-11-18

The Daten page's report link, the Impressum's contact details and the repository's own checks now say what is true. No stored figure or export changes. An offline render of the reference store with a `mailto:` report address writes the footer link "Datenfehler melden", without "(GitHub)".

### Fixed

- **The Daten page's "Datenfehler melden" link says "(GitHub)" only when it goes to github.com.** A `mailto:` address or a site path given as `--data-issues-url` was labelled GitHub before.
- **An operator e-mail whose name part holds `?`, `&`, `%` or `=` is refused.** The address becomes a `mailto:` link on the Impressum, where `?cc=` or `&bcc=` would add recipients. The build stops with "email is not an e-mail address" before any page is written.
- **An operator URL with a space anywhere in it is refused**, like one with a user or password.

### Changed

- **The authored codebook inputs (`LICENSE-DATA.md`, `docs/data-methods.md`, `scripts/data_dictionary.json`) are checked out with LF line endings on every machine**, so the exported copies equal the bytes the release commit holds.
- **`operator.json` and `operator.local.json` are ignored by git**, so a local operator file with a name and postal address is not committed by accident.
- **README and the design docs point to `PRODUCT.md` and `DESIGN.md`**, which replaced the deleted product design document.
## [0.46.18.0] - 2026-11-18

The test suite now checks three rules in `scripts/` that reviews used to catch by hand. They cover how a script opens a SQLite file, where a missing value could be published as a zero, and which modules may import which. Each failure message says why the rule exists and how to fix the cause. No stored figure, export or page changes in this release; only the way scripts open SQLite files changed, and the store comparison now reads the right store under an unusual path.

### Added

- **Only the build store's own opener can write to an existing database.** `scripts/sqlite_open.py` opens any SQLite file read-only, or creates a new one. `persist_dip_pulse_store.connect`, which refuses a downloaded distribution copy and turns on foreign keys, stays the only way to write an existing store. A test fails when a script opens SQLite any other way or attaches a second database.
- **A new `x or 0`, or a SQL `= ?` on a store column that can be NULL, fails a test unless it is listed with a reason.** The 86 existing `or 0` expressions are frozen in a list that only shrinks. Each of the 11 existing comparisons is listed with why it is right, or with the fix it waits for.
- **Every module in `scripts/` belongs to a layer, and an import that goes up a layer or sideways fails a test**, as does a new import cycle.

### Changed

- **The facts engine's staged copy of the store now has foreign keys on**, as the rebuild's staged copy already had.
- **The export reads its finished snapshot read-only.**

### Fixed

- **The store comparison and the store gate read the right store when its path contains `#`, `?` or `%`.** They built the SQLite address from the raw path, so a `#` or `?` opened an empty database in place of the store, and a `%20` failed to open.

## [0.46.17.0] - 2026-11-18

The Sitzungskalender line and the week-radar RSS feed now handle a calendar that lists a week twice, a cache stamped in the future, a stray control character in a title and a feed base URL carrying a user and password. No page or stored figure moves on the reference store. Its cached calendar (22 Sitzungswochen for 2026 and 21 for 2027, from 2 .ics files) lists every week once. An offline render of it with a site URL set writes a well-formed feed of 12 weeks, and the header still reads "Nächste Sitzungswoche: 23.–27. November 2026 (KW 48)".

### Fixed

- **A Sitzungswoche listed twice in the Bundestag calendar, or split into two events, counts once.** Before, ten events for five weeks passed the check that a year lists at least ten weeks, and a doubled week was stored twice.
- **A calendar cache stamped in the future is refreshed.** Before, a cache written while the clock ran ahead counted as fresh until the clock caught up with its stamp.
- **A control character in a heading or title no longer makes the whole RSS feed unreadable.** Characters XML forbids are dropped from item titles, links and descriptions.
- **An RSS item's date range reaches a Sondersitzung on the weekend when the sitting's date carries a time.**

### Changed

- **A feed base URL (`BUNDESTAG_PULSE_SITE_URL`) with a user or password, whitespace or a control character is refused.** The build writes no RSS and warns, as for any invalid URL. A refused value containing `@` is not shown in the warning, so the password never reaches the build log.

## [0.46.15.0] - 2026-11-18

A site rendered offline can no longer show vote panels filed from a different MdB-Stammdaten file than the one its store was built from, and a refresh can no longer move the seat tables back to an older file. Nothing moves on the offline replay of the 801-sitting reference store against main: no vote, group count, Rede or Fakt changes, the store records the same Stammdaten file, and a plain offline render of it runs as before.

### Fixed

- **A plain offline render stops when the cached MdB-Stammdaten file is not the one the store was built with.** This also covers a file missing for a store built with one, or a file present for a store built without one. It names both files' Stand and says to rebuild with `--offline --repersist`, before any page is written. Before, the vote panels could file Stimmen by one file while the store's counts came from another.
- **A downloaded MdB-Stammdaten file older than the cached one is not used.** The cached file stays and the build warns. Before, a server handing out an older file replaced the newer one, and the seat tables and the Stand on the Daten page moved backwards.
- **The stored fingerprint of the MdB-Stammdaten file names the exact bytes the seat tables came from.** The file is read once, so a file replaced mid-build can no longer pair the seat rows of one file with the fingerprint of another.

### Changed

- **An MdB-Stammdaten file that declares entities, or carries an implausible date, is refused.** A file whose header declares its own DTD entities is refused before it is parsed; the Bundestag's own header, which only names an external DTD, still reads. A Stand before 2017 or more than a day in the future is refused too.
- **The store gate's rebuilds use the input store's MdB-Stammdaten file**, so they file Stimmen the way the input store does. Under `--persist-only`, only a person cache it cannot read is reported as a gate error; any other failure keeps its traceback. An input store the current code cannot read now fails the gate with its cause instead of ending it without a receipt.

## [0.46.14.0] - 2026-11-18

The store comparison that checks a data correction (`scripts/compare_store_values.py`, the README's "Validate a data correction" recipe) now shows a Stimme filed under another group even when no vote outcome and no Abweichler changes. No stored figure, export or page changes in this release. On a copy of the 801-sitting reference store with one member of vote 1000 moved from SPD to fraktionslos, the report names exactly that vote, both groups' counts and that member; on two copies with no change it reports 0 of 657 shared votes moved.

### Added

- **A "vote groups" section compares every vote both stores hold, group by group.** It lists each group whose Ja, Nein, Enthaltung, nicht abgegeben or total count moved, and each member whose counted group or listed group moved, old and new.
- **Votes held by one store only are named.** The vote outcome section counts them and lists their ids; before, they moved the distribution rows with no line of their own.

### Changed

- **A member found in one store only is listed apart and no longer counts as an Abweichung move.** A changed member list showed up as "abweichung moved" before, even when no flag moved.
- **A member row with no matching person row is counted under its own id.** Before, it dropped out of the Abweichung counts without a word.

### Fixed

- **A damaged or truncated export copy reads "unavailable" instead of stopping the report with a traceback.**
- **An export manifest naming a path instead of a file name is refused**, so the comparison never reads outside the export directory.
- **When the second store cannot be opened, the first is closed before the script exits with code 2.**

## [0.46.13.0] - 2026-11-18

The abgeordnetenwatch client fails cleanly where it used to stop a build, and a speaker printed under a merged Redner-ID is now looked up by the right id. Nothing changes offline: the reference store holds no abgeordnetenwatch data, and profiles are only looked up on an online update. On the next one, Svenja Schulze's 10 Reden in 21/18, 21/24, 21/25, 21/28, 21/44 and 21/45, printed under the merged record "11005217 999990074", are looked up under her id 11005217. Before, the whole merged value was sent, which matches no profile.

### Fixed

- **A dropped connection, a timeout or a reply cut short no longer stops a build with a traceback.** Each counts as a failure, and after 8 in a row the client stops asking for the rest of the run. Nothing is cached for a failed lookup, so the next build asks again.
- **A speaker printed under a merged Redner-ID is looked up by its first id**, as the rest of the build already reads it.
- **A resolver that is switched off never asks the API.** It answers from its cache only.
- **The cache and the answers file are written through a temporary file of their own.** Two runs no longer share one temporary file, and a run stopped mid-write leaves the previous file whole.

### Changed

- **An HTTP 429 waits 60 seconds before each retry, up to 4 retries.** The old exponential back-off was capped at 60 seconds anyway.
- **The match-share measurement asks by the first id of a merged Redner-ID, as the build does.** Its M5 check no longer looks the raw value up, so the `merged_hit_by_first_not_by_raw` count is gone. It refuses a malformed answers file with exit 2, naming the file and the id, and it keeps the name searches already answered when a run is cut short.

## [0.46.12.0] - 2026-11-18

Four rules that decide whose abgeordnetenwatch profile, roster record or page link a speaker gets are now strict where they were loose. On an offline replay of the 801-sitting reference store against main, nothing moves: every table's row count, every vote and Rede, the person pages and `abgeordnete.json` are the same, and all 91,658 speaker units in the 802 cached reports keep their profile. Each rule closes a gap no stored sitting reaches today.

### Fixed

- **A profile found under a Redner-ID the Bundestag printed for two people reaches only its owner.** When cached sittings are read again, a profile is taken from, and copied to, only the occurrences of the person the corrections file names as that id's profile owner, by printed name or by the name reviewed for that occurrence. Before, a profile matched by name could pass from the profile owner to another person printed under the same id, such as from de Maizière to Steinmeier's address in 18/223.
- **A re-issued DIP person record is kept from an older store only if it was a roster record.** A record a sitting merely sampled under the old id is no longer carried forward with roster fields it never had.
- **A speaker link that carries a re-issued DIP id reaches the successor's page also for a person in a reviewed partition.** Before, only the plain DIP key was aliased.
- **A DIP person record whose Wahlperioden are not a list of numbers no longer cuts a Bundestag period.** A Land office excludes a Bundestag seat in the same Wahlperiode, so such periods are cut from a person's MdB periods; a role with an unreadable Wahlperiode now cuts nothing instead of being half read. On the cached records, the cut is the same for all 1,949 persons.

## [0.46.11.0] - 2026-11-18

The 83 sittings restored on 2026-11-17 are now measured against outside sources, and the record names every figure that moved, old and new. The reference store holds 801 sittings, up from 718. Of the 737 roll-call votes the Bundestag lists from WP 18 on, 727 are stored under their own date; the other 10 fall on 18/20, which stays out, or on two sittings newer than the store. Every restored sitting stores exactly the agenda items its XML prints, 8,189 in all. The abgeordnetenwatch match share of WP 18 and 19 Reden is 98.34% (98.27% on the earlier 400-sitting store), and no speech of ours is missing from CPP-BT. No code, export or page changes in this release; the measurements and their receipts are in `docs/plans/t4-acquire.md`.

### Changed

- **The CPP-BT comparison reads 77 more speeches as known differences.** Forty are units the project reviewed and files as procedure or chairing on purpose: the presidium elections of 18/1 and 19/1, the chancellor's election and the oaths of 19/19, two acceptances (19/68 and 19/158), and the chair's Sitzungsleitung in 19/1 and 19/19. The other 37 are the § 31 declarations 18/158 prints in its Sitzungsverlauf. A release review now has only the length ratios left to read by hand.
- **The source error E4 records its scale on the restored sittings.** 157 Stimmen in 87 roll-calls count for the group the Stammdaten prove on the vote's day, 57 of them in restored votes, all in the windows E4 already names.

## [0.46.10.0] - 2026-11-18

The check that refuses a build when the Bundestag prints one Redner-ID for two people no longer treats an office as a shared name. Before, two people printed under one Redner-ID with the same office in the name fields, such as "Dr. Carsten Sieling, Bürgermeister" and "Dr. Andreas Bovenschulte, Bürgermeister", shared the word "Bürgermeister", so the check filed both under one person. It now ignores office words and the punctuation around them, as it already ignored titles and name particles. The person corrections file also refuses three more mistakes before a build starts. On an offline replay of the 801-sitting reference store against main, no figure, person or page moves and no Redner-ID is refused. The check keeps its old limit. Two people printed with a word in common other than the office, such as the ministry's name, are still not told apart.

### Fixed

- **An office printed in the name fields no longer makes two people one.** The check ignores office words when it compares the names printed under one Redner-ID: Bürgermeister, Senator, Minister, Präsident and Staatssekretär with their compounds and feminine forms (Innenminister, Ministerpräsidentin), plus Parl., Stellv., Regierender, MdBR and similar. Brackets and commas around a word are stripped too, so "(Bürgermeister)" and "Bürgermeister," count as the same word. A real surname such as Meister still counts.
- **The person corrections file refuses three more mistakes.** It refuses one own id given to two people, a DIP own id written with leading zeros or as 0 ("dip:007", "dip:0"), which would miss the roster or the page link, and a DIP own id for the person who keeps a shared Redner-ID's profile, which would collide with that person's roster record.

### Changed

- **A registry rebuild reads the speaker records twice instead of three times.** The Redner-ID check now uses the read the merges already make. The successor map for re-issued DIP person records is built once per corrections file instead of on every lookup.

## [0.46.9.0] - 2026-11-18

Every Fraktion the parser reads from a Plenarprotokoll is now checked against the Fraktionen and Gruppen we know, so a stray string can no longer become a group of its own in a per-Fraktion count. Two such strings were stored. 18/222 printed the start of Dr. Astrid Freudenstein's reply inside her Fraktion ("CDU/CSU: Ich glaube, ich habe auch nicht gesagt – –"), and 19/60 printed the Land "Bremen" as the Fraktion of Bürgermeister Dr. Carsten Sieling. On an offline replay of the 801-sitting reference store, contributions naming CDU/CSU go from 5,713 to 5,714, Bundesrat Reden with no Fraktion from 108 to 109, and the parties table from 11 rows to 9. Each Redeanteil holds, because Sieling's Rede already counted for the Bundesrat by its Sprechrolle. Nothing else moves, and all 727 votes read as before. A store built before this keeps the two values until its next `--offline --repersist`.

### Fixed

- **A Fraktion followed by spoken text reads as that Fraktion.** Freudenstein's Erwiderung in 18/222 counts for CDU/CSU, as CPP-BT has it.
- **A Land's name beside a Bundesrat member who speaks for that Land is no Fraktion.** Sieling's Rede in 19/60 counts for the Bundesrat with no Fraktion, like every other Bundesrat Rede.
- **Any other `<fraktion>` value that names no Fraktion we know refuses the sitting,** naming the speaker. None of the 801 cached sittings does. Two spellings the Bundestag prints where no Rede is read yet ("CDU/ CSU", "BÜNDNIS90/DIE GRÜNEN") count as known.
- **An official "Antrag angenommen" is read as the ballot's word only on the chair's or DIP's evidence.** An inversion read only from a roll-call or Drucksache title no longer re-scopes the official result. A DIP decision bound to the ballot still does, also where a title agrees with it.
- **A malformed DIP record adds nothing instead of stopping the sitting,** and a tally written in other than ASCII digits is no tally. A vote that does not give a count no longer matches a DIP decision on that count as if it were 0. A rival vote with a missing count still blocks a match made on the tally alone.

## [0.46.8.0] - 2026-11-17

1,227 Reden in 39 sittings now carry their page. Their Inhaltsverzeichnis listed them under a title the sitting printed twice, such as "Tagesordnungspunkt II (Fortsetzung)" in 18/44, and the parser kept only the last block of each title, so the page of every Rede listed in an earlier one was lost. On an offline replay of the 801-sitting reference store, Reden without a page go from 1,643 in 46 sittings to 416 in 7. Agenda items without a page range go from 1,810 to 1,740, and those that hold Reden from 106 to 36. Beiträge without a page go from 19,792 to 19,664. No page or range that was already set changes, and no other figure moves. The 416 left are a separate gap: four sittings print every Inhaltsverzeichnis entry with an empty page, and three print Reden their Inhaltsverzeichnis does not list.

### Fixed

- **A Rede listed under a repeated Inhaltsverzeichnis title keeps its page.** Every block is read in source order, so a later block of the same title no longer hides an earlier one. Example: 18/44's `ID1804401300` now cites page 3952 B, and the agenda item "Tagesordnungspunkt II (Fortsetzung)" its range 3952 B to 3981 D.
- **A Rede outside any agenda item that two different Inhaltsverzeichnis titles list is refused.** It used to be filed silently under the first title. A Rede listed twice under one title is still placed once. No stored sitting has either shape.
- **A Rede outside any agenda item after another element is refused with the element's name.** The message used to say "after a TOP" whatever stood there.
- **The parser's mark for an agenda item it built from the Inhaltsverzeichnis can no longer come from the source XML.** A source element carrying it loses it before the parse, so it cannot be counted as such an item.

## [0.46.7.0] - 2026-11-17

The release script now refuses to publish while a sitting DIP lists with its XML is neither in the export nor on the exclusion record. Before, it only refused exclusions still waiting for acquisition or a rule, so a sitting a stopped acquisition run dropped from the record without storing it would have gone out unnoticed. On the reference export of 2026-11-16 the check names one such sitting, 21/107. A follow-up release's previous manifest is now checked against the releases actually published, not against this clone's tags. Only the release script and its checks change; no figure, export, page or schema does.

### Added

- **`--publish` refuses while a sitting DIP lists with XML is missing.** The script reads the DIP catalog the build leaves next to the exports directory (`plenarprotokoll-catalog.json`, or another file named with `--catalog`) and refuses, naming them, while a sitting from Wahlperiode 18 on that the catalog lists with an XML URL is neither in the export's `protocols` table nor on `coverage.excluded`. A sitting DIP lists without XML yet does not count. A dry run still builds the release directory and says what `--publish` would refuse. Every run refuses a catalog it cannot read or that was not fetched in full, and `--publish` refuses one that lacks a sitting the export holds, because such a catalog is older than the export.

### Changed

- **The previous manifest must be the latest published release, not the latest tag this clone knows.** Its version must be the newest `data-*` tag on origin (asked with `git ls-remote`, in a dry run too) and, with `--publish`, also the newest release gh lists. A clone that has not fetched, or holds a tag it never pushed, no longer decides which release came last. A tag left on origin without a release still gets the message that says how to delete it.

## [0.46.6.0] - 2026-11-17

The sittings T4 still has to acquire can now be stored without the build refusing on a speaker id the Bundestag printed for two people. The WP 18 run had stopped on two such ids, and the same name check run offline over the 719 stored sittings and the XML of the 83 T4 sittings finds exactly three; each now says who spoke, so the WP 19 run does not stop on the third. On the 719 stored sittings, one Rede moves: Thomas Heilmann's 2016 speech as Berlin Senator joins his own page. Persons 2,040 → 2,039, person pages 1,658 → 1,657, and the `erste-reden` fact of week 2018-W47 3 → 2, because his first Rede in our coverage is the 2016 one, not his first as an MdB in 2018 (the percentiles of 2018-W47, 2021-W25, 2021-W45 and 2021-W46 shift with it). The stub record goes (`mps` 6,387 → 6,386) and so does the fact's citation of the 2018 Rede (`fact_sources` 2,964 → 2,963); nothing else in the store moves.

### Fixed

- **Three speaker ids printed for two people now file each Rede under its own speaker.** `11004105` is Dr. Thomas de Maizière's id (also printed "Dr. Thomas Maizière" in part of WP 18), and 18/223 prints it for Bundespräsident Frank-Walter Steinmeier's address. `11002190` is Dr. Hermann Otto Solms's id, and 19/1 prints it for Präsident Wolfgang Schäuble's inaugural address. `999990055` is printed for Monika Heinold, Ministerin (Schleswig-Holstein), in 18/180 and for Thomas Heilmann, Senator (Berlin), in 18/183. Steinmeier's, Schäuble's and Heilmann's units land on their own Redner-IDs (`11004167`, `11001938`, `11004741`) and Heinold's on her DIP person (6983). A trusted abgeordnetenwatch profile found through the shared id does not travel with them.
- **An MdB whose own id the source also printed for a guest keeps that id.** A reviewed entry can name the id's holder: de Maizière and Solms keep their records, persons and profiles unchanged on the 719 stored sittings, and only the guest's address leaves. Without a holder, every de Maizière and Solms record would have been put under review.

## [0.46.5.0] - 2026-11-17

The release script closes five gaps it had to close before the first real `--publish`. A dry run and the `--publish` after it can now share one output directory, and a failed `gh release create` says how to recover. The script refuses a tag that already exists on origin, a commit id that a branch or tag of the same name could stand in for, a previous manifest that is not the latest release, an export older than the latest release, and an export file that changed after it was checked. Only the release script and its checks change; no figure, export, page or schema does.

### Fixed

- **A dry run no longer blocks the `--publish` after it.** A later run reuses an existing `data-<version>/` when its files are exactly the ones it builds, so `--publish` into the same `--output-dir` the same day publishes the rehearsed directory. A directory whose files differ (an extra or missing file, a symlink, a dry run from another day whose `changes.json` carries another date) is refused, naming the files and saying to remove it or use a fresh `--output-dir`. It is never overwritten.
- **A failed `gh release create` names the way out.** The directory is kept and the same command publishes it once the cause is fixed. The message names how to check for a tag or release gh left behind (`git ls-remote`, `gh release view`) and how to delete it, the local tag included.
- **A tag already on origin is refused.** `gh release create` attaches to an existing tag and ignores `--target`, so `--publish` now asks origin first and refuses when the tag exists or origin cannot be asked.
- **A branch or tag named like the export's commit can no longer stand in for it.** The 12-digit revision is looked up among commit ids only, and exactly one commit must match.
- **`--previous-manifest` must be the latest release.** Its version must be the newest one known (local `data-*` tags; with `--publish` also gh's releases), and it is refused when no release is known. A changelog against an older release reported false changes and could hide a schema change.
- **An export older than the latest release is refused.** An export whose version is older than the newest known release would otherwise go out after it, with its changelog computed backwards from the newer release.
- **An export file swapped after the check is refused.** Before the staged copy becomes the release directory, its `datenstand.json` is checked against the bytes that were verified and every file against the manifest's size and SHA-256.

## [0.46.4.0] - 2026-11-17

The vote-link review sheet now shows each reviewer the evidence of the right Tagesordnungspunkt, and says when a Drucksache is printed under it. `scripts/vote_link_review.py` writes the sheet the owner fills in before the first release, to judge whether each namentliche Abstimmung is linked to the right Tagesordnungspunkt. Nothing in the build, the store, the release or the site changes, and no figure moves.

### Fixed

- **A Drucksache printed under the Tagesordnungspunkt and linked to its Vorgang now shows both.** The `shared` column used to show only the Vorgang entry for such a number, so a link resting on the printed number looked as if it rested on the Vorgang alone; on the replayed store of 2026-11-15, 75 of the 91 rows linked through a printed number showed no printed entry. Such a number now reads `number:type:Vorgang:xml`; a number only the protocol prints still reads `number:xml:-`.
- **The evidence comes from the same Tagesordnungspunkt as the link.** The sheet read a Tagesordnungspunkt's Drucksachen from the cached report by its position, which a replay that adds a Tagesordnungspunkt renumbers in the store but not in the cached report, so a row could show a neighbour's Drucksachen. It now pairs them by the Tagesordnungspunkt's id and how often that id has occurred so far in the sitting, as the sheet's own key does, and shows `?` when the cached report lacks the Tagesordnungspunkt or holds its id a different number of times than the store.
- **A cached report with a malformed item index** is refused with a message and exit code 2 instead of a traceback.

## [0.46.3.0] - 2026-11-17

The replay comparison (`scripts/compare_store_values.py`, the README recipe "Validate a data correction") now shows each vote's stored outcome and Abweichler figures moving, and finds the distribution copy of an export made with a release tag. Nothing in the build, the store, the export or the site changes. On the 718-sitting store before and after the vote-figure change, it reports 330 accepted, 269 rejected and 20 NULL outcomes, 3,720 Abweichungen and 0 moved votes, and r3 at 1,390 rows on both sides.

### Added

- **Vote outcome and Abweichler figures in the comparison.** A new section compares `votes.application_result`, `votes.abweichler_count` and `vote_members.abweichung`: the outcome mix, the Abweichler sum and the votes whose count is NULL, and the member flags. Then it lists each vote both stores hold whose outcome, count or member Abweichungen moved, old and new, with the members whose flag changed. It follows `--cohort`, and a store from before these columns reads `unavailable`, never 0.

### Fixed

- **A tagged export's copy is found.** The `r3-abweichler` row runs on the distribution copy that the export's `datenstand.json` names. Before, the comparison looked only for `bundestag-pulse-local.sqlite.gz`, so an export made with `--data-tag <version>` reported r3 as unavailable.

## [0.46.2.0] - 2026-11-16

Two sittings still to be acquired, 18/158 and 19/13, will now be read as what they are, not as 94 Reden. Each protocol's XML misprints one thing, and a parser rule reads around each. Today's store holds neither sitting, so no figure in it moves, and the other 800 of the 802 XML files parse exactly as before. Once the two are acquired, they store 94 fewer Reden, withhold 3 fewer, and count 64 Fragen and Antworten of the Befragung der Bundesregierung that would otherwise have been Reden.

### Fixed

- **18/158: § 31 declarations printed as Reden.** The XML prints the 37 Erklärungen nach § 31 GO to the vote on the Asylpaket II as `<rede>`s after the sitting's close, under a Tagesordnungspunkt with no heading, and leaves its Anlage 7 with only their title. The Inhaltsverzeichnis still lists them under Anlage 7. They are now excluded as § 31 declarations, as the 9 printed in Anlage 15 are, and are not withheld, so they count against no coverage share. Stored Reden 137 → 100 with the withhold entries of 0.46.1.0, § 31 declarations excluded 9 → 46.
- **19/13: a Befragung der Bundesregierung under a broken heading.** The heading of Tagesordnungspunkt 1 is printed "Befr agung der Bundesregierung", so the Befragung was not recognised and every Frage and Antwort counted as a Rede. Headings are now compared with the whitespace removed. The minister's report stays the one Rede; stored Reden 70 → 13, withheld Reden 3 → 0, and 64 Fragen and Antworten of the Befragung. 19/13 leaves the list of sittings that withhold more than two Reden.
- **Both are listed as source errors** (E9, E10 in `docs/source-errors.md`), each with the scan that found the shape in no other file of the 802.

## [0.46.1.0] - 2026-11-15

Ten units that would have been counted wrongly in two sittings that are still to be acquired, 18/158 and 19/18, are now withheld. A review of the 82 sittings that come back with the next acquisition found them in the protocols' XML. Today's store holds neither sitting, so no figure in it moves. Once the two sittings are acquired, they count 10 fewer Reden and 8 fewer Zwischenfragen than the parser alone would give, and their withheld list grows by 10.

### Fixed

- **18/158: Zwischenfragen printed as their own `<rede>`.** In this sitting the XML starts a new `<rede>` for 11 Zwischenfragen. Seven of them would have counted as a Rede of the asker. In five of those, the Redner's answer and the rest of their Rede sit inside the asker's `<rede>` and would have counted as a Zwischenfrage. After two others, the Redner's answer follows as a further `<rede>` and would have counted as a second Rede of the same Redner. All nine units are withheld, each with its reason.
- **19/18: a whole Rede inside another.** Katharina Dröge's Rede is printed inside Klaus Ernst's `<rede>` after the chair calls her name ("Als Nächstes für Bündnis 90/Die Grünen …"), so it would have counted as one Zwischenfrage of Ernst's Rede. The unit the parser emits, Ernst's Rede with Dröge's inside, is withheld.
- **The figures, on the 82 sittings' XML:** withheld Reden 94 → 104, stored Reden 6,451 → 6,441, Zwischenfragen 498 → 490. Each entry names its Redner-ID, and the build refuses a sitting whose source names another owner.

## [0.46.0.0] - 2026-11-15

A release can now be reviewed against the Bundestag's own corpus. `docs/release-review.md` lists the steps the owner runs on a release before it becomes the stable one, and `scripts/compare_cpp_bt.py` runs the step that compares every sitting with CPP-BT, the corpus of the Plenarprotokolle on Zenodo. Nothing in the build, the release script or the site changes: a replay of the 718-sitting store moves no figure, and no export, page or schema differs.

### Added

- **A release review checklist.** `docs/release-review.md` has six steps: coverage per year, the figures that moved since the last stable release, spot checks against the protocols, the comparison with CPP-BT, the claims on the Daten page, and the verdict. It says when a release is stable, and that a bug found in review is fixed in a new main release, never patched into the candidate.
- **A per-sitting comparison with CPP-BT.** `scripts/compare_cpp_bt.py` joins our Reden to CPP-BT's by `rede_id` and writes a TSV: one row per sitting, one per difference (an id only CPP-BT has, a surname or Fraktion that differs, a word-to-token ratio far from its sitting's median) and a summary with the SHA-256 of both inputs. It uses only the standard library and imports nothing of this project, so a bug in the project cannot hide in its own check. It exits 2, with a message, when an input is unreadable or nothing could be compared, so a changed CPP-BT format cannot read as a pass. `scripts/cpp_bt_known_differences.tsv` lists the 96 differences already read by hand, each with a reason.
- **The first run, on the reference store.** `docs/release-reviews/cpp-bt-first-run-2026-11-14.md` records it: 718 sittings, no id of ours missing from CPP-BT in a shared sitting, and CPP-BT's side matching the research note of 2026-11-07 exactly. The token-ratio thresholds (15% and 50 tokens) are first values for the owner to sign off.

## [0.45.0.0] - 2026-11-15

A vote is now linked to the Tagesordnungspunkte of its sitting by one rule, whether the build fetches the sitting online, replays it from the cache or carries an older report forward, and the store records why each link was made. The codebook says what a link means and that the links are not yet checked by hand. No link moves: a replay of the 718-sitting store keeps the same 590 links, and every report, dossier, recipe CSV and Fakt value stays equal.

### Changed

- **One rule links a vote to its TOPs.** A vote links to every TOP of its sitting that shares a Drucksache with it, printed in the Plenarprotokoll or held by a DIP Vorgang of the TOP; with no shared Drucksache, to the one TOP whose title it matches. The online build, the replay of cached reports and the carry-forward of an older report all place votes this way, so a cached placement never outlives the rule. Persist refuses a report whose placement disagrees.
- **Each link says what it rests on.** `agenda_item_votes.basis` is `drucksache_xml` (174 of today's 590 links), `drucksache_vorgang` (401) or `title` (15).
- **The codebook says what a link means.** `agenda_item_votes` points to the TOP under which the Bundestag dealt with the voted Vorlage, and says the links are not yet checked by hand against protocol and DIP, so a link can still hit a TOP that did not deal with it. The methods page gains a section on votes and Tagesordnungspunkte.
- **Schema 14, export format 20.** A build store from before is refused with the instruction to rebuild it.

### Added

- **A review sheet for the vote links.** `scripts/vote_link_review.py` picks the links to check by hand from a store (three groups in full, plus a sample drawn with `--seed`) and writes them as a TSV sheet. It only reads the store.

## [0.44.0.0] - 2026-11-15

Every reader of a vote's outcome and its Abweichler now reads one stored figure, the one the vote panel shows. The store keeps each vote's outcome, its Abweichler count and, per MdB, whether they deviated. The Fakt *Die meisten Abweichler der Woche*, recipe r3, the votes archive and its badge read those columns instead of recomputing them in SQL of their own. No figure moves: a replay of the 718-sitting store keeps all 619 outcomes, the 3,720 Abweichungen, every recipe CSV, every Fakt value, the archive and every dossier equal.

### Changed

- **One stored outcome per vote.** `votes.application_result` holds the outcome after inversion and scope (330 accepted, 269 rejected, 20 unknown), written at persist by the rule the panel uses. The archive badge and the SQL snippet in the project documentation read it.
- **One stored Abweichler count per vote, and a flag per MdB.** `votes.abweichler_count` and `vote_members.abweichung` are written at persist and rewritten when two parties are merged. Recipe r3, the Fakt *Die meisten Abweichler der Woche* (metric version 1 → 2) and the archive read them. Nobody in a Fraktion whose member list does not add up to its counts, and nobody in Unbekannt, counts as an Abweichler. No vote in today's store has such a group.
- **The store gate checks the count against the flags.** `validate_store_gate.py` fails when a vote's `abweichler_count` differs from the sum of its members' `abweichung`.
- **Schema 13, export format 19.** A build store from before is refused with the instruction to rebuild it. The README, the data dictionary, the methods page and the stable-ID notes describe the three columns.

## [0.43.0.0] - 2026-11-15

A release can no longer publish data the coverage bar has not cleared, and its list of withheld Reden must match the rows a reader downloads. Stale cached reports say why they are stale. The store gate catches two more ways withheld Reden could go wrong. No figure moves: a replay of the 718-sitting store leaves every table, value and Fakt equal.

### Changed

- **`--publish` refuses while an excluded sitting still awaits acquisition or a rule.** Only an exclusion whose reason is final (`source_defect`, `not_narrowable`) may stand in a published release. Today all 85 exclusions await (83 `awaiting_acquisition`, 2 `awaiting_rule`), so every `--publish` is refused until T4 is done. The refusal gives the count and names the first 12 sittings. A dry run still builds and prints "--publish would refuse: …". A missing or unreadable exclusion record is refused too.
- **The release's withheld list must match the export.** Before building the release directory, the release compares the manifest's `withheld_reden` list with the exported `withheld_units` rows. It names every row that is only in the export, only in the list, or has a changed reason. A list that is missing, malformed or holds a duplicate is refused. From export format 17 on, the previous release must carry the list as well.
- **A stale cached report says why.** The refusal and the warning name each cause that applies: reports parsed under an older speech rule, and reports parsed under other entries of `scripts/reviewed_units.json` than it holds now. A report with no reviewed digest counts as stale. All 718 reports in today's store carry one. The demo fixture now carries the digest of its sitting.
- **A missing `scripts/reviewed_units.json` stops the build** with a message saying how to restore it. Before, it was read as an empty list.
- **An online build refuses another sitting's XML.** If the Plenarprotokoll XML's header names a sitting other than the one DIP's record gives, the online parse, the re-parse and `--fetch-xml` all refuse it, using the same check.

### Added

- **Two store-gate checks for withheld Reden.** `validate_store_gate.py` fails when a withheld Rede has no Redner-ID, and when a Beitrag nested inside a withheld Rede is still counted. A Kurzintervention or Erwiderung that answers a withheld Rede is its own Rede and is not flagged.

## [0.42.0.0] - 2026-11-15

A withheld Rede now counts as a gap. Its sitting is no longer complete for speeches, so the speech-based Fakten of its week and month read *unvollständig erfasst* and name it. *Erste Reden* no longer counts someone as a debutant when their real first Rede was withheld. Today's store holds no withheld Rede, so no figure moves. The change matters once the 85 sittings still awaiting acquisition are fetched.

### Changed

- **A sitting with withheld Reden is not complete for speeches.** Every speech-based Fakt in its week and month reads "unvollständig erfasst: Sitzung 21/20: 1 Rede zurückgehalten" (or "2 Reden"), and votes Fakten stay as they are. A cached report that does not record how many Reden it withheld also counts as incomplete, with the reason "no withheld count (report predates it)". Every report in today's store records the count. Rehearsed on a copy of the store with one withheld first Rede (Caroline Bosbach, 21/20): 2025-W37 and 2025-09 turn incomplete, and *Erste Reden* 2025-W42 goes from 2 debutants to 1.
- **A withheld first Rede rules out a debut.** *Erste Reden* (metric version 2 → 3) looks for a person's first Rede in our coverage among both stored and withheld Reden. A person whose first Rede is withheld is counted as a debutant in no week. A withheld Rede binds every person who shares its Redner-ID and binds no one if it has none. On today's store the only change is `facts.metric_version` 2 → 3 on the 273 *Erste Reden* rows.
- **A backfill leaves a sitting that is held back only by withheld Reden.** Fetching the sitting again never releases a withheld Rede; only a parser rule or a reviewed-list change does. `--backfill-incomplete` skips such a sitting and says so on its own `[backfill]` line, and the incomplete report names those sittings. A sitting that also has a roll-call gap is still fetched, for its votes.
- The data codebook, data dictionary, methods page and README describe both rules.


Jan Krampe and Jan Wenzel Schmidt each have one Personenseite again, and six former MdBs get their roll-call votes back on their own page. An offline replay of the store now groups persons exactly like the online build that wrote it, and the store gate checks that. Reden, Beiträge, votes and Fakten do not move.

### Fixed

- **A person DIP gave a second record is one person with one page.** DIP issued Jan Köstering a new record when he became Jan Krampe (8054 → 8257), and Jan Wenzel Schmidt one when he left the AfD (7406 → 8220), and it still lists both old records. Each old record now counts as the same person as its new one, through a reviewed list (`dip_successors` in `scripts/person_corrections.json`); it gives no page and no MdB biography of its own, and a speaker link with the old id opens the person's page. The empty "Jan Köstering" page and Schmidt's two extra pages are gone; Schmidt's page shows his 19 Reden, 3 Beiträge and 272 Stimmen under his current Fraktion, fraktionslos.
- **An offline replay no longer moves votes off a page.** `--offline --repersist` used to take the store's preserved roster entries out of person matching, so six former MdBs whom no cached sitting names lost their votes to a second, pageless person. Their pages show them again: Boris Gamanov 85, Jimmy Schulz 98, Agnes Alpers 51, Ronald Pofalla 51, Annette Schavan 20, Uwe Foullong 7.
- Old and new, replayed on the store of 718 sittings:
  - Persons 1,956 → 1,946, Personenseiten 1,661 → 1,658.
  - Stimmen on Personenseiten 417,707 → 418,104; pages with no Rede, Beitrag or Stimme 65 → 56.
  - MdB records per party: AfD 198 → 197, Die Linke 119 → 118 (the two old DIP records).

### Added

- **The store gate checks that a replay keeps every person and page.** `validate_store_gate.py` compares the replayed store with the store it replayed (the same grouping of persons, and every Personenseite with the same Reden, Beiträge and Stimmen), and with a fresh build of the same sittings that reads the MdB roster from the cached DIP person records (`data/dip-person-cache.json`). The fresh build must list the same DIP persons as the input store. A store from before this release fails both checks by design, because its persons regroup and the two old DIP records stop being MdB records. Replay it once with `--offline --repersist` before gating it.

## [0.40.0.0] - 2026-11-13

An oath, the acceptance of an election, chairing and an address to the Bundestag are no longer counted as Reden. 82 Reden in 24 kept sittings were oath answers or acceptances: they leave the counts, and two sittings, 18/4 and 20/5, now hold no Rede at all. Addresses by the Präsident, a Vizepräsident, the Alterspräsident or a guest become a Beitrag of their own, the Ansprache.

### Changed

- **Oath answers and election acceptances printed as a `<rede>` are no longer Reden.** "Ich schwöre es, so wahr mir Gott helfe." or "Ich nehme die Wahl an." is no contribution to a debate. Each such `<rede>` is named in a reviewed list (`scripts/reviewed_units.json`) and recorded as a procedural turn, not stored. Old and new, replayed on the store of 718 sittings:
  - Reden 54,937 → 54,855.
  - Sprechrolle Bundesregierung 2,849 → 2,790 (59 oath answers of the Bundeskanzler(in) and Minister), weitere 22 → 18 (the Wehrbeauftragte and the Polizeibeauftragte).
  - CDU/CSU 14,882 → 14,874, SPD 11,555 → 11,550, Grüne 7,670 → 7,667, Die Linke 5,639 → 5,637, FDP 4,374 → 4,373: the acceptances of Kanzler, Präsidentinnen and Vizepräsident(inn)en. AfD, BSW and fraktionslos are unchanged.
  - 24 sittings move, for example 21/2 24 → 5, 20/1 14 → 8, 21/1 17 → 12; 18/4 14 → 0 and 20/5 18 → 0. Beiträge do not move.
  - Fakten: 50 of 1,922 values move, mostly first-Rede weeks whose debut was an oath (2021-W49 10 → 4, 2025-W20 43 → 46); 2025-W19 has no first-Rede fact any more, so publishable weeks go 182 → 181.
- **An address to the Bundestag is an Ansprache, shown and counted nowhere.** The Dossier card reads "Ansprache · Präsident" (or the guest's role), the agenda item lists it under "Weitere Beiträge, keine Reden", and a person page counts Ansprachen apart. No kept sitting holds one yet. Ten excluded sittings that held only for these kinds (18/173, 18/178, 18/193, 18/215, 18/223, 18/245, 19/1, 19/9, 19/19, 19/73) now parse with every role mapped, 14 Ansprachen among them; `coverage-exclusions.json` records them as awaiting acquisition instead of a rule.
- **A presidium `<rede>`, oath answer or acceptance nobody reviewed is withheld.** A Präsident(in) or Alterspräsident(in) who owns a `<rede>`, or a short `<rede>` that reads like an oath (up to 400 characters) or an acceptance (up to 200), counts only once the list names it; until then that Rede is withheld with the new reason `unreviewed_presidium` (`withheld_units`), named on the Dossier, and the sitting stays. The ADR 0004 entries share `scripts/reviewed_units.json` with the withheld units of 0.39.0.0: a stale entry stops the run, an edit re-reads exactly the sittings it touches. A Vizepräsident(in) printed with a Fraktion still speaks for it.
- **A sitting with no Rede says so.** Its Dossier shows no Rede or Text share and says what the protocol prints there are procedural steps, not "Keine Reden im XML".
- **18/1's acceptance is read.** "Herr Alterspräsident, lieber Kollege Riesenhuber, ich nehme die Wahl gerne an." was an unresolved turn, so 0.39.0.0 withheld the Rede holding it (`ID1800100100`); it is now a Rede with the acceptance as a procedural turn.
- **The speech rule goes from 8 to 9 and the export format from 17 to 18** (`contributions.kind` gains `ansprache`, `withheld_units.reason` gains `unreviewed_presidium`). A store built before this release refuses facts, export and rendering until one `--offline --repersist`.

## [0.39.0.0] - 2026-11-13

A Rede the parser cannot read no longer keeps its whole sitting out. The parser withholds that one Rede, with its reason and text, and keeps the sitting's other Reden, agenda items and votes. A withheld Rede counts nowhere, neither as a Rede or Beitrag nor for a person or a Fraktion. No figure moves on the 718 sittings held today, since none of them withholds a Rede.

### Added

- **Withheld Reden are stored apart, with their reason.** Two new tables hold them: `withheld_units` (who spoke, as printed, the page, the reason, the speaker's own words and their count) and `withheld_turns` (other speakers' passages inside the Rede). Both are in the Daten export and the data dictionary. The reasons are a passage by another speaker that no rule explains, a speaker in a Befragung who is neither asker nor answerer, and an entry on a reviewed list.
- **A reviewed list withholds single known-wrong Reden.** `scripts/reviewed_units.json` names five Reden in 18/2, 18/29, 18/83 and 19/25 that read wrongly without any refusal. An entry whose Rede or speaker no longer matches the source stops the run, and editing the list forces a re-read of exactly the sittings it touches.
- **DATA.md shows coverage by year and the withheld share.** The share is the withheld Reden's own words over all Reden's own words, per year, per Fraktion and per sitting; the Daten page gives the totals and each excluded sitting's reason. The Dossier names each withheld Rede and its reason, without the text.
- **Every excluded sitting says why it is out.** `coverage-exclusions.json` now needs a reason code (`source_defect`, `not_narrowable`, `awaiting_rule`, `awaiting_acquisition`) and a sentence for each sitting; `--exclude-document-number` needs `--exclusion-reason` and `--exclusion-detail`. A record with the old bare "excluded" is refused. The 86 reasons for the current record are in `docs/plans/coverage-gate-pr2/coverage-exclusions.json`.
- **A release that adds more than two newly withheld Reden needs them named.** `publish_dip_pulse_data.py` refuses it until each is confirmed with `--confirm-withheld 18/1:ID…`; the data changelog lists every Rede a release newly withholds or releases.
- **Checks for withholding.** `scripts/check_withhold_one.py` withholds one Rede per agenda item and checks that nothing else moves, the store gate checks that no withheld Rede is also counted, and `compare_store_values.py` lists withheld Reden added, released or changed.

### Changed

- **A Rede's position is its place among the agenda item's Reden in the source.** `speeches.sequence` used to count stored Reden only, so withholding a neighbour would renumber it. 5,556 of 54,937 speeches in 425 sittings take a new number, for example 21/105 `ID2110505700` 12 → 14; no other stored value moves (0 of 1,922 Fakt values).
- **The speech rule goes from 7 to 8, the store schema from 11 to 12 and the export format from 16 to 17.** A store built before this release needs one `--offline --repersist`. Copy `docs/plans/coverage-gate-pr2/coverage-exclusions.json` to `<site-dir>/data/` first, because the old record is refused.

### Removed

- **`scripts/audit_offline_turns.py` and the W1 preflight tool are retired.** The parser now withholds by itself; both scripts stay in git history.

Measured on the 84 fetched XML of the 85 sittings still out of the store: 71 parse once their refused Reden are withheld (90 Reden, 94,697 words), and 4 more parse with their reviewed entries. Twelve wait on rules for presidium and guest Reden and 18/20 stays out, so the coming acquisition step can bring back 72 of the 85 plus 21/106.

## [0.38.0.0] - 2026-11-13

How many WP 18 and 19 speakers can carry a trusted abgeordnetenwatch profile is now measured: 937 of the 945 distinct MdB Redner-IDs (99.2%) find their profile by their Bundestag id, and every hit a precision review had to see was checked by hand and is the right person. No page, figure or export changes in this release.

### Added

- **A read-only script measures the abgeordnetenwatch match share of the WP 18/19 Redner.** `scripts/measure_aw_match_share.py OUTPUT_DIR --cache PATH` counts the build's own speaker set, splits MdBs by their Mandat in each Wahlperiode, and writes a receipt listing every hit a reviewer must look at. It never writes the store or its private directory, sends nothing with `--offline`, and a rerun asks only the ids that had no answer. A share stays a range while any id is unanswered.
- **The result:** 640 of 640 MdB ids in WP 18 and 719 of 727 in WP 19 find their profile; 98.3% of Reden (26,251 of 26,714) are by a speaker who does. The 8 WP 19 misses are wrong ids at abgeordnetenwatch (four-digit Bundestag ids), not parser errors.

### Changed

- **Builds ask abgeordnetenwatch at most once every 2 seconds** (was 0.5 s) and wait 60 s after a rate-limit reply, following the API's fair-use limit of 30 requests a minute. The abgeordnetenwatch part of an `--enrich aw-profiles` run takes up to four times as long.
- **An error reply from abgeordnetenwatch is no longer stored as "no profile".** It counts as a failed lookup and is asked again next time; after eight connection failures or error replies in a row a run stops asking. A cache write that is cut short keeps the previous cache.

Measured on an APFS clone of the store built on 2026-11-12 (400 WP 18/19 sittings): about 1,070 abgeordnetenwatch requests, 0 DIP requests, 0 store writes. The committed receipt was regenerated from the same answers with the network blocked, and every figure is identical.

## [0.37.0.0] - 2026-11-12

A sitting can no longer lose a Rede without the build saying so. Every `<rede>` of a Plenarprotokoll now ends as a stored Rede or Beitrag, a zu Protokoll gegebener Beitrag, a Verfahrensbeitrag, or an exclusion under a named rule; a sitting where one does not is refused. No figure moves: all 718 held sittings parse exactly as before.

### Changed

- **A Rede the parser would skip now stops the sitting.** A `<rede>` printed where the parser does not read (before or after the sitting's proceedings, nested inside another Rede), one without an id outside an annex, or an id printed twice now refuses the sitting instead of leaving it out of every count. So does a split Rede part with no status. The online build marks such a sitting as a rejected source; the offline `--repersist` stops with "rede reconciliation failed for …" and keeps the previous store, where it used to say the XML was corrupt.
- **An annex holding Reden needs a known title.** "Zu Protokoll gegebene Rede(n)" annexes count as before. §31 declarations, the continuation block of 19/115 and the reprints in 19/35 and 19/45 stay out under named rules. An annex with any other title now refuses the sitting until a rule names it.
- **Every Fragestunde speaker marker must open a turn.**
- **The methods text says what the check does not cover.** It accounts for whole `<rede>` elements, not every word: 50 speaker markers standing outside any `<rede>` in 24 of the 718 sittings (median 8 words, about 1,750 in all) and other speakers' passages inside a zu Protokoll gegebene Rede can still be missing without a refusal.

Checked on the store rebuilt on 2026-11-12: 718 sittings parse to identical results before and after, 0 refused, and a full `--offline --repersist` moves 0 values (0 of 1,922 Fakt values). Of 84 of the 85 sittings still outside the store (18/20's file holds another sitting), the same 71 refuse for the known located reason as before and none for the new check. The speech rule stays at 7, so no repersist is needed.

## [0.36.0.0] - 2026-11-10

29 Reden and 16 written submissions that the parser dropped without a word now count. 18/49, a budget sitting, shows all 51 of its Reden instead of 25.

### Fixed

- **Reden printed outside any agenda item now count.** 18/49 prints 26 of its 51 Reden, from Dr. Wolfgang Schäuble's budget 2015 speech on, and 18/44 three, with no `<tagesordnungspunkt>` around them (`docs/source-errors.md` C7). Each run now sits under the item the protocol's own Inhaltsverzeichnis names for it: "Tagesordnungspunkt 1", "Allgemeine Finanzdebatte …", "Einzelplan 06" and "Zur Geschäftsordnung", labels other sittings use as agenda items. A Rede with no Inhaltsverzeichnis entry, or one printed after an agenda item, stops the build instead of being placed by guess. Old and new, on the A3 store of 716 sittings:
  - Reden 54,718 → 54,747: 18/49 25 → 51, 18/44 41 → 44.
  - Per Fraktion: CDU/CSU 14,952 → 14,963, SPD 11,612 → 11,620, Grüne 7,638 → 7,643, Linke 5,611 → 5,616. Redeanteil counts CDU/CSU +9, not +11, because Schäuble and de Maizière speak as Bundesregierung (2,836 → 2,838). Every share stays at its rounded value.
  - 18/49's agenda items 1 → 4. Einzelplan 07 now holds 25 Reden, 49.0% of the sitting, where it held all of them; Einzelplan 06 13 (25.5%). Zwischenfragen 3,058 → 3,061, all in 18/49.
  - Agenda items 7,131 → 7,135; Politikfelder rows 11,460 → 11,465 ("Einzelplan 06" gets Innere Sicherheit and Migration from its Einzelplan rule).
  - Carsten Schneider, Dr. Eva Högl and Christine Lambrecht gain SPD as their Fraktion, which only these Reden printed.
- **Written submissions under a longer annex title count.** "Zu Protokoll gegebene Reden zur Beratung" (18/133) and "… zur Beratung:" (18/134) were skipped: 18/133 27 → 32, 18/134 0 → 11; zu Protokoll 3,326 → 3,342 in all. §31 declarations stay out (ADR 0002), also the two in 19/115 whose second block lost the words "nach § 31 GO", and so do the reprints "Neudruck eines Redebeitrages" in 19/35 and 19/45, which repeat a Rede of the sitting before.

Votes, persons, Abstimmungen and Fakten do not move. Agenda item ids follow the order of a sitting, so in 18/44 and 18/49 six ids now name another item and four are new.

### Changed

- **The speech rule goes from 6 to 7.** A store built before this release refuses facts, export and rendering until one `--offline --repersist`, which reads the cached reports again and adds the new agenda items.
- **The three new agenda items of 18/49 and "Zur Geschäftsordnung" of 18/44 have no DIP Vorgang or Drucksache link yet.** Their Reden count; the links need a matching rule for an item that has no heading, then a new DIP fetch.

## [0.35.0.0] - 2026-11-09

A Rede or Beitrag now belongs to the person who gave it, also where the Bundestag printed the same speaker id for several people. Per-Fraktion figures do not move; per-person figures and some Abgeordnete pages do.

### Fixed

- **43 Reden and Beiträge move to the person who gave them.** Five speaker ids in the Plenarprotokoll XML name more than one person (`docs/source-errors.md` E7), and the store had filed every unit under one of them. Old and new, on the A3 store of 716 sittings:
  - Annette Widmann-Mauz gains 19 Fragestunde answers and 2 Reden that sat on Dr. Andreas Bovenschulte's page (34 Reden, 82 Beiträge now).
  - Anette Kramme gains 14 Fragestunde answers that sat on Maika Friemann-Jennert's page (19 / 204).
  - Peter Beuth gains 3 Reden from Enak Ferlemann's page; Judith Gerlach gains 2 Reden and 1 Erwiderung from Dr. Mehmet Daimagüler's.
  - Dr. Carsten Sieling gains 1 Rede and Olaf in der Beek 1 Frage that sat on a second Marja-Liisa Völlers page.
  - Fraktion and Sprechrolle stay as the protocol prints them on every unit, so the per-Fraktion figures, votes and Redeanteile are unchanged.
  - Per person: `docs/plans/shared-redner-ids-old-new.tsv`.
- **A person split across pages by a shared id is one page again.** Enak Ferlemann's Staatssekretär page joins his main page (32 Reden, 362 Beiträge). Marja-Liisa Völlers (three pages) and Olaf in der Beek (two) each join their DIP record and their roll-call votes on one page. Profile pages drop from 2,005 to 1,999.
- **The garbled speaker "Dr. Dirk-UlrichLena Mende Kreck" of 20/82 is Dr. Lena Kreck,** as the printed label and the chair name her.
- **No abgeordnetenwatch profile is shown on the wrong person.** Ferlemann's page linked Peter Beuth's profile and Daimagüler's linked Judith Gerlach's; each person now keeps only the profile found under their own name.
- **Five `erste-reden` Fakten change value,** because each person now debuts once and as themselves: 2014-W23 27 → 26, 2015-W12 3 → 2, 2022-W11 49 → 50, 2022-W27 1 → 2, 2023-W50 0 → 1. 22 more rows change only their percentile.

### Changed

- **A build stops when one speaker id is printed for two unrelated names,** naming the id and the names, until `scripts/person_corrections.json` says who each printed name is. Name changes such as a new surname do not trip it. The 85 sittings outside the coverage run are checked this way when they come in.
- **The codebook says what `mps.xml_redner_id` holds for a reviewed shared id:** the person's own Redner-ID, or nothing for a person with only a DIP id.
- **The v1 scope review is recorded:** the owner's decisions in `PRODUCT.md` and the TODOS roadmap, a comparison with other Bundestag research datasets, and a cross-check against the CPP-BT corpus that found these shared ids.

## [0.34.2.0] - 2026-11-09

A vote on a Beschlussempfehlung to reject an Antrag now says that the Antrag fell, where the site said the opposite or left it open. Every badge on such a vote names what its outcome is about.

### Fixed

- **Vote 990 (21/51) read "Antrag: Angenommen" although Antrag 21/627 was rejected.** bundestag.de contradicts itself there: its text and Beschluss list say the Beschlussempfehlung to reject passed, and its roll-call box says "Antrag 21/627 angenommen". On a vote established as a recommendation to reject, a Ja majority now outranks that box: the result stays official and reads "Antrag: Abgelehnt". The contradiction is filed as E6 in `docs/source-errors.md`.
- **Five rejections the site missed now read "Antrag: Abgelehnt":** votes 638 (19/127), 695 (19/187), 774 (20/37), 777 (20/38) and 801 (20/56) read a bare "Angenommen". DIP's record of the decision ("Annahme der Beschlussempfehlung auf Ablehnung") is now evidence of direction when it matches the vote's exact tally and a shared Drucksache; it ranks below the chair's announcement and the listing's wording. On the 350 votes with both an outcome and a DIP decision matching their tally, the site's outcome disagreed with it 6 times before and 0 times now.
- **A badge on a Beschlussempfehlung names it:** "Beschlussempfehlung: Angenommen", or "Antrag: …" where the outcome is the Antrag's. A bare word next to an Antrag's title read as the Antrag passing.

Old and new values, replayed on the same 619-vote store:
- `votes`: 6 rows change. `inverted` 90 → 95 (638, 695, 774, 777, 801). `result_scope` application 25 → 24 (990, now proposition).
- Votes archive: 133 badge texts change (these 6, 126 gain "Beschlussempfehlung:", 846 gains "Antrag:"), and the Fraktion filter counts 5 votes as gegen/für den Antrag instead of Ja/Nein.
- Unchanged: vote totals, Mehrheitsvotum, Abweichungen, facts, recipes r1–r6 and every other export table.

## [0.34.1.0] - 2026-11-07

Documents only: no page, figure or export changes in this release. `DESIGN.md` is ready to be applied to the site.

### Changed

- **"Stimmkarte" takes a lighter, more open direction.** The ground is white, headings and navigation use Atkinson, D-DIN stays for verdicts and lead figures, and hairlines replace the heavy rules. Evidence stays in sight: no source, count or gap is folded away for looks.
- **Every sheet says where it comes from, and pages say how to cite them.** A sheet opens with its source, and vote, Sitzung, person and analysis pages say how they relate to the stable release. On Daten, CSV is a real control that opens the file list.
- **Home and Aktuell show the newest vote,** with its date, verdict, title, strip and counts. The Analysen door shows one small panel per Fraktion, and door links read as links.
- **The open questions from the first version are settled,** with rules for the components it left out, a component inventory, and the owner's v1 decisions: the name open-parlament, seven navigation links and two kinds of release.

### Fixed

- `DESIGN.md` now says where a vote row's numbers come from since the re-filing in 0.34.0.0: the stored count can differ from what the Bundestag's page prints, and a row with a moved Stimme says so with both numbers.

## [0.34.0.0] - 2026-11-06

A roll-call Stimme now counts for the group its member belonged to on the day, where the Bundestag's own page files it under another. A data user can read both: the corrected group and the one the page lists.

### Fixed

- **100 Stimmen in 55 roll-calls of WP 19 and 20 count for the group the MdB-Stammdaten prove.** The vote pages list six MdBs (Kamann, Bülow, Pasemann, Witt, Huber, Heßenkemper) under the wrong group on those days; the Bundestag's Textarchiv agrees with the Stammdaten in every case. Old and new values, measured on the same store against the code before this change:
  - `vote_fractions`: 146 rows change, and no vote's total.
  - Mehrheitsvotum: 9 fraktionslos rows change.
  - Abweichungen: 3,711 → 3,720, all Bülow under the SPD. Recipe r3: 1,389 → 1,390 rows.
  - Seat cross-check: `shift_between_groups` 55 → 0, agreeing roll-calls 551 → 606.
  - Fakten: 0 of 1,908 move.
  - Per vote and group: `docs/plans/e4-refiled-votes-old-new.tsv`.
- **A Stimme stays where the page has it wherever the Stammdaten prove nothing:** a vote after the file's Stand, a group change on the vote's own day (the 111 Gruppe rows of 2024-02-02), a name without one MdB in that Wahlperiode, or a vote whose rows can't absorb the move.

### Changed

- **Schema 11, export format 16: `vote_members.listed_party_id` holds the group the page lists wherever a Stimme moved,** so the page's counts can be read back from the store. A person's record keeps the page's group, so no one's Reden and Stimmen split. An older store needs `--offline --repersist`.
- **The dossier panel shows the corrected groups and names each member it moved,** with the group on the Bundestag page. The Quellen card, the Daten page's Datenstand line and the DATA.md dictionary say the file also decides these groups.
- **A release needs the MdB-Stammdaten.** A tagged export and `publish_dip_pulse_data.py` refuse a store built without them, because all 100 Stimmen would be back under the page's group while DATA.md describes the correction. A local build still runs, and its warning says what is missing.
- **A plain `--offline` render corrects from the cached file too, and stops with a named error if that file can't be read.**

## [0.33.0.1] - 2026-11-06

A stronger test for roll-call member rows. Only a test changes, so no figure moves.

### Changed

- **The store test for members whose card links back to the Abstimmung now checks every group's rows against its counts.** It already caught those members folding into one person. It now also fails when a Stimme is stored with the wrong vote or under the wrong group, or when a group's `vote_fractions` row is missing.

## [0.33.0.0] - 2026-11-05

Twenty small backlog items. No row of the store moved, and every recipe publishes the same rows as before (measured on a 716-sitting store, main's code against this one).

### Changed

- **Export format 15: the r2 recipe is now `r2-textanteil-fraktion`, "Textanteil je Fraktion oder Gruppe".** It was `r2-redeanteil-fraktion`, "Redeanteil je Fraktion nach Zeichen". Characters are not speaking time, so the recipe no longer calls them a Redeanteil. It now sorts by characters within a Wahlperiode, not by the number of Reden. The 40 rows of its full result are unchanged and reorder; its published rows are the same.
- **Recipes pick "the first sitting" by sitting number, not by the text of the protocol number,** so 21/99 comes before 21/100. This applies to `_VOTE_PROTOCOL_SQL` (r3, r4, r6) and to r5's `erste_drucksache`. In r5's full result, 278 of 7,925 rows get a smaller number (for example 19/21 becomes 19/5); none is in the published top rows, and r1, r3, r4 and r6 move no row.
- **The Daten page's scope line names the excluded sittings when there are any.**
- **`vote_documents.rank` is described as what it is:** a gapless rank in the vote's sorted number list, not the place of the first mention. The value does not change.
- **The exclusion record is written after the store swap,** so a rebuild that fails leaves the record naming what the store still holds.

### Fixed

- **A bad data option stops the build before any network or store work:** `--data-base-url`, `--data-issues-url`, and a release tag beside `$BUNDESTAG_PULSE_DATA_MANIFEST` used to fail only after a whole online update.
- **`--data-base-url` refuses what a browser reads as another URL:** any other `scheme:` (such as `javascript:`), a bad port, whitespace or control characters, a query and a fragment. A value that may hold credentials or a token is never printed.
- **`--exclude-document-number` refuses a number DIP does not list,** and refuses to run beside `--offline` or `--fetch-xml`, where it used to be silently dropped or ignored.
- **Operator file:** an empty `--operator-file` or `$BUNDESTAG_PULSE_OPERATOR_FILE` is an error (an unset CI secret used to build placeholder legal pages with exit 0). A repeated key, a non-regular file and a file over 64 KiB are refused, a refused e-mail is not echoed, and a stale path no longer blocks modes that render nothing.
- **The MdB-Stammdaten gate refuses what would break a later rebuild or silently misfile seats:** a Wahlperiode whose Mandate are all fraktionslos (a renamed `INSART_LANG` label), a membership or seat row with no day left, a negative or zero seat count, and a repeated row. The current file passes (2,914 Zugehörigkeiten, 171 seat rows). A refused download keeps the cached file.
- **`refresh` and the cross-check report check the private directory first and no longer fail the build on an `OSError`.** A corrupt cache is named as unreadable rather than as "no cached file", and a lost ETag write says the file was cached.
- **The README's "Validate a data correction" recipe copies the cached MdB-Stammdaten,** without which a replay falsely reported the seat tables as moved, and the README says `--enrich all` includes that download.

## [0.32.1.0] - 2026-11-05

Documents only: no page, figure or export changes in this release.

### Added

- **`DESIGN.md` is the site's design system, "Stimmkarte":** colours, type, layout and components, with their measured contrast limits. Fraktion colours stay, tuned for the new surfaces. No page uses it yet.
- **`docs/plans/frontend-go-no-go.md` records why the site stays Python-generated HTML.** The same chart was built in plain Python, in Python with a chart library, and in Astro. Across two change tasks Astro needed 27 changed lines against plain Python's 30, short of the third fewer the criteria required, so the owner accepted a no-go on 2026-11-04. Charts will be small Python modules drawing SVG.

### Changed

- **`PRODUCT.md` names the design direction and the rejected generator.** `docs/plans/a4-site-from-release.md` gains the dated review of the re-scope that led to the prototype, marked as not applied.

## [0.32.0.0] - 2026-11-04

### Changed

- **`votes/index.html` renders from the SQLite store, not the cached report JSON.** The archive runs the same vote rules as the dossier panel (`merge_fractions`, the Fraktion positions, the Abweichler count, the procedure type, the Politikfeld state, the Drucksache links) on stored rows. On the reference store (619 votes) every archive row is identical to the old one, and the archive agrees with the dossier panel on every vote's result badge, Drucksache links and Abweichler figure. The header and footer now say the list covers the namentliche Abstimmungen of the sittings in this build's database, which are only sittings with a Dossier.
- **The archive's Politikfelder come from the store.** A refreshed Vorgang cache reaches them only with a repersist; puls.html still reads the cache at render time.
- **Store schema 10 and export format 14.** The store now keeps what the archive needs: the order of a vote's Drucksachen and Fraktionen (`vote_documents.rank`, `vote_fractions.rank`) and each agenda item's own Drucksache url and order (`agenda_item_documents.url`, `agenda_item_documents.rank`). An existing store is refused until `--offline --repersist` rebuilds it, and the first export after this release re-exports once.
- **A vote total the source did not give is stored as NULL, not 0** (`votes.yes_count`, `no_count`, `abstain_count`, `absent_count`). The roll-call listing parser no longer pads a missing count with 0, and persist reads a total of four zeros (what older cached reports carry for a listing without chart values) as missing too: a real roll-call's counts add up to the seats. An Abweichler count can no longer rest on an invented zero, on the archive or the dossier panel, and recipe r4 leaves such votes out instead of ranking them first as the closest vote; the Fakten already skipped them (`yes + no > 0`). The reference-store replay, run before the four-zeros rule, found no NULL total; the count of four-zero totals there is still to be replayed. `scripts/compare_store_values.py` lists every vote whose total moved from 0 to NULL.

### Removed

- `collect_votes_archive`, `VotesComponent.write_pages` and the votes archive's feature-selection callables. `render_site` calls the archive writer directly.

## [0.31.0.0] - 2026-11-02

### Added

- **Seat counts per Fraktion and Gruppe.** `--enrich mdb-stammdaten` downloads the Bundestag's MdB-Stammdaten (only when the file changed; a failed fetch, or a file that fails the seat checks, keeps the previous one with a warning) into the store's private directory, never into the published site. Every rebuild derives three tables from it: `mdb_zugehoerigkeiten` (each MdB's Fraktion, Gruppe or fraktionslos per Wahlperiode and stretch), `party_seats` (seats per Zusammenschluss and fraktionslos per stretch, WP 18–21) and `mdb_stammdaten_stand` (the file's Stand and sha256). Fixed rules cut the stretches (handover day, Mandat limits, Nachrücker), and each day's total must stay within the legal size (631, 709, 736, 630) and reach it. Without the file the tables stay empty and the build says so.
- **Recipe r2 shows the seat share beside the speech share.** The new column `sitzanteil_prozent` is a group's mean seat share over the Wahlperiode's sitting days. On the reference store, WP 21: CDU/CSU 33.0 % of the seats and 28.3 % of the speech characters, AfD 23.9 % and 22.5 %. The caveat names the file's Stand: later changes are not in the file, so sittings after it carry the composition at the Stand forward.
- **A seat cross-check on every build.** Each roll-call's group totals are compared with the seat counts on its date, every disagreement is filed under a cause (a change on the vote's day, members filed under another group, members missing from the list, after the Stand, unexplained) in a private `seat-crosscheck.json`, and the build warns about drift and unexplained cases without failing. On the rebuilt reference store, 619 roll-calls compare with 0 unexplained; 55 are the Bundestag's own misattributions listed in `docs/source-errors.md` (E4).
- **The Daten page and the manifest name the seat source.** A "Sitzzahlen" line gives the MdB-Stammdaten Stand and sha256 (or says none are loaded), and `datenstand.json` carries them as `stammdaten`.

### Changed

- **Store schema 9 and export format 13.** An existing store is refused until `--offline --repersist` rebuilds it, and the first export after this release re-exports once, now with 32 table CSVs. No existing figure moves: a replay of the reference store matched the baseline in all 27 shared tables.
- **`--enrich all` includes `mdb-stammdaten`.**

## [0.30.0.0] - 2026-11-01

### Added

- **Impressum and Datenschutz.** Every build writes `impressum.html` and `datenschutz.html`, and every page's footer links both at its depth. The Impressum gives the operator's name, address and e-mail (§ 5 DDG, § 18 MStV), the contact routes and the sources. The Datenschutz page names the hoster and its server logs, the two settings stored in the browser (theme and KI-Zusammenfassungen, each only after a click), that no cookies, tracking or third-party content are used, the download host when the downloads live elsewhere, the people in the data and the reader's rights under the DSGVO. The publication check refuses an output without either page.
- **`--operator-file` (or `$BUNDESTAG_PULSE_OPERATOR_FILE`).** The operator's details come from a local JSON file outside git, so an address never enters the repository history. `docs/project-documentation.md` shows its shape. A value the file does not give renders as a marked „Angabe folgt.“ placeholder (`data-operator-missing`), so an incomplete build is visible. A path that is set but unreadable, or a file with unknown fields, wrong types, control characters, a malformed e-mail or a URL that is not https or carries credentials, stops the build before any work, naming the path.
- **Licence files.** `LICENSE` puts the code under MIT. `LICENSE-DATA.md` at the repository root is the one data-licence source: each source layer keeps its own terms (DIP terms of use, roll-call results from bundestag.de, CC0 for abgeordnetenwatch.de, CC BY 4.0 for the project's own derivations). Every export carries it as `LICENSE-DATA.md` beside `DATA.md`, and the Daten page links that copy. `sources.html#lizenz` shows the four layers as a table instead of the placeholder that said the wording was still open.

### Changed

- **The default licence string is the short string of `LICENSE-DATA.md`.** Without `--data-license`, `datenstand.json`, the DATA.md header and the Daten page now carry it instead of an empty string. On the Daten page, its mention of `LICENSE-DATA.md` links the export's copy.
- **Export format 12.** The manifest lists the licence file as a file of its own (kind `license`) with its SHA-256, and a reused export re-hashes it. The first build after this release re-exports once.
- **A release checks the export's licence file.** `scripts/publish_dip_pulse_data.sh` verifies that the export's `LICENSE-DATA.md` is non-empty and identical to the one its commit holds, and copies nothing from the working tree. `--publish` refuses an export without a licence string.
- **`--data-base-url` refuses more bad input.** A host that does not parse, a base with no host, a backslash (browsers read `/\host/` as another site) and a URL with credentials are refused at the start of the export.

### Fixed

- **The release script before its first real run.** A `--previous-manifest` holding JSON `null`, a number or a list, or missing the counts the changelog reads, is refused instead of labelling the release the first one; a previous manifest of an older export format stays usable. Relative `--output-dir`/`--exports-dir` are made absolute before `gh` sees them, and an `--output-dir` containing `#` is refused. A release `--data-tag` refuses `--data-manifest`, and the build stops when no export carries the tag instead of leaving an older release-tagged export behind. A checkout with `core.autocrlf=true` no longer builds an export the release script refuses as "differs from commit".

## [0.29.0.0] - 2026-11-01

### Changed

- **Every page renders from the SQLite store.** An online update always rebuilds the store, and an `--offline` render reads it. To preview a sitting without touching the site you serve, build into a clone copy of the output directory (README "Try a fetch or a backfill in a scratch directory"). Every online build now also refreshes the Sitzungskalender when it is due.
- **An `--offline` render refuses instead of rendering from half the data.** With no store it exits 1 with `error: no store at …`, naming `--offline --repersist` (or an online update). When the store and the cached reports cover different sittings, it exits 1, names up to 5 sittings per case and the repair: a cached report the store lacks (`--offline --repersist`), a stored sitting whose report is gone (restore the report, or exclude the sitting), or an excluded sitting the store still holds (`--offline --repersist`). The offline render checks before any page is written. An online build runs the same check after its rebuild.
- No page changes. A full-site render of the 716-sitting reference store before and after this change (measured against 40fa3bc, before the merge of 0.28.0.0) differed only in timestamps, generation names and the hashes that follow from them; 0 of 1,908 Fakt values moved.

### Removed

- **`--no-persist`.** Passing it is now an error. The `database.html` fallback no longer mentions it.

## [0.28.0.0] - 2026-11-01

### Added

- **"Nächste Sitzungswoche" on puls.html.** The header names the next planned Sitzungswoche from the Bundestag's Sitzungskalender, for example "Nächste Sitzungswoche: 5.–9. Oktober 2026 (KW 41), laut Sitzungskalender". While a planned week is running it says "Sitzungswoche läuft". When planned weeks after the shown week have passed, it adds how many and that they are not evaluated yet. A small script picks the line for the reader's date (Europe/Berlin), and the build date's text is the fallback. The calendar is cached in `data/sitzungskalender.json`. An online build that persists refreshes it when it is more than 7 days old, and from October on daily until next year's calendar is listed. A failed fetch keeps the old cache with a warning. `--offline` and `--no-persist` never fetch, and without the cache puls.html is byte-identical to before.
- **The week radar as data.** Every build writes `feeds/week-radar.json`, with the radar rows of the last 12 weeks with a Sitzung: titles, shares, the Redeanteil per Fraktion or Sprechrolle (with the release's codes) and links. With `BUNDESTAG_PULSE_SITE_URL` set (https, ending in `/`), it also writes `feeds/week-radar.xml`, an RSS feed with one item per finished week. Without it, an old RSS file is removed. The publication check scans both files.
- **Reporting data errors.** Two GitHub issue forms ("Datenfehler" and "Fehler auf der Seite") apply triage labels, and blank issues are off. `SECURITY.md` explains how to report a vulnerability privately, and `CODE_OF_CONDUCT.md` sets short German conduct rules (no party politics, no disparaging statements about people). The Daten page footer link reads "Datenfehler melden (GitHub)". `docs/project-documentation.md` gives the form URL that pre-fills the page.

### Changed

- **Long "Worum es geht" lists fold.** A vote panel shows the first 3 Vorgang blocks and folds the rest behind "N weitere Vorgänge anzeigen" when 2 or more would be hidden. The note about a Vorgang whose record was not fetched stays outside the fold. The panel's three toggles show a ▸/▾ marker again. No current panel has more than 3 Vorgänge, so none changes.

### Fixed

- **A rebuild keeps the store's group.** A store chgrp'ed to the web server's group stayed readable only until the next rebuild or facts write. Now the staged copy gets the store's group before anything is persisted, and a group the builder cannot set stops the write with a message.
- **The private staging directory is checked before it is used.** A symlink, a non-directory or a directory owned by another user is refused before anything is written or swept. A group-writable one is repaired to 0700. The sweep removes only this store's own staged copies, not a similarly named store's. A store in a `data` directory directly under the filesystem root keeps its private directory beside itself.
- **Daten export CSV files are world-readable (0644).** They were written 0600, so a web server running as another user could not serve them.
- **An abstract's script or style block is dropped even when its close tag lies past the 12,000-character window.** Before, its body could show as text in an over-long abstract. 0 of 8,737 cached abstracts change.

### For contributors

- The browser checks now cover the votes archive filter and the next-Sitzungswoche line (`node tests/run_bills_browser_check.mjs <python>`).

## [0.27.0.0] - 2026-11-01

### Added

- **Coverage from Wahlperiode 18 on (v1).** The site and the Daten export now cover every Sitzung the DIP catalog lists with Plenarprotokoll XML for WP 18 to 21, from 18/1 (2013-10-22) on. On the reference store that is 716 Sitzungen (WP 18: 194 of 245, WP 19: 206 of 239, WP 20: 213 of 214, WP 21: 103 of 103), up from 290. With the branch tip, 619 namentliche Abstimmungen and 54,718 Reden are counted, up from 217 and 26,267. The 85 Sitzungen not covered are on a reviewed exclusion list (below). README, PRODUCT.md and the Daten page state the covered range.
- **A reviewed exclusion list.** `--exclude-document-number N` keeps a Sitzung out of every later build, online or offline, and records it in `data/coverage-exclusions.json`. Use it only after reading the parser's rejection diagnostic. `--include-document-number N` takes it back. The Daten page counts these Sitzungen as "nicht erfasst (ausgeschlossen)". Any other rejected source still stops the build before the store is replaced.
- **An unattended WP-by-WP backfill.**
  - `--backfill-incomplete` judges from the first Sitzung of WP 18, so an empty store finds every WP 18 and 19 Sitzung. `--protocol-wahlperiode N` limits a run to one Wahlperiode. The run prints the judged range per Wahlperiode before it acquires anything.
  - It waits 2 s between DIP requests and scans the roll-call list down to its oldest target (at most 200 pages).
  - Every online build ends with a `[summary]` of the Sitzungen it did not acquire, and exits 1 when one was lost to an outage.
- **Fewer DIP requests.**
  - Closed Wahlperioden come from the cached catalog for 7 days.
  - Vorgang-Drucksachen and `/person` records are cached across runs and saved after every Sitzung.
  - Paging stops once a page holds the whole result.
  - After 2 failed DIP requests in a row a run asks DIP nothing more.
  - XML downloads are paced per window.
  - Together this took the backfill from about 26 to about 4 DIP requests per Sitzung.
  - `DIP_REQUEST_LOG=<file>` writes one line per request attempt, without the API key.
- **Bulk prefetch, `scripts/prefetch_dip_bulk.py`.** It fills the Drucksache and person caches for a closed Wahlperiode in month chunks, checked against DIP's own counts. `--overlap-only` serves the current Wahlperiode.
- **The store gate, `scripts/validate_store_gate.py`.** It checks a store clone with a repersist and integrity checks, a fresh build against a half-then-full build, a byte-identical unchanged replay, a link audit and the export against its manifest, and writes a JSON receipt. On the merged tree it passed all 11 checks.
- **Former Abgeordnete.** The MdB roster spans WP 18 to the present (`--roster-wahlperiode`, repeatable). Members of earlier Wahlperioden keep their pages and appear in a "Frühere Abgeordnete seit der 18. Wahlperiode" table on the Abgeordnete index. The index lists the newest Wahlperiode's members.
- `scripts/compare_store_values.py` lists moved Fakt values per period and metric (value, denominator, percentile).

### Changed

- **Daten recipes are counted per Wahlperiode.** Each recipe now has a `wahlperiode` column. Fraktionen are keyed by name, so a whole-store figure would have pooled four Wahlperioden. The export format moves to 11.
- **WP 18/19 Plenarprotokolle are read correctly** (speech rules v6).
  - A whole Rede printed inside the previous one is its own Rede.
  - Presidium markers and an election acceptance are Sitzungsleitung, and a role-less marker of the sitting's chair is Sitzungsleitung too.
  - An addressed MdB given the floor makes a Zwischenbemerkung.
  - One exchange is one Zwischenfrage, not one per marker. On WP 20/21 this merges some Zwischenfragen that were counted per marker.
  - A Vizepräsident(in)'s own Rede counts for the Fraktion (ADR 0004).
  - WP 18/19 role spellings, Fraktion spellings and Einzelplan tables are mapped.
- **Who counts as an MdB, and when.**
  - A roll-call voter's bundestag.de link is compared by its member number, and two numbers conflict only within one Wahlperiode.
  - Bundesrat roles no longer count as Bundestag membership.
  - A Wahlperiode in which DIP records only a Land-government office is no MdB period. On the reference DIP data this corrects 11 people, for example Olaf Scholz (WP 18–21 becomes 20–21) and Eva Högl (no longer listed as a WP 21 member).
- The erste-reden Fakt caveat names the store's real coverage start ("seit Beginn der 18. Wahlperiode") instead of a fixed "seit Januar 2022". The stored and exported `fact_metrics.caveat` carry the filled text.
- The knappste-abstimmung caveat no longer claims "gemessen über 58 vergleichbare Wochen". The store now has 110.
- abgeordnetenwatch biographies come from Bundestag mandates only, never a Landtag mandate. Biographies cached by the old rule are fetched again.
- The publication guard no longer flags `/home/` inside a quoted web address.

### Fixed

- A DIP `/person` stall stops a Sitzung's person lookups after 3 failures instead of hanging the run.
- Excluding a Sitzung that is already in the store no longer makes every rebuild fail with "Missing cached evidence".

## [0.26.1.0] - 2026-11-01

### Changed

- DIP abstracts on the vote panels and in the export are read by the project's own markup scanner instead of Python's html.parser. The same abstract now reads the same on every Python patch level. The 2025 html.parser changes no longer reach it. An abstract over the 10,000-character limit keeps its text up to the cut, instead of losing all of it on some tag shapes. Measured on the 3,922 cached abstracts: 0 change. Broken markup that no cached abstract contains reads slightly differently. An unclosed `<script>` no longer adds a space, and a `<![…]>` section reads as a space.
- On a vote panel, a long description's teaser now sits inside the "Ganze Beschreibung" toggle. Opening the toggle replaces the teaser with the full text, also in browsers without `:has()`. The Abweichler lists keep their list semantics in Safari and VoiceOver.
- A roll-call member links to an abgeordnetenwatch profile only when the match came from the Redner-ID. A profile found by name alone was a guess, and the member's own link is used instead. On the reference data, 0 of 173,407 Einzelstimmen rows change.
- DATA.md names both sources of the licence note (`--data-license` or `$BUNDESTAG_PULSE_DATA_LICENSE`). It warns that opening a CSV by double-click lets a spreadsheet evaluate cells that start with `=`, `+`, `-` or `@`, such as DIP titles starting with „- “. Cell values stay unchanged. The data dictionary now describes the „Unbekannt“ party row.

### Fixed

- A vote id with spaces or other unsafe characters gave an invalid anchor and an archive link that did not scroll. Anchors now use only safe characters, one per vote id. A vote id is cleaned the same way on the page and in the store. A missing id is refused instead of becoming `"None"`. A Vorgang id that is not all digits no longer goes into a DIP link. No reference vote or link changes.
- A CSV cell holding a bare carriage return is always quoted, so it cannot read back as a row break on Python 3.11 or 3.12. A BLOB value or a repeated recipe column name stops the export instead of writing `b'…'` or a wrong column. DATA.md no longer prints „..“ after a licence note that ends in a full stop. Carriage returns in DATA.md table cells become line breaks. No CSV value in the reference store changes.
- When the week radar's topic filter hid the last row, the last visible row kept its bottom border. A browser check now covers the radar filter at desktop and mobile widths.

## [0.26.0.0] - 2026-10-31

### Added

- A data release script, `scripts/publish_dip_pulse_data.sh` (logic in `publish_dip_pulse_data.py`). It turns an existing Daten export into an immutable, versioned release directory `data-<version>/`, which holds `datenstand.json`, the export files, `CHANGES.md`, `changes.json` and `SHA256SUMS`.
  - **Dry run by default:** it prints the site-build flags and the `gh release create` command it would run.
  - **`--publish`** creates the GitHub release. It refuses until `LICENSE-DATA.md` exists (ADR 0003) and the export carries a licence string.
  - **What gets refused:** an export not built with a release tag, a cited revision that is not a bare commit of this repository, authored inputs that differ from that commit, any file that does not match the manifest, and an existing tag or release directory.
  - Nothing has been published yet.
- Release versions are calendar versions, `YYYY.MM.DD` (`.2`, `.3` for further releases on the same day), tagged `data-<version>`. `--next-version` prints the next one. The site build takes it as `--data-tag`, which accepts only `local` or a release version.
- Every release carries a public data changelog: `CHANGES.md` plus `changes.json`, in the format described in `docs/data-changelog.md`.
  - **Derived from the two manifests:** export format, store schema, key version and schema hash, plus protocol, vote and row counts, old to new.
  - **Authored per release:** a summary, schema changes, added coverage, and every correction of a published value (table, key, column, old value, new value, reason).
  - **Refusal:** a release whose schema moved without an authored description is refused.
- `CITATION.cff` at the repository root. It claims no DOI or version yet.

### Changed

- The cited build revision is reproducible.
  - **Same edit, same revision:** the same edit gives the same `-dirty-<hash>` under the common git diff settings. A git timeout gives `-unverified-<hash>`, which still changes with every edit, instead of one fixed `-unverified`.
  - **Release requirements:** a release export needs a bare 12-digit commit, and its authored codebook inputs must be committed and unchanged.
  - **Where it's explained:** the Daten page and DATA.md explain the suffix.
  - **Effect on local exports:** a dirty tree's revision string changes form and hash once. No figure moves.
- The publication check (`--validate-publication`) also scans the export's `DATA.md` and `datenstand.json` for leaked local paths and placeholders.

### Fixed

- An export that fails after swapping in its new generation puts the previous generation back. Before, the old manifest could be left pointing at the new files.

## [0.25.2.0] - 2026-10-31

### Changed

- A vote panel can now quote an Antrag whose demand sentence puts a clause between „die Bundesregierung“ and „auf“: „im Rahmen der verfügbaren Haushaltsmittel auf“, „unter Einhaltung der haushälterischen Vorgaben auf“, „zur … auf“, „zum … auf“ and „dazu auf“. The opening quotes the whole sentence. On the saved 91-document corpus, ten more Drucksachen are quoted, each checked word for word against the PDF: quoted documents 64 → 74 of 91, reference cohort 50/71 → 60/71 (84.5 %). Derived but not measured on a site build: vote panels with a description 196/217 → 206/217. A store persisted with the previous extractor is refused until it is re-persisted with `--offline --repersist`.

### Fixed

- An Antrag is quoted only where its text proves the structure, so no quote on the saved corpus is wrong any more. Incorrect quotes went from 3 to 0:
  - 18/2742 joined „jesidisch-“ and „kurdischen“ into „jesidischkurdischen“ and is now not quoted.
  - 18/3154 lost its nine bullet markers and is now not quoted, instead of showing a flattened list.
  - 19/16794 carried the printer's imprint (Gesamtherstellung, Vertrieb, ISSN) between two demands and is now quoted without it.
- A lettered list that runs past z) into aa) to gg) keeps every item. 20/13415 folded aa) to ff) into demand z).
- An Antrag whose source text glues a dropped hyphen to „oder“ („Überoder Unterforderung“, 20/2345) is not quoted.
- The facts engine and the rebuild refuse a downloaded release SQLite given as `--database-path` and leave the file byte for byte as it was. Before, the facts engine could write into it and a rebuild replaced it with a fresh build store.

## [0.25.1.0] - 2026-10-31

### Changed

- In a vote panel's opening sentence, „namentliche Abstimmung“ links to the explainer on `bundestag.html#abstimmen`. All 246 vote leads on the reference site carry the link.

### Fixed

- A Fakt card shows its whole caveat, up to four lines, instead of cutting it after two. The caveats of „Die knappste Abstimmung der Woche“ and „Die meisten Abweichler der Woche“ lost their second half before. The caveat now ends just above the footer and grows upward, and the comparison text moves up to make room. The widest caveat line measures 869 of the 920 px available. The caveat texts are unchanged.
- A vote panel says „Niemand stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe“, and the Abstimmungen archive gives an Abweichler count, only when the Fraktionen and Gruppen add up to the vote's total. Where Stimmen are missing from the groups, the panel shows the gap note once, under the vote. On the reference site all 217 votes add up, so no panel or archive count changes (217 archive rows, 632 Abweichler).
- A context teaser no longer ends after an abbreviation that follows a bracket or quote, such as „(sog.“ or „(Abs.“; it cuts at the last real sentence end or at a word with „…“. 10 of 3,922 cached teasers change, all of which ended in „(sog.“.
- An abstract cut at 10,000 characters no longer ends in a fragment of a tag or entity („<a hr“, „&am“) as visible text; only the one tag the cut splits is dropped. No cached abstract reaches the cut (the longest has 5,111 characters), so none changes.
- An abstract reads the same on every Python patch release. html.parser's 2025 security releases (3.11.13, 3.12.11, 3.13.4) drop a tag that never closes („Ende <a hr“ became „Ende“) and read an unclosed comment to the end; older releases keep both as text. Each comment is now removed and each never-closing „<“ escaped before parsing, so both keep the text, and an abstract with a marked section („<![CDATA[“) always takes the plain-text fallback. 0 of 3,922 cached abstracts change on either release.

## [0.25.0.0] - 2026-10-31

### Added

- Every data export now carries `DATA.md`, a German codebook you can read without the website: what each table and column means, its unit, source and licence layer, the per-Wahlperiode coverage of exactly this SQLite file (sittings, date range, TOPs, Reden, Beiträge, Abstimmungen, Stimmen), the counting rules, the exact SQL of each published recipe, the layered licence terms and how to cite the export. Every definition was checked against the code that writes the column.
- The six SQL recipes on the Daten page now also ship as result CSVs (`recipe-<id>-<tag>.csv`), with every SQL column in projection order, including the link IDs the page hides, so each result can be reproduced against the export's SQLite file. The Daten page links `DATA.md` in the download panel and each recipe's CSV beside its table.

### Changed

- Export format 10: `datenstand.json` lists every file of a generation with its kind (`sqlite`, `table_csv`, `recipe_csv`, `codebook`), size, SHA-256 and, for CSVs, row count, and each recipe names its CSV. A manifest of another export format is refused; re-export with this version.
- r3 („Abweichler“) counts per person and Fraktion: someone who switched Fraktion gets one row per Fraktion instead of one row with the label of one of them. On the reference export the top five are unchanged (Bayram 30, Dieren 18, Kraft 13, Koeppen 11, Kubicki 9); 2 of 363 persons now have two rows, both below the cut.
- The cited build revision is a 12-character commit, with `-dirty-<hash>` when tracked files differ from it and `-unverified` when git cannot tell. A release export needs a clean revision. An export re-runs when the codebook inputs, the revision or the exporter change, and a cached generation whose `DATA.md` or recipe CSVs were altered is written again.

### Fixed

- The licence notice (`docs/data-license.md`) lists every column it gives CC BY 4.0, including `speeches.sprechrolle`, `speeches.unattributed_char_count` and `speech_rule_inputs`, which it previously left under DIP terms.

## [0.24.1.0] - 2026-10-30

### Added

- „So arbeitet der Bundestag“ (`bundestag.html`), the ninth nav entry: who brings in Vorlagen, when the Bundestag sits, how it votes (Handzeichen, Hammelsprung, namentliche Abstimmung), the freies Mandat and the way from Gesetzentwurf to Gesetz. Every section names its legal basis with a link to the Grundgesetz on gesetze-im-internet.de or the Geschäftsordnung on bundestag.de, checked against the official texts. Both glossaries on the sources page and the week radar's „namentlich abgestimmt“ badge link to it; a visited badge keeps its colour.

### Fixed

- The Abgeordnete list no longer includes members of the Bundesrat. The roster took every DIP person whose function contained „MdB“, which matched „MdBR“ and „Stellv. MdBR“: on WP 21 (DIP, 2026-10-30) the list showed 740 people, 151 of them Bundesrat members; it now shows the 589 with the function MdB. A store built before this drops them on its next rebuild: an `--offline --repersist` or an online build re-derives the MdB flag from each carried-forward roster row's stored function, with no roster refetch (A3 store, 2026-10-31: 1,712 → 1,360 roster MdBs, the 352 Bundesrat rows dropped). Only a build that does not rewrite the store (`--offline` without `--repersist`, or `--no-persist`) still shows them. 48 MdBs whose current office is a government one are still missing (DIP lists them without the MdB function), a known gap with its own TODO; adding them now would split 29 of them into two Personen.
- A Personenseite of someone who is not in the Abgeordnete list says „Redner“ with the Sprechrolle they spoke in, from Reden and Beiträge (Bundesregierung, Bundesrat, weitere Sprechrolle), and „Mitglied des Bundestages laut Plenarprotokoll“ with the Fraktion when a Rede or Beitrag counts for a Fraktion or they cast a namentliche Abstimmung, instead of an empty Fraktion and Wahlkreis. A page kept without any Rede or Beitrag says „Keine Reden erfasst“. The Abgeordnete index lists the Redner under „Weitere Rednerinnen und Redner“, which the search filters but the Fraktion filter does not, so their pages are reachable.
- „Der meistdiskutierte Vorgang des Monats“ (metric version 3) counts a Tagesordnungspunkt only when it debates exactly one Vorgang; the Reden of a verbundene Beratung of several Vorgänge count for none, where version 2 credited them all to the Vorgang DIP listed first. An Entschließungsantrag debated with its Gesetzentwurf does not make a second Vorgang. On WP 21 sittings 21/87–21/103, 3 of 4 monthly winners change: June from „Infrastruktur-Zukunftsgesetz“ (16 Reden) to „Empfehlungen der Rentenkommission …“ (13), July from „… Straßenverkehrsgesetzes (Tempolimit)“ (17) to „Deutschland braucht echte Reformen …“ (14), September from „Haushaltsgesetz 2027“ (16) to „Das Solidarprinzip stärken“ (13); October stays „Nachhaltigkeit und Zukunftsfragen“ (26). Each old winner was debated together with other Anträge. When the one Vorgang is a co-advised (mitberatener) one, it is named by its own title. The card and the Methodik state the rule in full.
- A roll-call profile link with a `.` or `..` path segment, also percent-encoded, is no longer taken as a person's profile (it could resolve to the Abstimmung page itself). No stored link had one.
- The zero-network demo shows 14 Reden for TOP 32 of 21/84, as today's parser counts them, instead of 16; the Kurzintervention and its Erwiderung appear as Beiträge, with a Zwischenfrage.

## [0.24.0.0] - 2026-10-29

### Added

- Vote panels can quote an Antrag's demands when DIP has no abstract, with sponsor attribution, a link to the original Drucksache and a fold for longer passages. Existing DIP descriptions take precedence.

### Changed

- Antrag texts are cached for offline extraction and included in schema 8 / export format 9 through document passages and vote associations. Rebuild older stores with `--offline --repersist`.
- Local validation increases reference votes with descriptions from 153 to 196 of 217. Extraction remains below its acceptance threshold, and three historical WP 18/19 quotation fidelity defects remain documented.

### Fixed

- Quotes retain an elision hyphen stranded at a line break, such as `Steuerzahler und -zahlerinnen` in Drucksache 21/224. Extractor version 7 requires re-persisting existing passage data.
- A context that already has a quotation still reports when another candidate's text or metadata has not been fetched.

## [0.23.6.0] - 2026-10-29

### Fixed

- puls.html's Redeanteil card is headed „Redeanteil der Fraktionen und Gruppen“ and lists every row. It stopped at eight before, so in a WP 21 week (up to ten rows) the Bundesrat or fraktionslos row could drop and the bars summed to less than 100 %. Bundesregierung, Bundesrat, weitere Sprechrolle, fraktionslos and Unbekannt now follow the Fraktionen and Gruppen below a rule; in the Wochenvergleich a row that spoke only in the compared week shows at 0 % with its loss, so the shifts net to zero; and a cut-short week's note reads „Zuordnung für N von M Reden erfasst“.
- A dossier cached before the parser checked link hosts no longer shows a number read off a quoted news URL as a Drucksache (88/739016 from a syriahr.com link in 20/206), and the vote panel no longer takes such a link. Every reader of the XML Drucksache references applies the rule persist already used, so no stored figure moves.
- On bundestag.de vote pages a fractional majority such as „2/3-Mehrheit“ is no longer read as a Drucksache number: it neither refuses an official outcome as naming another document nor joins a vote's documents from the roll-call list. No stored vote changes until it is fetched again, since the official outcome is read at fetch time.
- A `--data-manifest` override must carry exactly this build's recipes (same ids in order, identical SQL); the Daten page takes each recipe's title and SQL from the build, so a tampered manifest cannot show other text as SQL next to the copy button. An override exported by code with different recipe SQL is refused with the recipe named; re-export it. A recipe without `empty_reason`, or with a row that is not an object, is refused instead of crashing the build.
- A build stopped by a stale cached report prints the command that re-fetches that very sitting (`--document-number 21/82`), and a refused vote shape names its TOP or `sitting_votes`. A refusal of reports from an older counting rule says to run `--fetch-xml`, then `--offline --repersist`, and names for a re-fetch only the reports without an `xml_url`; `ERROR [persist]` now prints that fix too. README no longer says a plain online update re-fetches a deleted report.

## [0.23.5.0] - 2026-10-29

### Fixed

- A bill's „Zuletzt erfasst“ step on a day with several events is now the procedurally latest one: the sitting's Beratung over a Drucksache filed that day (a same-day „Gesetzentwurf“ no longer beats „1. Beratung“), the Beratung over a same-day Entschließungsantrag or roll-call vote, and the Gesetzesbeschluss over the 2. Beratung. On the reference cache 8 of 562 bills change: 5 from „Beschluss“ to „Abstimmung über Vermittlungsvorschlag“, 1 from „Geschäftsordnungsantrag zur Beratung“ to „2. Beratung“, 1 from „2. Beratung“ to „3. Beratung“ and 1 from „Unterrichtung“ to „2. Beratung“. The 47 bills whose latest step is „Gesetzesbeschluss“ keep it.

## [0.23.4.0] - 2026-10-29

### Changed

- The Methodik page and the Plenarprotokoll overview call a Sitzung's page a „Dossier“ („Jedes Dossier verlinkt den Zwischenbericht als JSON“, „Erzeugte Dossiers“) instead of „Sitzungsseite“ and „Sitzungsdossiers“.

## [0.23.3.0] - 2026-10-29

### Fixed

- The demo build's grouped Antrag TOP on puls.html lists each Antrag's own title instead of one bold block of the joint „a) … b) …“ agenda heading. The demo fixture had copied that heading into both titles; real builds were not affected.
- `scripts/extract_demo_fixture.py` runs again: it passed bytes to the protocol parser, which now takes text.

## [0.23.2.0] - 2026-10-29

### Changed

- puls.html flags a week older than four ISO weeks with „Nicht aktuell: letzte Woche mit Sitzung vor N Wochen“ right after the heading, instead of only in the muted facts line; shorter gaps still lead the facts line with the age.
- The site calls its reporting period „Woche mit Sitzung“ (or „Woche“), not „Sitzungswoche“, which names the Bundestag's planned calendar. This covers the Wochenvergleich, the Fakt der Woche cards and footer („Vergleich: N Wochen mit Sitzung“), and the Fakten Methodik.

## [0.23.1.0] - 2026-10-28

### Fixed

- Bill search now ignores accents and treats ß as ss, so “fur” finds “für” and “strasse” finds “Straße”. Titles and query spelling remain unchanged, including when restoring searches through browser history.

## [0.23.0.0] - 2026-10-26

### Added

- Each roll-call vote panel now introduces the recorded subject, date, outcome and raw vote counts, followed by its committee citation where available. Calculated and unavailable outcomes remain clearly labelled.
- Vote panels link to the associated Bundestag report where one can be identified. The optional source link is also included in SQLite and CSV downloads; existing cached reports need an online vote refresh to acquire it.

## [0.22.1.0] - 2026-10-26

### Fixed

- Weeks without an eligible comparison week retain their current totals and fraction shares without repeated `n/a` markers or an empty delta column. Comparisons with no shared sitting weekdays retain their per-row unavailable deltas.

## [0.22.0.0] - 2026-10-24

### Fixed

- Vote panels now explain when a Ja supports a recommendation to reject an Antrag, using the chair's announcement and its Drucksachen. All 14 previously missed reference votes show the inversion legend; direct votes on a Vorlage remain uninverted.
- Existing caches recover vote interpretation with `--offline --repersist`, keeping every copy of a vote consistent across dossiers, the archive and data exports. Vote 1005 now shows `Antrag: Abgelehnt (berechnet)` instead of a missing result, and sitting-level votes survive online acquisition.
- Official outcomes remain attributable when the read-out tally differs from the final tally by up to three votes per side, only within a uniquely identified document block. The reference-page comparison recovers 43 additional official outcomes without changing an existing one; vote 996 shows the official Antrag rejection at 439/135 without double inversion. Ambiguous matches stay unresolved.

## [0.21.1.0] - 2026-10-23

### Added

- Regression coverage for offline audit comparisons ensures an independently loaded historical parser uses its own classifier and leaves current counts unchanged across multiple XML files.

## [0.21.0.0] - 2026-10-23

### Added

- Each roll-call vote on a dossier says what it was about: a "Worum es geht" block with DIP's description of the Vorgang the vote decides, linked to DIP by its title, with a short teaser and the full text behind "Ganze Beschreibung". A vote's Vorgang comes from its own Drucksachen, narrowed to its TOP's Vorgänge. On the reference cache 217 of 217 votes have their Vorgang, and 153 have a DIP description; the others say "Keine Beschreibung in DIP", "Kein einzelner DIP-Vorgang ermittelt" or "Vorgang nicht abgerufen".
- Each vote cites the committee recommendation it was taken on: "Beschlussempfehlung des Haushaltsausschusses (Drucksache …)", found among the vote's Drucksachen across the whole sitting, or "Ausschuss nicht ermittelt". 190 of 217 reference votes cite one.
- Under each Fraktion or Gruppe of a vote, the panel names who voted against its majority (Ja against a Nein-Mehrheit or Nein against a Ja-Mehrheit), the first ten inline and the rest behind "alle N anzeigen", linked to their Personenseite. "Niemand stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe" is said only when every group's Einzelstimmen are complete; a group whose Einzelstimmen do not add up to its tally says so instead of naming no one. The reference votes have 632 such Stimmen.
- The votes archive shows how many voted against their group's majority on each vote (only when that count is complete), and each archive entry links straight to its vote panel (`…#vote-<id>`, 217 of 217 resolve).
- The Daten export has a `vote_proceedings` table (the Vorgänge a vote is about, with rank), `proceedings.abstract` (DIP's description as plain text) and `votes.context_state` (resolved, none or not_fetched), labelled as derived or source data, and a sixth recipe, `r6-ausschuss`, counting votes by the committee whose Beschlussempfehlung they cite.

### Changed

- Store schema 6 and Daten export format 7 with 28 CSVs. A store built by an earlier version is refused with the instruction to run `--offline --repersist`.
- A vote's procedure type is read from the Drucksachen of the whole sitting, not only its own TOP, so the archive rows showing "–" fall from 5 to 0.
- An online build also asks DIP again for vote Vorgänge whose description is empty (86 on the reference cache; none had gained one).
- Persist and the standalone renderer refuse a stale vote shape (a TOP's singular `"vote"`, non-list votes, a vote without an id) instead of treating the sitting as voteless; a stale report outside the build's catalog no longer stops the build, and a null or empty `"vote"` passes.

### Fixed

- An Einzelstimmen card that links back to the Abstimmung (bundestag.de does this for an MP without a biography; 77 rows in 14 votes) is no profile URL any more: it no longer serves as an identity that folded every such MP of a vote into one, is not stored as the MP's profile (14 → 0 mps), and the name is no longer linked to the vote page. The registry kept the 63 occurrences it had already folded on their records, so the reference store was rebuilt without its earlier registry: `vote_members` 154,015 → 154,078, persons 4,265 → 4,298 (47 records, one per affected MP, replace the 14 folded ones; 41 stale `xml:` records from an older identity rule fold into their MPs' current records with no speech or contribution changing person; 10 bindings to speeches and contributions that no longer exist are gone). Abweichler are unchanged (632).
- Einzelstimmen whose biography link fails the profile check (a backslash, user info, a port or whitespace in the URL, or anything other than an https bundestag.de biography or abgeordnetenwatch profile) are no longer linked or used as an identity. No reference link is affected.
- In dark mode, the "Einzelstimmen (N Abgeordnete)" control under each vote is readable (it was dark blue on the dark panel, about 2.2:1; now 8.2:1).

## [0.20.8.0] - 2026-10-23

### Fixed

- The Debattenprofil now counts each agenda item once per procedure type in both compared calendar weeks, so bundled petitions no longer inflate the profile. The card and glossary explain the counting rule.
- Returning procedures now appear under “Wieder auf der Tagesordnung”, with notes consistently calling them Vorgänge.

## [0.20.7.0] - 2026-10-23

### Fixed

- Fact citations now say “Belege”, and the data export description includes agenda items among the evidence types.
- Monthly facts without an observation now say “diesen Monat nicht messbar”.
- Fact pages and Methodik now explain that rebuilding can change earlier cards after data, rule or wording changes, and that cards disappear when their evidence no longer resolves.

## [0.20.6.2] - 2026-10-22

### Changed

- The refresh guide now explains how `--protocol-wahlperiode` works with acquisition limits, with examples for the current period, older periods and all periods.

## [0.20.6.1] - 2026-10-22

### Fixed

- Assistive technology can now identify the bill overview's search and filter controls as a search landmark named “Gesetzesvorhaben finden”. Empty publications continue to omit the controls.

## [0.20.6.0] - 2026-10-22

### Fixed

- Protocol citations now consistently use `BT-PlPr.` with their document number. Bill timelines and fact sources identify Bundestag and Bundesrat documents by chamber and type while preserving their source links.

## [0.20.5.1] - 2026-10-22

### Fixed

- Data exports now correctly identify abgeordnetenwatch as the source of MP birth year, gender, profession, constituency and state. Export format 6 refreshes cached provenance labels without changing row IDs or the store schema.

## [0.20.5.0] - 2026-10-22

### Changed

- Bill pages now label linked plenary records as ‘Beratungen im Plenum’, including records without speeches; counts are unchanged and the section anchor is now #plenarstellen.

## [0.20.4.0] - 2026-10-21

### Changed

- The dossier sidebar now says "Meiste Reden". Its methodology explains that topics are ranked by speech count and the bars show speech and text shares within the sitting. Existing links to the ranking still work.

## [0.20.3.0] - 2026-10-21

### Fixed

- A failed SQL recipe copy preserves text selected elsewhere, including identical text in another recipe, instead of replacing the reader's selection.

## [0.20.2.0] - 2026-10-20

### Fixed

- Resetting the Gesetzesvorhaben filters returns keyboard focus to the search field, clears the query, year and page, and keeps the selected sort order.
- Following the same speech link again reopens a closed speech card, including when activated with Enter. Modified clicks, downloads and links targeting another browsing context keep their native behavior.

## [0.20.1.0] - 2026-10-20

### Fixed

- DIP refreshes retain valid Vorgänge when another record is malformed, leave incomplete lookups retryable, and distinguish validation errors from outages. ID lookups cannot overwrite unrelated cached Vorgänge.
- Offline replay refuses any previously fetched TOP or vote becoming `not_fetched`, even when another identity recovers. Unreadable, locked, corrupt or incomplete stores stop replay without replacing the database.
- Builds preserve unsupported or unreadable Vorgang caches and explain how to recover. Corruption backups have unique names, and atomic cache writes retry beside the cache when private staging fails, including during the final rename.
- Politikfeld and Fraktion filter buttons on the week radar and votes archive have 44px touch targets; desktop sizing stays unchanged.

## [0.20.0.0] - 2026-10-19

### Added

- Every Tagesordnungspunkt and every roll-call vote has one to three Politikfelder from a closed list of 13 (Migration, Soziales, Wirtschaft & Finanzen, Energie & Klima, Verteidigung, Innere Sicherheit, Justiz, Digitales, Gesundheit, Bildung, Verkehr, Außenpolitik, Staat & Demokratie), or is explicitly untagged. They are derived without a model from DIP's Sachgebiet labels: of the Vorgänge a TOP belongs to, otherwise of the Drucksachen it names, otherwise of the Einzelplan in its heading. A vote takes the fields of its own Drucksachen, otherwise those of its TOP. On the reference cache 2,109 TOPs are tagged through their Vorgänge, 196 through their Drucksachen and 149 through their Einzelplan, 458 stay untagged (mostly Fragestunden, Befragungen, Wahlen and Geschäftsordnung), and 216 of 217 votes are tagged.
- Dossiers show the Politikfelder of each TOP. The week radar shows them on each row and can be filtered by Politikfeld. The votes archive shows them on each vote and can be filtered by Politikfeld, including "Ohne Politikfeld", together with the Fraktion filter; `votes/index.html?politikfeld=Migration` (repeatable) opens it filtered.
- The Daten export has two new tables, `agenda_item_politikfelder` and `vote_politikfelder` (field, rank and source of each tag), labelled as derived data, and `proceedings.sachgebiet` carries DIP's raw labels.
- Every build prints how the Politikfelder came out, by source, and names any Sachgebiet label DIP uses that the mapping does not know.

### Changed

- Store schema 5 and Daten export format 5 with 27 CSVs. A store built by an earlier version is refused with the instruction to run `--offline --repersist`.
- An online build fetches the DIP Vorgänge and Drucksache numbers the tags need into `data/dip-vorgang-cache.json`, paced at about 1.5 requests a second so DIP's edge does not block the API. The first fill of the reference archive (about 2,400 numbers) takes about 45 minutes; later builds fetch only what is new. Offline builds use the cache as it is; a TOP or vote whose input is missing from it is stored as `not_fetched` and shown without a tag.
- `--offline --repersist` refuses to run when the Vorgang cache would leave more TOPs or votes without their tags than the current store has (a missing, emptied or partly restored cache), and names the fix: run an online update first.
- A DIP answer that is not JSON (a bot-challenge page, a cut-off body) is retried like a dropped connection, and a list answer of the wrong shape fails with a clear error instead of a traceback.

## [0.19.1.0] - 2026-10-19

### Fixed

- CDU/CSU is visible in dark mode. Its party colour was near-black on dark surfaces, so its Fraktion bars, stacks and dots all but disappeared; it is now light grey in dark mode and unchanged in light mode.
- In dark mode, navigation links highlight on hover again, and the current page keeps its highlight while hovered.
- No text on the Wochenübersicht is smaller than 12px: badges, the "Wer sprach" legend and the Wochenpuls labels moved up from 11px, and the "Wer sprach" column is wider so the legend wraps less.
- Headings on the Wochenübersicht break into balanced lines instead of leaving one word alone, and the sitting chips keep a space between date and protocol number.
- On touch screens the Wochenübersicht's buttons, sitting chips, section links, "Sitzungsbelege prüfen" and the "Debatte im Protokoll öffnen" links are at least 44px tall.

## [0.19.0.0] - 2026-10-18

### Changed

- A Drucksache is identified by its issuer (Bundestag or Bundesrat) and its number, not by its URL. A DIP URL rewrite no longer creates a new document, and Bundesrat numbers no longer collide with Bundestag numbers. On the reference cache the store holds 7,952 documents instead of 7,956 (5,749 Bundestag, 2,203 Bundesrat): four numbers had a second, wrong or malformed URL (20/11710, 20/13328, 21/1060, 21/1061), and each now keeps the URL that encodes its number. Junction links, grouping, person keys, roster bindings and facts are unchanged.
- Store schema 4 and Daten export format 4. A store built by an earlier version is refused with the instruction to run `--offline --repersist`; every document id is minted once more, so document receipts in the facts change id once.
- The Daten recipes r1 and r3 name each person from the same row the Personenseite uses (roster row, then speaker row): 496 r1 names, 16 r1 parties and 25 r3 labels change on the reference cache, and one Personenseite heading changes.
- A repeat offline rebuild of the reference cache takes about 245 s instead of about 300 s.
- Nothing is written inside the published output while a build runs: the staged store, the writer lock, the facts write and the Daten export's scratch files live in a private directory beside the output directory (`.OUTPUT.private/`). A failed export leaves the published files as they were.

### Fixed

- Removing an applied partition (for example Föhr/Mende) from the corrections file is refused instead of silently giving one speaker the other's profile.
- An incremental build groups persons the same way a fresh build does after a roll-call profile link is corrected; a record with two contradicting abgeordnetenwatch ids gets no profile instead of whichever sorts first; reviewed merges no longer depend on file order.
- DIP persons without an id are skipped with a warning instead of all sharing one “Unbekannt” person. DIP person ids written as 7, "7" or " 07 " are one person.
- An agenda index given as text ("3") is the same item as 3 everywhere: in the store, in page anchors and links, in bill pages, in summary reuse and when re-reading cached XML. A malformed, missing or repeated index in a cached report is refused with a message.
- `--offline` over a store that cannot be opened, or a data pipeline that fails in SQLite or in the staged write, ends with one `error:` line and exit 1 instead of a traceback; the store is left as it was.
- Person pages are never written through a symbolic link, and a page directory that resolves outside the output directory is refused.
- On the same sitting day, the first-speech fact orders protocols by number (21/9 before 21/10), and vote receipts list Drucksachen in number order.

## [0.18.0.0] - 2026-10-14

### Added

- Find a Gesetzesvorhaben by title or Drucksache number, narrow the list to the year of its latest recorded activity, and sort it by newest, oldest or title. The list shows 20 entries per page, keeps search, year, sort and page in the URL so Back and shared links restore the view, and announces result counts to screen readers. Without JavaScript, or if the script fails, every entry stays readable; printing always includes the whole list.
- Open each recorded speech of a speaker straight from a bill page: one speech gets a direct “Rede lesen” link, several get a dated list with sitting and page. The link opens that speech in the sitting dossier and scrolls to it.
- Parliamentary terms on bill pages (Drucksache, Plenarprotokoll, Tagesordnungspunkt, Beratungen, Beschlussempfehlung und Bericht, Stellungnahme and others) explain themselves on hover or keyboard focus and link to a new “Parlamentarische Begriffe” section on the sources page, each with its official Bundestag source.

### Changed

- The bill overview is a plain, readable list: one title link per bill, its latest recorded step and date, and counts of documents, debates and roll-call votes. The browser-only “Folgen” marker, its counter and the summary boxes are gone.
- Bill pages read in a fixed order — Verlauf grouped by date, Debatten, Rednerinnen und Redner, Abstimmungen, Dokumente, Quellen und Daten — with section links at the top. All speakers are listed (twelve shown, the rest behind “Weitere Rednerinnen und Redner”) instead of only the first twelve. Bundesrat papers are labelled “Bundesrat-Drucksache” rather than as Bundestag Drucksachen (2,047 of 4,627 bill documents on the reference cache).
- Sitting dossiers no longer overflow phone screens: long compound words in headings, metrics and speech text wrap and hyphenate.

### Fixed

- Speech counts on bill pages count each speech once. A bill whose agenda item appeared under several DIP positions counted that item's speeches once per position. On the reference cache the total falls from 11,726 to 9,274 speeches and from 49,528,541 to 37,448,236 characters across 53 of 562 bills; the Haushaltsgesetze move most (2024: 984 → 307, 2025: 974 → 309, 2026: 886 → 280). No speaker row is added or lost.
- The latest step of a bill is the parliamentary step, not the sitting's Plenarprotokoll recorded on the same day: 156 of 562 bills previously showed “Plenarprotokoll” and now show their Beratung (95 “1. Beratung”, 49 “2. Beratung”, 12 others). No latest date changed.
- Bills that share a date keep the same order before and after the page's script runs, and in print.
- Debate rows label Zusatzpunkte and Einzelpläne as such instead of “Tagesordnungspunkt Zusatzpunkt …”.
- Search finds titles regardless of how an umlaut is encoded.
- Each bill's raw source data lists a repeated agenda item once (1,075 → 895 items on the reference cache).

## [0.17.1.0] - 2026-10-09

### Fixed

- A speaker who is printed under several names or parties in the protocols (a Fraktion switcher, a name with and without a title) now gets the same person page, name, party and biography whichever sitting is processed last. Before, the last sitting decided, so a rebuild in another order could group the same speaker differently. On the reference cache this joins 21 pairs of speaker and roster records that the old order had left split, among them former Linke members now in the BSW Gruppe, Wagenknecht, Hunko, Helferich, Spaniel and Seitz; 23 roll-call records of party-switching members stay unattached to their person instead of being attached by chance (3,095 persons become 3,094). No published count of Reden per Fraktion or per Sprechrolle, no page and no fact moved.
- A person whose record is listed in the Abgeordnetenkader keeps the title, Wahlperioden and function from that list. A value cached in an older dossier no longer wins just because it sorts first.
- A roll-call record printed under two parties attaches to a roster or speaker person only when exactly one of them matches, and two roll-call records that voted in the same roll call, or whose profile links disagree, never attach to the same person through different parties. The result no longer depends on the hash seed of the Python process.
- A speaker's two Redner-IDs that share one abgeordnetenwatch profile now both link the person page; before, only the one persisted last did.
- The name shown for a person prefers the plain printed form over a “Nachname, Vorname” roll-call form or a DIP title with its “, MdB, Partei” tail.

## [0.17.0.0] - 2026-10-07

### Changed

- Open the latest generated sitting directly from the homepage, alongside a separate weekly overview with dates and coverage labels. A pinned historical week keeps its own period while the latest sitting stays current.
- Find the public areas through concise homepage sections, replacing the introductory cards, archive counters and principles.
- The weekly view is now named “Wochenübersicht”. Below 1024 px, secondary navigation sits under “Weitere Bereiche”; keyboard focus stays visible when the layout changes.

## [0.16.0.0] - 2026-10-06

### Added

- Compare speech classifications across cached XML and historical counting rules with a read-only audit, including source hashes, unresolved turns and count changes.

### Fixed

- Offline replay recognises source-backed question permissions, renewed consent and corrected recipients while preserving refusals and keeping named and faction permissions separate.
- Procedural exchanges no longer inflate speech counts. Split replies and explicitly resumed speeches retain their native speaker, text and identity, with excluded or merged turns preserved as diagnostics.

## [0.15.1.0] - 2026-10-05

### Fixed

- Offline replay retains nested Zwischenfragen when the main speaker or chair interrupts, or when an explicit grant or acknowledgement supplies the evidence. Multi-speaker grants apply only to the named askers; refusals and unrelated later speakers do not inherit consent.
- Cached reports and stores made under earlier counting rules require a fresh `--offline --repersist` rebuild before their counts are used. Stale-rule diagnostics describe older classifications accurately and request `--fetch-xml` only when XML is missing.

## [0.15.0.0] - 2026-10-05

### Added

- Read nested Zwischenfragen and explicitly written submissions as separate Beiträge, with their own text, speaker and source links. Written submissions without a proven Tagesordnungspunkt appear with the sitting; they do not count as delivered Reden.
- Rebuild cached reports with `--offline --repersist` under the current counting rules. Facts, exports and store-backed pages refuse older rule provenance and name the rebuild needed to refresh it.

### Fixed

- Historical Befragung and Fragestunde sources now use the role printed on each occurrence, recognised headings and explicit question/answer evidence. Unresolved or contradictory source evidence rejects the affected sitting instead of silently counting it as a Rede.
- Kurzintervention classification distinguishes grants from refusals and closing announcements, while read-out questions receive an asker only when the sitting's source evidence identifies one uniquely.
- Cached replay proves each TOP association before carrying votes or enrichment forward, checks paired XML hashes, and leaves accepted outputs intact when source matching fails.
- Vote receipts take their sitting id, document number and date from one authoritative source row, including when duplicate or stale links exist.

## [0.14.0.0] - 2026-10-04

### Added

- Names in dossier roll-call member lists now link to their Personenseite, where you can follow the person's votes and speeches. Members without an internal match keep their Bundestag profile link, or their plain name when no profile is available.

### Fixed

- Vote records printed surname-first now join their roster or speaker identity when the match is unambiguous. Conflicting ids, ambiguous namesakes and distinct people in the same roll call remain separate; vote-member occurrence ids stay unchanged. On the 285 cached sittings, 147,971 of 154,015 stored member rows now resolve internally, producing 166,656 working member links.
- Personenseiten prefer roster and speaker biography over vote-list attributes, and correctly label a Bundestag profile fallback.

## [0.13.0.0] - 2026-10-03

### Added

- Kurzinterventionen, Erwiderungen, and the Fragen and Antworten of the Befragung der Bundesregierung and the Fragestunde are now stored as their own Beiträge, typed by kind, in a new `contributions` table and CSV (24 CSV files now; export format 3). Each Beitrag has a stable text id and its speaker is bound in the person registry like a Rede's. Each dossier shows them beside its Reden, a Person's page shows them apart from their Reden, and the week radar reads “2 Reden, 59 Fragen, 55 Antworten” for a Befragung. The Fragestunde, which has no `<rede>` elements and stored nothing for 75 of 76 sittings, is read from its flat turns.
- Change what counts as a Rede without fetching anything again. Every online update now keeps the sitting's Plenarprotokoll XML in `data/xml/`, and `--offline --repersist` re-reads Reden and Beiträge from it. `--fetch-xml` downloads the XML for sittings cached before this release (public bundestag.de files, about 0.3 s each).
- A build that writes the store re-reads a cached report from before this counting rule from its cached XML, and refuses to persist one it cannot re-read, naming it and the fix, so old and new Reden counts never mix in the store. A build that persists nothing warns instead.

### Changed

- Only Reden count as Reden. On the 285 cached sittings the Reden count falls from 34,775 to 25,800 (DIP's own count is 26,396) and the characters of all Reden by 6.1 %. The Bundesregierung's Redeanteil falls from 14.6 % to 4.6 %; CDU/CSU 22.2 to 24.8, SPD 17.7 to 21.2, AfD 14.6 to 15.2, Grüne 13.5 to 14.5, FDP 7.4 to 8.5, Linke 6.9 to 7.4. The opening reports of a Befragung stay Reden. The five Fakt der Woche metrics that count Reden are at version 2.
- Kurzinterventionen are detected from the Sitzungsleitung's wording, and the parser compares them and the Erwiderungen per sitting with DIP (638 of 682 and 583 of 646 overall, 57 of 285 sittings differ). Detection prefers precision, so some Kurzinterventionen still count as Reden.
- A cached report with a Befragung or Fragestunde heading is never ranked as a week topic, also when the report was made before this release.

### Fixed

- A Befragung or Fragestunde whose heading the Bundestag XML sets in a different paragraph class (20/143, 20/159) is recognised: 212 Fragen and Antworten no longer count as Reden and 67 Fragestunde turns are stored.
- A Kurzintervention the Sitzungsleitung asks for with “Sie möchten eine Kurzintervention machen? – Bitte schön.” (20/112) is now recognised, and a remark that closes one (“Damit ist die Kurzintervention beendet”) no longer turns the next Redner's Rede into one.
- A Fragestunde question the Sitzungsleitung reads out is credited to the MdB only when the announcement contains their whole surname, not a longer name that contains it. Fragestunde turns whose speaker marker names no MdB and no official are counted in `fragestunde_unplaced_turns` of the validation summary instead of vanishing. (No cached sitting has one, and the surname rule moves no real row.)
- An online update caches the sitting's XML only when it keeps the report. A failed vote scan that keeps the cached dossier no longer leaves revised XML beside the old report, and `--offline --repersist` drops an AI summary whose cited Reden the re-read changed.
- A sitting week with only Fragestunde turns lists them in the “Außerdem” line of the week radar instead of only saying that no Reden were extracted.
- The export format is now `2` (`export_format` and the distribution copy's `user_version`): it added `contributions.csv.gz`.
- `--offline --repersist` now also refreshes each agenda item's heading, Drucksachen and page range from the cached XML, so a repersisted store shows the same headings as an online build. Before, the 16 items whose heading sits in a `T_ZP_NaS` paragraph (Befragung, Fragestunde, an Eidesleistung and 12 Zusatzpunkte) kept an empty heading. On the cached sittings the only matching change is that the Eidesleistung of 20/159 now picks up its Wahl position.
- A Rede after a Kurzintervention is an Erwiderung only when the same Redner gives it. Fifteen real Reden, including a maiden speech that the “erste Reden” Fakt needs, had been filed as Erwiderungen.
- `--offline --repersist` refuses cached XML that is not the protocol of its sitting (a maintenance page, another sitting, no agenda items), names the file, and leaves the store untouched. It no longer marks such a report as current. The profiles resolved online survive the re-parse.

## [0.12.0.0] - 2026-10-02

### Added

- Every published row has a stable, source-derived id, and every person a durable key that survives rebuilds: a link to a speech, a vote or a person page still points to the same thing after the next build.
- Person pages at `abgeordnete/<person_id>.html`, with redirect pages for keys a merge retired, and dossier, bill and fact links that follow the speech occurrence to the right person.
- Reviewed corrections in `scripts/person_corrections.json`: partitions for a Redner-ID that two people share, and merges with an optional survivor. Alexander Föhr and Dirk-Ulrich Mende, who share Redner-ID `11005304`, now have separate pages (13 speeches / 51,884 characters and 9 / 42,000, previously one person with 22 / 93,884). Protocol pages and bill tallies show the reviewed speaker; the cached dossier JSON keeps the printed one as source evidence.

### Changed

- Build-store schema 3 and export format 2 use text entity keys; facts and recipes read the persisted person of each record. Receipt identity no longer depends on presentation position.
- Old stores are upgraded only by an explicit `--offline --repersist`. A rebuild carries the person registry forward, requires the cached evidence of every stored protocol, holds one writer lock, recomputes facts once and validates integrity and foreign keys before the database is swapped in atomically. A full 285-report rebuild takes about 150 s instead of about 300 s.
- Name-based person matches are recomputed on every build, so an incremental and a fresh build group records identically (checked on the 285-report reference cache: grouping unchanged, 3,386 persons).
- `--offline --no-persist` renders without reading the store, and a store that is not a database ends with an error line instead of a traceback.

### Removed

- `persist_dip_pulse_store.py` no longer writes a single report into an existing store; it names `--offline --repersist`, the one write path that reconciles persons correctly.
- Occurrence assignments and splits in `person_corrections.json` are refused until they are redesigned; no shipped correction used them.

## [0.10.0.0] - 2026-09-30

### Added

- See every fetched roll-call vote in its sitting, even when no agenda item can be assigned. Unambiguous title matches link votes to their topic; unmatched votes appear under “TOP nicht zugeordnet” and remain in the archive, member histories, facts, and data export.
- Read the Antrag outcome and faction positions when a vote concerns a recommendation to reject it, with an explicit “Ja = Antrag ablehnen · Nein = Antrag annehmen” explanation and retained source evidence.

### Changed

- Special-majority procedures remain unknown without an attributable official result. Ordinary votes retain the Ja/Nein rule, and raw vote counts remain unchanged.
- Vote acquisition completeness now measures scans and successful detail fetches independently of topic assignment. Existing stores migrate sitting links and interpretation fields without losing votes.

### Fixed

- Conflicting or negated recommendation evidence no longer reverses the displayed outcome. Results derived from counts use the voted proposition’s scope when official text cannot establish an outcome.
- Fresh profile resolution updates vote members instead of silently keeping stale cached links.

## [0.9.0.0] - 2026-09-29

### Added

- Apply stored-value corrections to every cached sitting without network access using `--offline --repersist`. The rebuild preserves the MdB roster, leaves the previous database untouched on failure, and keeps the file when its content is unchanged.
- Compare two builds with a read-only report showing changes in speech text, vote majorities, affiliations, person pages, legislative pages, and published facts. Shared-sitting and whole-store modes keep new acquisitions distinct from corrected values.

### Fixed

- Speech lengths now include only the named speaker’s words, excluding the chair and intervening speakers. Unattributed text is measured separately.
- Parliamentary groups and factions use consistent names, including the historical Gruppe Die Linke; duplicate speaker names and merged source records are handled consistently.
- Government, Bundesrat, and other official speaking roles count separately from factions. Unknown roles stop persistence with a diagnostic naming the affected speeches.
- Vote majorities are absent on a tie or when nobody voted. Vote panels, archive filters, and dissent counts use the same rule; non-attached members are excluded from faction dissent.
- Person pages use verified identifiers and unambiguous name matches, keeping namesakes and conflicting DIP identities separate while rejoining corroborated records for people with two speaker IDs.
- Only legislative procedures receive Gesetzesvorhaben pages; other procedures on the same agenda item (Entschließungsanträge, Anträge) are listed on each Gesetzgebung’s page as such, not as its companions. Public labels and the data-correction recipes now describe these rules.

## [0.8.0.0] - 2026-09-29

### Added

- An update now fetches roll-call votes by default. Until now they were an opt-in, so every update since June recorded votes as "not requested" and the July and September 2026 votes never reached the site. `--no-votes` skips the scan for one run. Backfilled into a copy of the reference store, votes went from 217 to 232 and the newest vote from 2026-06-12 to 2026-09-25.
- Every build now says what is incomplete: the weeks and months that cannot post a Fakt yet, the sittings DIP lists that are missing or not fully acquired, why, and the exact command that fixes it. `--backfill-incomplete` acquires exactly those sittings and keeps every other cached dossier.
- A Fakt week or month that is held back names the sitting that is missing ("unvollständig erfasst: Sitzung 21/96 (2026-09-24) fehlt").
- The build logs how many roll-call list pages and vote pages each sitting needed, and the sittings of one build share the list pages.
- The repository now carries a domain glossary (`CONTEXT.md`) and decision records (`docs/adr/`) that define the terms the site uses (Sitzung, Dossier, Rede, Fakt, completeness and more), and why a Kurzintervention is not counted as a Rede.

### Changed

- A week or month is now complete only when every sitting DIP lists for it is in the store and fully acquired. Before, a sitting whose dossier failed or was never built was invisible, so a period could look complete on one of three sittings. On the reference copy this withholds the weeks and months that lack sittings (for example June 2026, which had been measured on 3 of 6 sittings), and 15 sittings whose roll-call votes match no agenda item stay incomplete until the match rule improves.
- A vote acquisition is complete only with evidence: the scan passed the sitting's date, no request failed, every listed vote found its agenda item, and the report records how the scan ended. Older reports without that record are re-acquired by the backfill.
- Every online build fetches the whole DIP catalog (checked against DIP's own count) and keeps every cached dossier. `--limit` and `--document-number` now narrow only which sittings are refreshed, never what the site and the store keep.
- A vote scan that fails for a network or server reason keeps the sitting's cached dossier instead of replacing it.
- Roll-call and XML page requests retry a transient network error; a reset while reading a DIP response no longer ends a long build.
- The README documents the backfill recipe, a scratch-directory preview, and the order in which config files, environment and flags decide which enrichments run.

### Fixed

- A Drucksache reference with a foreign URL no longer aborts the build (a cached 2022 dossier quotes a syriahr.com article).
- Cached reports and the catalog are written atomically, so an interrupted build cannot leave a truncated file.

### Removed

- `--preserve-existing-dossiers`. Every build keeps the dossiers it has cached; delete a dossier's JSON file to drop it. A systemd unit or script that passes the flag must drop it.

## [0.7.0.0] - 2026-09-28

### Added

- Every roll-call vote panel now shows whether the motion passed. The badge reads "Angenommen" or "Abgelehnt", sourced from bundestag.de's own stated result when the page states one, or otherwise computed from the vote count and marked "(berechnet)" so the difference is visible on hover.
- Every Drucksache a vote panel mentions now links to its source document instead of showing plain text, and a link to the vote's XLSX Namensliste export appears next to the detail link when bundestag.de has published one.
- A new "Abstimmungen" page lists every roll-call vote across every sitting the site has built, reverse-chronological and grouped by month, with a Fraktion filter (by that Fraktion's majority position on each vote).

## [0.6.6.0] - 2026-09-26

### Added

- The dossier sidebar now marks the TOP you are reading. The highlight follows scrolling, sidebar clicks, resizes and the end of the page, keeps the marked row in view inside the ranking list, and turns off where the sidebar sits above the text (narrow or short windows) and in print.
- Each SQL recipe on the Daten page has a "Kopieren" button. Where the browser cannot write to the clipboard, the button selects the SQL for ⌘C/Strg+C instead; a copy that fails late never overrides a newer click or your own selection. Without JavaScript the button stays hidden.
- Dossier footers link to the Daten page when the build has data to show, like the other pages' Daten links.

## [0.6.5.0] - 2026-09-25

### Changed

- When sitting counts differ, the Wochenvergleich now compares speeches, agenda items, speech text, and Fraktion speaking shares across weekdays present in both weeks. The page names those weekdays and keeps `n/a` when none overlap.

### Fixed

- The Wochenpuls sparkline now identifies its full-week trend when the figures above it use matched weekdays.

## [0.6.4.0] - 2026-09-25

### Changed

- The architecture diagram now traces Fakten, the Daten export and generation manifest through to the Daten page. A short contributor guide links the test, offline rebuild and online update commands.

### Fixed

- Command-line scripts now reject Python versions below the documented 3.11 floor with a clear English and German error.

## [0.6.3.0] - 2026-09-25

### Fixed

- Aufmerksamkeitsrang rows now begin with the agenda topic instead of procedural wording, keeping the first sub-item's topic on a bundled heading (an Antrag under a) followed by a Gesetzentwurf under b)); the complete normalized heading remains available on hover.

## [0.6.2.0] - 2026-09-25

### Fixed

- Ranking links retain matching TOP anchors when an index contains HTML-sensitive characters.
- Links share teal visited states and visible keyboard focus outlines, including pages without their own teal palette variable.

### Removed

- New stores and speech writes no longer duplicate speech text in `paragraphs_json`. Existing stores drop the column on SQLite 3.35+; older versions log a warning and retain it. Distribution downloads keep the same schema and row counts.

### Verified

- Dossiers already show the session title above the content and place the protocol developer dump after it. Regression coverage preserves both; explicit developer builds retain their existing visible raw data without a toggle, while normal builds omit it.

## [0.6.0.0] - 2026-09-24

### Added

- A new "Fakt der Woche" page series shows one standout, statistically unusual fact per sitting week (and, monthly, per calendar month): the closest vote, the most rebel votes against a Fraktion's line, the longest debate and longest single speech, the longest sitting, the most first-time speeches, the most active MP of the month and the month's most-discussed legislative matter. Every card names its comparison population and links straight back to the protocol, speech, vote or bill it cites; a Methodik page explains the rule and why some weeks post no fact at all (the numbers only qualify once they're unusual enough, not merely "the most" of a slow week). A new "Fakten" entry joins the site's main navigation.
- Each fact ships as a downloadable, shareable image card alongside its page — the longest-speech card now also names the debate's topic, not just who spoke.
- The Daten export documents the three new fact tables and the speech-time Fraktion column as derived/DIP-sourced data respectively, so a downloaded copy of the database is self-explanatory about where every column comes from.

### Changed

- The "Redeanteil nach Fraktion" export recipe now groups speeches by the Fraktion the speaker belonged to at the time of the speech, not their current party — a member who has since switched or left a Fraktion no longer retroactively changes an earlier week's speech-share numbers.
- Building the Fakt der Woche pages resolves each fact's source citation once per build instead of twice, and stops re-scanning the whole debate-topic table once per citation — the archive keeps rebuilding at the same speed as it grows week over week.

### Fixed

- Merging a duplicate party record (the historical "list-repr" party-name bug) now recomputes which side of a vote was the majority from the merged tallies, instead of leaving a stale majority that could misclassify who voted with or against their Fraktion.
- A citation whose page reference has no quadrant marker — a normal, common case in the protocol XML — now resolves correctly instead of being wrongly treated as an unrecoverable source.
- A sitting week with genuinely zero first-time speeches now counts correctly toward the "most first-time speeches" metric's history, instead of being silently dropped and skewing how surprising later weeks' counts look.
- Building the site with `--no-persist`, or before the Fakt der Woche data has ever been generated, no longer deletes a previous real build's published fact pages and cards, or overwrites the fact archive with a false "nothing published yet" message.

## [0.5.0.0] - 2026-09-19

### Added

- A deterministic, zero-credential demo now builds the official Plenarprotokoll 21/84 TOP 32 a/b acceptance case offline, validates the deployable artifact, and links all 16 speeches plus Drucksachen 21/6354 and 21/4833.
- Publications now carry a schema-v2 data-state manifest and a reader-facing Datenstand section that distinguish unavailable, partial, genuine-empty, reused, and not-requested data.
- Operators can inspect acquisition capabilities and resolved configuration without network access through `--list-capabilities` and `--explain-config`; development views are isolated from deployable output.

### Changed

- Every visitor now receives the same complete public experience—Aktueller Puls, Sitzungen, Gesetze, Abgeordnete, and Quellen—without a gear menu, feature switches, or hidden building blocks.
- AI summaries are the only content preference: valid summaries are expanded initially, clearly labelled as AI-generated and not editorially reviewed, globally collapsible, source-bound, citation-checked, and omitted cleanly when unavailable.
- `--enrich` now controls only optional acquisition of votes, abgeordnetenwatch profiles, and the full MP roster; deprecated feature inputs remain translating aliases through `0.5.x` and are scheduled for removal in `0.6.0`.

### Fixed

- Public source links now require allowlisted HTTPS hosts, generated paths are confined to the publication root, and CI rejects developer-marked or incomplete publication artifacts.
- The fixed public experience remains intact on the week-radar and Daten pages after integrating the latest `main` releases.

## [0.4.0.0] - 2026-09-19

### Added

- The "Daten" page (`database.html`) replaces the sample-row explorer with a download page: one click gets the gzipped SQLite distribution copy or any of the 16 CSV tables, each with its size and full sha256; a Datenstand band shows how many catalog protocols are covered as dossiers and which Bausteine (roll-call votes, abgeordnetenwatch profiles, MdB roster) the file contains; five SQL "Rezepte" run at every build against the very file offered for download, with their result rows shown next to the SQL and linked to the MP, protocol and bill pages; a "So geht's los" section gives three copy-paste routes (shell, Python stdlib, pandas); every table's columns, keys and foreign keys are listed in compact schema rows with a data dictionary that marks which source each column comes from.
- The distribution copy is built by `export_distribution_data()`: `speeches.paragraphs_json` (a duplicate of `speeches.text`) is dropped, `mp_canonical` maps every `mps` row to its consolidated person, and a `datenstand` table plus `PRAGMA user_version` mark the file as a distribution copy. Export needs SQLite ≥ 3.35; older builds render the page with a "Daten nicht erzeugt" notice naming the reason. Files are deterministic (gzip without timestamps), so unchanged inputs give byte-identical downloads; the export is skipped when nothing it depends on changed (store, recipes, export format, tag, licence, issues URL, coverage counts, Baustein readiness), re-run with `--force-export`, and skipped entirely when `--data-manifest` overrides it. Each export writes a fresh `data/exports/g-<hash>/` generation and removes the previous one only after `datenstand.json` points at the new one; concurrent builds are serialised by `data/exports/.lock`, and a lock left by a crashed build is cleared automatically.
- New CLI flags `--data-base-url`, `--data-manifest`, `--force-export`, `--data-license`, `--data-issues-url` with `BUNDESTAG_PULSE_DATA_*` env fallbacks (CLI beats env beats default); a `--data-manifest` URL is an explicit opt-in fetch (10 s timeout, 32 MB cap) that `--offline` refuses; an override manifest is shape-checked before rendering and the issues URL must use `https://`, `http://`, `mailto:` or a site-relative path. Documented in `docs/project-documentation.md`; the licence wording lives in `docs/data-license.md` (still pending).
- `persist_dip_pulse_store.connect()` refuses to open a distribution copy as a build store.

### Changed

- Nav label and every "Datenbank"/"Datenbank erkunden" mention across `index.html`, `overview.html`, `api-sitzungen.html` and `sources.html` renamed to "Daten"; the index page's two SQLite-download/explorer cards merge into one "Daten" card with a "Stand … · N Protokolle" line; the SQLite download link on every page now points at the distribution copy instead of the build store, and the in-page "Daten" links appear exactly when the page has content.
- `collect_abgeordnete()` returns a third value, `canonical_by_mp_id`, mapping every `mps.id` (not only page-eligible ones) to its consolidated person.
- `sources.html` gains a "Lizenz und Weiterverwendung" entry (`#lizenz`) that the Daten page links to; the wording is a placeholder until the data licence is settled.

### Fixed

- SQLite errors while building the distribution copy (locked store, full disk) surface as a named `error:` line instead of a traceback.

### Known stale docs

- `docs/bundestag-puls-architecture.html`/`.json` omitted the Daten export step and the Daten page; regenerated in 0.6.4.0.

## [0.3.0.0] - 2026-09-18

### Added

- `puls.html` is a week radar now (`docs/designs/puls-wochenradar.md`): the page header names the newest sitting week (or `--week`) with one chip per sitting and a facts sentence that says whether the week is still running, how old it is and when the build ran ("Auswertung vom"); "Themen der Woche" ranks the week's agenda items by speech count, names them by their DIP Vorgang titles (an Antrag-only group lists every title at equal weight), shows the share of all speeches with a bar, who spoke per Fraktion, a "Fortgesetzt" trace when the procedure ran in an earlier week, the KI-Zusammenfassung with receipts (`summaries`), a "namentlich abgestimmt" badge (`votes`) and a link into the protocol on every row; question formats (Befragung, Fragestunde, Regierungsbefragung) and the remaining agenda items are listed under the rows with their counts.
- The Wochenvergleich band gains a "Namentliche Abstimmungen" card aggregated over the week (`votes`), keeps its cards without a comparison week (Wochenpuls and Redeanteil of the current week, no deltas), and reads "n/a" on the Wochenpuls chips when the two weeks hold a different number of sittings.
- Build diagnostics for the page on stderr: `[puls] KW 24/2026: 3 Sitzungen, 5 Themen, 1 Frageformat, 22 weitere, today=…`, plus warnings for undated sittings, a week without extracted speeches and a build date before the sitting week (README §8).

### Changed

- `--today`, `SOURCE_DATE_EPOCH` and `--week` now shape `puls.html`; two builds of the same cache with the same pins are byte-identical.

### Removed

- The old `puls.html` hero (sitting summary, fact tiles, "Quellen" row), the Themenbewegung card, the per-sitting Abstimmungsverschiebung panel and the `#bewegung` anchor. `#wochenvergleich` and `#abstimmungen` stay.

## [0.2.3.0] - 2026-09-18

### Added

- Builds can be pinned: `--today YYYY-MM-DD` fixes the build date, `--week YYYY-WW` names the ISO sitting week for `puls.html`, and `SOURCE_DATE_EPOCH` (UTC) is honoured when `--today` is absent. Both are validated on every build now; `puls.html` starts reading them with the week radar in the next release.
- A `--week` that the build cannot hold is refused before any file is written, and the error lists the sitting weeks that are available.

### Changed

- Source links taken from DIP data (PDF sources on positions, activities, the KI-Zusammenfassung receipts and the developer details, XML/PDF links on the overview and Daten pages) are emitted only for `http(s)` URLs; anything else degrades to plain text.
- Groundwork for the `puls.html` week radar (`docs/designs/puls-wochenradar.md`): topic naming across positions and mitberaten twins, a shared occurrence index for the returning-procedures card, roll-call votes counted by id instead of by attachment, and shared receipt rendering. Nothing on the site changes yet; the page itself follows in the next release.

## [0.2.2.0] - 2026-09-14

### Fixed

- The Aufmerksamkeitsrang sidebar on protocol dossiers is now fully reachable: on desktop it stays pinned while its rows scroll inside the sidebar, with a fade showing when more agenda items are below, instead of clipping the tail until the very end of the page.
- On narrow screens the ranking opens as a short index (five agenda items, three on phones) with an "Alle N Tagesordnungspunkte anzeigen" button, so the agenda list sits right below it; expanding moves focus to the first revealed item, and every agenda item links back to the ranking.
- Dossiers without agenda items or without extracted speeches show a plain notice instead of an empty ranking, and printouts show every ranking row with no controls.

## [0.2.1.0] - 2026-09-13

### Fixed

- Protocol dossiers now show Drucksachen directly below each agenda item heading and give speaker lists the full card width instead of leaving a mostly empty second column.
- Agenda items without linked Drucksachen no longer show an empty public placeholder; the developer diagnostics continue to report the missing source data.

## [0.2.0.0] - 2026-09-06

### Added

- Website Bausteine are now true per-browser preferences: every publication contains all user-facing areas, switches apply immediately, survive reloads, and default to the core-only view.
- Settings report whether optional vote, summary, profile, and roster data is available, partial, or unavailable without triggering network requests.
- `--enrich votes|aw-profiles|mp-roster|all` explicitly selects optional update-time data acquisition; summary generation remains separately protected by `--summary-mode`.

### Changed

- Offline and reduced-enrichment builds no longer remove bill or MP pages. Missing source data produces an honest empty state instead.
- Browser dependencies are resolved locally: enabling bill following enables bills, and disabling bills disables bill following.
- The old feature-selection CLI, JSON, and environment inputs are deprecated for one release. They remain accepted with warnings but no longer control published UI.

## [0.1.1.0] - 2026-08-03

### Changed

- The README is now a full setup guide. It covers prerequisites, where to get a DIP API key, the first online build a fresh clone needs, the sub-second offline preview loop for everyday work, and what to run after new Bundestag data or after pulling code changes.
- Refreshing is documented as the three separate things it actually is: reloading the browser, fetching new parliamentary data, and rebuilding the site after a code update. Each one now has the exact command.
- The flags that decide how much of your local site survives an online build are spelled out, including why `--preserve-existing-dossiers` matters and how to rebuild a site that a narrow update shrank to a single sitting.
- Bausteine are documented end to end: per-build flags, durable defaults in `features.local.json`, why an offline build cannot fetch votes or profiles, and the difference between what a build makes available and what the gear menu shows.
- New sections cover server settings, hosting the generated site elsewhere, and a troubleshooting table keyed to the exact error messages you can hit, including the empty `DIP_API_KEY=` line that silently overrides a key you passed on the command line.

### Fixed

- The project documentation no longer suggests passing `DIP_API_KEY` as a one-command prefix without saying that a copied `.env.local` overwrites it, which made the suggested fix fail with the error it was meant to solve.

## [0.1.0.0] - 2026-08-02

### Added

- A single Baustein registry now controls build availability and browser visibility for votes, summaries, abgeordnetenwatch profiles, MP pages and roster data, bill tracking, and developer views.
- Repeatable `--enable`/`--disable` flags, `--features`, JSON configuration files, `BUNDESTAG_PULSE_FEATURES`, and `--list-features` provide one configuration vocabulary with dependency resolution.
- Every generated page now includes a settings gear, an instant local visibility panel, and a link to the full `settings.html` view. A tooling manifest is written to `data/features.json`.
- Addon modules are discovered lazily through `scripts/features/loader.py` and expose shared enrich, persist, page, section, style, and script hooks.

### Changed

- The shipped default is now strict core-only: DIP fetch, sitting catalogs, protocol dossiers, and the SQLite store/explorer. Optional network and content features must be enabled explicitly.
- Global navigation and page bootstrap/runtime scripts are centralized, so nested pages derive their links from their depth and every template receives the same feature behavior.

### Fixed

- Bill pages no longer generate the broken `bills/abgeordnete/index.html` link.
- The Datenbank navigation item no longer disappears from dossier, bill, or MP pages.
- Developer-only content is hidden before first paint, and every theme toggle on a page is now initialized.

## [0.0.2.0] - 2026-07-31

### Fixed

- "Aktueller Puls" now opens on the newest sitting you have data for. Offline previews used to pick whichever dossier file sorted first by name, so the 100th sitting of the 20th Bundestag from 27 April 2023 was presented as the current one.
- The home page snapshot, the sitting overview, and the sources page now name the same latest sitting as "Aktueller Puls" instead of disagreeing with it.
- The cached sitting catalog is written newest-first, whatever order the DIP API hands it back in.

### For contributors

- Regression coverage pins newest-first ordering across the rendered pages and the cached catalog, including dossiers whose metadata is missing or truncated.

## [0.0.1.0] - 2026-07-30

### For contributors

- Project agents now automatically select the right workflow for common planning, review, QA, and shipping tasks.
- Regression coverage now protects offline preview builds that reuse legacy SQLite caches.

### Fixed

- Offline previews now open legacy SQLite caches without crashing when newer MP biography fields are missing.
