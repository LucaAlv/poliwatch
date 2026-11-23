# Speaker markers outside any `<rede>`

Prepares the owner decision on a parser gap found on 2026-11-22. It came up while recounting the sentence in `docs/data-methods.md`, "Begriffe und Zählgrenzen" (TODOS.md "Vergleich section in DATA.md", item 5, first bullet). That sentence says markers outside a `<rede>` hold "meist kurze Antworten wie „Ja, gerne.“, im Median 8 Wörter, zusammen rund 1.750 Wörter". The figure was wrong when it was written. The population is 74 markers holding 19,686 words, including 23 whole Reden.

Measured on 2026-11-22 against main v0.46.43.0 (d9d2f12), read-only on the reference store `.context/dip-pulse-site` (806 sittings, replayed on v0.46.42.0). Nothing is built here.

**Built 2026-11-22** on the owner's answers (section 4). The build changed two things the review did not foresee:
- **19/114 M7 and M10 are remarks, not Fragen.** They were proposed as `befragung_frage`. Each is the asker accepting the offer of a Zusatzfrage ("Ja, eine Zusatzfrage, wenn ich darf.", "Ja, gerne."), followed by the Frage under its own marker. The Befragung rules give each marker a Beitrag of its own, so they would have counted two Fragen too many.
- **A `next` move leaves the chair text in the TOP.** Moving the chair's words into the `<rede>` together with the turn hid the Kurzintervention announcement in 20/9, and Hilse's Kurzintervention and Wenzel's Erwiderung turned into Reden. Now only the turns move.

**Recommendation in short:** store every one of these turns as what it is (option S): a Rede, a Beitrag, or words added to the neighbouring Rede, bound by a reviewed list entry per marker, as #207 did for speakers printed as `<name>`. A marker with no entry refuses its sitting, so the gap cannot reopen unnoticed.

## 1. What the source shows

### The 2026-11-12 count was right on markers and wrong on words

The coverage gate's PR 1 (`docs/plans/coverage-gate-w1-w2.md`, "PR 1 validation") counted `<p klasse="redner">` elements that stand directly in a Tagesordnungspunkt (TOP) that is not a Fragestunde. On the 718 sittings it found 50 such markers in 24 sittings. Today's census finds exactly the same markers in those 24 sittings, plus 24 in 7 sittings that T4 and the 18/62/18/90 run restored since: 18/2, 18/6, 18/10, 18/26, 18/83, 19/14 and 19/201.

The word count stopped at the first element that is not a paragraph, which is usually a `<kommentar>` with applause. That gave 4,313 words across today's 74 markers, where the old figure for its 50 was about 1,750. Counting each marker's paragraphs up to the next marker, `<name>` or `<rede>` gives 19,686. For example, Kassner's report in 18/115 is 346 words, not 292, and Gabriel's Rede in 18/33 is 2,194 words, not 214.

### None of it is stored

The parser reads text outside a `<rede>` only in a Fragestunde (`speech_kinds.fragestunde_turns`). The Rede reconciliation counts `<rede>` elements, so these markers fall outside it (TODOS.md "Rede reconciliation", item 3).

For each marker, the census takes 80 characters from the middle of its longest paragraph and searches every stored speech and contribution of the sitting. Only 7 of 74 are found, and all 7 are stock phrases that occur elsewhere in the sitting: "Ja, gerne.", "Vielen Dank.", "Bitte schön.". A first pass that probed each turn's opening found 12. Five of those hits were salutations ("Sehr geehrter Herr Präsident! Liebe Kolleginnen …"), which match any Rede. A hand check confirms the result: Jan Korte's Rede opening the Aktuelle Stunde in 18/7 (885 words) is in no table.

### The population: 74 markers, 46 runs, 31 sittings

The full list is [`loose-speaker-markers.tsv`](loose-speaker-markers.tsv), one row per marker. Two scripts reproduce it:

```bash
python -I docs/plans/loose-speaker-markers/census.py <store> census.tsv
```

```bash
python -I docs/plans/loose-speaker-markers/classify.py census.tsv docs/plans/loose-speaker-markers.tsv
```

