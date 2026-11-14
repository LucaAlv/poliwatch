# Release review checklist

A main release becomes stable when the owner has run every step below on it and the record `docs/release-reviews/<version>.md` says "stable". Run it about every three months (plan decision Q3, `docs/plans/release-readiness.md`). The first release is reviewed in full and is the first stable.

**Inputs.**
- The candidate's release directory `data-<version>/`, checked with `shasum -a 256 -c SHA256SUMS`. Its SQLite is the asset `bundestag-pulse-<version>.sqlite.gz`.
- The last stable's release directory (none for the first).
- The source XML of the candidate's sittings: `data/xml/` of the site output directory the release was built from.
- CPP-BT's newest speech metadata from Zenodo (`CPP-BT_<date>_DE_CSV_Reden_Metadaten.zip`, concept DOI 10.5281/zenodo.4542661, CC0). Download it with the owner's approval, and record its version and SHA-256 in the review record. Never commit it.

**1. Coverage per year.** From the candidate's DATA.md, "Abdeckung nach Jahr und zurückgehaltene Reden" and "Ausgeschlossene Sitzungen":
- every exclusion's Grund reads „Fehler der Quelle, der die ganze Sitzung betrifft“ (`source_defect`) or „Ein Fehler, der sich nicht auf einzelne Reden eingrenzen lässt“ (`not_narrowable`); a „Wartet auf …“ Grund (`awaiting_rule`, `awaiting_acquisition`) stops the review. DATA.md prints these labels, not the keys (`EXCLUSION_REASONS` in `scripts/build_dip_pulse_site.py`);
- per year: sittings, Reden stored, Reden withheld, share withheld. Compared with the last stable, explain every year whose sittings fell or whose withheld share rose;
- per Wahlperiode: our sittings against CPP-BT's (step 4 prints both).

**2. Figures moved since the last stable.** `scripts/compare_store_values.py` takes two site output directories (each holding `data/bundestag-pulse.sqlite`). Use the candidate's output directory, and for the last stable a scratch directory with its SQLite unpacked to `<dir>/data/bundestag-pulse.sqlite`. Run it with `--cohort shared` and again with `--cohort all`. Pages read "unavailable", which is expected. Every value that moved in the shared cohort must be named by a correction in some release's `changes.json` between the two, or follow from a rule change the CHANGELOG names. An unexplained move is a bug (see "A bug found in review").

**3. Spot checks against the protocols.** Draw five sittings with a seed written into the record: one per Wahlperiode, plus the newest. In each, check against the protocol PDF:
- five Reden: Redner, Fraktion, TOP, and the opening and closing sentence;
- every withheld Rede: its reason, and that the text is the printed one;
- up to three named votes: the tally against the bundestag.de page, and the linked TOPs.

Also check every sitting that changed its status since the last stable (newly held, newly withheld Reden, released Reden).

**4. Comparison with CPP-BT, per sitting.**

```bash
python3 scripts/compare_cpp_bt.py --export <candidate sqlite or .sqlite.gz> --xml-dir <site output>/data/xml \
  --cpp-bt <CPP-BT zip> --out docs/release-reviews/<version>-cpp-bt.tsv
```

The script uses only the standard library and imports nothing of this project. It writes three blocks into one TSV (blocks start with a `# ` line): one row per sitting (an empty cell means that side does not hold the sitting, which is not zero), one row per difference with a `status`, and a summary with each input's SHA-256. It exits 0 whenever it compared, and 2 when an input is unreadable. The join rules are the script's own `sitting_key()` and `source_rede_id()`: a trailing ` (neu)` is dropped from CPP-BT's protocol number, `:N` from our `rede_id`, and `nested:` ids and ids without a value (Fragestunde) are skipped by name and counted in the summary. Pass when:
- no row has the kind `only_ours`, and the summary line `ids_only_ours` is 0: no `rede_id` of ours is missing from CPP-BT in a sitting both hold;
- every id only CPP-BT has carries a class. `withheld`, `paragraph_31`, `paragraph_31_continuation` and `reprint` pass as `classified`. `in_top_presidium`, `in_top_other`, `annex_zu_protokoll`, `annex_other`, `outside_top` and `unclassified` are read by hand unless `scripts/cpp_bt_known_differences.tsv` lists the id with a reason (`status` `known`). The 82 `in_top_other` ids of the first run are listed there: 81 reviewed procedural units (ADR 0004) and 21/43 `ID214301700`;
- surname and Fraktion differ on a shared id only where `scripts/cpp_bt_known_differences.tsv` lists the pair (spellings and name changes, each with a reason; `docs/source-errors.md` C5 and C6 for the two Fraktion rows). Any other is `read_by_hand`. A surname agrees when every word of CPP-BT's surname is a word of our name, a hyphen counting as a separator;
- word-to-token ratio: a shared Rede over 50 CPP-BT tokens whose ours-words to their-tokens ratio differs from its sitting's median by more than 15% is listed as `ratio`. Read the 20 largest by deviation. The ratio is a lead on text, not a verdict: of the first run's largest, three were read (19/72, 19/7, 18/44) and are Reden whose XML element holds what follows the speech, such as the whole debate, of the kind `docs/source-errors.md` C1 describes. **The two thresholds are first values, to be signed off by the owner after the first run** (`docs/release-reviews/cpp-bt-first-run-2026-11-14.md`).

CPP-BT is automatic too and does not check deeply. Agreement is no proof both are right; disagreement is a lead. The comparison covers units that carry a `rede_id`, so Fragestunde turns and the text itself are outside it.

**5. Claims.** Re-check the "Vergleich" table of DATA.md against each dataset's page when its date is more than six months before the candidate, and update the date. Check that the licence section still names the open roll-call question, or its answer. (The table lands with PR C of the release-readiness plan; until then this step has nothing to check.)

**6. Verdict.** Write the record: inputs and their digests, each step's result, findings with their fix release. Then tag `stable-<version>` on the commit of `data-<version>`, and archive the release on Zenodo once that exists.

**A bug found in review.** The candidate is not patched and does not become stable. The fix goes into a new main release. Replay the fix on a copy of the store (README, "Validate a data correction") and check that only the figures it should move moved. That release's `changes.json` names the correction, and steps 2 and 4 run again on the new release, limited to what the fix touches. The new release then becomes stable. Until then the last stable stays the stable one.
