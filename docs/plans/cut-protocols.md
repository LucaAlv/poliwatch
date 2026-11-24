# Plan: mark the 33 cut protocols incomplete

Owner, 2026-11-23: plan it, to be built before the first `--publish`. Cause and numbers: [zu-protokoll-gap.md](zu-protokoll-gap.md), `docs/source-errors.md` E16. Measured on the v0.46.49.0 replay (806 sittings), read-only. Nothing is built.

**Base:** main after v0.46.50.0 (`claude/paragraph-breaks`) is merged, with `claude/modest-boyd-90f16f` (this branch, docs only) merged or cherry-picked first. v0.46.50.0 edits the parser, `persist_dip_pulse_store.py`, `data_dictionary.json` and TODOS.md and takes export format 25. This build takes the next free numbers (expected: export format 26, store schema 16). Check both against origin/main before shipping.

## What changes

A sitting whose Protokoll XML is a first edition stays stored with its Reden, TOPs and votes. It is marked, it is not complete for speeches, and what DIP lists for the missing part is stored as a list that counts nowhere.

No stored Rede, Beitrag, vote or vote link changes: 61,137 Reden and 4,164 `zu_protokoll` stay. Fakten change.

## Decisions for the owner

**D1. Mark and keep the sitting. Decided 2026-11-23** ("Yes, plan it"). Rejected: excluding the 33 as `source_defect`, which drops 4,555 stored Reden and the 70 votes held on those days and leaves a larger hole; and naming them in DATA.md only, which leaves Fakten that claim completeness.

**D2 (open). `laengste-sitzung` gets a Completeness basis of its own (recommended).** It reads only the start and end times, which a cut file prints. Under the speeches basis the longest days would leave its own comparison: its published Fakten would fall from 92 to 67 over WP 19 to 21, and the remaining ones would compare with shorter weeks. Proposed basis `times`: the XML is parsed and has both times. Two end times need a reading first. 20/178 prints 23:11 in the XML and 23.12 in the PDF. 20/210 prints 02:19 in its head and 02:15 at its end. 20/147, 21/40, 21/83 and 21/99 agree with their PDFs. The other 27 (20/210 aside) were not compared: step 0 does it, and needs a go for 28 more PDFs (about 67 MB).

**D3. The PDF pilot comes after the release. Decided 2026-11-23.** Under D1 published Fakten fall from 590 to 531 with `laengste-sitzung` left as it is (506 without D2), and WP 21 loses the most. Basis `times` as D2 proposes it also frees the weeks that withheld Reden hold back: `laengste-sitzung` goes from 114 published Fakten to 152 (WP 18 22 to 42, WP 19 29 to 46, WP 20 43 to 43, WP 21 20 to 21), so 569 in all. On v0.46.50.0 every total is one lower (2016-W07 lost `laengste-debatte`, WP 18).

| | complete periods now | after | published now | after |
|---|---|---|---|---|
| `laengste-debatte`, WP 21 weeks | 35 of 36 | 15 | 18 | 3 |
| `laengste-rede`, WP 21 weeks | 35 | 15 | 17 | 7 |
| `erste-reden`, WP 21 weeks | 35 | 15 | 7 | 6 |
| `aktivste-abgeordnete`, WP 21 months | 16 of 17 | 3 | 7 | 0 |
| `meistdiskutierter-vorgang`, WP 21 months | 16 | 3 | 5 | 0 |
| `laengste-debatte`, WP 20 weeks | 72 of 73 | 62 | 39 | 32 |
| `laengste-rede`, WP 20 weeks | 72 | 62 | 43 | 37 |
| `erste-reden`, WP 20 weeks | 72 | 62 | 14 | 13 |
| `aktivste-abgeordnete`, WP 20 months | 38 of 39 | 31 | 21 | 17 |
| `meistdiskutierter-vorgang`, WP 20 months | 38 | 31 | 25 | 20 |

31 weeks and 20 months stop being complete. WP 21 gets no monthly Fakt at all. The withheld figures were not right to begin with, so this plan does not wait for the PDFs. The order is: build this plan, release, then the pilot on 20/147, 20/178, 21/40, 21/83 and 21/99. So the first release has no monthly Fakt for WP 21. Numbers: simulated with `facts.compute` on the unchanged store, `today` = 2026-11-23, without step 4.

## Detection

Two independent rules pick the same 33 sittings out of 806. Near misses: none for the first, 18/83 for the second (3 and 3).