`census.py` opens SQLite with `mode=ro&immutable=1`. A *run* is the stretch of a TOP between two `<rede>` elements (or the TOP's edge). `M<ordinal>` is the marker's 1-based position among all markers standing directly in the sitting's TOPs, Fragestunde TOPs included, in source order. `classify.py` holds the proposed kind and attachment for each marker. That table is the review.

The runs follow two patterns:

- **A TOP opens without `<rede>`** (15 runs, 11 sittings, all WP 18). The chair opens the debate, and every Rede up to the first `<rede>` is printed loose, including Zwischenfragen, consents and the chair's remarks. 18/6 TOP 16 prints Golze, Bär and Brantner this way. 18/10 TOP 3 prints Annen (with Ströbele's Zwischenfrage) and Beyer. 18/23 ZP 4 prints four Erklärungen nach § 31 in a row.
- **A short turn just outside a `<rede>`** (31 runs). A speaker answers the chair before their own `<rede>` starts ("Das Wasser fehlt.", "Genau.", "Ja, sehr gerne."), or adds a line after it ends. 19/114 TOP 1, a Befragung der Bundesregierung, holds 11 such runs: consents, Zusatzfragen and Scholz's short replies.

| Kind | Markers | Words | What it is | Becomes |
|---|---:|---:|---|---|
| `rede` | 23 | 16,639 | A whole Rede: 15 debate Reden, 7 Erklärungen nach § 31 (Kipping, Wadephul, Haßelmann and Gysi in 18/23; van Aken 18/91; Hupach 18/115; Sitte 18/2), and Kassner's report as Berichterstatterin in 18/115. | A Rede of that speaker, in a wrapped `<rede>` |
| `own_words` | 36 | 2,376 | The speaker's own later turns. Eight lie inside a loose Rede (1,744 words): consents to a Zwischenfrage, the answer to it, and continuations after a chair remark. Six follow the speaker's own `<rede>`, including Kühne's last 407 words in 19/62. Twenty-two come just before it: consents, "Genau.", or a first sentence before the chair interrupts. | Words of that Rede (`wrap`), or of the `<rede>` just before (`prev`) or after (`next`) |
| `zwischenfrage` | 2 | 269 | Ströbele in Annen's Rede (18/10), Lay in Koeppen's (18/83). | A Zwischenfrage Beitrag |
| `befragung_frage` | 4 | 63 | Zusatzfragen of Glaser, Stark-Watzinger and Toncar in 19/114, printed after the minister's `<rede>`. | A Frage Beitrag in that `<rede>` |
| `befragung_antwort` | 2 | 23 | Scholz's reply to Schmidt's remark (19/114), Merkel's remark after Rüthrich's Frage (19/201). | An Antwort Beitrag, as Wanka's answers in #207 |
| `procedural` | 3 | 11 | Bartels accepts his election (18/76); Pistorius and Kukies thank the House after their oath (20/79, 20/197). | A procedural diagnostic, as oath answers are |
| `sitzungsleitung` | 1 | 296 | 19/14 TOP 8 prints Vizepräsident Oppermann with a speaker marker for the vote that closes the TOP and a remembrance of the Geschwister Scholl. | Chair text, stored nowhere |
| `remark` | 3 | 9 | Gremmels declines a Nachfrage ("Nein."); Glaser and Stark-Watzinger accept the offer of a Zusatzfrage before asking it (19/114 M7, M10). | Nothing |

Every `next` and `prev` attachment was checked against the `<rede>` it joins. Each `own_words` turn joins a `<rede>` of the same speaker. Each `befragung_*` turn joins the minister's answer or the asker's Frage next to it.

## 2. The options

