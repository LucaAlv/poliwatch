# Reden zu Protokoll that DIP lists and the store lacks

Check of 2026-11-23 on the v0.46.49.0 replay (`.context/ship-after/data`, 806 sittings, 61,137 Reden). Nothing is built: no parser, store or figure changes.

## Finding

**The gap is larger than the TODO says.** 33 Protokoll XML files are first editions that stop mid-sitting. They lack the spoken end of the sitting as well as the annexes: 1,189 Reden that DIP lists, beside 429 Reden zu Protokoll.

| WP | Cut sittings | Reden after the cut | Reden stored | Missing share | Reden zu Protokoll missing |
|---|---|---|---|---|---|
| 18 | 0 | – | 12,838 | – | 10 (another cause) |
| 19 | 1 of 239 | 41 | 19,869 | 0.2 % | 0 |
| 20 | 11 of 214 | 389 | 19,069 | 2.0 % | 148 |
| 21 | 21 of 109 | 759 | 9,361 | 7.5 % | 281 |

Share: missing over stored plus missing. "After the cut" counts DIP's Aktivitäten "Rede" whose page and quadrant come after the XML's last `<rede>`, without the chair's. DIP types the chair's farewells and greetings as "Rede" (624 in the 806 sittings); the store holds none of them as a Rede. 23 stand after the cut: 19 in 20/210, two in 20/209, one each in 20/203 and 20/207. The first count of 2026-11-23 included them (1,212; WP 20 412, 2.1 %). The plain difference DIP minus stored in the same sittings is 1,208 (41, 404, 763), and 1,145 without all 63 entries by the chair: stored Reden include some DIP types otherwise.

The 435 of the TODO: DIP 4,599, stored 4,164. 429 in the 33 cut files, 10 in WP 18 (below), less 4 stored ones DIP does not list as such (18/237 Karin Binder and Jutta Krellmann, 19/36 Stamm-Fibich, 20/66 Till Steffen).

Six cut sittings lack no Rede zu Protokoll, so the TODO's count did not show them: 19/55, 20/175, 20/185, 21/53, 21/56 and 21/65. 19/107 prints the notice but is whole.

Files: [per-sitting.tsv](zu-protokoll-gap/per-sitting.tsv) (47 sittings: a difference or the notice), [census.py](zu-protokoll-gap/census.py) (read-only, reproduces it; totals on stderr).

## Cause