"Rede" below leaves out the chair's farewells and greetings, which DIP types as "Rede" and the store never holds as one (`CHAIR` in the census; 624 in the 806 sittings). With them rule 2 would mark a whole sitting that prints the notice and has farewells (19/236, without the notice, lists 35 Reden more than are stored, 36 of its own by the chair), and person pages of the chair would count Reden that are none.

1. **The notice.** "Der gesamte und damit endgültige Stenografische Bericht der N. Sitzung wird am D veröffentlicht", soft hyphens removed and whitespace collapsed. 34 files print it, each with its own sitting number and one date.
2. **DIP.** A sitting with the notice is whole only when its DIP Aktivitäten are there and list no more "Rede" than the XML's Reden, and no more "Rede (zu Protokoll gegeben)" than its `zu_protokoll`. That is 19/107 (167 and 167, 43 and 43) and no other. No Aktivitäten, or more of either, means cut. A sitting DIP has not indexed yet is therefore marked, not assumed whole.
3. **A cut file without the notice.** At least 5 DIP Reden after the last `<rede>` by page and quadrant, and at least 5 more DIP Reden than stored. All 33 meet it (smallest: 21/65 with 10 and 7, 20/185 with 6 and 5; 20/210 needs rule 4). A sitting that meets it without the notice stops the gate, for a person to read. It marks nothing.
4. **The place of the last `<rede>`** comes from the Inhaltsverzeichnis. 20/210 prints it without pages: then it is the place of DIP's single Rede by that speaker (Christiane Schenderlein, 27367 B), and several such entries refuse.

The notice goes when the Bundestag replaces the XML, so a re-read of a complete file clears the mark.

## Steps

Each is one commit with its tests. Tests first where a rule is named.

**0. Read the end times** (needs the download go, D2): the closing line "(Schluss: …)" of the 28 PDFs not read against `sitzung-ende-uhrzeit`. Result as a TSV beside the census. If they differ by more than a minute anywhere but 20/210, D2 goes back to the owner.

