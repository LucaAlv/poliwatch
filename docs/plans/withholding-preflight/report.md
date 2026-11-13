# Withholding preflight: the 85 sittings (W1, 2026-11-12)

Fetched from dserver.bundestag.de on 2026-11-12, after the fresh store rebuild had finished its downloads, and audited with `fetch_and_audit.py`. Re-audited on 2026-11-13 from the same XML at main a4acab0, after #147's Rede reconciliation (speech rule 7, parser sha256 `deb0cb17c87e…`): the first run, at main 28799ac plus the W1 fixes (parser `4b0c6686f532…`), predates #147 and counted 19/36 as parsing once withheld (see "19/36" below). Sittings: the 84 of `a3-wp18-19-round2-result.md:234` plus 20/11 (`sittings-85.txt`). The data is in `preflight.json` beside this file.

## Result

- **70 sittings parse once single Reden are withheld.** Every turn refusal is `located_nested_contribution`, located to a Rede and marker (107 markers: 105 in the 70, 2 in 19/36). No sitting refused for a turn class that cannot be narrowed (no `conflicting_roles`, `befragung`, `fragestunde_marker`, `nested_needs_source_id` or `outside_top`).
- **1 refused, not narrowable:** 19/36, `rede_reconciliation`. Once its one located Rede is withheld, #147's reconciliation refuses an annex Rede that no rule covers.
- **13 parse with no refusal:** 18/2, 18/29, 18/62, 18/83, 18/90, 18/178, 18/223, 18/245, 19/1, 19/9, 19/19, 19/25, 19/73. These are the sittings TODOS lists "with no refusal": N7's four (18/2, 18/29, 18/83, 19/25) whose known wrong units need the reviewed list, seven that wait on ADR 0004, and 18/62 and 18/90, out by the owner's round 2 decision. Parsing cleanly does not clear them.
- **1 fetch rejected:** 18/20, by design (dserver's `18020.xml` holds sitting 21).
- **Withheld:** 89 Reden, 93,582 words, of 4,804,026 words in the Reden of the sittings that parse once withheld. Share per sitting: median 1.71%, max 8.42%.
- **Pass-1 moves out of withheld Reden:** none (`sittings_with_moves_out` is empty), so D7's rule for moved text has no case in the 85.

The 89 Reden are the blockers file's 87 sitting-Rede pairs, less 18/20 (not fetched) and 19/36 ID193612200 (its sitting refuses), plus four it does not list: 18/89 ID1808901500, 18/124 ID1812400500, 18/173 ID1817303100 and 20/11 ID201100900.

This run gives no reason to fall back to releasing WP 20 and 21 first: every turn refusal narrows to single Reden, and the one refusal that does not (19/36) is a source shape the parser has no rule for yet, not a turn. The fallback's own trigger, the first of the coverage gate's proofs (withholding one unit leaves every other unit unchanged), is PR 2's to show.

## Against the blockers file

`a3-wp18-19-round2-blockers.tsv` has 103 marker rows in 69 sittings and 86 distinct Rede ids. The T3 review's 87 counts sitting-Rede pairs (87): ID1802102900 is listed under both 18/20 and 18/21. **86 is the right count of Reden.**

67 of the 69 listed sittings parse once withheld, 66 with exactly the listed markers. The ones that differ:

- **18/20** (fetch failed): expected 1, found 0; not found: ID1802102900 marker 2.
- **19/36** (refused, not narrowable): its two listed markers, ID193612200 markers 6 and 8, are found before the refusal (see "19/36" below).
- **18/89** (parses once withheld): expected 2, found 4; found, not listed: ID1808901500 marker 3, ID1808901500 marker 4. ID1808901500 stands outside any TOP; the round 2 audit predates #143, which reads such Reden, so it never saw them.
- **20/11** is not in the blockers file (it was added to the 85 separately): one located marker, ID201100900 marker 2.

## 19/36

The audit withholds ID193612200 (Roderich Kiesewetter, CDU/CSU, markers 6 and 8, 1,125 words). Then the parse refuses: `rede reconciliation: ID193616800 (annex "Liste der entschuldigten Abgeordneten") has no status`. Anlage 2 of the source carries that title but holds no list. It holds one `<rede>`, headed "Zu Protokoll gegebene Fortsetzung des abgebrochenen Redebeitrages der Abgeordneten Martina Stamm-Fibich (SPD)" with "(Tagesordnungspunkt 5, Seite 3370 C)". Before #147 the parser dropped this Rede without a word. Since #147 the sitting refuses until a rule names the block. 19/36 therefore stays out until the parser reads that block as the Zu-Protokoll continuation it is, or names it in `ANNEX_EXCLUSIONS`. Withholding cannot fix this, so this run does not count the sitting among those that parse once withheld. The first run counted 1 Rede, 2 markers, 1,125 words and 113,658 words in Reden for it.

## The two flagged sittings

18/124 and 18/173 were outside the 69/13/18-20 groups, refused with "unresolved nested contribution" after their role conflict was fixed (`a3-wp18-19-round2-result.md:211`). Both now refuse only located nested contributions and parse once withheld:

- 18/124: ID1812400500 marker(s) 2, Volker Kauder (CDU/CSU), 2,909 words.
- 18/173: ID1817303100 marker(s) 3, Markus Kurth (BÜNDNIS 90/DIE GRÜNEN), 1,410 words.

## The B2 case

18/89 is the only one of the 84 fetched sittings that prints Reden directly under `<sitzungsverlauf>` (15) [measured]. Its withheld Reden are not split parts, so they are found with or without fix B2: B2 changes no figure in this run. It still matters for any later run, where a split part of such a Rede would otherwise count 0 words. 18/43 `ID1804301900:6` is a split part inside a TOP, found either way (Hubertus Heil, 2,389 words).

## Withheld words (N9)

By year (sitting date):

| Year | Words withheld |
|---|---:|
| 2013 | 4,714 |
| 2014 | 19,367 |
| 2015 | 21,383 |
| 2016 | 14,889 |
| 2017 | 5,704 |
| 2018 | 12,900 |
| 2019 | 2,311 |
| 2020 | 7,422 |
| 2021 | 3,990 |
| 2022 | 902 |

By Fraktion of the withheld Rede's speaker:

| Fraktion | Words withheld |
|---|---:|
| CDU/CSU | 60,921 |
| BÜNDNIS 90/DIE GRÜNEN | 11,264 |
| SPD | 8,326 |
| DIE LINKE | 6,507 |
| AfD | 3,812 |
| (keine) | 1,890 |
| FDP | 862 |

The share per sitting is in the table below. The share per year and Fraktion needs the words of the held sittings too; the fresh store (718 sittings, 2026-11-12) holds them, and T4 computes it.

## Per sitting

| Sitting | Date | Status | Withheld Reden | Markers | Words withheld | Words in Reden | Share | Blockers expected / found |
|---|---|---|---:|---:|---:|---:|---:|---|
| 18/1 | 22.10.2013 | parses once withheld | 1 | 1 | 26 | 2,416 | 1.08% | 1 / 1 |
| 18/2 | 18.11.2013 | parses, no refusal | 0 | 0 | 0 | 30,567 | 0.00% | 0 / 0 |
| 18/3 | 28.11.2013 | parses once withheld | 2 | 3 | 3,301 | 68,158 | 4.84% | 3 / 3 |
| 18/6 | 19.12.2013 | parses once withheld | 1 | 1 | 1,387 | 23,288 | 5.96% | 1 / 1 |
| 18/8 | 16.01.2014 | parses once withheld | 1 | 1 | 1,094 | 62,208 | 1.76% | 1 / 1 |
| 18/10 | 29.01.2014 | parses once withheld | 1 | 1 | 741 | 57,231 | 1.29% | 1 / 1 |
| 18/11 | 30.01.2014 | parses once withheld | 2 | 3 | 2,145 | 92,194 | 2.33% | 3 / 3 |
| 18/20 |  | fetch failed | 0 | 0 | 0 | 0 |  | 1 / 0 |
| 18/21 | 14.03.2014 | parses once withheld | 1 | 1 | 325 | 36,785 | 0.88% | 1 / 1 |
| 18/26 | 03.04.2014 | parses once withheld | 3 | 4 | 4,476 | 85,277 | 5.25% | 4 / 4 |
| 18/29 | 09.04.2014 | parses, no refusal | 0 | 0 | 0 | 63,966 | 0.00% | 0 / 0 |
| 18/36 | 22.05.2014 | parses once withheld | 1 | 1 | 2,184 | 88,597 | 2.47% | 1 / 1 |
| 18/42 | 25.06.2014 | parses once withheld | 2 | 2 | 405 | 89,732 | 0.45% | 2 / 2 |
| 18/43 | 26.06.2014 | parses once withheld | 1 | 1 | 2,389 | 61,655 | 3.87% | 1 / 1 |
| 18/50 | 10.09.2014 | parses once withheld | 1 | 1 | 1,725 | 76,669 | 2.25% | 1 / 1 |
| 18/60 | 16.10.2014 | parses once withheld | 1 | 1 | 1,434 | 92,326 | 1.55% | 1 / 1 |
| 18/62 | 05.11.2014 | parses, no refusal | 0 | 0 | 0 | 13,350 | 0.00% | 0 / 0 |
| 18/63 | 06.11.2014 | parses once withheld | 1 | 1 | 1,087 | 84,959 | 1.28% | 1 / 1 |
| 18/67 | 14.11.2014 | parses once withheld | 1 | 1 | 1,362 | 43,883 | 3.10% | 1 / 1 |
| 18/82 | 29.01.2015 | parses once withheld | 2 | 2 | 3,628 | 80,333 | 4.52% | 2 / 2 |
| 18/83 | 30.01.2015 | parses, no refusal | 0 | 0 | 0 | 45,385 | 0.00% | 0 / 0 |
| 18/88 | 26.02.2015 | parses once withheld | 2 | 3 | 1,709 | 83,980 | 2.04% | 3 / 3 |
| 18/89 | 27.02.2015 | parses once withheld | 2 | 4 | 1,609 | 50,911 | 3.16% | 2 / 4 |
| 18/90 | 04.03.2015 | parses, no refusal | 0 | 0 | 0 | 14,410 | 0.00% | 0 / 0 |
| 18/97 | 26.03.2015 | parses once withheld | 1 | 1 | 514 | 77,903 | 0.66% | 1 / 1 |
| 18/98 | 27.03.2015 | parses once withheld | 1 | 1 | 893 | 34,398 | 2.60% | 1 / 1 |
| 18/110 | 12.06.2015 | parses once withheld | 2 | 2 | 1,418 | 48,392 | 2.93% | 2 / 2 |
| 18/112 | 18.06.2015 | parses once withheld | 1 | 1 | 2,243 | 89,507 | 2.51% | 1 / 1 |
| 18/113 | 19.06.2015 | parses once withheld | 1 | 1 | 1,428 | 36,884 | 3.87% | 1 / 1 |
| 18/117 | 17.07.2015 | parses once withheld | 1 | 1 | 2,055 | 24,395 | 8.42% | 1 / 1 |
| 18/118 | 19.08.2015 | parses once withheld | 1 | 1 | 1,431 | 20,909 | 6.84% | 1 / 1 |
| 18/124 | 24.09.2015 | parses once withheld | 1 | 1 | 2,909 | 95,383 | 3.05% | 0 / 1 |
| 18/127 | 01.10.2015 | parses once withheld | 1 | 1 | 220 | 83,478 | 0.26% | 1 / 1 |
| 18/143 | 03.12.2015 | parses once withheld | 1 | 4 | 1,326 | 87,726 | 1.51% | 4 / 4 |
| 18/158 | 25.02.2016 | parses once withheld | 4 | 4 | 2,389 | 99,738 | 2.40% | 4 / 4 |
| 18/159 | 26.02.2016 | parses once withheld | 1 | 1 | 743 | 46,291 | 1.61% | 1 / 1 |
| 18/160 | 16.03.2016 | parses once withheld | 1 | 1 | 1,103 | 21,163 | 5.21% | 1 / 1 |
| 18/161 | 17.03.2016 | parses once withheld | 1 | 1 | 867 | 83,196 | 1.04% | 1 / 1 |
| 18/171 | 13.05.2016 | parses once withheld | 1 | 1 | 2,295 | 41,432 | 5.54% | 1 / 1 |
| 18/173 | 02.06.2016 | parses once withheld | 1 | 1 | 1,410 | 92,841 | 1.52% | 0 / 1 |
| 18/178 | 22.06.2016 | parses, no refusal | 0 | 0 | 0 | 12,820 | 0.00% | 0 / 0 |
| 18/180 | 24.06.2016 | parses once withheld | 1 | 1 | 919 | 54,550 | 1.68% | 1 / 1 |
| 18/184 | 08.07.2016 | parses once withheld | 1 | 1 | 1,353 | 42,433 | 3.19% | 1 / 1 |
| 18/193 | 29.09.2016 | parses once withheld | 1 | 2 | 1,441 | 85,494 | 1.69% | 2 / 2 |
| 18/210 | 16.12.2016 | parses once withheld | 1 | 1 | 2,369 | 50,593 | 4.68% | 1 / 1 |
| 18/215 | 26.01.2017 | parses once withheld | 1 | 1 | 880 | 84,257 | 1.04% | 1 / 1 |
| 18/219 | 17.02.2017 | parses once withheld | 2 | 2 | 1,838 | 39,931 | 4.60% | 2 / 2 |
| 18/221 | 09.03.2017 | parses once withheld | 1 | 2 | 1,256 | 112,922 | 1.11% | 2 / 2 |
| 18/223 | 22.03.2017 | parses, no refusal | 0 | 0 | 0 | 7,102 | 0.00% | 0 / 0 |
| 18/241 | 23.06.2017 | parses once withheld | 1 | 1 | 1,730 | 49,774 | 3.48% | 1 / 1 |
| 18/245 | 05.09.2017 | parses, no refusal | 0 | 0 | 0 | 30,202 | 0.00% | 0 / 0 |
| 19/1 | 24.10.2017 | parses, no refusal | 0 | 0 | 0 | 6,860 | 0.00% | 0 / 0 |
| 19/9 | 22.01.2018 | parses, no refusal | 0 | 0 | 0 | 12,756 | 0.00% | 0 / 0 |
| 19/12 | 02.02.2018 | parses once withheld | 2 | 2 | 1,127 | 38,093 | 2.96% | 2 / 2 |
| 19/13 | 21.02.2018 | parses once withheld | 3 | 3 | 258 | 14,874 | 1.73% | 3 / 3 |
| 19/14 | 22.02.2018 | parses once withheld | 1 | 1 | 183 | 89,943 | 0.20% | 1 / 1 |
| 19/18 | 02.03.2018 | parses once withheld | 2 | 2 | 1,434 | 40,742 | 3.52% | 2 / 2 |
| 19/19 | 14.03.2018 | parses, no refusal | 0 | 0 | 0 | 698 | 0.00% | 0 / 0 |
| 19/20 | 15.03.2018 | parses once withheld | 2 | 2 | 400 | 75,749 | 0.53% | 2 / 2 |
| 19/23 | 22.03.2018 | parses once withheld | 1 | 1 | 1,661 | 92,696 | 1.79% | 1 / 1 |
| 19/25 | 18.04.2018 | parses, no refusal | 0 | 0 | 0 | 18,043 | 0.00% | 0 / 0 |
| 19/32 | 16.05.2018 | parses once withheld | 1 | 1 | 789 | 70,028 | 1.13% | 1 / 1 |
| 19/36 | 07.06.2018 | refused, not narrowable | 0 | 0 | 0 | 113,658 |  | 2 / 2 |
| 19/40 | 15.06.2018 | parses once withheld | 1 | 1 | 1,432 | 56,318 | 2.54% | 1 / 1 |
| 19/42 | 28.06.2018 | parses once withheld | 1 | 1 | 558 | 108,846 | 0.51% | 1 / 1 |
| 19/44 | 03.07.2018 | parses once withheld | 1 | 1 | 1,007 | 79,902 | 1.26% | 1 / 1 |
| 19/47 | 11.09.2018 | parses once withheld | 1 | 1 | 862 | 59,882 | 1.44% | 1 / 1 |
| 19/59 | 19.10.2018 | parses once withheld | 1 | 1 | 312 | 52,556 | 0.59% | 1 / 1 |
| 19/61 | 08.11.2018 | parses once withheld | 1 | 1 | 742 | 104,751 | 0.71% | 1 / 1 |
| 19/68 | 29.11.2018 | parses once withheld | 2 | 2 | 2,135 | 94,212 | 2.27% | 2 / 2 |
| 19/73 | 16.01.2019 | parses, no refusal | 0 | 0 | 0 | 10,048 | 0.00% | 0 / 0 |
| 19/92 | 04.04.2019 | parses once withheld | 1 | 1 | 1,382 | 97,936 | 1.41% | 1 / 1 |
| 19/101 | 16.05.2019 | parses once withheld | 1 | 1 | 823 | 101,775 | 0.81% | 1 / 1 |
| 19/102 | 17.05.2019 | parses once withheld | 1 | 1 | 106 | 60,687 | 0.17% | 1 / 1 |
| 19/158 | 07.05.2020 | parses once withheld | 1 | 2 | 1,435 | 81,549 | 1.76% | 2 / 2 |
| 19/170 | 02.07.2020 | parses once withheld | 1 | 1 | 1,431 | 101,336 | 1.41% | 1 / 1 |
| 19/173 | 10.09.2020 | parses once withheld | 1 | 2 | 1,634 | 96,627 | 1.69% | 2 / 2 |
| 19/189 | 05.11.2020 | parses once withheld | 1 | 1 | 201 | 95,334 | 0.21% | 1 / 1 |
| 19/192 | 19.11.2020 | parses once withheld | 1 | 2 | 705 | 90,654 | 0.78% | 2 / 2 |
| 19/193 | 20.11.2020 | parses once withheld | 1 | 1 | 455 | 52,604 | 0.86% | 1 / 1 |
| 19/201 | 16.12.2020 | parses once withheld | 1 | 3 | 1,561 | 44,002 | 3.55% | 3 / 3 |
| 19/215 | 04.03.2021 | parses once withheld | 1 | 1 | 918 | 95,183 | 0.96% | 1 / 1 |
| 19/227 | 06.05.2021 | parses once withheld | 1 | 1 | 1,378 | 98,025 | 1.41% | 1 / 1 |
| 19/239 | 07.09.2021 | parses once withheld | 1 | 1 | 1,694 | 39,156 | 4.33% | 1 / 1 |
| 20/11 | 13.01.2022 | parses once withheld | 1 | 1 | 902 | 86,374 | 1.04% | 0 / 1 |
