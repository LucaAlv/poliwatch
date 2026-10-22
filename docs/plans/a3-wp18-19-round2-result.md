# WP 18/19 round 2: rules built, re-audit, review, exclusion list (2026-10-22)

The owner's round-2 decisions ([a3-rule5-wp18-19-round2.md](a3-rule5-wp18-19-round2.md#owner-decisions-2026-10-22)) are built, one commit each, test-first. This record holds what moved, what the new-rule review found, and the exclusion list that follows. **Two questions for the owner are at the end.**

## Commits

| Commit | Rule | WP 18/19 parse (of 484) | WP 20/21 |
|---|---|---:|---|
| (before) | 6a–6d | 372 | – |
| ab5708d | R2, role spellings | 379 | unchanged |
| a2ff538 | R4, middle initial | 387 | unchanged |
| 27352f7 | R3, 6c floor wording | 393 | unchanged |
| 738aa62 | R1b + R1c, consent and offers | 411 | unchanged |
| 3a16c46 | role-less chair | 412 | 21/17 only |
| d803f96 | one Zwischenfrage per exchange; speech rules v6 | 412 | 95 sittings move |
| b372409 | R2 follow-up: the six ministry abbreviations map to the Bundesregierung | 412 | unchanged |
| ef271dd | backfill pacing (decision 9) | – | – |

- **"Unchanged"** means `units_sha` and a new `roles_sha` (speaker id, role, role_short, Sprechrolle) were identical in all 290 gate files. The harness copy is `~/agent-runs/a3/round2/parse_audit2.py`; the runs are `parse-*.json` beside it.
- **Suite:** 1429 tests, OK (2 skipped). It was 1397 before round 2.
- **Changed tests:** each was updated to the decided rule, and the reason is in its commit:
  - two 6a tests, from R1b;
  - two resume tests and the offline-v5 source tests, from per-exchange counting;
  - the rule-version assertion.

## Moved counts

**Silent miscounts fixed in sittings that already parsed (old → new):**
- **18/17:** zwischenfrage 5 → 1, rede +1. Kudla's whole Rede was a Zwischenfrage plus 4 fragments. Now it is Rede `ID1801709200:3`, and Ernst's real Zwischenfrage inside it is counted.
- **18/30:** zwischenfrage 4 → 0, rede +1 (Gehring).
- **18/39:** zwischenfrage 1 → 0, rede +1 (Strengmann-Kuhn).
- **18/94:** zwischenfrage 2 → 0, rede +1 (Dagdelen).
- **18/28:** zwischenfrage −1. The chair Singhammer's offer had been counted as his Zwischenfrage.
- **21/17 (WP 21, live data):** zwischenfrage −1. The chair Ortleb's "erlauben Sie eine Zwischenfrage …" had been counted as her Zwischenfrage.

**Per exchange (decision 8), WP 20/21:**
- 290 of 290 sittings accepted on both sides by `audit_offline_turns` against the parser of 3a16c46.
- The only change is zwischenfrage **1432 → 1246 (−186)**, in 95 sittings, for 111 of 356 MdBs.
- Per MdB, old and new: [a3-round2-zf-per-exchange-wp2021.tsv](a3-round2-zf-per-exchange-wp2021.tsv). The largest moves are Throm 24 → 16, Hoffmann 20 → 15, P. Schmidt 14 → 8 and Brandner 14 → 9.
- WP 18/19 has 228 merges in its parsing sittings.
- **Why the new figure is more correct:** a Zwischenfrage is one granted question with its continuation. The old count added one unit for every time the chair or the Redner broke into it ("Kommen Sie zu Ihrer Frage", "Was war jetzt die Frage?").

**Totals in parsing sittings (not certified counts; they include sittings that stay excluded):**

| | WP 18 before → after | WP 19 before → after |
|---|---|---|
| Sittings parsing | 166 → 201 | 206 → 211 |
| rede | 7298 → 9917 | 16370 → 16925 |
| zwischenfrage | 651 → 835 | 946 → 867 |

