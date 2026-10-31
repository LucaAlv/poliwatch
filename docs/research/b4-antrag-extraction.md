# B4 extractive fallback: first run on real Drucksachen

Research note, 2026-10-28/29. Part of step 0 of [the plan](../plans/b4-extractive-antrag.md). Run 1 (2026-10-28) used PDFs only. Run 2 (2026-10-29, below) used DIP's `drucksache-text` itself. The reference store (which votes have no abstract) was not available in either run.

## Run 1: PDFs only (2026-10-28)

## Sample

- 3 Anträge the research note names (21/2234, 21/4466, 21/5780).
- 48 Drucksachen at spread numbers, 12 per WP 18–21, fetched at 2 s spacing. By their first-page type: 15 Kleine Anfragen, 14 Antworten, 8 Beschlussempfehlungen, 4 Unterrichtungen, 4 Anträge (18/9042, 19/7398, 20/4666, 20/13902), 2 Gesetzentwürfe, 1 unknown.

So 7 Anträge in all. That is far too few for the plan's ≥90 % gate; the gate is not claimed.

## Method

Each PDF was read with pdftotext 24.02.0 in two modes: reading order (the default) and `-layout`. The extracted passage was compared word for word with its span of the source text, and every passage was read against the layout rendering by hand.

## Results

**False positives: none.** None of the 44 non-Anträge yields a passage, in either mode.

**Reading-order text** (the default; closest to a plain text dump):