**1. Parser** (`scripts/validate_dip_protocol.py`). `first_edition_notice(root, sitting)` gives the announced date, refuses a notice naming another sitting, and gives the last `<rede>` of the Sitzungsverlauf with its place. `protocol_cut(parsed, aktivitaeten)` applies rule 2 and builds the list of DIP entries after the cut: each "Rede" whose place is later, and each "Rede (zu Protokoll gegeben)" not matched to a stored one by name within the sitting. The parser has no DIP person for an XML speaker (and only 11 of 61,137 stored Reden have a record with a `dip_person_id`); matched by surname, the 33 sittings leave 429 and no stored one over. Written to `validation_summary["protocol_cut"]` (null, or date, last Rede, place, list). A `cut_rule_version` in the summary and a cause of its own in `build_dip_pulse_site.stale_causes`, which compares three named versions today and would not notice a fourth, make older cached reports stale, so `--offline --repersist` re-reads all 806.
   - Tests: the notice with soft hyphens and "16.Oktober" (19/55's spelling), a foreign sitting number, 19/107's shape, no Aktivitäten, an Inhaltsverzeichnis without pages, a Fragestunde after the last `<rede>` (18/3's shape, not cut), a Rede starting in the cut's own quadrant.

**2. Store and dictionary** (`persist_dip_pulse_store.py`, `data_dictionary.json`, `stable_ids.py`).
   - `protocols.xml_cut` (0 or 1), `xml_final_announced`, `xml_last_rede_id`.
   - Table `unprinted_contributions`: id, protocol_id, dip_activity_id, kind (`rede` or `zu_protokoll`), mp_id where the DIP person resolves, speaker as DIP prints it, page, page_quadrant. Licence layer DIP. Expected on the replay: 33 marked sittings, 1,189 `rede` and 429 `zu_protokoll`. A table, not a flag on `speeches`: ADR 0005's reason holds (a count that forgot to filter would count them).

**3. Completeness** (`facts.py`). Reason code `CUT_PROTOCOL`; speeches incomplete when the report's `validation_summary["protocol_cut"]` is set (Completeness is read from the reports, not from the store); a report without the key is unknown and incomplete, and null is whole. `gap_note`: "Sitzung 21/99: Protokolldatei abgebrochen". Basis `times` for `laengste-sitzung` (version 2), in `COVERAGE_DOMAINS`, in the check of `validate_registry` (which allows "votes" and "speeches" only), in `completeness_from_reports` and in `_GAP_DOMAIN_TEXT` (`gap_note` raises a KeyError without it). Note that `times` also frees weeks held back by withheld Reden: report that shift separately.

**4. `erste-reden` version 4.** A first Rede can lie in a cut part. The entries of `unprinted_contributions` of kind `rede` rank as a withheld Rede does, after all printed Reden of their sitting (they have no `item_index` or sequence, and bind by `mp_id`, not by Redner-ID): a person whose first Rede is one of them has no debut row. Seven people are counted as debuting too late today: Alexander Jordan, Dario Seifert, Florian Bilic, Georg Günther and Vanessa Zobel (first Rede in 21/14), Jan-Wilhelm Pohlmann (21/31) and Michael Arndt (21/47). So the published 2025-W28 (28) and 2025-W37 (9, with Bilic and Jordan) are too high. 2025-W28 stays a complete week, so step 3 alone would leave it wrong. Found by name, confirmed by DIP person id 2026-11-24. Johannes F. Kretschmann (20/210) has no stored Rede under that name at all.

**5. Backfill and the run's warnings** (`build_dip_pulse_site.py`). Leave `CUT_PROTOCOL` out of `_acquirable_reasons`, with its own line in the run summary. Exception: the catalog's `xml_hash` differs from the md5 of the cached XML, so the Bundestag may have replaced the file; then the sitting is acquired again. No code reads `xml_hash` today, and the report holds a sha256 (`xml_sha256`), so this step takes the md5 of the cached file itself. For closed Wahlperioden the catalog can be a week old (`CATALOG_FULL_FETCH_DAYS`).

**6. Gate** (`validate_store_gate.py`): every marked sitting has the notice in its cached XML and the reverse, but for the whole ones; rule 3 finds nothing unmarked; no row of `unprinted_contributions` shares person, place and sitting with a stored Rede; the 33 and the two counts are in the receipt.

**7. Reader-facing.**
   - Dossier of a cut sitting: a note under the heading with the place where the file stops, the two counts, the PDF link at that page, and the list of speakers DIP names after it. No list item looks like a Rede.
   - Fakten pages and Puls weeks: the gap note. Daten page: the coverage line beside the withheld one.
   - Redeanteil, Rangfolge and person pages: one generated sentence where the scope holds a cut sitting ("In 21 Sitzungen dieser Wahlperiode endet die Protokolldatei vorzeitig; 759 Reden laut DIP fehlen"). On a person page, that person's count of `unprinted_contributions`.
   - N9 (98 % minimum coverage): a period that holds a cut sitting is thin whatever its share, as with an excluded one, since the missing words are unknown. The build records it in ADR 0006 (step 9), applied when the analyses are built: no code for it exists.
   - Check in a browser in both themes, against DESIGN.md.

**8. Export and DATA.md.** The table and columns; `coverage.cut_protocols` in the manifest; a generated table per Wahlperiode and per sitting beside "Abdeckung nach Jahr". The hand-written figures in `docs/data-methods.md` ("Abgebrochene Protokolldateien") then go, and the rule stays: a figure typed into DATA.md is stale at the next cut Thursday. The sentence that the sittings can count as complete goes too.

**9. Words.** `CONTEXT.md`: Completeness basis, Sitzung completeness, and a term for the cut protocol (proposed *abgebrochenes Protokoll*). New ADR 0006, because it is hard to reverse and a reader would ask why 20 more weeks of WP 21 count as incomplete. ADR 0005 and 0002 stay. `docs/release-review.md`: a check of new cut sittings. The weekly run will meet them often: 21 of 109 sittings of WP 21.

**10. Replay and compare.** `--offline --repersist` from the cached XML, `compare_store_values.py` against the v0.46.50.0 replay: only the new table, columns, `facts`, and the export version move. Report every Fakt that changes, as a TSV (metric, period, old, new, why). Update `docs/plans/zu-protokoll-gap/` by rerunning the census. Coverage gate on the new store.

## Acceptance

- 33 sittings marked, the list of E16; 19/107 is not.
- 1,189 `rede` and 429 `zu_protokoll` rows; 61,137 Reden and 4,164 `zu_protokoll` unchanged.
- 31 weeks and 20 months lose completeness for speeches and no other; none gains it.
- The seven people of step 4 have no debut row.
- A cached report from before the build never reads as complete.
- Two runs give the same store.

## Not in this plan

The ten WP 18 texts of E17 (TODO of their own, P1: two wrong attributions). Reading the missing text from the PDFs. Reporting E16. The 11 votes without a TOP in these sittings.

## Size

M to L: steps 1 to 6 one session, 7 to 10 another. Two reviews by the checklist, since Fakten move. Files it will share with other open work: `facts.py` and `build_dip_pulse_site.py` (TODOS.md facts items), `persist_dip_pulse_store.py` and `data_dictionary.json` (v0.46.50.0), `docs/data-methods.md`.