- **S, store them by reviewed entries.** One entry per marker in `scripts/reviewed_units.json`, generated from the TSV. The machinery is #207's: a wrapped `<rede>` for a Rede outside any `<rede>`, and a `listed_kind` on markers the existing rules must classify a given way. Moving a short turn into its neighbouring `<rede>` is new.
- **R, refuse the 31 sittings.** This is what the reconciliation would do if it counted these markers. It drops 31 sittings to save 19,686 words. Withholding under ADR 0005 is not available, because a marker outside any `<rede>` belongs to no unit that could be withheld.
- **D, document the gap.** Rewrite the data-methods sentence with the true figures and change nothing else. 23 Reden stay missing from 23 person pages, and per-MP and per-Fraktion counts stay low.

S is the only option that matches the dataset's rule that every Rede the protocol prints is counted. D leaves a known wrong figure in the release.

## 3. Figures S moves (estimated from the TSV, measured by the replay)

- **Reden:** 61,637 → 61,660 (+23, all WP 18), about 18,400 words: 16,639 in their opening turns and 1,744 in their later turns. By side, from the printed markers: Die Linke +10 (Sitte, Golze, Korte, Kipping, Gysi, Hein, Lay, van Aken, Kassner, Hupach), CDU/CSU +6 (Bär, Beyer, Wadephul, Binninger, Weinberg, Koeppen), SPD +3 (Annen, Rüthrich twice), BÜNDNIS 90/DIE GRÜNEN +3 (Brantner, Haßelmann, Beck), and Bundesregierung +1 (Gabriel as minister; his marker prints his Fraktion, and the Sprechrolle decides, ADR 0001).
- **Beiträge:** 45,991 → 45,999 (+8): two Zwischenfragen, four Befragung Fragen and two Antworten.
- **Words added to existing Reden:** 632 (the 28 `own_words` turns with `prev` or `next`).
- **First Reden:** three of the 23 are their speaker's first stored Rede of WP 18. Bär moves from 2014-07-03 to 2013-12-19, Brantner from 2014-01-29 to 2013-12-19, and Beyer from 2014-02-20 to 2014-01-29.
- **Sittings:** stored rows change in 27 sittings. In the other four, nothing stored changes: 18/76, 20/79 and 20/197 gain a procedural diagnostic, and 19/14 gains nothing.
- **Fakten, coverage, Redeanteil:** measured by the replay, not here. Every Rede added falls in WP 18 weeks that already have Reden.

## 4. Recommendation and owner questions

**Store them (S).** **The owner answered all three as recommended on 2026-11-22:** S, the TSV is the review, and the seven oral Erklärungen nach § 31 count as Reden for now.

Questions, my pick first:

1. **Store the 74 markers by reviewed entries (S), rather than refuse 31 sittings (R) or only document the gap (D)?** A: S.
2. **Is the TSV's `kind` and `attach` per marker your review, so that the build writes `scripts/reviewed_units.json` from it?** Yes. (No means you read the 74 rows in the build PR first.) Every marker carries its printed Redner-ID, so no identity question arises. Kühne's 407 words in 19/62 and Lechte's first sentence in 20/115 are the cases most worth reading.
3. **Count the seven oral Erklärungen nach § 31 as Reden?** Yes, for now. No rule names an oral § 31 statement printed as a `<rede>` in the Sitzungsverlauf. Written ones are excluded by a named rule (`ANNEX_EXCLUSIONS`, including the 37 that 18/158 prints in its Sitzungsverlauf). A quick scan found three `<rede>`s that follow the chair giving the floor "nach § 31 der Geschäftsordnung": two are stored as Reden and one as a Beitrag. Whether an oral § 31 statement is a Rede at all is a separate question that would move both kinds together, so it goes to TODOS.md and not into this build.

Settled by this plan and not asked:
- A marker outside any `<rede>` in a TOP that is not a Fragestunde, with no entry, refuses its sitting. This is #207's rule for `<name>` outside any `<rede>`.
- A wrapped Rede ends after the last turn listed into it. Trailing chair text stays in the TOP, as does the roll-call result Pau reads in 18/10 TOP 3 before Neu's Rede.
- The Sitzungsleitung, procedural and remark kinds store no text.

## 5. Build outline (option S)

**Parser** (`scripts/validate_dip_protocol.py`):

