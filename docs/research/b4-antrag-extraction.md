# B4 extractive fallback: first run on real Drucksachen

Research note, 2026-10-28. Part of step 0 of [the plan](../plans/b4-extractive-antrag.md). Scope is limited: the cloud session could reach `dserver.bundestag.de` (the PDFs) but had no DIP API key, so **DIP's `drucksache-text` was not fetched**, and the reference store (which votes have no abstract) was not available. What was tested is `antrag_text.extract_forderung` on pdftotext output of real PDFs, used as a stand-in for DIP's text body.

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