`speech_kinds.VERSION` 5 → 6: every cached report and store made under v5 is stale and needs `--offline --repersist`.

## Re-audit

The audit (`~/agent-runs/a3/tools/rule5/audit_all.py`, run `~/agent-runs/a3/round2/audit-484.json`) gives:
- 412 parse;
- 69 are refused at a turn, with 103 refused markers ([a3-wp18-19-round2-blockers.tsv](a3-wp18-19-round2-blockers.tsv));
- 3 stop on a role spelling outside R2's six: 18/124 ("Parl. Staatssekretär im Bundesministerium des Innern" / "… BMI"), 18/136 (BMBF), 18/173 (BMG).

Eight sittings that the audit expected the rules to fix still refuse, because their wording is outside what was decided:
- 18/210 and 19/227: the consent is longer than 12 words.
- 18/60: the Redner makes the offer himself.
- 18/82: "ermöglichen".
- 19/101 ("Gestatten Sie? – Okay.") and 19/201 ("Mögen Sie?"): the offer names no asker.
- 18/136 and 18/173: the role spellings above.

None was widened to fit.

## Review of what the new rules admit

A per-turn diff against the parser before round 2 (e13f60f) lists 422 changed turns in 163 files (`turn-diff-484.json`, `turn-changes.tsv`). Every disappeared turn sits in a file with a new 6c split. Sonnet readers checked each item in the source (brief and results in `~/agent-runs/a3/review/round2/`).

| Set | Items | Correct | Wrong |
|---|---:|---:|---:|
| Newly admitted units: Zwischenfrage, procedural, merged; plus R1 units in the role-error files | 68 | 66 | 2 |
| Merges: all 112 flagged (question or grant wording between the turns), 45 spanning more than one Redner turn, the 8 of the top WP 20/21 movers, 30 random | 195 | 194 | 1 |

**Wrong:**
- **18/26 `ID1802606600:2` m6:** Alois Karl's whole Rede after "Jetzt spricht der Kollege Alois Karl …". This word order is outside R3's forms. 18/26 stays refused.
- **18/83 `ID1808302100:2:2:2` m8, found twice:** Tempel's nested Kurzintervention ("eine ganz kurze Kurzintervention …") was merged into his earlier Zwischenbemerkung. 18/83 stays excluded.

**Borderline, judged correct:**
- 20/97 Hüppe;
- 18/190 Birkwald;
- 19/7 Ernst;
- 19/210 Huber;
- 18/243 Scharfenberg.

21/78 Paus m3 may belong to the same exchange as m4, which would mean one unit fewer. It is left split: undermerging is the old behaviour.

**The kind that proved wrong, checked in all 414 merges:** one wrong merge came from a chair-granted Kurzintervention, a kind the flag regex did not look for. So the untruncated between-text of every merge (`merges-full.tsv`) was searched for Kurzintervention, Erwiderung and erwidern. There are six hits, and only 18/83 is a grant. The others are the chair reminding the asker inside the same exchange:
- 20/109 Throm: "Sie müssen zum Ende Ihrer Kurzintervention kommen";
- 21/25 Emmerich: "keine Kurzintervention, bitte";
- 19/140 Mast, twice: "Sie sollen keine Kurzintervention, sondern eine Zwischenbemerkung machen";
- 19/231 Rosemann: "Es kann vielleicht noch die Möglichkeit einer Kurzintervention … geben".

No WP 20/21 count moves.

**6c splits, DIP Aktivitäten check (ADR 0002):**
- 63 new splits in 19 sittings, 70 in all.
- Each was matched by its printed page to the speaker's DIP activity on that page (`split_pages.py`, cache `dip-aktivitaeten-6c-r2.json`).
- DIP answered all 17 new sittings at 2 s spacing, the slowest in 0.25 s.
- **62 are a "Rede" in DIP.**
- **One is not:** 18/29 Groth `ID1802902700:2`, which DIP lists as "Mündliche Erklärung gem. § 31 GO" (2384D). R3's floor wording let an Erklärung zur Abstimmung through as a Rede, so 18/29 stays excluded (erklaerung-nested TODO).
- **18/2:** Oppermann's split is on page 55, a Rede in DIP (55B). His Geschäftsordnung statement is a different turn on 68D, so the round-1 tag "go-debate" does not hold for this split.