- `mark_loose_markers(root, entries, created)` runs right after `mark_name_speakers`, so the `N<ordinal>` Reden it wraps are `<rede>` elements already. It numbers the markers that stand directly in a TOP, in source order, and looks each one up by `M<ordinal>` and Redner-ID. A marker in a Fragestunde TOP is skipped. The TOP format is known before classification, so the function takes the Fragestunde TOPs from the same `speech_kinds.heading_formats` test the census uses.
  - **`rede` (`wrap`):** the marker, its paragraphs and everything up to the end of the last turn whose entry says `wrap` for this Rede are wrapped into `<rede id="M<ordinal>">`. That covers chair remarks, consents, Zwischenfragen and continuations. The id goes into `created`, as #207's `N<ordinal>` ids do.
  - **`own_words`, `zwischenfrage`, `befragung_*` with `prev` or `next`:** the marker and its paragraphs, plus the chair text between them and the `<rede>`, move to the end or the start of that `<rede>`. A `next` move goes in after the `<rede>`'s own first marker, so the owner test (`rede.find("./p[@klasse='redner']")`) is unchanged. The marker carries `listed_kind` for a Beitrag kind, as in #207.
  - **`procedural`:** a diagnostic, as `name_procedural`. **`sitzungsleitung`, `remark`:** nothing.
  - **Unlisted:** `UnlistedLooseMarkerError(ValueError)`, which refuses the sitting. **Stale entry**, or a Redner-ID that differs from the marker's: `ReviewedUnitsError`.
- `reconcile_reden` records the `M<ordinal>` Reden as emitted.
- `mark_presidium_markers_outside_reden`'s docstring ("which only a Fragestunde reads", `:1251`) is corrected.

**List** (`scripts/reviewed_units.py`, `scripts/reviewed_units.json`):

- New kinds `loose_rede`, `loose_own_words`, `loose_zwischenfrage`, `loose_befragung_frage`, `loose_befragung_antwort`, `loose_procedural`, `loose_sitzungsleitung` and `loose_remark`, plus one key, `attach` (`wrap`, `prev`, `next` or `none`). `rede_id` is `M<ordinal>`. `redner_id` is the marker's printed id and is required, because every marker prints one.
- 74 entries, generated once from the TSV by a script in the PR.

**Rules and versions:**

- `speech_kinds.VERSION` 11 → 12, because the parse output changes. That forces a full re-read.
- No new withheld reason, so no export-format bump is expected. Check `scripts/data_dictionary.json` in the build.
- No store schema change.

**Tests** (`tests/test_loose_markers.py`, synthetic XML):

- a TOP that opens loose with two Reden, a Zwischenfrage and a continuation;
- a wrap that stops before trailing chair text;
- `prev` and `next` moves, including a Beitrag kind;
- procedural, Sitzungsleitung and remark;
- a Fragestunde TOP left alone;
- an unlisted marker refuses;
- a stale entry and a wrong Redner-ID stop the run;
- interaction with an `N<ordinal>` name Rede in the same run.

`reviewed_units` tests cover the new kinds and the `attach` key. `scripts/check_withhold_one.py` and the full suite stay green.

**Docs:**

- `docs/data-methods.md`: replace the sentence with what the parser now does. No marker outside a `<rede>` goes unread: it is read by a reviewed entry or refuses its sitting.
- ADR 0004 or a new short ADR amendment, the same shape as #207's.
- `docs/source-errors.md`: a new entry for WP 18 TOPs printed without `<rede>`.
- CHANGELOG.
- TODOS.md: close "Rede reconciliation" item 3's TOP-marker half and "Vergleich" item 5's first bullet. Add the oral § 31 question.

**Replay:**

- One full `--offline --repersist` of a copy of the reference store.
- `scripts/compare_store_values.py` against a `cp -cR` baseline, following the README recipe "Validate a data correction".
- Expected: stored rows change in exactly the 27 sittings of section 3, and Reden rise by 23. Then a store gate run on the release main.

**Size:** about 150 lines of parser, 40 of list code, 74 generated entries and 250 lines of tests, plus docs. One PR, one replay.
