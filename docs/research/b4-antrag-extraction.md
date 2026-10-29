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