**Rede-shaped Zwischenfragen, re-scanned** with `floor_zf.py` and `rede_shaped_zf.py` over every parsing file:
- **18/2:** Haßelmann (4209 chars) and Korte (5099) are whole Reden still counted as Zwischenfragen, so 18/2 stays excluded.
- **18/83:** Weinberg (11401 chars), the same. 18/83 is excluded.
- **19/25 (new finding, not caused by round 2):** the XML gives `<rede>` `ID192507100` to Keul, whose Zwischenfrage opens it, and Röttgen's Rede is nested inside it (4459 chars). The parser counts Keul's Zwischenfrage as a Rede and Röttgen's Rede as a Zwischenfrage. Proposed for exclusion.
- The other new units over 2500 chars (18/39, 18/95, 18/209, 18/234) are merged exchanges that the merge review covers.

## Exclusion list: 73 → 78

**Added (9):**
- 18/60, 18/82, 18/210, 19/101, 19/201, 19/227: wording outside R1b/R1c;
- 18/136, 18/173: role spellings outside R2;
- 19/25: the swapped Rede, a new finding that needs the owner's yes.

**Removed (4):**
- 18/28, now counted correctly;
- 18/95, 18/170, 18/190, which parse and whose new units passed review.

**Kept although they now parse:**
- 18/2: whole Reden as Zwischenfragen;
- 18/29: an Erklärung split as a Rede;
- 18/83: Reden as Zwischenfragen, and a Kurzintervention merged;
- 18/245 and 19/1: presidium Reden, as decided.

The list, for `--exclude-document-number`:

18/1, 18/2, 18/3, 18/6, 18/8, 18/10, 18/11, 18/20, 18/21, 18/26, 18/29, 18/36, 18/42, 18/43, 18/50, 18/60, 18/63, 18/67, 18/82, 18/83, 18/88, 18/89, 18/97, 18/98, 18/110, 18/112, 18/113, 18/117, 18/118, 18/124, 18/127, 18/136, 18/143, 18/158, 18/159, 18/160, 18/161, 18/171, 18/173, 18/180, 18/184, 18/193, 18/210, 18/215, 18/219, 18/221, 18/241, 18/245, 19/1, 19/12, 19/13, 19/14, 19/18, 19/20, 19/23, 19/25, 19/32, 19/36, 19/40, 19/42, 19/44, 19/47, 19/59, 19/61, 19/68, 19/92, 19/101, 19/102, 19/158, 19/170, 19/173, 19/189, 19/192, 19/193, 19/201, 19/215, 19/227, 19/239.

## Other findings

- **dserver's `18020.xml` is sitting 21.** Its `sitzung-nr` is 21, with the same date as 18/21, and the content differs slightly. The real 18/20 is not in the corpus. 18/20 is excluded. `fetch_missing_xml` already refuses an XML whose Wahlperiode or Sitzungsnummer differs from the request, so 18/21 cannot be cached twice.
- **R2 follow-up:** with the six abbreviations mapped in `SPRECHROLLE_RULES`, an abbreviation and its long form agree on the side by themselves. `effective_role` now reconciles only the bare title against its "(Land)" form.

## The exclusion list cannot exclude a sitting that parses

`--exclude-document-number` (D2) is consulted only when the parser rejects a sitting (`build_dossiers_with_progress`: the `source_rejected` branch). A listed sitting that parses is acquired and counted like any other. Six of the 78 parse: 18/2, 18/29, 18/83, 18/245, 19/1 and 19/25. A backfill would count their wrong units (whole Reden as Zwischenfragen, an Erklärung as a Rede, presidium Reden). And a role no Sprechrolle rule maps raises at acquisition whether or not the sitting is listed (pilot record, "Known limit"). So "exclude" for a parsing sitting cannot be carried out with today's mechanism.

## Questions for the owner

