# Plan: mark the 33 cut protocols incomplete

Owner, 2026-11-23: plan it, to be built before the first `--publish`. Cause and numbers: [zu-protokoll-gap.md](zu-protokoll-gap.md), `docs/source-errors.md` E16. Measured on the v0.46.49.0 replay (806 sittings), read-only. Nothing is built.

**Base:** main after v0.46.50.0 (`claude/paragraph-breaks`, merged as #215) with `claude/modest-boyd-90f16f` (this branch: docs, the census script and its test; no parser, store or page code) merged first. v0.46.50.0 edited the parser, `persist_dip_pulse_store.py`, `data_dictionary.json` and TODOS.md and takes export format 25. This build takes the next free numbers (expected: export format 26, store schema 16). Check both against origin/main before shipping.

## What changes

A sitting whose Protokoll XML is a first edition stays stored with its Reden, TOPs and votes. It is marked, it is not complete for speeches, and what DIP lists for the missing part is stored as a list that counts nowhere.

No stored Rede, Beitrag, vote or vote link changes: 61,137 Reden and 4,164 `zu_protokoll` stay. Fakten change.

## Decisions for the owner

**D1. Mark and keep the sitting. Decided 2026-11-23** ("Yes, plan it"). Rejected: excluding the 33 as `source_defect`, which drops 4,555 stored Reden and the 70 votes held on those days and leaves a larger hole; and naming them in DATA.md only, which leaves Fakten that claim completeness.

**D2. `laengste-sitzung` gets a Completeness basis of its own, and four end times are corrected. Decided 2026-11-24:** "Yes, times + fixes", to "Judge laengste-sitzung by sitting times, with the four end times corrected from the PDFs?". The metric reads only the start and end times, which a cut file prints. Under the speeches basis the longest days would leave its own comparison: its published Fakten would fall from 92 to 67 over WP 19 to 21, and the remaining ones would compare with shorter weeks. Basis `times`: the XML is parsed and has both times. The owner allowed the 28 PDFs on 2026-11-24 (the check, not the basis). Result ([end-times.tsv](zu-protokoll-gap/end-times.tsv), head time of the XML, which `laengste-sitzung` reads, against the PDF's "(Schluss: …)"): 29 of 33 agree, 20/210 among them (2.19; its closing element says 02:15). Four differ: 19/55 by two minutes (XML 01:30, PDF 1.28), and 20/178 (23:11, 23.12), 21/89 (23:36, 23:37) and 21/96 (00:16, 00:15) by one. Under `times` with the four corrected, 152 Fakten stay published: four values move by one or two minutes (2018-W41 990 to 988, 2024-W26 851 to 852, 2026-W28 876 to 877, 2026-W39 916 to 915), and 2024-W41's percentile is 0.587 instead of 0.603 (0.597 on the store as it is, under the speeches basis). A reviewed list citing the PDFs corrects 19/55, 20/178, 21/89 and 21/96 (step 3b). Sittings that are not cut were not compared with their PDFs; the basis reads the XML's times for them as `laengste-sitzung` does today.

**D3. The PDF pilot comes after the release. Decided 2026-11-23.** Under D1 published Fakten fall from 590 to 506. With D2 they would be 531 if `laengste-sitzung` kept its 114, and WP 21 loses the most. Basis `times` (D2) also frees the weeks that withheld Reden hold back: `laengste-sitzung` goes from 114 published Fakten to 152 (WP 18 22 to 42, WP 19 29 to 46, WP 20 43 to 43, WP 21 20 to 21), so 569 in all. On v0.46.50.0 every total is one lower (2016-W07 lost `laengste-debatte`, WP 18).

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

**0. Read the end times. Done 2026-11-24:** result under D2; the four corrections are step 3b.

**1. Parser** (`scripts/validate_dip_protocol.py`). `first_edition_notice(root, sitting)` gives the announced date, refuses a notice naming another sitting, and gives the last `<rede>` of the Sitzungsverlauf with its place. `protocol_cut(parsed, aktivitaeten)` applies rule 2 and builds the list of DIP entries after the cut: each "Rede" whose place is later, and each "Rede (zu Protokoll gegeben)" not matched to a stored one by name within the sitting. The parser has no DIP person for an XML speaker (and only 11 of 61,137 stored Reden have a record with a `dip_person_id`); matched by surname, the 33 sittings leave 429 and no stored one over. Written to `validation_summary["protocol_cut"]` (null, or date, last Rede, place, list). A `cut_rule_version` in the summary and a cause of its own in `build_dip_pulse_site.stale_causes`, which compares three named versions today and would not notice a fourth, make older cached reports stale, so `--offline --repersist` re-reads all 806.
   - Tests: the notice with soft hyphens and "16.Oktober" (19/55's spelling), a foreign sitting number, 19/107's shape, no Aktivitäten, an Inhaltsverzeichnis without pages, a Fragestunde after the last `<rede>` (18/3's shape, not cut), a Rede starting in the cut's own quadrant.

**2. Store and dictionary** (`persist_dip_pulse_store.py`, `data_dictionary.json`, `stable_ids.py`).
   - `protocols.xml_cut` (0 or 1), `xml_final_announced`, `xml_last_rede_id`.
   - Table `unprinted_contributions`: id, protocol_id, dip_activity_id, kind (`rede` or `zu_protokoll`), mp_id where the DIP person resolves, speaker as DIP prints it, page, page_quadrant. Licence layer DIP. Expected on the replay: 33 marked sittings, 1,189 `rede` and 429 `zu_protokoll`. A table, not a flag on `speeches`: ADR 0005's reason holds (a count that forgot to filter would count them).

**3. Completeness** (`facts.py`). Reason code `CUT_PROTOCOL`; speeches incomplete when the report's `validation_summary["protocol_cut"]` is set (Completeness is read from the reports, not from the store); a report without the key is unknown and incomplete, and null is whole. `gap_note`: "Sitzung 21/99: Protokolldatei abgebrochen". Basis `times` for `laengste-sitzung` (version 2), in `COVERAGE_DOMAINS`, in the check of `validate_registry` (which allows "votes" and "speeches" only), in `completeness_from_reports` and in `_GAP_DOMAIN_TEXT` (`gap_note` raises a KeyError without it). Note that `times` (D2, decided) also frees weeks held back by withheld Reden: report that shift separately.

**3b. The four end times** (D2). Nothing on main corrects a time: `protocols.xml_header_json` holds the XML head's `sitzung_end` as printed, and `laengste-sitzung` reads it there.
   - **List:** `scripts/reviewed_end_times.json`, with `reviewed_end_times.py`, on the pattern of `reviewed_vote_links`: read once, checked whole, its own error class that is not a `ValueError`. A list of its own, since `reviewed_units.json` names single units of a sitting. Keys of an entry: `sitting`, `xml_end`, `end` (both HH:MM), `pdf_url`, `pdf_md5`, `pdf_page` (page of the file), `reason`. A sitting appears once, and `end` differs from `xml_end`. The four:

   | Sitting | `xml_end` | `end` | `pdf_md5` | `pdf_page` |
   |---|---|---|---|---|
   | 19/55 | 01:30 | 01:28 | 8eea57bbf4299710b4dabd82d557abfb | 214 |
   | 20/178 | 23:11 | 23:12 | 489347d2871edcb8866faf11746d3014 | read before writing the entry, not noted on 2026-11-23 |
   | 21/89 | 23:36 | 23:37 | 69343172e5682c610303993b04f6535d | 206 |
   | 21/96 | 00:16 | 00:15 | c237cbde7afeef863bd94f12f735856b | 214 |

   - **Store:** `xml_header_json` stays what the XML says. New column `protocols.sitting_end_corrected` (HH:MM, NULL without an entry), written by `persist_dip_pulse_store.replace_protocol` in the same write as `xml_header_json`, with dictionary text that names the list; the text of `xml_header_json` says it is uncorrected.
   - **Readers:** `_SITZUNG_END` in `facts.py` becomes `COALESCE(p.sitting_end_corrected, json_extract(p.xml_header_json, '$.sitzung_end'))`, which carries value, `times` basis, citation and the SQL on the page. `_fact_protocol_citation` in `build_dip_pulse_site.py` and the replay label read the same expression. No other code reads the end time.
   - **Refusal:** persist stops the run, naming the entry and the file, when the report's `xml_header.sitzung_end` is not the entry's `xml_end`, so also when the Bundestag replaces the file and the XML now agrees with the print: the entry is then deleted. An entry whose sitting the store lacks (demo, a partial store) is skipped. The stored column is compared with the list where `require_current_speech_rules` compares `reviewed_digest`, so that a store persisted under other entries is stale and asks for `--offline --repersist`.
   - **Gate** (step 6): every entry whose sitting the store holds is in the column, and the column holds no other; each entry's `pdf_md5` equals the `pdf_hash` of the cached DIP record, so that a PDF replaced later is read again.
   - **Tests, first:** a malformed list, a repeated sitting, `end` equal to `xml_end`; persist applies an entry and leaves `xml_header_json` alone; refuses a changed `xml_end`; skips an absent sitting; a store under an older list is stale; the minutes of 19/55's shape (past midnight, 09:00 to 01:28, 988); a sitting without an entry keeps its value; `times` complete with a corrected time, and incomplete for 18/23, which prints no end time.
   - **Pages today:** no page prints a clock time. The time shows only as a duration (headline, card SVG, "Verlauf" of the Fakt page and of the later weeks that list it) and in the published SQL. Four durations change: 2018-W41 16 h 30 min to 16 h 28 min, 2024-W26 14 h 11 to 14 h 12, 2026-W28 14 h 36 to 14 h 37, 2026-W39 15 h 16 to 15 h 15. The receipt of such a Fakt gets one line naming both times and the PDF page ("Ende laut PDF 1.28 Uhr, laut Protokolldatei 01:30 Uhr"): a reader who checks the XML would find another end.

**4. `erste-reden` version 4.** A first Rede can lie in a cut part. The entries of `unprinted_contributions` of kind `rede` rank as a withheld Rede does, after all printed Reden of their sitting (they have no `item_index` or sequence, and bind by `mp_id`, not by Redner-ID): a person whose first Rede is one of them has no debut row. Seven people are counted as debuting too late today: Alexander Jordan, Dario Seifert, Florian Bilic, Georg Günther and Vanessa Zobel (first Rede in 21/14), Jan-Wilhelm Pohlmann (21/31) and Michael Arndt (21/47). So the published 2025-W28 (28) and 2025-W37 (9, with Bilic and Jordan) are too high. 2025-W28 stays a complete week, so step 3 alone would leave it wrong. Found by name, confirmed by DIP person id 2026-11-24. Johannes F. Kretschmann (20/210) has no stored Rede under that name at all.

**5. Backfill and the run's warnings** (`build_dip_pulse_site.py`). Leave `CUT_PROTOCOL` out of `_acquirable_reasons`, with its own line in the run summary. Exception: the catalog's `xml_hash` differs from the md5 of the cached XML, so the Bundestag may have replaced the file; then the sitting is acquired again. No code reads `xml_hash` today, and the report holds a sha256 (`xml_sha256`), so this step takes the md5 of the cached file itself. For closed Wahlperioden the catalog can be a week old (`CATALOG_FULL_FETCH_DAYS`).

**6. Gate** (`validate_store_gate.py`): every marked sitting has the notice in its cached XML and the reverse, but for the whole ones; rule 3 finds nothing unmarked; no row of `unprinted_contributions` shares person, place and sitting with a stored Rede; the 33 and the two counts are in the receipt.

**7. Reader-facing.**
   - Dossier of a cut sitting: a note under the heading with the place where the file stops, the two counts, the PDF link at that page, and the list of speakers DIP names after it. No list item looks like a Rede.
   - Fakten pages and Puls weeks: the gap note. Daten page: the coverage line beside the withheld one.
   - Redeanteil, Rangfolge and person pages: one generated sentence where the scope holds a cut sitting ("In 21 Sitzungen dieser Wahlperiode endet die Protokolldatei vorzeitig; 759 Reden laut DIP fehlen"). On a person page, that person's count of `unprinted_contributions`.
   - N9 (98 % minimum coverage): a period that holds a cut sitting is thin whatever its share, as with an excluded one, since the missing words are unknown. The build records it in ADR 0006 (step 9), applied when the analyses are built: no code for it exists.
   - Check in a browser in both themes, against DESIGN.md.

**8. Export and DATA.md.** The table and columns; `coverage.cut_protocols` in the manifest; a generated table per Wahlperiode and per sitting beside "Abdeckung nach Jahr". The hand-written figures in `docs/data-methods.md` ("Abgebrochene Protokolldateien") then go, and the rule stays: a figure typed into DATA.md is stale at the next cut Thursday. The sentence on the four end times says that the PDF's time applies. The sentence that the sittings can count as complete goes too.

**9. Words.** `CONTEXT.md`: Completeness basis, Sitzung completeness, and a term for the cut protocol (proposed *abgebrochenes Protokoll*). New ADR 0006, because it is hard to reverse and a reader would ask why 20 more weeks of WP 21 count as incomplete. ADR 0005 and 0002 stay. `docs/release-review.md`: a check of new cut sittings. The weekly run will meet them often: 21 of 109 sittings of WP 21.

**10. Replay and compare.** `--offline --repersist` from the cached XML, `compare_store_values.py` against the v0.46.50.0 replay: only the new table, columns, `facts`, and the export version move. Report every Fakt that changes, as a TSV (metric, period, old, new, why). Update `docs/plans/zu-protokoll-gap/` by rerunning the census. Coverage gate on the new store.

## Acceptance

- 33 sittings marked, the list of E16; 19/107 is not.
- 1,189 `rede` and 429 `zu_protokoll` rows; 61,137 Reden and 4,164 `zu_protokoll` unchanged.
- 31 weeks and 20 months lose completeness for speeches and no other; none gains it.
- The four end times are in `sitting_end_corrected`, `xml_header_json` is unchanged, and `laengste-sitzung` has 152 published Fakten (WP 18 42, WP 19 46, WP 20 43, WP 21 21) with 2018-W41 at 988 (was 990), 2024-W26 852 (851), 2026-W28 877 (876), 2026-W39 915 (916) and the percentile of 2024-W41 at 0.587 (0.603 under `times` without the corrections, 0.597 today). No other value moves for the corrections. Simulated 2026-11-24 on the v0.46.49.0 replay.
- The seven people of step 4 have no debut row.
- A cached report from before the build never reads as complete.
- Two runs give the same store.

## Not in this plan

The ten WP 18 texts of E17: a fix of their own, before the first release (owner, 2026-11-24). Not started: it needs `speech_kinds.py`, `validate_dip_protocol.py` and `reviewed_units.*`, which `claude/rede-count-leftovers` is changing. Reading the missing text from the PDFs. Reporting E16: the owner sends it. The 11 votes without a TOP in these sittings.

## Size

M to L: steps 1 to 6 one session, 7 to 10 another. Two reviews by the checklist, since Fakten move. Files it will share with other open work: `facts.py` and `build_dip_pulse_site.py` (TODOS.md facts items), `persist_dip_pulse_store.py` and `data_dictionary.json` (v0.46.50.0), `docs/data-methods.md`.
