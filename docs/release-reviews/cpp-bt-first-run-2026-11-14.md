# First run of `scripts/compare_cpp_bt.py`, 2026-11-14

Not a release review: the first run on the reference store, to check the join against the research note of 2026-11-07 (`docs/research/bundestag-corpora-landscape-2026-11.md`, "Cross-check against CPP-BT") and to calibrate the thresholds of `docs/release-review.md`, step 4.

## Inputs

| | |
|---|---|
| Export | `.context/dip-pulse-site/data/bundestag-pulse.sqlite`, replayed on v0.41.0.0 on 2026-11-14, 718 sittings. SHA-256 `4e17622b82c4480da893cd5a305a72a7a36e31c157e1ddb0b17c336ee7e6c1e5` |
| Source XML | `.context/dip-pulse-site/data/xml/`, 718 files |
| CPP-BT | `CPP-BT_2026-09-19_DE_CSV_Reden_Metadaten.zip`, Zenodo record 22844952, version 2026-09-19 (still the latest), 10,714,166 bytes, CC0. SHA-256 `d40cd969f96f34fd48cd56ee1f747b909f269cd4a9a22b49274997ce5b186dee`, the digest the research note records. Zenodo's own MD5 `4c82f8f95b92f30f3c8208d9b482ba08` matches. Downloaded with the owner's approval, kept outside the repository |
| Run | `uv run --python 3.13 python -I scripts/compare_cpp_bt.py ...`, about 4 seconds, exit 0. The full TSV (802 sitting rows, 3,523 difference rows: 1,487 ratio, 1,752 only theirs, 282 surname, 2 Fraktion) is not committed: it is reproducible from the inputs above |

## Join figures against the research note

Per Wahlperiode, sittings ours / theirs / both, and `rede_id`s in shared sittings ours / theirs. Ours is "both" because no id of ours is missing from CPP-BT.

| WP | Sittings | Ids in shared sittings | Only ours | Only theirs | Note, 2026-11-07 (716 sittings): ids ours / theirs, only theirs |
|---|---:|---:|---:|---:|---|
| 18 | 194 / 244 / 194 | 13,816 / 14,373 | 0 | 557 | 13,790 / 14,373, 583 |
| 19 | 206 / 239 / 206 | 22,501 / 23,010 | 0 | 509 | 22,506 / 23,010, 504 |
| 20 | 213 / 214 / 213 | 25,840 / 26,403 | 0 | 563 | 25,869 / 26,403, 534 |
| 21 | 105 / 94 / 94 | 11,615 / 11,738 | 0 | 123 | 11,643 / 11,738, 95 |