0. **D2's semantics.** Should a listed number be skipped before acquisition, whatever the parser says? That would carry out the six exclusions above and the proposals below. The alternative is a rule for each kind. This is not built.
1. **26 parsing sittings off the list carry a role no Sprechrolle rule maps.**
   - **Why it matters:** strict persist (`derive.check_sprechrollen`) refuses the whole run on any one of them. As the pilot record notes, an unmapped role raises at acquisition and is not passed by `--exclude-document-number` either.
   - **Official and presidium addresses,** the same kind as 18/245 and 19/1 (ADR 0004 TODO): 18/178 (Lammert), 18/223 (Bundespräsidenten, Präsidentin des Bundesrates), 19/9 (Schäuble, Präsident der Assemblée nationale), 19/19 (Präsident: oath and government formation), 19/73 (Schäuble). Proposal: exclude, as 18/245 and 19/1 are.
   - **A Vizepräsident(in)'s own Fraktionsrede printed with the presidium `rolle_lang`:** 18/46, 18/51, 18/61, 18/62, 18/65, 18/66, 18/73, 18/81, 18/85, 18/90, 18/93, 18/96, 18/99, 18/101, 18/109, 18/115, 18/116.
     - These are MdB Reden.
     - Mapping "Vizepräsidentin" to a Sprechrolle would count them for the wrong side.
     - They need a rule that reads them as the MdB's Fraktionsrede when the `<rede>` is debate (ADR 0004), or exclusion until then.
   - **Role spellings outside the decision:**
     - BMBF, BMG, BMZ (19/67, 19/106; and 18/136, 18/173 above);
     - "Parl. Staatssekretär im Bundesministerium des Innern" (18/124);
     - "Parl. Staatssekretär für Verkehr und digitale Infrastruktur" (18/211);
     - "S taatsministerin bei der Bundeskanzlerin", the split-letter defect the "B undesminister" rule already covers (19/70);
     - "Drogenbeauftragte der Bundesregierung" (18/109).

     Proposal: extend R2's closed list with these spellings.
2. **19/25:** exclude, as proposed above, or a rule for an asker who owns the `<rede>`.

## Owner decisions (round 2 result, 2026-10-22)

The owner asked for the costs before deciding. The figures come from the parse audit `parse-r2b.json`. An excluded sitting loses every unit it holds, not just the wrong ones.

| Group | Sittings | Reden in them | Wrong units |
|---|---:|---:|---|
| D2's six that parse (18/2, 18/29, 18/83, 18/245, 19/1, 19/25) | 6 | 172 | a few per sitting |
| Official and presidium addresses | 5 | 53 | the addresses |
| A Vizepräsident(in)'s own Fraktionsrede | 17 | 1,015 | 21 Reden |
| All parsing WP 18/19 sittings | 412 | 26,842 | |

0. **D2: a listed number is skipped before acquisition**, whatever the parser says. There is no report, no store row and no fetch. The number is recorded in `data/coverage-exclusions.json` the way a source rejection is. Parser rules shrink the list later.
1. **Official and presidium addresses** (18/178, 18/223, 19/9, 19/19, 19/73): exclude them, as 18/245 and 19/1 are.
2. **A Vizepräsident(in)'s own Fraktionsrede: build the rule this round.** The owner chose this over exclusion, which would have cost 1,015 Reden to keep out 21. The rule follows ADR 0004 and its boundary is exact:
   - **When it fires:** the marker that owns a `<rede>` (its first `redner`) has the role Vizepräsident or Vizepräsidentin (whitespace removed), and the marker prints a `<fraktion>`.
   - **What it does:** the unit is that MdB's Rede for the printed Fraktion. The presidium role gives no Sprechrolle.
   - **What it leaves alone:**
     - Präsident and Alterspräsident are not covered.
     - A presidium marker inside someone else's `<rede>` stays Sitzungsleitung, as before.
   - **The scan behind the boundary** covered all 484 WP 18/19 files and the 290 WP 20/21 files:
     - 24 owner markers with a Fraktion fit the rule, in 18 sittings. Three of those sittings are already on the list for other reasons: 18/110, 18/112 and 18/113.
     - 3 owner markers have no Fraktion: 18/245 Bulmahn and Singhammer, and 18/215.
     - WP 20/21 has 0.
   - **What tells a debate Rede from a presidium address:** only the printed Fraktion. The code cannot tell a debate item apart. 18/245's Vizepräsident(in) Reden carry no `<fraktion>`, so they stay unmapped, and 18/245 stays out because it is on the list.
   - **18/90 is not covered.** Pau's Vizepräsidentin marker there is a Fragestunde Nachfrage outside any `<rede>`, not a `<rede>` she owns. The rule is not widened to it. 18/90 goes on the list, and the case goes back to the owner.
