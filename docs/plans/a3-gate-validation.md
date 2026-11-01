# A3 Phase 0: merged A1/A2 gate on the reference store (2026-10-19)

Closes the TODOS gate "Validate final merged A1/A2 before the A3 backfill". Receipt: [a3-gate-validation.json](a3-gate-validation.json), written by `scripts/validate_store_gate.py`.

## What ran

- Input: an APFS clone (`~/agent-runs/a3/gate`) of the reference directory `.context/dip-pulse-site` (291 cached report files, 290 reports in the catalog, 290 XML files, catalog fetched 2026-10-06). The reference directory was not touched.
- Code: `main` at v0.20.0.0 (cfcd249) plus the gate script (43ab74d). The receipt's `commit` field reads 4b4c0fe, the docs-only commit before the gate script; scripts are identical.
- `--today 2026-10-19` on every replay, so the stored facts are comparable.
- Full suite before the run: 1,350 tests, OK (2 skipped).

## Checks

| Check | Result |
|---|---|
| `--offline --repersist` of the clone | exit 0, 290 reports persisted, store replaced (453 s) |
| `PRAGMA integrity_check` / `foreign_key_check` | ok / 0 violations |
| Fresh store vs. store from every other report, then replayed with all | identical grouping fingerprint `e1b3a6af…`, 3,094 persons, 198,186 bindings |
| Replayed store vs. fresh store, on the bindings the fresh store holds | identical; the replayed store also keeps 10 bindings of retired occurrence ids (registry carry-forward, by design) |
| Second, unchanged replay | exit 0, "store content unchanged, file kept": same sha256, size, mtime and inode |
| Link audit, 3,224 pages | 209,897 local links and anchors, 0 broken |
| Export (`datenstand.json`, generation `g-d0feab75c821`) | 28 files match size and sha256; protocols 290, votes 217, vote members 154,015 equal the store |
| `--validate-publication` | passes |

The replayed-vs-fresh comparison is an extra check, not one of the plan's. Its first version compared all bindings and failed on those 10 carried-forward bindings: six `contribution-v1-…` and four `speech-v1-…` ids that are in the reference store's registry but in no report any more (their occurrences were re-keyed by later speech rules). On the 198,186 live bindings the grouping is identical. The check now compares live bindings and reports the carried-forward count; the receipt value was recomputed on the same stores after the run.

## 21/50

Plan step 2 (reacquire 21/50) was not needed on this store: the repersist accepted 21/50. The TODOS entry "Cached report 21/50 no longer matches its XML" was measured on another cache (`right-counts-a1/after`); this reference directory's 21/50 report is byte-identical to the one in the post-v0.20 replay `~/agent-runs/b3-review-replay`, which also persisted it.

## Figures against the last combined run (2026-10-05)

| Figure | 2026-10-05 (`a1-scratch-validation.json`) | 2026-10-19 | Change | Why |
|---|---:|---:|---:|---|
| Reden | 26,271 | 26,267 | −4 | speech rule 5 (offline-v5): Brandner's turn becomes a Kurzintervention, the replies of Rosenthal and Scholz Erwiderungen, and the other reclassified turns in [offline-v5-validation.md](offline-v5-validation.md) |
| Beiträge (contributions) | 16,799 | 16,787 | −12 | same rule changes; per kind below |
| zwischenfrage | 1,448 | 1,433 | −15 | the 2026-10-05 snapshot predates rule 4/5; the rule-5 audit of these 290 XML files counts 1,433 (offline-v5-validation.md) |
| erwiderung | 596 | 598 | +2 | rule 5 (Rosenthal, Scholz) |
| kurzintervention | 646 | 647 | +1 | rule 5 (Brandner) |
| befragung_*, fragestunde_*, zu_protokoll | 3,901 / 3,961 / 2,687 / 2,701 / 859 | same | 0 | |
| Persons (distinct `person_id` of `person_records`) | 3,370 | 3,094 | −276 | 3,370 was measured on the A1 scratch overlay before roll-call member records and name pass 3 (v0.14.0.0–v0.17.0.0); `main` v0.17.0.0 already read 3,095 on this reference directory, and the order-independent evidence fold (v0.17.1.0) made it 3,094 ([a2-validation.md](../a2-validation.md), "Re-measured on the merged tree") |
| Source records / bindings | 4,263 / 198,200 | 4,306 / 198,196 | +43 / −4 | +43 roll-call member records (v0.14–v0.17, same source); bindings follow the re-keyed occurrences |

Every Rede and Beitrag count equals the final rule-5 audit of the same 290 XML files, so no figure moved for an unexplained reason. Documents: 8,117 (no 2026-10-05 figure recorded).

## Timing and memory

Not for extrapolation: the full test suite ran alongside for its first ~90 s. Total 1,571 s. Repersist plus render plus export 453 s, unchanged replay 360 s, database-only persists 248 s (fresh), 116 s (half), 254 s (half then full). Largest process RSS 2.59 GB (the replay with render), against the 1.3 GB measured earlier for loading the reports alone.