CPP-BT's side and the 8,235 ids in the 84 sittings we exclude match the note exactly (4,151 + 3,950 + 134 + 0). Our side moved with two releases since the note, and the movement explains every cell:
- **Added since the note (v0.36.0.0, `docs/plans/reden-outside-tops.md`):** the 29 Reden outside any TOP (WP 18: 29) and the 16 written submissions of 18/133 and 18/134. WP 18: 13,790 + 45 = 13,835.
- **Removed (v0.40.0.0, ADR 0004):** oath answers and election acceptances, 82 in all: 19 in WP 18, 5 in WP 19, 29 in WP 20, 29 in WP 21. WP 18: 13,835 − 19 = 13,816. WP 19: 22,506 − 5 = 22,501. WP 20: 25,869 − 29 = 25,840. WP 21: 11,643 − 28 = 11,615 (WP 21 removed 29, but the 29th, `ID2110100100` in 21/101, sits in a sitting newer than CPP-BT's file, so only 28 move the shared ids; 21/43 `ID214301700`, which the note counted as "not lost" and never held, is a separate unit and none of the 82).
- **Only theirs, 1,752 now against 1,716:** 1,666 § 31 declarations, 2 `paragraph_31_continuation` (19/115), 2 `reprint` (19/35, 19/45), and 82 `in_top_other`, which are the 81 reviewed procedural units and 21/43 `ID214301700`. The 16 and 29 the note called lost are no longer missing. 1,666 + 4 + 82 = 1,752.

The sittings columns match the note's for WP 18 to 20. WP 21 holds 105 sittings now (103 then); 11 sittings are newer than CPP-BT's file.

## Who and which Fraktion

- **Surname:** 73,767 shared ids compared (5 had no name on a side), **282 differ**. The note counted 185 of 73,803 with a matching rule it does not record, so the two counts are not comparable; this run is stricter on diacritics (Dağdelen against Dagdelen counts) and looser on hyphens (`Alabali-Radovan` agrees with `Alabali Radovan`, `Bluhm` with `Bluhm-Förster`). All 282 fall into 12 pairs, each listed with its reason in `scripts/cpp_bt_known_differences.tsv`: 175 diacritics (Dağdelen 138, Özoğuz 37), 33 Kemmer / Schmitt, 19 dos Santos-Wintz / dos Santos Firnhaber, 20 `von der Leyen` / `der Leyen` where our name omits the prefix, 10 Benkstein / Lenk, 10 `SchulzeSchulze` (the XML repeats the name), 9 Obermeier / Bartz, 4 Willkomm / Kloke, and two Reden whose XML name element joins two persons (20/82, 20/94). The reasons come from the XML's printed names, read for one Rede of each pair.
- **Fraktion:** 64,156 shared ids compared (9,616 have no label on one side), **2 differ**: 20/94 `ID209407600` (C5) and 18/222 `ID1822204600` (C6), the two the note found. Folding removes label noise only: `Gruppe ` prefix, case, dots. Both are listed.

## Token ratio, and the thresholds for sign-off

On 53,819 shared Reden with more than 50 CPP-BT tokens, the ratio of our words (`text.split()` of our speeches, summed over a split element's parts) to their tokens has a sitting median between 0.85 and 0.89 in 99% of the 705 sittings it can be computed for (all lie between 0.826 and 1.069; the middle 80% between 0.864 and 0.874).

With the first values, a 15% deviation from the sitting's median and a 50-token floor:

| Deviation above | Reden listed | of them with fewer words than their tokens suggest |
|---:|---:|---:|
| 15% | 1,487 (2.8%) | 963 |
| 25% | 569 | 453 |
| 40% | 206 | 189 |
| 60% | 90 | 84 |
| 80% | 25 | 21 |

Three of the largest were read: 19/72 `ID197202600` (our 16 words, their 1,457 tokens), 19/7 `ID19709200` and 18/44 `ID1804401200` (259 against 5,275). In each the XML `<rede>` runs on past the speech into the rest of the sitting's business (19/72 and 19/7 are an AfD motion on the Beschlussfähigkeit, whose element goes on to the chair's remarks, and in 19/7 to the end of the sitting; 18/44 ends with the chair resuming the Haushaltsberatungen), so CPP-BT counts all of it as one Rede and the parser stores the speech part. This is the pattern of `docs/source-errors.md` C1 and TODOS.md "WP 18/19: nested Erwiderung, Erklärung and Geschäftsordnung turns"; nothing here is new to the store. Adding our nested Zwischenfragen, Kurzinterventionen and Erwiderungen to our words made the fit worse (3,425 listed), so CPP-BT's token count does not include them and the script does not add them.

**For the owner to sign off:**
- **15% and 50 tokens:** the list is 1,487 long, so the 20-largest rule does the reading, not the threshold. Raising the tolerance to 25% would list 569 and keep every deviation the 20 largest show. Recommendation: keep 15% as the listing threshold (a listing costs nothing), keep the 20-largest reading rule, and re-run on every stable review to watch the count move.
- **Five sittings in the spot check (step 3):** this run did not exercise step 3; the size stays a first value.

## What the run did not find

No id of ours is missing from CPP-BT in a shared sitting (`ids_only_ours` 0). No id only CPP-BT has is `unclassified`, `outside_top`, `annex_zu_protokoll` or `annex_other`. After the known-differences file, the only rows left for a person to read are the 1,487 ratio rows.

## Correction after review

The first version of the script skipped a Rede whose stored text is empty, so the worst case, no words at all, was the one silent case. It now counts such a Rede as 0 words and lists it. On this store that adds one row, the second largest by deviation (1.000, as for every Rede with no text): 19/2 `ID19205800` (Altmaier), 0 words against 1,000 CPP-BT tokens. Only 21/43 `ID214301600` is larger (683 words against 261 tokens, deviation 2.015; our Rede holds Frömming's resumed speech that CPP-BT lists as `ID214301700`, `docs/data-methods.md`). It is the speech with an empty `<redner id>`, which the store keeps as an unattributed speech without its text (`docs/source-errors.md` E2: 6,180 characters, counted as unattributed). A review reading the 20 largest will meet it among the first two each time. Every figure above that moved by it moved by one (ratio rows 1,486 to 1,487, compared Reden 53,818 to 53,819, and each row of the threshold table by one); no other figure changed. The same store replays to the same bytes twice.