3. **Role spellings:** extend R2's closed list with the eight spellings proposed above.
4. **19/25:** exclude it. Excluding it costs 15 Reden and about 200 Befragung and Fragestunde units, to keep out 2 swapped units. Revisit if more cases turn up.

## Built from the owner decisions (2026-10-22)

| Commit | Change | Result |
|---|---|---|
| 27a93d5 | D2: a listed number is skipped before acquisition | Tests: the listed sitting that parses is not counted, the one with an unmapped role does not raise, an unlisted refusal still stops the run |
| 691b4fa | The eight role spellings | WP 18/19 parse 412 → 413 |
| 5cc5982 | A Vizepräsident(in)'s own Rede counts for the Fraktion | 15 of 17 sittings: no unmapped role left |

**D2 in detail:**
- A listed number is skipped before acquisition.
- `coverage-exclusions.json` records it with the reason `excluded`, a new failure code. It no longer keeps a D4 diagnostic, because nothing is parsed.
- The coverage line now reads "nicht erfasst (ausgeschlossen)". The manifest key `coverage.source_rejected` is unchanged.
- **Known limit:** `--offline --repersist` and `--fetch-xml` read cached reports and do not consult the list. A sitting cached before it was listed would still be re-persisted. *Fixed after round 3: offline runs and `--fetch-xml` leave out every sitting the exclusion record lists.*

**Parse audit:**
- The reference store's XML stands in for the deleted gate. The parser before this round reproduces `parse-r2b.json` exactly on it.
- After all three commits, WP 20/21 is unchanged: 290 of 290 files, by status, `units_sha` and `roles_sha`. The runs are `parse-d2base.json`, `parse-sp.json` and `parse-vp.json`.

**Spellings:**
- 18/136 now parses. Its 7 Zwischenfragen and 2 merges were reviewed: 9 correct, 0 wrong (`~/agent-runs/a3/review/round3/result-18-136.tsv`). Schwarzelühr-Sutter's turn is an MdB Zwischenfrage: she is printed "(SPD)", with no government role. 18/136 leaves the list.
- 18/124 and 18/173 lose their role conflict, but now refuse at a turn ("unresolved nested contribution"), so both stay listed.
- 19/67, 19/106, 18/211 and 19/70 have no unmapped role left, and their units are unchanged.

**The Vizepräsident(in) rule:**
- **Review:** all 24 Vizepräsident(in)-owned `<rede>` elements that carry a Fraktion were reviewed. 19 are debate Reden and 5 are Befragung questions. None is an address or chair text (`result-vp-owned.tsv`).
- **Moved units, all corrections.** A Vizepräsidentin asking in the Befragung had been counted as the government's answer:
  - **18/65 Bulmahn:** befragung_antwort → befragung_frage.
  - **18/81 Pau:** befragung_antwort → befragung_frage.
  - **18/96 Pau:** two befragung_antwort → befragung_frage. The opening exchange had been counted as two Reden; it is now Pau's befragung_frage and de Maizière's befragung_antwort. Rede 15 → 13.
- **Not covered:** in 18/62 and 18/90 Pau asks in the Fragestunde, outside any `<rede>`, and is read as a fragestunde_antwort with an unmapped role. In 18/62 Singhammer's chair turn is read the same way. Both go on the list. A Fragestunde rule would be a new owner question.
- `speech_kinds.VERSION` is not bumped. Only sittings that strict persist refused before have changed.

