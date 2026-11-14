# Vote links (N10) and the persisted vote figures

**Status (2026-11-14):** plan only, nothing built. Covers two TODOS.md entries: "Check that vote links are right" (P1, decision N10) and "Persist or prove the vote outcome and Abweichler count" (P2, before A4 slice 2). Measured read-only on the reference store `.context/dip-pulse-site` (v0.41.0.0 replay of 2026-11-14, 718 sittings) and, where a query needs `mp_canonical`, on its distribution copy `data/exports/g-083161332932/bundestag-pulse-local.sqlite.gz`. Nothing was fetched online. The decisions the owner has to make are at the end.

Main is v0.41.0.0, schema 12, export format 18. Every PR below takes the next free numbers at ship time; on today's main that is schema 13 / export 19 for the first one.

## Part 1: check that vote links are right (N10)

### What the store holds

| Measurement (reference store) | Value |
| --- | --- |
| Roll-call votes | 619 in 260 sittings (WP 18: 149, 19: 198, 20: 187, 21: 85) |
| Links (`agenda_item_votes`) | 590 |
| Votes with at least one link | 556; 63 have none and hang on their sitting through `votes.protocol_id` |
| TOPs with at least one vote | 436 |
| Votes linked to more than one TOP | 13, with 47 links (980 and 960: 7 TOPs each; 961 and 894: 5; 979 and 898: 4; 897: 3; 781, 609, 608, 493, 319, 318: 2) |
| TOPs with more than one vote | 84, with 238 links |
| Links in either group | 271 (14 links are in both) |
| Plain links (one vote, one TOP) | 319 |
| Links across sittings or across dates | 0 and 0 |

The A3 figures in the TODO (590 / 556 / 13 / 84) hold unchanged on the reference store.

### What the rule really is

The TODO names `match_roll_call_votes` (`scripts/validate_dip_protocol.py:3355`). That function is dead code: only `tests/test_review_fixes.py:102` calls it. The live rule is inline in `enrich_with_api` (`validate_dip_protocol.py:4060`, the vote part at `:4150-4330`) and has two steps:

1. **Drucksache.** A vote links to every TOP of its sitting whose Drucksache numbers share at least one number with the vote's `document_numbers` (read from the bundestag.de list page). A TOP's numbers are those the protocol XML prints under it, plus every Drucksache of every DIP Vorgang whose position `position_matches_top` assigns to the TOP, plus the Vorgänge those positions list as `mitberaten` (`top_document_numbers`).
2. **Title fallback.** A vote that matched no TOP by Drucksache links to a TOP when `title_matches` finds exactly one TOP in the sitting whose heading or position titles match the vote title (token overlap of at least 0.65).

Recomputed offline from the cached reports, the rule reproduces all 590 stored links, in every one of the 260 sittings. The links rest on:

| Basis | Links |
| --- | --- |
| A Drucksache the protocol prints under the TOP | 174 |
| Only a Drucksache reached through a DIP Vorgang | 401 |
| The title fallback | 15 |

So two links in three rest on DIP's Vorgang closure, not on anything the protocol prints under the TOP. That is where the errors are.

### Pilot (12 votes, 32 links, offline evidence only)

Read against the protocol XML (the chair's result announcement, found by the vote's exact Ja/Nein tally) and the cached DIP Vorgang and Drucksache records. Rows and verdicts: [`vote-links-and-figures/pilot.tsv`](vote-links-and-figures/pilot.tsv). All verdicts are provisional until the review.

| Verdict | Links | Cases |
| --- | --- | --- |
| right | 10 | One link each of 960, 980, 894, 781, 493; all of 863, 805 (both title fallback), 973, 831, 438 (three random plain links) |
| wrong | 18 | Pattern A: 17. Pattern C: 1 |
| unsure | 4 | 608 and 609, both linked to two Zusatzpunkte of 19/105 through DIP Vorgänge only |

Three patterns showed:

- **A. Umbrella Drucksache (Haushalt).** Every Einzelplan TOP of a budget week prints the Haushaltsgesetz Drucksachen (21/1061 and 21/1064 in 21/24; 20/8661 in 20/150). A vote on Einzelplan 04 therefore links to all seven Einzelplan TOPs of the day (960), and the Schlussabstimmung in third reading also links to the second-reading TOP and the Einzelplan TOPs (980: 7 links, 1 right). The 10 budget votes among the 13 (318, 319, 781, 894, 897, 898, 960, 961, 979, 980) hold 41 of the 47 multi-TOP links.
- **B. One Beschlussempfehlung or Vorgang for several Vorlagen.** 608 (Fachkräfteeinwanderungsgesetz) also links to ZP 15, the Grünen bill: DIP lists the government bill's Drucksache 19/8285 on the Grünen bill's Vorgang. The protocol text has to decide which Zusatzpunkt dealt with the voted bill.
- **C. A DIP position assigned to the neighbouring TOP.** 493 (UNAMID) also links to TOP 13, the next Bundeswehr mandate. TOP 13 prints no Drucksache in the XML. It holds the UNAMID Vorgang only because `position_matches_top` accepted the position by page overlap and the fuzzy title match (both titles read "Fortsetzung der Beteiligung bewaffneter deutscher Streitkräfte …"). This is review checklist class 7, neighbour binding, one step upstream of the vote rule. A fix there also moves `agenda_item_documents`.

The likeliest error the TODO named, an amendment sharing a Drucksache with an unrelated TOP, did not show in the pilot. It is a form of pattern B and stays in the review.

**A candidate fix is not safe without the review.** "Keep only the TOPs holding a vote Drucksache no other matched TOP holds, else the title match, else all" takes the 47 multi-TOP links to 25. It fixes 894, 897, 898, 781, 961, 980 and 318. It leaves 960 and 979 alone, because the Bundestag's title ("Haushalt 2025: Geschäftsbereich des Bundeskanzleramts") does not pass `title_matches` against "Einzelplan 04 Bundeskanzler und Bundeskanzleramt"; they need an Einzelplan-number match. And it narrows 608 to ZP 15, the Grünen bill, which is probably the wrong one of the two. So the review comes first, and its verdicts become the rule's test oracle.

**Machine evidence is usable but incomplete.** The vote's exact Ja/Nein tally occurs once in its sitting's protocol for 579 votes, more than once for 7 and not at all for 33. Where it occurs once, the announcement nearby names the voted subject. Of the 590 links, the announcement names a Drucksache printed under the linked TOP for 99, a Drucksache not printed there for 179 (usually an Änderungsantrag or Beschlussempfehlung the TOP heading does not list), and no Drucksache for 284. For 28 there is no unique announcement. A second prototype tried to find the TOP each roll call was *held* in, through the footnote "Ergebnis Seite …" printed where the vote closes. It placed 179 of 619 votes, because the WP 20 and 21 XML has no page markers in the Sitzungsverlauf. It is a review aid at most, never a gate.

### What a link means (recommended, owner decision 1)

A link says: **the roll call was taken on a Vorlage that this TOP dealt with** (the Vorlage itself, its Beschlussempfehlung, or an Änderungs- or Entschließungsantrag to it). **Where the protocol splits one debate into sub-items, the link goes to the most specific one:** the Einzelplan TOP for a vote on an Einzelplan, and the third-reading TOP for a Schlussabstimmung. A link does not say that this vote alone settled the TOP.

Under this meaning the 17 pattern-A links of the pilot are wrong. Under the looser meaning, "same sitting and a shared Drucksache", they are right by definition, and the link mostly says that DIP filed two items under one Vorgang. That reading would not carry the claim in PRODUCT.md (Positioning).

### The review

**Sample.** It is about 150 review units, not 150 links:
- **S1:** all 13 votes linked to more than one TOP (47 links), one unit per vote.
- **S2:** all 84 TOPs with more than one vote (238 links), one unit per TOP. 14 links are also in S1.
- **S3:** all 15 title-fallback links (8 plain, 7 already in S2). They come from a second rule, so a random draw is not enough.
- **S4:** 50 random plain links from the 311 that rest on a Drucksache, stratified by basis (34 of 212 Vorgang-only, 16 of 99 XML-printed), drawn with a fixed seed recorded in the file.

In all: 329 links in about 155 units. If S4 finds no error, the plain-link error rate is below 6% at 95% confidence (rule of three). S4 is an estimate, not a proof, and DATA.md says so.

