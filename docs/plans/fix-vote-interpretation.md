# Fix vote interpretation

Planning only, 2026-10-23, based on `429556b` on branch `plan/fix-vote-interpretation`.
Source todo: [Vote reading misses half the inverted votes and never stores it](../../TODOS.md#vote-reading-misses-half-the-inverted-votes-and-never-stores-it), P1.

## Findings verified while planning

- The reference store at `.context/dip-pulse-site/data/bundestag-pulse.sqlite` has 217 votes with both `inverted` and `result_raw` NULL. Its cached reports contain 246 vote occurrences, also without populated interpretation fields. The blanks precede storage; this snapshot does not establish why they were originally omitted.
- `fetch_roll_call_vote_detail` populates official/result fields and calls `interpret_vote`; `enrich_with_api` interprets again with matched DIP documents and procedure context (`scripts/validate_dip_protocol.py:1866`, `:2851`). There are no other interpretation callers. The present online path therefore differs from a replay; an actual online build remains unverified.
- `repersist_cached_reports` loads reports and reparses XML, but never interprets votes (`scripts/build_dip_pulse_site.py:1769`). `persist_vote` writes the supplied values, including NULLs (`scripts/persist_dip_pulse_store.py:1242`). `_write_csv` exports those columns directly (`scripts/build_dip_pulse_site.py:2957`). Existing columns suffice.
- The detector misses vote 906. Its cached protocol `20/157` explicitly recommends rejecting Antrag `20/9143`, then opens the roll call on Beschlussempfehlung `20/10433`. All 14 missed IDs have local report and XML sources; document-linked recommendation paragraphs exist for each. That establishes available evidence, not yet that one extraction rule handles every case.
- `_official_vote_text` requires an exact Ja/Nein match (`scripts/validate_dip_protocol.py:1472`). Cached XML for vote 996 (`21/67`) confirms the read-out tally of 438/135; the report holds the final 439/135. The research note records the page's outcome as `Antrag 21/4466 abgelehnt`; that page text was not fetched again during planning.
- Rendering already consumes these fields: `derive.vote_outcome` respects `result_scope="application"`, and `features/votes.py` supplies the inversion legend, Antrag badge prefix and fraction positions. A corrected raw recommendation result must be inverted once; an official Antrag result must not be inverted again.

## Scope and decisions

Use protocol evidence to identify the voted object and recommendation direction; use the Beschluss page for its official outcome. Keep final counts unchanged. Reuse `interpret_vote`, the existing XML replay and atomic store rebuild, the current exporter and panel rendering.

No schema or export-format bump, new dependency, new acquisition command, majority-rule expansion, or B4 prose work. Defer `majorityType`, timestamps and Fundstelle anchors from the todo's optional context. Do not change persistence to conceal missing report data with SQL defaults or unconditional carry-forward.

The largest correctness risks are attaching another vote's evidence in a bundled TOP, mistaking a vote on a Gesetzentwurf for a vote on its recommendation, and applying an inversion twice. Ambiguous evidence stays unknown; it never earns an official label.

## Implementation order

### 1. Pin the missing cases and the online/replay boundary

Add small source fixtures for WP20 vote 906, vote 996's Beschluss block, and a real `zu Gesetzentwurf … (… ablehnen)` non-inversion. Record vote ID, protocol, document numbers and source retrieval date. Use the existing 1002 fixture for compatibility; include 1005 in replay acceptance.

Exercise the fresh acquisition path with fixture-backed fetches, then serialize, reload and repersist the same report. Compare interpretation fields at each boundary. Also start with the legacy shape missing those fields. This distinguishes missing input from a serialization or upsert loss without needing a paid or live service in unit tests.

Files: `tests/test_b1_interpretation.py`, `tests/test_roll_call_scraping.py`, `tests/test_repersist.py`, and minimal additions under `tests/fixtures/`.

### 2. Extract attributable protocol evidence and share interpretation

Extend the existing protocol parser to retain only the procedural evidence needed for vote interpretation. Read the chair's announcement/recommendation passages from the sitting proceedings, including across adjacent paragraphs; do not scan arbitrary speeches or annex declarations as authoritative announcements. Associate evidence by the named Drucksachen and voted object, with a unique vote match. A result can be announced under a later TOP, so TOP membership alone must not decide attribution.

Require evidence that the vote is **on the recommendation to reject the Antrag**. A rejection recommendation merely mentioned during a vote on the Gesetzentwurf, Antrag or Änderungsantrag does not establish inversion. An explicit vote on a Vorlage must prevent a title fallback from overriding that object. Acceptance, negation, conflicting passages and ambiguous document/part matches must remain conservative.

Feed this evidence into `recommendation_inversion`/`interpret_vote`, recording its source and a bounded excerpt in the existing provenance fields. Retain the current title/DIP fallback only where it is unambiguous and does not contradict stronger object evidence. Do not infer direction from which Fraktion voted Nein.

Extract the existing sitting-wide document/procedure-context assembly into the smallest shared report interpretation step needed by both online enrichment and XML replay. Preserve special-majority unknown results and official application scope. Reinterpretation must be idempotent.

JSON reload creates separate dictionaries for repeated copies of a vote. Derive once from all attributable evidence, then apply the same interpretation to every occurrence used by panels, sitting votes and report provenance; one duplicate must not erase another's evidence during persistence. Reuse existing vote identity/iteration helpers.

Files: `scripts/validate_dip_protocol.py`; extend the existing interpretation and replay tests. No renderer-side inference.

### 3. Match official outcomes without requiring identical provisional counts

Adapt the existing Beschluss parser to identify bounded vote blocks, using their roll-call announcement, tally and immediately associated outcome. Resolve a unique block by its relevant Drucksache/object evidence; keep exact tally matching as the fallback where document evidence is absent. A shared Drucksache or several parts of one recommendation is not a unique match.

For a document-identified block, a small provisional/final discrepancy must not discard its explicit outcome. Do not introduce an unrestricted ±3 search across the whole Beschluss section. Keep the existing refusal rules for conflicting document numbers, duplicate candidates, negation, missing outcomes, blank-line/paragraph boundaries and neighboring decisions. If document attribution cannot distinguish blocks, return unknown rather than choose the nearest tally.

Use the same matched block to obtain both the outcome and its scope, so those cannot come from different matches. For 996, the page's `Antrag … abgelehnt` means `result_raw="rejected"`, `result_source="official"`, `result_scope="application"`, with `inverted=True`; the panel must still say the Antrag was rejected. Keep final counts 439/135.

Tests must cover a one-vote discrepancy, a three-vote discrepancy from the measured corpus, a nearby unrelated tally, conflicting documents, two blocks sharing documents, and a documentless exact-match compatibility case. Add a full detail-fetch test proving matching, scope and interpretation cooperate.

Files: `scripts/validate_dip_protocol.py`, `tests/test_roll_call_scraping.py`, and the interpretation fixtures/tests.

### 4. Repair cached reports and prove storage/export/panel parity

Wire the shared interpretation step into the existing `--offline --repersist` XML reparse path before the fresh store is built. Persist and render those same prepared report objects, then save the repaired JSON through the existing report writer. Follow the existing source-identity checks and failure behavior: a failed reparse/rebuild must leave the prior store intact.

Offline recovery can derive ordinary outcomes and recover inversions from cached XML/DIP evidence. It cannot recover the page's official wording when that evidence was never cached. Preserve already recorded official results and scope during replay; do not relabel a derived result as official. Missing source evidence must not silently clear a previously supported interpretation. A contradictory fresh source requires an explicit test and conservative resolution, rather than blanket preservation.

Use existing targeted acquisition (`--document-number`, with votes enabled) to refresh `21/67` for 996's official result and any other reports whose official page evidence needs recovery. First compare a focused online acquisition with its saved JSON and subsequent offline replay on a disposable site copy. No live-site or reference-cache mutation is part of planning. Normal `--offline` then reuses the repaired reports; document that legacy caches need the one-time repersist, plus an online refresh where official evidence is missing.

Add an integration regression that starts from a serialized legacy report and cached XML, runs the actual repersist path, writes/reloads repaired JSON, exports through the existing exporter, and renders dossier and archive panels. Compare by vote ID: `inverted`, `inversion_source`, `inversion_excerpt`, `result_raw`, `result_source`, `result_scope`, and final counts. Include an official application result, a derived recommendation result, a duplicate TOP occurrence and a sitting-only vote. Run the repair twice to prove semantic stability and verify failed source validation does not replace the old store.

Expected production changes beyond the validator: only the replay integration in `scripts/build_dip_pulse_site.py` if needed. Verify existing storage/export/render code before changing it. Tests may extend `tests/test_repersist.py`, `tests/test_b1_store.py`, `tests/test_daten_export.py`, `tests/test_b1_consumers.py`, and `tests/test_features_votes.py`; share a meaningful round-trip fixture instead of duplicating the same assertions in every file.

## Acceptance and validation

On a disposable copy of the reference site, record before/after results:

| Check | Required result |
| --- | --- |
| Missed inversion IDs | 773, 790, 793, 798, 803, 811, 819, 841, 850, 855, 873, 882, 892, 906 all have supported inversion provenance and render `Ja = Antrag ablehnen · Nein = Antrag annehmen` in every panel occurrence |
| Negative control | The direct Gesetzentwurf vote is not inverted; accepting recommendations and existing conflict tests retain their correct behavior |
| Replay | Recovered fields agree in saved/reloaded JSON, SQLite, downloadable SQLite and `votes` CSV; second replay changes no interpretation |
| Vote 1005 | An inversion legend and an Antrag outcome replace `Kein Ergebnis verfügbar`; a tally-derived result remains visibly marked `(berechnet)` |
| Vote 996 | Official Antrag rejection, unchanged 439/135 final tally, correct scope and no double inversion; result survives offline replay |
| Corpus comparison | Review every changed result/source/scope and inversion, including the research note's 43 tally discrepancies; report unresolved cases instead of forcing all results to official |
| Other consumers | Archive badges, fraction positions and existing dissenters/member-history behavior agree with the corrected interpretation; raw member/fraction counts stay unchanged |

Run `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests` and the script compilation check from CI after implementation. Keep source-fetching mocked in regression tests. Build and validate the zero-network demo as in `.github/workflows/ci.yml`. For the repaired reference site's visible panels, use Chrome DevTools MCP if available, inspecting at least 906, 996, 1005 and the direct-vote control; use another driver only if DevTools is unavailable and state that limitation. A visual check supplements field/HTML assertions.

Update the linked todo with measured results only after these checks pass. Add a short README recovery note if the one-time repersist/targeted refresh procedure needs clarification. Leave the optional metadata and broader B4 work open.

## Implementation notes

- The interpretation, replay and repair tests live in a new `tests/test_vote_interpretation.py` instead of extending `tests/test_b1_interpretation.py` and `tests/test_repersist.py`: they share one protocol and vote fixture, which the existing files do not use. The Beschluss block tests extend `tests/test_roll_call_scraping.py` as planned.
- "Missing source evidence must not silently clear a previously supported interpretation" (step 4) is read as a missing XML: a report replayed without its XML keeps a protocol inversion. A present XML is the source and decides again, also when it announces nothing attributable for a vote, so a corrected rule reaches every cached report.

## Planning validation and limits

Passed: 30 tests in `test_b1_*.py` and 59 tests in `test_roll_call_scraping.py`. Inspected the local reports/XML and the persistence/export/render paths. No implementation, database repair, live acquisition, browser run or full-suite run was performed. The historical cause of the blank cached reports remains unproven; fresh-versus-replay fixture coverage and a focused online comparison are the first implementation checks.