## Exclusion list: 78 → 84

- **Added (7):**
  - the official and presidium addresses 18/178, 18/223, 19/9, 19/19, 19/73;
  - 18/62 and 18/90: a Vizepräsidentin in the Fragestunde.
- **Removed (1):** 18/136, which parses and passed review.
- 13 of the 84 parse and are kept out only by D2: 18/2, 18/29, 18/62, 18/83, 18/90, 18/178, 18/223, 18/245, 19/1, 19/9, 19/19, 19/25, 19/73.
- **Check:** every one of the 400 WP 18/19 sittings off the list parses, and every role in them is mapped. They hold 26,685 Reden.

The list, for `--exclude-document-number`:

18/1, 18/2, 18/3, 18/6, 18/8, 18/10, 18/11, 18/20, 18/21, 18/26, 18/29, 18/36, 18/42, 18/43, 18/50, 18/60, 18/62, 18/63, 18/67, 18/82, 18/83, 18/88, 18/89, 18/90, 18/97, 18/98, 18/110, 18/112, 18/113, 18/117, 18/118, 18/124, 18/127, 18/143, 18/158, 18/159, 18/160, 18/161, 18/171, 18/173, 18/178, 18/180, 18/184, 18/193, 18/210, 18/215, 18/219, 18/221, 18/223, 18/241, 18/245, 19/1, 19/9, 19/12, 19/13, 19/14, 19/18, 19/19, 19/20, 19/23, 19/25, 19/32, 19/36, 19/40, 19/42, 19/44, 19/47, 19/59, 19/61, 19/68, 19/73, 19/92, 19/101, 19/102, 19/158, 19/170, 19/173, 19/189, 19/192, 19/193, 19/201, 19/215, 19/227, 19/239.

## Pilot re-run: not run

- **Disk:** 3.2 GB free (100% used) on 2026-10-22. A v6 `--offline --repersist` of the 290-sitting store (2.6 GB, staged beside the 353 MB store; peak RSS 2.6 GB at the gate) plus a render needs more than that leaves as margin.
- **DIP:** it did not answer the first `/person` probe (a3-pilot.md, Finding 2, 2026-10-22).
- Both block step 4.
- **When it runs:**
  - pass `--sleep 2` explicitly (without `--backfill-incomplete` the default is 0);
  - pass the 78 via `--exclude-document-number`;
  - put the nearest parsing sittings with mapped roles in place of 18/245 and 19/1, whose unmapped roles would end the run.

## Owner decisions (round 3, 2026-10-22)

1. **18/62 and 18/90 stay excluded.** No Fragestunde rule.
   - **Why:** a scan of all WP 18/19 files found 5 presidium markers that print a Fraktion outside any `<rede>`, all in these two sittings: Pau's Nachfragen (3 in 18/62, 1 in 18/90) and Singhammer in 18/62.
   - Singhammer's marker has the same printed form as Pau's, "Johannes Singhammer (CDU/CSU)", but its text is chair text ("Sie, Frau Kollegin, haben mit Sicherheit eine Nachfrage.").
   - A rule reading such a marker as an MdB question would turn that chair turn into a question. Only the content tells the two apart.
   - **Cost of exclusion:** 24 Reden and 281 Befragung/Fragestunde units (18/62: 11 + 161, 18/90: 13 + 120), to keep out about 5 wrong units. This matches the 19/25 decision.
   - Revisit if more cases turn up.
2. **The three changes made without a decision are confirmed:**
   - the coverage label "nicht erfasst (ausgeschlossen)";
   - the failure code `excluded`;
   - the manifest key `coverage.source_rejected` is renamed to `coverage.excluded`.
   - **Check before confirming:** the key exists only on this branch (not on `origin/main`), so no published export carries it. The `[summary]` and D2 code paths only put listed sittings in it; an unlisted source rejection still stops the run.
   - README.md still described the old D2 behaviour ("Quelle abgelehnt", "with its diagnostic", "a listed sitting the parser accepts again is acquired"). It is corrected with the rename.
3. **Push:** not yet.