**Evidence per link, in this order:**
1. **Protocol text** (`data/xml/`, offline): the TOP's own section of the Sitzungsverlauf, the chair's call of the vote, and the result announcement found by the exact tally, with the Drucksachen it names.
2. **DIP** (cached `dip-vorgang-cache.json`, `dip-vorgang-drucksachen-cache.json`, the report's `api.positions`, offline): which Vorgang holds the shared Drucksache, its type and title, and how the position reached this TOP (printed number, title match or `mitberaten`).
3. **The bundestag.de vote page.** Its parsed fields are in the cached report (`title`, `description`, `vote_heading`, `document_numbers`). The raw page is not kept (TODOS "Keep the raw vote pages"). An online look, two requests per vote, only for links still "unsure" after 1 and 2, and only with the owner's OK and a stated count (owner decision 5).

**The review record: a committed TSV.** `docs/plans/vote-links-review/review.tsv`, one row per link, with a header comment holding the seed, the store and the code revision. The generator pre-fills every column except the verdict columns:

| Column | Content |
| --- | --- |
| `stratum` | S1 to S4, or several |
| `protocol`, `date`, `vote_id`, `vote_title` | the vote |
| `item_index`, `top_id`, `top_heading` | the TOP; first 120 characters of the heading |
| `basis` | `drucksache_xml`, `drucksache_vorgang`, `title` |
| `shared` | the shared Drucksachen as `number:type:Vorgang id` |
| `announced` | Drucksachen named in the tally announcement, or `-` |
| `tally` | `unique`, `several`, `none` |
| `other_tops` | the vote's other linked TOPs |
| `verdict` | `right`, `wrong`, `unsure` |
| `pattern` | `A`, `B`, `C`, a new letter, or `-` for a one-off |
| `action` | `none`, `rule`, `drop`, `flag` |
| `evidence` | source and place (XML page or quoted words under 15, Vorgang id), one line |
| `reviewer` | agent run or owner |

The key of a row is `(vote_id, protocol, top_id, occurrence of that top_id in the sitting)`; 961 has "Tagesordnungspunkt I" twice. `item_index` is informative only, because a re-parse that adds a TOP renumbers the items.

**Who reviews.** An agent fills the verdicts from the pre-filled evidence and the protocol section. A second agent, without seeing the first one's verdicts, re-reviews every `wrong` and `unsure` row and 20 random `right` rows. Disagreements go to the owner in chat, one line each. The owner sees the summary before PR C ships.

**The rule for fixing (owner decision 2).** Recommended:
- **A pattern** is an error that at least two reviewed links share, with a cause in the rule's inputs (A, B, C above). Fix it in the rule, never with entries.
- **A one-off wrong link** is removed by an entry in a reviewed list, and the vote page says so in one line: "Ein Abgleich verband diese Abstimmung auch mit TOP X; die Prüfung vom … ergab, dass sie nicht dazu gehört."
- **A one-off unsure link** stays, flagged on the vote page: "Zuordnung zu TOP X ungeprüft sicher: …" plus the note.

A known-wrong link stays out of the data, because the pre-release rule judges on accuracy alone. Only uncertainty is shown as a flag.

**The reviewed list.** `scripts/reviewed_vote_links.json`, beside `reviewed_units.json` but separate from it. That file is about Reden, and the withheld-Reden plan edits its loader. One entry per link: the row key above, a `heading_starts` prefix checked against the TOP, `decision` (`drop` or `flag`), `note`, and the review row it rests on. The loader stops the run, as `reviewed_units` does, on:
- a malformed file;
- an unknown vote or TOP;
- a heading that does not start with the prefix;
- a `drop` for a link the rule no longer makes. A stale entry must be deleted, not kept.

### DATA.md: the sentence on what a link means

Two places, both outside the sections the release-docs session edits (the Vergleich table):
- `scripts/data_dictionary.json`, table `agenda_item_votes`. Today it reads "Kennung des Tagesordnungspunkts, auf dem die Abstimmung verzeichnet ist" and "die auf diesem Tagesordnungspunkt liegt". Under pattern A that is false for 6 of 960's 7 links, so replace it, and describe the new columns `basis` and `review_note`.
- `docs/data-methods.md`, a short subsection "Abstimmungen und Tagesordnungspunkte" under "Personen und Abstimmungen". Draft, with every figure generated from the store or the review file at export, none typed in:

  > Eine Zeile in `agenda_item_votes` verknüpft eine namentliche Abstimmung mit einem Tagesordnungspunkt derselben Sitzung, unter dem der Bundestag die abgestimmte Vorlage behandelte; teilt das Protokoll eine Beratung in Unterpunkte, mit dem genauesten. Gefunden wird sie über eine gemeinsame Drucksache: im Protokoll unter dem TOP gedruckt (`basis = drucksache_xml`, {n}) oder über einen DIP-Vorgang dieses TOPs (`drucksache_vorgang`, {n}); nennt die Abstimmung keine passende Drucksache, über einen eindeutigen Titelabgleich (`title`, {n}). Sie sagt nicht, dass diese Abstimmung allein über den TOP entschied. {n} Abstimmungen haben keinen TOP und hängen über `votes.protocol_id` an ihrer Sitzung. Vor der Veröffentlichung wurden {n} Verknüpfungen von Hand gegen Protokoll und DIP geprüft: {n} richtig, {n} durch eine Regeländerung berichtigt, {n} einzeln entfernt, {n} markiert (`review_note`). Für die übrigen einfachen Verknüpfungen ist das eine Stichprobe von {n}; sie fand {k} Fehler.

The first two sentences land with PR B, where they are already true of the rule. The review figures land with PR C.

### The 85 sittings after T4

T4 fetches the votes, TOPs and links of the excluded sittings (coverage gate step 6). Their attribution runs through the same function as everything else, so if PR C has landed, they get the fixed rule from the start; if not, the next replay applies it. Then:
1. Run the review-sheet generator on the new sittings only (`--protocols` from `coverage-exclusions.json`, the ones whose reason is `awaiting_acquisition`).
2. Review all of their votes linked to more than one TOP, all their TOPs with more than one vote, all their title-fallback links, and plain links at S4's rate (16%, at least 10). Append the rows to the same TSV with `batch = t4`, together with the N8 review of the restored sittings.
3. Extract their cases into the CI oracle fixture (below).
4. The store gate refuses until every multi-TOP vote among them has a review row. DATA.md's counts regenerate.

How many votes the 85 sittings hold is unknown until they are fetched; the store has 0 on those dates.

### The gate that keeps a fixed pattern fixed

1. **CI oracle, no store needed.** `scripts/vote_link_review.py --fixture` writes `tests/fixtures/vote_links/<protocol>.json` for every reviewed sitting. Each file holds only what the attribution reads: candidate id, title and numbers; per TOP `top_id`, heading, printed numbers, linked numbers and position titles. `tests/test_vote_link_oracle.py` runs the attribution on each file and checks every reviewed row:
   - `right`: the link is made;
   - `wrong` with a pattern: the link is not made;
   - `wrong` one-off: the link is made by the rule and dropped by its entry;
   - `unsure`: the link is made and carries its flag.

   A later rule change that brings back a fixed pattern fails here. The demo fixture (`extract_demo_fixture.py`) is the precedent for committing extracted source text.
2. **Store gate.** `scripts/validate_store_gate.py` gets two checks on the real store:
   - every reviewed row's verdict holds;
   - every vote linked to two or more TOPs has a review row. New ones are rare: 13 in 556 votes today, fewer after the fix.

   TOPs with several votes are routine (amendments plus final vote) and are only sampled, not gated.
3. **Pattern unit tests** in `tests/test_vote_links.py`, one synthetic case per confirmed pattern. They run before the oracle is extracted, so the rule is written test-first.

### Files

| File | PR | Change |
| --- | --- | --- |
| `scripts/vote_links.py` (new) | B | One pure function `attribute_votes(report) -> report` (with the basis per link), lifted from `enrich_with_api`; a new module keeps out of `validate_dip_protocol.build_report`, which the withheld-Reden plan edits |
| `scripts/validate_dip_protocol.py` | B | `enrich_with_api` calls `vote_links.attribute_votes`; delete `match_roll_call_votes` |
| `scripts/build_dip_pulse_site.py` | B | Call the attribution in `reparse_cached_xml` beside `dip.interpret_report_votes`, and after the carry-forward at `:2862` |
| `scripts/persist_dip_pulse_store.py` | B, C | `agenda_item_votes.basis` (B); `agenda_item_votes.review_note` (C); schema bump each |
| `scripts/vote_link_review.py` (new, read-only) | B | Writes the review sheet and, with `--fixture`, the oracle fixtures |
| `scripts/data_dictionary.json`, `docs/data-methods.md` | B, C | The DATA.md text above |
| `docs/plans/vote-links-review/review.tsv`, `summary.md` | review | The review record and its counts |
| `scripts/reviewed_vote_links.json` + loader in `vote_links.py` | C | Drops and flags |
| `scripts/vote_links.py` | C | The pattern rules the review confirms |
| `scripts/features/votes.py` | C | The drop and flag line on the vote panel (component per DESIGN.md, checked at build time) |
| `scripts/validate_store_gate.py` | C | The two gate checks; rebase onto the withheld-Reden plan's PR B, which also edits it |
| `tests/test_vote_links.py`, `tests/test_vote_link_oracle.py`, `tests/fixtures/vote_links/` | B, C | Below |
| `TODOS.md` | B | Correct the entry: the live rule, the title fallback, the sample in units and links |

### Tests to write first

PR B (no figure moves):
- `attribute_votes` reproduces the live rule:
  - a printed number, a Vorgang-only number and a `mitberaten` number;
  - a unique title match, an ambiguous title (no link) and a candidate with no numbers;
  - the basis on each link.
- Shuffling the candidates gives the same links (class 3).
- `reparse_cached_xml` corrects a report whose stored TOP votes disagree with the rule, offline.
- The carry-forward cannot restore a link the rule no longer makes (class 2: `carry_forward` at `build_dip_pulse_site.py:2862` copies `previous["votes"]` into a TOP with none).
- `agenda_item_votes.basis` persisted for all three values; schema check refuses the old schema.
- `tests/test_review_fixes.py:102` moves to the live path's fetch-failure behaviour (`vote_fetch_errors`), since the function it tests is deleted.
- Replay on a copy of the reference store gives the same 590 links (the offline recompute above already shows it).

PR C:
- One unit test per confirmed pattern (A at least: an Einzelplan vote, a Schlussabstimmung against second reading).
- The oracle test over the extracted fixtures.
- Loader refusals for `reviewed_vote_links.json` (each case listed above) and the drop and flag effects.
- The panel renders the drop and flag lines; a dropped link is gone from the TOP's panel and from the bill page.
- Gate: refuses an unreviewed multi-TOP vote and a reviewed-wrong link that is present.

### Figures that will move (PR C) and how to report them

A link feeds more than the dossier (class 6). Replay with the README recipe "Validate a data correction" (`compare_store_values.py` already compares `agenda_item_votes`, `:152`) and report old and new for:
- `agenda_item_votes` rows: 590 now. The candidate rule alone gives 568 (47 → 25 multi-TOP links); the reviewed rule decides the real figure.
- Votes per TOP and TOPs per vote, and the 13 / 84 above.
- The vote's supplying item in `features/votes.stored_votes` (lowest `item_index` of its linked TOPs). It decides the vote panel's place and anchor. 980 moves from TOP I to TOP II, 961 likewise.
- `vote_politikfelder` rows with `source = top` (tags taken from the linked TOPs).
- Vote lists on bill pages (`bill["votes"]`, `build_dip_pulse_site.py:8081`).
- Vote facts in `facts.py` that join `agenda_item_votes` (`:204`, `:255`, `:2844`).
- Recipes r3 and r4 through `_VOTE_PROTOCOL_SQL`. These cannot move while no link crosses sittings (0 today), but check.
- If pattern C is fixed in `position_matches_top`, `agenda_item_documents` rows (`api` source) and every figure read from them: bill pages, Politikfelder by Drucksache, committee lines.

### PR split for part 1

1. **PR B: one attribution function, `basis`, review sheet.** No figure moves; replay gives 590 identical links. Schema and export bump. Size S–M.
2. **The review.** A docs-only commit or PR with `review.tsv` and `summary.md`. CC about half a day for the generator run, both agent passes and the owner's disagreements [estimated].
3. **PR C: pattern rules, reviewed list, panel line, oracle, gate, DATA.md counts.** Figures move; report them as above. Schema and export bump (`review_note`). Size M.
4. **After T4:** the review rows and fixtures for the 85 sittings, in the T4 work or right after it.

## Part 2: persist the vote outcome and the Abweichler count

### The three definitions, measured

| Comparison (all 619 votes) | Result |
| --- | --- |
| `derive.vote_outcome` against the SQL snippet in `docs/project-documentation.md:667-674` | equal on 619 |
| `derive.vote_abweichler_count` (store path, as `votes_archive_rows` calls it) against recipe `r3-abweichler` counted per vote (distribution copy) | equal on 619; 3,720 Abweichungen in both |
| `vote_abweichler_count` returns None | 0 votes: every vote has complete groups that cover its total |
| The recipe's person joins (`mp_canonical`, `representative`) drop rows | 0 |
| The dossier path (report JSON votes) against the store path, outcome and count | equal on 619 |

Outcome mix: 423 `accepted`, 176 `rejected`, 20 NULL; `inverted = 1` on 95 votes, 94 of them with scope `proposition` (outcome reversed) and 1 with `application`.

**No figure moves**, whichever way this is settled.

### Recommendation: persist both (owner decision 3)

Equality holds today only because of the data. The definitions differ on inputs the code can receive:
- **A partial group** (member Stimmen that do not add up to the group's counts, as when the bundestag.de member list is incomplete): the derive function says None for the whole vote and the panel names nobody, while the recipe counts the deviating members of that group anyway.
- **A group named `Unbekannt` with a fraction row**: the derive function skips it (`NO_ZUSAMMENSCHLUSS`), the recipe counts it (it excludes only `fraktionslos`).
- **The outcome**: the SQL returns any other `result_raw` text unchanged, the function returns None. No such value exists today.

The 85 sittings after T4 are new data, so a proof made today would have to be made again, and a gate would then hold the definitions together instead of the code. Persisting makes one definition by construction, and it is what L4 asks of a renderer from A4 slice 2 on.

**Columns** (written at persist by the derive functions, which stay the one definition):
- `votes.application_result` TEXT, `accepted` / `rejected` / NULL. The name the SQL snippet already uses.
- `votes.abweichler_count` INTEGER, NULL exactly where `vote_abweichler_count` is None.
- `vote_members.abweichung` INTEGER:
  - 1: an Abweichung;
  - 0: not one;
  - NULL: no Mehrheitsvotum to check against (the member's group is partial or has no counts, or the member is `fraktionslos` or `Unbekannt`).

**Readers:**
- The SQL snippet in `docs/project-documentation.md` becomes `SELECT application_result FROM votes`, with one sentence on how it is derived.
- Recipe `r3-abweichler` counts `WHERE vm.abweichung = 1`. The recipe's method text and the DATA.md "Abweichung" paragraph say that a partial group counts nobody.
- `votes_archive_rows` and the result badge read the columns for store votes. Dossier panels keep calling the same derive functions on report JSON until A4 slice 4 moves them onto the store. It is the same function, so it is no third definition.
- `validate_store_gate.py` checks `abweichler_count = SUM(abweichung)` wherever the count is not NULL.

**Recompute sites (class 6).** The `vote_fractions` merge in `persist_dip_pulse_store.py` (`:694-707`, which already recomputes `leading_vote` after a merge) and `derive.refile_vote_members` (`derive.py:1177`) change the inputs. Both must rewrite the three columns.

### Files and tests (PR A)

| File | Change |
| --- | --- |
| `scripts/persist_dip_pulse_store.py` | Three columns, written from `derive`; recomputed in the merge path; schema bump |
| `scripts/build_dip_pulse_site.py` | Recipe r3 SQL and method text; `votes_archive_rows` reads the columns; export format bump |
| `scripts/features/votes.py` | Badge and archive read `application_result` where the vote comes from the store |
| `scripts/data_dictionary.json`, `docs/data-methods.md`, `docs/project-documentation.md` | Column meanings, the snippet, the partial-group sentence |
| `scripts/validate_store_gate.py` | The SUM check (after the withheld-Reden plan's PR B) |

Tests first:
- `tests/test_vote_figures_persisted.py`: persist fixture votes and assert the three columns equal the derive functions for each of these cases:
  - complete groups with one deviator;
  - a partial group (count NULL, flags NULL in that group);
  - a deviating `Unbekannt` member with a fraction row;
  - a deviating `fraktionslos` member;
  - `inverted` with scope `proposition`, `inverted` with scope `application`, and `result_raw` NULL;
  - a re-filed member;
  - a `vote_fractions` merge.
- `tests/test_mehrheitsvotum.py:163` (r3): the same expectations through the new column. Add a partial-group case that now counts 0, where the old SQL counted 1. That change is on an input no current vote has.
- Archive and badge tests read the column, not the function.
- Replay on a copy of the reference store: 619 / 619 / 3,720 unchanged, recipe r3 output byte-identical.

**PR split:** one PR, size S. It is independent of part 1 and can ship first; it must land before A4 slice 2.

## Review checklist (docs/agents/review-checklist.md), applied to the plan

| Class | Where it bites | Answer in the plan |
| --- | --- | --- |
| 1 Sibling path | Attribution runs online (`enrich_with_api`), after carry-forward, on `--offline --repersist` | One function `attribute_votes`, called on all three paths; T4's fetch goes through it too. Figures: persisted at one place, recomputed on merge |
| 2 Stale beats fresh | Carry-forward `item["votes"] = deepcopy(previous["votes"])` (`build_dip_pulse_site.py:2862`) can restore a link the fixed rule drops | Attribution runs after carry-forward; test in PR B |
| 3 Order and history | Title fallback "unique in the sitting"; pattern rules over the matched set | Order-independent by construction; shuffle test |
| 4 One key, one function | Review rows and drop entries need a key that survives renumbering | `(vote_id, protocol, top_id, occurrence)` plus `heading_starts`, one function in `vote_links.py` |
| 5 Absent vs zero | `abweichler_count` NULL vs 0; `abweichung` NULL vs 0; `basis` never NULL | Spelled out per column; tests for each |
| 6 Derived columns | Links feed supplying item, tags, bill pages, facts, recipes; figures feed r3 and the badge | Listed under "Figures that will move"; merge path recomputes the figure columns |
| 7 Neighbour binding | Exactly N10: Vorgang closure and `position_matches_top` page overlap | Proof of identity: the printed Drucksache, the tally announcement; report FP/FN on all 590 before and after PR C |
| 8 Hostile text | Tally and Drucksache regexes in the review generator; `heading_starts` | Generator is a read-only tool; the loader compares prefixes, no regex on entries |
| 9 Input shape | `reviewed_vote_links.json`, generator flags | Loader refusals listed; `--protocols` validated against the store |
| 10 Interrupted run | New columns written inside the staged store swap | No new write outside the existing staging; the generator writes only its TSV |
| 11 Claims | The DATA.md sentences, recipe r3 method, the panel lines | Every figure generated from store or review file; each sentence cites its code line in the PR |
| 12 Loop cost | Attribution per sitting O(candidates × TOPs); review over 590 links; flags over 425,322 `vote_members` rows | Measured: the whole offline recompute ran in seconds; flags are computed in the existing per-vote persist loop |
| 13 Last commit | Each fix commit | At ship |

Checks no diff review replaces: PR A and PR C each need the replay with old and new values (PR A: none should move); PR C needs the browser check of the panel line at 375px and in dark mode.

## Decisions for the owner

1. **What a link means.** Recommended: the TOP that dealt with the voted Vorlage, the most specific sub-item where the protocol splits one; it does not mean the vote settled the TOP alone. This makes the pilot's 17 Haushalt links wrong.
2. **One-off errors.** Recommended: a wrong link is removed and the vote page says so; an unsure link stays, flagged. Patterns (two or more links, one cause) are fixed in the rule.
3. **Outcome and Abweichler count.** Recommended: persist both (three columns). They agree on all 619 votes today, but differ by definition on partial groups, so a proof would hold only for today's data.
4. **Sample size.** Recommended: 329 links in about 155 units (all multi-link cases, all 15 title links, 50 random plain), instead of "about 150 links".
5. **Online checks.** Recommended: none by default; ask once, with a count, for the links still unsure after protocol and DIP.
6. **Gate.** Recommended: every release refuses a vote linked to two or more TOPs without a review row.