| Drucksache | Result |
|---|---|
| 21/2234 | quoted, 14 demands, word-identical |
| 21/4466 | quoted, 4 demands, word-identical |
| 18/9042 | quoted, 8 demands, **but the text layer dropped a real hyphen**: "Gender-" at a line end became "GenderBudgeting-Strategie" (pdftotext's own join). The extractor cannot see a hyphen that is not in its input. |
| 21/5780 | the text layer moved list markers away from their items ("2." "3." alone, later "4."). **Before this note the extractor accepted it and would have quoted a reordered list**; it now gives no quote. |
| 19/7398 | a detached "2." followed sub-item "e." of point 1. **Before this note the extractor glued them ("2. e. handels- …")**; it now gives no quote. |
| 20/13902 | a detached "2." trails the passage; no quote. |
| 20/4666 | the anchor is inverted ("Daher fordert der Deutsche Bundestag die Bundesregierung im Rahmen … auf"); no quote. |

2 of 7 correct quotes, 1 with a text-layer error, 4 with none.

**Layout text** (`-layout`): 6 of 7 quoted, every list in source order, word-faithful to their source span (21/2234, 21/4466, 21/5780, 18/9042 with "Gender-Budgeting" intact, 19/7398 with its "a."–"f." sub-items, 20/13902); 20/4666 gives none, as above. Where both modes yield a passage they agree, except the 18/9042 hyphen.

## Changes made from this

- A bare list marker takes the next line as its text; a bare marker followed by another marker, or by a line that opens with one, or at the end of the passage, means the text layer lost the order: no quote (`_lines`).
- Lettered items with a full stop ("a.") are list items (19/7398).
- The fold under a quote says "Ganzen Forderungsteil zeigen" instead of "Weitere N Forderungen": sub-items and bullets are paragraphs too, so a count misstated 19/7398 (2 numbered demands, 10 sub-items).
- `EXTRACTOR_VERSION` 2 → 3.
- Real texts of 21/2234, 21/5780, 19/7398 and 20/13902 are regression fixtures (`tests/fixtures/antrag-text/`, provenance in `a1-source-manifest.json`).

## What this means for D3 (text source)

The quality of the quote depends on the text layer more than on the extractor. A reading-order dump scrambles lists in 3 of 7 Anträge and can drop real hyphens; a layout-order rendering of the same PDFs did neither. What DIP's `drucksache-text` body looks like is the open question:

- If it reads like the layout rendering, keep DIP text as planned.
- If it reads like the reading-order dump, the fail-closed rules keep wrong quotes out, but coverage would be poor (about 3 in 7 here), and a dropped hyphen would still pass. Then the PDF with `pdftotext -layout` is the better source (a poppler dependency and a dserver fetch per Antrag), which is D3's fallback.

## Still open (the rest of step 0)

1. With a DIP key: fetch `drucksache-text` for the same 7 Anträge and compare with both renderings; that settles D3.
2. On the reference store: the abstract-less votes' Anträge (about 64 votes), and about 20 WP 18/19 Anträge from A3's sittings, with a hand check of every quote.
3. Count the inverted anchor ("fordert der Deutsche Bundestag die Bundesregierung … auf") before deciding whether to support it (D5).

## Run 2: DIP `drucksache-text` (2026-10-29)

**API assumptions checked**, through the project's own `ApiClient`, `fetch_drucksache_metadata` and `fetch_drucksache_texts`, 2 s apart, 10 requests in all: one `/drucksache` call with 7 repeated `f.dokumentnummer` returned all 7 records, each with its own `dokumentnummer`, `drucksachetyp`, `urheber[].titel`, `vorgangsbezug` and `fundstelle.pdf_url`; one `/drucksache-text` call with repeated `f.id` returned all 7 texts. The same held for a batch of 32.

**Sample.** The 7 Anträge of run 1, plus 32 more: one DIP page of Anträge per WP 18–21 (`f.drucksachetyp=Antrag`, the newest 100 of each WP), every twelfth or so of each page. They cluster at the end of each Wahlperiode, so an older WP 18/19 layout may be under-represented. 37 of the 39 are by a Fraktion or Gruppe, 2 by the Bundesregierung (mandates, no demands section).

**Method.** Each DIP passage was compared word for word with the passage extracted from the same Drucksache's PDF via `pdftotext -layout`; every difference was read against the PDF.

**DIP's text keeps list order.** None of the scrambled lists of run 1 appear, and 18/9042 keeps "Gender-Budgeting". Where DIP and the PDF reading differ, DIP is right in every case read ("gewährleisten" and "Umweltschutzes", which the PDF reading splits). So D3 is settled: **DIP text stays the source**; no PDF path, no poppler dependency.

**Three traps in DIP's text, found and handled** (`EXTRACTOR_VERSION` 3 → 5):

| Trap | Where | Before | Now |
|---|---|---|---|
| The first-page head repeated at a page break: "Deutscher Bundestag Drucksache 21/5780" / "21. Wahlperiode 05.05.2026" | 21/5780 | quoted inside demand 3 | dropped as a running head |
| The advance-copy watermark, letter-spaced over three lines: "V" / "orabfassung – w" / "ird durch die lektorierte Fassung ersetzt." | every page of 21/8314, 21/8551, 21/8568, 21/8821 | quoted mid-sentence inside demands | removed wherever it stands |
| A page-foot footnote inside the operative part: "3 Vgl. Bundestagsdrucksache 21/4996, S. 52 …", splitting the word "beauf-sichtigt" | 21/8385, 21/8551 | quoted inside demand 1 (also from the PDF) | no quote |

The footnote rule fails closed because a footnote cannot be removed with confidence: its reference digit sticks to the word it follows. No accepted passage in the sample has a bare-number line or a digit glued to a word end, so the rule cost no quote beyond the two.

One anchor form was added: the adverb before the object, "fordert daher die Bundesregierung auf" (18/12797).

**Result on DIP text, Fraktion and Gruppe Anträge: 32 of 37 quoted (86 %)**, none known to be wrong: each is word-identical to the PDF reading, or differs only where the PDF reading is at fault. The 5 without a quote:

- 18/12638: no demands section ("… wird zustimmend zur Kenntnis genommen"). Correct.
- 20/4666, 19/30983: the inverted form inside a longer sentence ("Um … zu erreichen, fordert der Deutsche Bundestag die Bundesregierung … auf"). Quoting from "fordert" would start mid-sentence; supporting it means quoting from the sentence start. Left for D5: 2 of 37 here.
- 21/8385, 21/8551: footnote in the passage, as above.

Excluding 18/12638, which has nothing to quote: 32 of 36 (89 %). That is just under the plan's 90 % gate, with zero known wrong quotes; the gate is not claimed.

**Still open:** the reference store's votes without an abstract (the population that matters; this sample is Anträge in general, not abstract-less ones), WP 18/19 Anträge from the middle of those periods, and whether the inverted form is common enough there to support.

Regression fixtures from DIP's text: `tests/fixtures/antrag-text/dip-*.txt` (21/5780, 21/8568, 21/8385, 18/12797), provenance in `a1-source-manifest.json`.

## Follow-up: line-end hyphens (2026-10-29, Greptile P1 on PR #113)

A hyphen at a line end before a lower-case word was always taken as a break hyphen, so a hard one ("EU-" / "weite") was dropped. In the 39 DIP texts there are 66 such line ends, most in the Begründung or URLs; after a capital both kinds occur ("NATO-geführten" is hard, "BA-föG" in 21/8385 a break). The rule now follows the text's own spelling elsewhere in the document: the hyphenated word printed whole keeps the hyphen, the joined word printed whole (also as part of a compound, "BAföG-Reform") drops it; after a capital with no evidence either way the passage is not quoted. `EXTRACTOR_VERSION` 6. The 39-text results are unchanged (32 of 37).

## Run 3: local reference and mid-period validation (2026-10-29)

**Decision: leave the validation TODO open.** Extraction coverage is below 90% on the reference corpus, and the mid-period sample contains three incorrect passages. The reference's quotations are verified after one small layout correction; that does not establish fidelity for older periods. Broad anchor, footnote and source-quality changes remain separate follow-ups.

The durable [per-document audit](b4-local-audit-2026-10-29.csv) contains all **91 unique documents**, every reference vote→document association, extraction state, demands-section judgment, verification/miss/defect, source URLs and SHA-256 hashes. Mid-period records have agenda/Vorgang associations, not invented roll-call IDs. Complete passages, PDFs, comparisons and commands remain locally in `.context/b4-local-20261029-163417/` (`RUN` below). They are validation artifacts, not release data.

### Preservation and acquisition

The starting worktree was clean at `3df50d1`. All 4,096 canonical reference files were hashed in `RUN/source-sha256.json`, then copied using APFS clones to `RUN/baseline`, `RUN/control`, and `RUN/working`. The canonical `.context/dip-pulse-site` was never a build/fetch target. Baseline: **290 cached reports, 4,677 catalog entries, 217 votes, 260 vote→Vorgang associations, 3,111 stored proceedings**. Every vote has resolved context. Renderer-equivalent narrow selection (`report_vote_vorgaenge`, not all proceedings or all linked numbers) confirms **153 votes with at least one abstract, 64 with none**; the historical 153/217 figure holds. `cohort-before.json` records the selection.

`RUN/control` was rebuilt offline without text enrichment. The older schema was handled by calling `load_cached_protocols`, `load_existing_detail_entries(strict=True)`, `politikfelder.load_cache`, `antrag_text.load_cache`, and `refresh_vorgang_cache` directly for the working copy, before `--offline --repersist`. No sitting reports were reacquired and no A3 backfill ran. The existing client, pacing constant (`NUMBER_LOOKUP_PAUSE = 0.5 s`), batch sizes, retries and stop-on-failure behavior were reused. Credential loading used `dip.load_local_env`; no credentials are in artifacts.

Successful reference acquisition: **108 DIP HTTP requests**, all 200: 84 Vorgang pages, 8 Drucksache metadata pages, 16 text pages. The refresh filled/refreshed 4,142 Vorgänge, 157 number keys and 71 texts, with zero fetch/shape failures. There were initially 15 sandbox-denied DNS attempts; the existing failure limit stopped that pass. The normal outside-sandbox retry succeeded. PDF audit: **71 downloads, 12,794,781 bytes**, all successful, after three initial sandbox DNS failures. Each unique PDF was downloaded once successfully, at two-second spacing; associations remain per vote.

The reference text cache is **274,184 compressed bytes**, 860,255 uncompressed JSON bytes; its 71 bodies total 744,581 characters / 757,060 UTF-8 bytes. **Empty texts: 0**. The mid-period fetch added 6 DIP and 20 PDF requests (4,816,335 PDF bytes), with no empty texts or failures. Thus 205 successful HTTP requests cover this validation, separately from denied sandbox attempts. Empty-text retry-on-`aktualisiert` remains a known latent limitation; the task's conditional fix was not triggered.

### Coverage, with explicit denominators

A description means a vote has at least one rendered DIP abstract or quoted passage; a mixed vote already counts as described before enrichment. A candidate is a distinct BT Antrag/Entschließungsantrag selected for an abstract-less context by the implemented renderer selection. A demands-section denominator excludes only documents whose operative text was read and confirmed to have no demand addressed to the Bundesregierung. Fetch/extraction failures stay in candidate denominators.

| Population | Eligible unique documents / vote associations | Extracted | All-candidate coverage | Verified demands sections | Demands-section coverage |
|---|---:|---:|---:|---:|---:|
| All reference context blocks, including mixed votes | 71 / 71 | 50 | 50/71 = **70.4%** | 68 | 50/68 = **73.5%** |
| Only the 64 wholly abstract-less reference votes | 60 / 60 | 43 | 43/60 = **71.7%** | 59 | 43/59 = **72.9%** |
| Mid-period WP 18/19 sample | 20 / no roll-call association claimed | 16 | 16/20 = **80.0%** | 16 | 16/16 = **100%** |

Vote coverage: **43/64 (67.2%)** of the original abstract-less votes gain a quote; 60/64 have an eligible candidate and four do not. Across all reference votes, 71/217 have eligible candidate associations and 50/217 render a quote (including seven already described mixed votes). Document and vote candidate counts happen to be equal here because each selected vote has one eligible document.

Among all 217 reference votes, passage states are **50 extracted, 21 no_passage, 0 not_fetched, 146 not_applicable**. Among the original 64 without abstracts: **43 extracted, 17 no_passage, 0 not_fetched, 4 not_applicable** (votes 856, 929, 930, 932 have no eligible candidate). Those are distinct from the 11 mixed votes with an abstract-less context: 7 gain a quote and 4 remain no_passage. Original/control descriptions **153/217 (70.5%)**; final **196/217 (90.3%)**, a gain of 43. This description percentage is **not** the extraction gate.

Document states: reference **50 extracted, 21 no_passage, 0 not_fetched**; mid-period **16 extracted, 4 no_passage, 0 not_fetched**. All 91 documents: **66 extracted, 25 no_passage, 0 not_fetched**. Combined nominal extraction is **66/91 (72.5%)**, or **66/84 (78.6%)** among verified demand-bearing documents. Of the 66 quotations, 63 are verified and three are incorrect; neither denominator adjustment nor a higher description count clears the gate.

Reference misses (all 71 candidates): **10 interposed anchor clauses**, **1 `dazu` adverb**, **1 `möge beschließen`**, **1 `fordert` without an explicit Bundesregierung object**, **4 footnotes in the passage**, **1 direct motion to revoke a regulation**, **3 without an applicable demands section**. The direct motion is `20/3596` (mixed vote 799): “Die Verordnung … ist mit sofortiger Wirkung aufzuheben” is retained in the demands denominator despite lacking a supported anchor. For the wholly abstract-less subset, the counts respectively are **9, 1, 1, 1, 4, 0, 1**. Mid-period misses: four without an applicable demands section. `reference-audit-v7.json` and the CSV name each document. No unsupported inverted **Bundesregierung** anchor was found in either sample. `20/8411` does have an inverted sentence addressed to the **Bundeskanzler** in section III, outside that anchor; its separate section IV is quoted correctly. The two cloud inverted examples remain unaddressed.

### Quotation fidelity and small fixes

All 50 reference quotations were compared in full against `pdftotext -layout`, with sentence openings, terminal boundaries, demand/subitem order, hard hyphens, footnotes, headers, watermarks and attribution checked. The boundary audit records all source endings: signature/date lines, except `21/3031`, which stops before section III. Direct DIP/PDF passage comparison initially matched 47/50 after whitespace normalization. PDF images resolved two `so-`/`wie` line breaks (`20/7630`, `20/4053`) in favor of DIP's correct `sowie` spelling. The third discrepancy was a real extractor defect: `21/224` (vote 952) ended a DIP line with `Steuerzahler und -` and continued `zahlerinnen`; the quote inserted a space after the elision hyphen.

V7 joins only that demonstrated `und -` + lower-case continuation. The full real DIP body is now a regression fixture (`dip-2100224.txt`, provenance in `a1-source-manifest.json`); the regression failed before the fix and passes afterwards. **EXTRACTOR_VERSION 6 → 7**. Re-extracting all 71 reference and 20 mid-period bodies changes only that one space in `21/224`; extraction states and counts stay unchanged. The corrected ten-demand passage matches the source (PDF page 3 inspected visually). **Final reference: 50/50 correct, zero known incorrect passages.** Shared-extractor comparisons alone are insufficient: the separate boundary/hyphen audit and visual resolution of differences are retained.

A second small fix keeps “Antragstext nicht abgerufen” visible when a context already quotes one document but another text/metadata candidate is missing. Regression coverage exercises both partial states without replacing the valid quote with a generic gap. This is a rendering fix; it changes no stored values.

The 20 A3-linked mid-period documents are 10 each from WP 18 and 19, dated 2014–2016 and 2019–2020, selected from sittings 18/100, 18/150, 18/154, 19/145 and 19/150. All 16 demand-bearing texts extract, but **13 are correct and 3 incorrect**, confirmed against PDF images:

- **18/2742**, demand 9: `jesidisch-kurdischen` becomes `jesidischkurdischen`. A hard lower-case compound hyphen is lost without lexical evidence.
- **18/3154**: the PDF has nine dash bullets; DIP omits their markers and the quote flattens the list into one paragraph. Wording/order alone cannot establish complete list fidelity.
- **19/16794**: DIP places printer lines (`Gesamtherstellung`, `Vertrieb`, `ISSN`) between demands 3 and 4; the quote includes them. They are visibly page-bottom matter, not the demand.

`midperiod/v7-validation-report.md` supersedes the earlier v6 assessment of `19/16794`, which incorrectly treated that footer discrepancy as safe. V7 changes none of the 20 sample outputs. The secondary Fraktion/Gruppe denominator is 18 candidates (two government deployment motions excluded explicitly), 16 extracted / 16 with demands, or 88.9% across those 18 candidates; the three incorrect quotes still fail the fidelity requirement. Footnotes remain fail-closed: reference `20/9155`, `21/354`, `21/4750`, `21/2553`; no removal rule was inferred.

### Protected data, rendering and checks

Direct SQLite comparisons by stable primary keys are in `sql-baseline-control.json`, `sql-control-working.json` and `sql-baseline-working.json`, with a compact summary. The offline replay control explains **every protected-field difference** from the old store: 208 formerly null results become 162 accepted / 46 rejected with source `derived`; all 217 null result scopes become `proposition`; 40 null inversion flags/sources/excerpts are filled (37 protocol, 3 roll-call sources); nine null procedure types become eight constitutional amendments and one confidence vote. These same differences occur without fallback enrichment. No previously populated interpretation value is changed.

Between replay control and enriched working copy, protected fields are equal: all 217 vote records apart from the added `passage_state`, all 1,498 fraction rows, 154,078 member rows, 371 vote tags, 260 context associations, 3,111 proceedings including abstracts, 8,117 documents' pre-existing fields, 512 vote-document links and 4,768 agenda tags. No protected difference is attributable to live DIP changes. The fallback adds/updates only the passage states, document passage fields and 71 vote-passage associations. Compare-store aggregate output is supplementary; the stable-ID row comparisons are the evidence.

The final **v7** build repersisted all 290 cached reports and rendered 217 archive votes. `preservation-verification.json` confirms **all 4,096 canonical and baseline files remain hash-identical**, with no added/deleted files. `export-render-parity.json` verifies all 50 HTML quotation occurrences across 53 candidate-bearing dossier pages against their exact stored document passages and vote associations. Export format 9 CSV fields match SQLite for **8,117 documents, 217 votes and 71 vote_passages**; the compressed exported SQLite has the same passage fields and associations. The v7 replay's `sql-comparison-summary.json` reconfirms protected-field parity; fallback fields are the only control→working differences.

Chrome DevTools MCP was discovered and invoked first. Its configured profile was occupied by an existing browser; a separate **Chrome DevTools MCP 1.12.0 isolated temporary profile** completed the audit without interrupting it. The final matrix (`browser/matrix-theme-verified-summary.json`, screenshots/contact sheets under `browser/`) has **28 cases**: votes **906, 996, 1005**, abstract control **846**, real no_passage **997**, and two labelled constructed states on disposable pages (906 with its text removed; 906 retaining a quote while a second number's metadata is absent). Each was checked at **1280×900 desktop** and **390×844 mobile**, in actual **light/dark site themes**, using the site's theme toggle when needed. The first discovery matrix used media emulation only and is superseded by this actual-theme-verified pass.

Attribution/PDF and DIP link targets agree with metadata; quote folds contain whole demands and toggle by Enter, keyboard focus is visible, abstract precedence and state copy are correct, and there is **no horizontal overflow** in any case. All 28 keyboard checks pass. Console inspection found **no JavaScript errors/warnings**; two early cases recorded only the validation server's missing root `/favicon.ico` (404), corroborated by `browser-server.log`. Source links were checked as targets against PDFs already downloaded; external navigation was not required. Constructed pages are under `RUN/constructed/` and explicitly labelled; neither the working cache nor reference cache was altered for those states.

Final source checks (`.context/b4-checks-final-v7-20261029/`, source/test/fixture fingerprints unchanged during execution):

```sh
/opt/miniconda3/bin/python3.13 -m py_compile scripts/*.py
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -v
node tests/run_bills_browser_check.mjs /opt/miniconda3/bin/python3.13
```

Compilation passes; **1,590 unittest cases run, one skipped**. The Node browser runner passes (sandbox loopback binding initially failed with EPERM; normal outside-sandbox retry passed). CI's zero-network demo/publication commands also pass: ordinary demo build, expected protocol file, `--validate-publication`, capability listing, configuration explanation, development-marked demo, and expected rejection of that dev artifact. The complete final working publication also passes `--validate-publication` (`working-publication-validation.log`). `git diff --check` passes. `/review` ran against merge-base `71ade833` with fresh `origin/main` at `2a71d50`, including native adversarial re-review of the small fixes. No additional code defect was found in those changes; the measured corpus defects and unmet gate are explicit outstanding findings. Final validation-doc review is recorded in `RUN/review/`.

The optional Claude challenge failed authentication inside the sandbox. Per AGENTS, the same runner was retried with normal escalation; **automatic approval review rejected that external transfer of repository source/docs without payload-specific authorization**. No external-review workaround was attempted. That review coverage remains blocked and is not counted as passed.

### Reproduction and next session

The run root retains the baseline/control/working sites and all logs. Preparation, acquisition, audit and equality scripts are retained as `.context/b4_prepare.py`, `b4_reference_audit.py`, `b4_fetch_pdfs.py`, `b4_compare_sql.py`, `b4_export_parity.py`, `b4_browser_fixtures.py`, `b4_make_browser_actions.py`, and `b4_mcp.py`. The preparation script records cohorts before and after calling the existing refresh; PDF downloads are separate and never feed implementation extraction. Replay commands used:

```sh
/opt/miniconda3/bin/python3.13 .context/b4_prepare.py --fetch
/opt/miniconda3/bin/python3.13 scripts/build_dip_pulse_site.py --offline --repersist --output-dir .context/b4-local-20261029-163417/control --today 2026-10-29
/opt/miniconda3/bin/python3.13 scripts/build_dip_pulse_site.py --offline --repersist --output-dir .context/b4-local-20261029-163417/working --today 2026-10-29
/opt/miniconda3/bin/python3.13 .context/b4_compare_sql.py
/opt/miniconda3/bin/python3.13 .context/b4_export_parity.py
```

Recommended next session: **quotation fidelity before coverage**. Add real fixtures/provenance for `18/2742`, `18/3154`, `19/16794`; preserve the hard hyphen and all nine bullet boundaries, remove only proven printer matter, or return `no_passage` where source fidelity cannot be established. Bump the extractor and re-audit this saved 91-document corpus with **zero incorrect accepted passages**; do not reconstruct absent bullets by guessing. Then a separate anchor follow-up can address the measured ten interposed-clause misses (for example `20/6712`, `20/10050`, `20/1336`) and `20/6708`, preserving the **complete sentence opening**. Re-run the cloud inverted cases `20/4666`, `19/30983` before supporting them. Closure still requires ≥90% coverage with all denominators explicit and zero incorrect passages, plus required checks. No commit, push, merge or deployment was performed.

## Run 4: source fidelity and interposed anchors (2026-10-31, extractor 7 to 9)

Offline replay of `extract_forderung` over the cached texts of the saved 91-document corpus (`.context/b4-local-20261029-163417/reference-documents/*.dip.txt`, `midperiod/texts/*.txt`; read only, no network, no site build, no store touched). Source hashes in [the audit CSV](b4-local-audit-2026-10-29.csv) are unchanged; the CSV itself is the 2026-10-29 record and was not rewritten.

**Step a, source fidelity (EXTRACTOR_VERSION 8).** Each of the three incorrect quotes has a real DIP-text excerpt fixture (`tests/fixtures/antrag-text/dip-1802742.txt`, `dip-1803154.txt`, `dip-1916794.txt`, provenance in `a1-source-manifest.json`) and is now refused or quoted correctly:

| Document | Defect | Now |
|---|---|---|
| 18/2742 | `jesidisch-` + `kurdischen` joined to `jesidischkurdischen` | `no_passage`: a lowercase line-end hyphen after a part of 5+ letters that the text also uses as a word (`jesidischen`) is a break only where the text spells the joined word |
| 18/3154 | nine bullet markers lost, list flattened | `no_passage`: an item line opening with a bare space after a finished clause is a dropped marker; none is reconstructed |
| 19/16794 | printer imprint (`Gesamtherstellung`, `Vertrieb`, `ISSN`) between demands 3 and 4 | quoted without the imprint (295 characters fewer, otherwise identical); imprint lines are dropped like running heads |

Over the 91 documents, 66 to 64 extracted; the only changes are these three. Incorrect accepted passages 3 to 0. Trade-off, measured: the hyphen rule refuses only 18/2742 here (one further lowercase join without evidence in the corpus, a URL slug in 19/17515, stays quoted, already audited correct, because its left part is no word); on text with more unattested compounds it will refuse more.

**Step b, interposed anchors (EXTRACTOR_VERSION 9).** The anchor accepts a punctuation-free clause between `die Bundesregierung` and `auf` before a comma or colon, opening with `im Rahmen`, `unter Einhaltung`, `zur` or `zum`, and `dazu auf`; the opening paragraph keeps the whole sentence. Fixtures: 20/6708 (`dazu`), 20/6712, 20/10375, 20/13417; also 20/13415 and 20/2345 below. Exactly the ten reference documents the audit named as interposed-anchor or `dazu` misses become extractable (20/6708, 20/6712, 20/10050, 20/10375, 20/11393, 20/11758, 20/13415, 20/13416, 20/13417, 20/1336); nothing else changes. 20/2345, also an interposed miss, is refused (below).

Each new quote was checked against the PDF `pdftotext -layout` text: the whole quote matches word for word (whitespace and hyphen-insensitive) and ends directly before the date line; list-label sequences were read for all ten; every line-end hyphen decision inside the ten spans was listed and read (all syllable breaks or elisions except the defect below). Two defects found this way, fixed with a failing fixture first:

- **20/13415**: the list runs `a)` to `z)` then `aa)` to `gg)`; `_successor("z")` was `{`, so `aa)` to `ff)` were folded into demand `z)`. `aa)` is now the successor of `z)`.
- **20/2345**: DIP's text reads `Überoder Unterforderung` (line 99 of the saved body) where the PDF prints `Über-` / `oder Unterforderung`; the hyphen was dropped at the source and the conjunction glued. A capitalised fragment of 3+ letters glued to `oder` is refused (`und` cannot be told apart: Bund, Grund, Hintergrund; a scan of all 74 quotes finds no other glued token). Source defect for a correction request; `docs/source-errors.md` lives on `worktree-a3-plan`, so it is not added here.

**Cloud inverted cases `20/4666`, `19/30983`: not supported.** Their texts are not in the saved corpus and no network was used, so they could not be re-checked; the anchor stays Bundesregierung-only and the inverted form stays `no_passage`.

### Re-audit, explicit denominators (extractor 9)

| Population | Candidates | Extracted | All-candidate | With demands section | Demands-section coverage |
|---|---:|---:|---:|---:|---:|
| Reference cohort (all context blocks) | 71 | 50 to **60** | 50/71 (70.4%) to 60/71 (**84.5%**) | 68 | 50/68 (73.5%) to 60/68 (**88.2%**) |
| Wholly abstract-less reference votes | 60 | 43 to **53** | 43/60 to 53/60 (**88.3%**) | 59 | 43/59 to 53/59 (**89.8%**) |
| Mid-period WP 18/19 sample | 20 | 16 to **14** | 16/20 to 14/20 (**70.0%**) | 16 | 16/16 to 14/16 (**87.5%**) |
| All 91 | 91 | 66 to **74** | 66/91 to 74/91 (**81.3%**) | 84 | 66/84 to 74/84 (**88.1%**) |

Incorrect accepted passages: **3 to 0** (reference 0, mid-period 3 to 0). Demands-section judgments are those of the 2026-10-29 audit and were not redone; the two newly refused mid-period documents and 20/2345 stay in the demands denominators as misses.

Derived, not site-measured: each of the ten newly extractable reference documents belongs to one vote, and each of those votes has that one candidate and was a wholly abstract-less `no_passage` vote, so the narrow-cohort description count would move **196/217 to 206/217** (43/64 to 53/64 of the abstract-less votes). No site build or store replay was run; `votes.passage_state` of a store persisted with extractor 7 is refused until `--offline --repersist`.

**Gate:** zero incorrect passages holds on this corpus, but no population reaches 90% (best 89.8% of demand-bearing abstract-less documents; 88.2% for the reference cohort). The TODO stays open.

Remaining misses (17 of 91 documents: 10 demand-bearing, 7 without a demands section): footnotes in the passage 20/9155, 21/354, 21/4750, 21/2553 (fail closed); `möge beschließen` 20/10055; `fordert` without a Bundesregierung object 20/14699; direct motion to revoke a regulation 20/3596; source defect 20/2345; lost structure refused 18/2742, 18/3154; no applicable demands section (not in the demands denominators) 20/9775, 20/10194, 20/14150, 18/4689, 19/17095, 19/17032, 19/17286. Reaching 90% of the reference cohort (62/68) needs two more of the footnote, `möge beschließen`, no-object or revoke documents, each a separate rule with its own fidelity risk.