- **The notice.** Each cut file ends "Der gesamte und damit endgültige Stenografische Bericht der N. Sitzung wird am … veröffentlicht.", in its Inhaltsverzeichnis, in its Sitzungsverlauf and in its last annex. The date is five or six days after the sitting. All but 20/209 (a Wednesday) are Thursdays.
- **Not our cache.** On 2026-11-23 dserver sends all 34 files with the notice at the cached size (`HEAD`, Content-Length). Every cached file's md5 is the `xml_hash` of its DIP record.
- **The PDF is final.** Last-Modified of the five PDFs is the announced date or later, their md5 is DIP's `pdf_hash`, and they print no notice.
- **No cut file without the notice.** 30 other sittings have a DIP Rede after the last `<rede>` by page (26, the chair's left out) or print no page in the Inhaltsverzeichnis (4). None is cut: their DIP and stored Rede counts differ by at most 3 where DIP lists more. With the chair's farewells and greetings counted, 18/193, 18/240, 18/241, 18/243, 18/244, 19/234 to 19/238, 20/76, 20/208, 20/211 and 20/212 hold 5 to 35 Reden fewer than DIP; without them the store holds at most one fewer in each.

### The five PDFs

| Sitting | XML stops at | Print ends | Body in print after the cut | Annexes XML / print | of them zu Protokoll | Reden after the cut in print | Reden zu Protokoll in print |
|---|---|---|---|---|---|---|---|
| 20/147 | 18766 B, TOP 23 | 18799 | 17 % | 9 / 20 | 1 / 12 | 38 of 38 | 34 of 34 |
| 20/178 | 23141 D | 23169 | 14 % | 1 / 9 | 0 / 8 | 33 of 33 | 24 of 24 |
| 21/40 | 4645 D | 4703 | 25 % | 4 / 18 | 0 / 13 | 57 of 57 | 29 of 29 |
| 21/83 | 10083 D | 10150 | 29 % | 7 / 25 | 1 / 17 | 68 of 68 | 38 of 38 |
| 21/99 | 12420 B | 12477 | 24 % | 2 / 18 | 1 / 14 | 66 of 66 | 32 of 32 |

"In print": the page DIP gives prints the person's speaker label. Two needed a look: diacritics (Trăsnea in 20/147, Özoğuz in 21/40), and Jörg Cezanne's label in 21/40 stands one page after the annex title DIP points to. So the print has an annex the XML lacks, in all five. Share of the body: characters of the extracted text, pages after the cut.

sha256 of the PDFs (not kept in the repository): 20147 `597757e4…32305a2`, 20178 `b041db23…9d7e7`, 21040 `eec2cca2…7c5bb`, 21083 `9a9ce50e…1a39f`, 21099 `408da981…b7b99`.

Printed page numbers jump between the body and the annexes (20/147: 18800 to 18817 do not exist in the PDF), so a page offset must be taken per part.

### WP 18: ten, another cause

The text is in the XML, without a `<rede>` of its own (`docs/source-errors.md`, E17): 18/17, 18/23, 18/34, 18/46, 18/47, 18/63, 18/66, 18/112, 18/115, 18/155. Two are stored inside the previous speaker's text, a wrong attribution: Lenkert under Thews (18/23), Engelmeier under Steiniger (18/63). Two rows are empty, with no speaker: 18/63 `ID1806309700`, 18/76 `ID1807611000`.

## What it touches

- **Reden, Beiträge, TOPs** after the cut are in no table, page or figure: Reden per person, Redeanteil, Rangfolge, TOP ranking, Puls.
- **Not random:** the end of long sitting days, 32 of them Thursdays, so the last debates. Missing Reden by group in WP 21: AfD 199, CDU/CSU 191, Grüne 122, Linke 111, SPD 90, others 46. The AfD has 26 % of them against 23 % of the stored Reden; its share of all WP 21 Reden moves from 23.4 to 23.6 %. Counts move more than shares.
- **Fakten:** the week and month of a cut sitting count as complete. `laengste-debatte` of 2026-W41 (21/99) is `complete = 1` and publishable.
- **Votes:** roll-calls come from bundestag.de and are not cut. 11 of the 70 roll-calls in the cut sittings have no TOP: 883 (20/141), 943, 944, 945 and 948 (20/210), 956 (21/14), 969 (21/37), 977 and 978 (21/40), 1008 (21/83), 1034 (21/99). Likely called after the cut; not checked one by one.
- **CPP-BT has the same gap.** Its comparison found no Rede id in a shared sitting that we lack (`docs/release-reviews/cpp-bt-first-run-2026-11-14.md`), so agreeing with it says nothing here.
- **The gates saw nothing.** The coverage gate reconciles the `<rede>`s a file prints.

## Where the text could come from

| Source | Holds the rest? | Checked |
|---|---|---|
| dserver XML | No | All 33, size |
| Open Data page XML | No | 20/147 read, byte-identical. WP 20/21 lists hold the other 31 files under their own ids, not read |
| DIP `plenarprotokoll-text` | No, the first edition's text under the final PDF's hash | 20/147 read |
| PDF on dserver | Yes | Five read |
| DIP Aktivitäten | Speaker, person id, Fraktion, page, quadrant, kind, Vorgang; no text | All, cached |
| CPP-BT | No | By its comparison |
| Other corpora | Unknown | Not read |

## Recommendation for the owner

1. **Before the first `--publish`: mark the 33 sittings as incomplete.** A coverage record per sitting ("Protokolldatei abgebrochen", with the cut and DIP's count of what follows), read by Period completeness, so that their weeks and months are not complete, shown in the dossier, and exported. Detect the notice at parse time and compare with DIP's Reden after the last `<rede>`, so that new long Thursdays do not enter unnoticed and 19/107 passes. Naming the gap in DATA.md alone leaves "complete" Fakten that are not. This moves Fakten and needs an owner decision. Effort M.
2. **Report E16 to the Bundestag** (the owner sends it; contact in `docs/source-errors.md`). A replaced XML at the same address fixes everything with a re-fetch, for other users too.
3. **After that, if the XML is not replaced: read the rest from the PDF,** as a pilot on the five sittings. The PDFs' text layer is clean enough to find every label by page; DIP's Aktivitäten give the skeleton (person, kind, page, quadrant, Vorgang), and each PDF Rede must match one or the sitting refuses. The open questions are Kommentare, chair words and column order, text hyphenated at line ends, TOP headings, and ids: the print has none, so these need a project id of their own, as `N…` and `M…` have. About 1,189 Reden and 429 Reden zu Protokoll in 33 sittings. Effort L.
4. **Do not** fill in Reden from DIP without text: a Rede without words would enter Reden counts and leave characters, share and search wrong.
5. **WP 18:** the ten are a parser task of their own (E17), small, and two of them are a wrong attribution, so they belong before the release. Effort S.

Owner, 2026-11-23: 1 before the first release (planned in [cut-protocols.md](cut-protocols.md)), 3 after it. Owner, 2026-11-24: `laengste-sitzung` by sitting times with four end times corrected (D2); 5 before the first release; 2 the owner sends themselves (contact: `docs/source-errors.md`).

## Not read

28 of the 33 PDFs, but for their closing line (2026-11-24, [end-times.tsv](zu-protokoll-gap/end-times.tsv)). The Open Data XML and the DIP text of the other 32. The passages after the cut beyond the labels. Where the 11 unlinked votes were called.
