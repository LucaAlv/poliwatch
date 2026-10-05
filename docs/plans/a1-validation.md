# A1 follow-up validation

Date: 2026-10-05. Branch: `a1-followups`, base `4818b4c`. T1–T8 implemented under approved D1/D3/D4, with final merged-A2 validation deferred explicitly by the user. The user explicitly deferred the final merged-A2 gate after Claude reached its usage limit; this document distinguishes completed A1 checks from the in-progress A2 snapshot. The deferred gate is a P1 TODO before A3.

## Source evidence and fixtures

The implementation follows [the turn investigation](a1-turn-investigation.md). Fixture provenance, official XML URLs, original hashes and trimming rules are in [the fixture manifest](../../tests/fixtures/a1-source-manifest.json). Fixtures preserve the speaker markers, historical headings and question classes. Long ordinary body paragraphs are shortened; fixture text lengths are not whole-sitting count goldens.

The frozen [baseline](a1-source-baseline.json.gz) and [current snapshot](a1-source-current.json.gz) record SHA-256 of UTF-8 XML text with normalized line endings, source unit/position, kind and text length across 290 cached WP20/21 XML files plus the 21 bounded WP18/19 sources from the investigation. Both use identical source text; original transport-byte hashes are separately recorded in the fixture manifest. The baseline ran at `4818b4c` before implementation. [The comparison](a1-source-comparison.json) records every changed native label. Reproduce current capture with Python 3.13 and `tests/a1_source_audit.py --xml-dir <cached-xml> --xml-dir <historical-xml> --output <snapshot.json.gz>`.

| Kind | Baseline | Current |
|---|---:|---:|
| Rede | 27,165 | 27,122 |
| Kurzintervention | 672 | 666 |
| Erwiderung | 610 | 610 |
| Befragung Frage | 4,101 | 4,200 |
| Befragung Antwort | 4,056 | 4,131 |
| Fragestunde Frage | 3,468 | 3,345 |
| Fragestunde Antwort | 3,205 | 3,339 |
| Zwischenfrage | 0 | 1,505 |
| Written submission (`zu_protokoll`) | 0 | 894 |

All 70 changed native labels have inspected explanations: 18/13's opening report and 13 government answers; 18/84's 25 questions and 25 answers; six retrospective chair announcements in 21/4, 21/30, 21/43, 21/47, 21/65 and 21/94 restored to Reden. Every existing native unit retains its own text length. Valid pending grants, including 20/135, are retained; 21/37 explicitly refuses further interventions and remains a Rede. Historical flat-turn shifts follow printed-role and uppercase `P` recovery. Added nested segments keep the original speaker's text unchanged; nested government turns in Befragung remain format answers. Written counts include 301 submissions with no unambiguous TOP, retained at sitting level. These are source-cohort counts, not the full WP18/19 census.

The fixture's direct Befragung counts are 18/13: one opening Rede, 13 questions and 13 answers; 18/84: one opening Rede, 25 questions and 25 answers. Corrected Fragestunde counts are respectively 94/91 and 51/51 questions/answers. Unresolved or conflicting explicit evidence rejects acceptance, including nested question-format speakers. The reported pronoun case in 21/81 was not reproduced in the inspected source; pronoun rejection is regression-tested without claiming that source defect was observed.

## Written and guest coverage

[18/100 XML](https://dserver.bundestag.de/btp/18/18100.xml) explicitly types 35 written submissions. The original TODO's 29 units in [19/239 XML](https://dserver.bundestag.de/btp/19/19239.xml) and 11 in [18/200 XML](https://dserver.bundestag.de/btp/18/18200.xml) are §31 declarations, a different annex type; they are excluded. Tests retain a §31 negative alongside a written submission. Missing TOP or page evidence stays null; no neighboring page/TOP is invented.

The [2016 memorial notice](https://www.bundestag.de/webarchiv/textarchiv/2016/kw04-vorschau-402656) places Ruth Klüger's address at noon before the plenary sitting. [18/151 XML](https://dserver.bundestag.de/btp/18/18151.xml) starts at 13:31 and contains no speaker marker for her. The [2021 memorial notice](https://www.bundestag.de/webarchiv/presse/pressemitteilungen/pm-210121-gedenkstunde-818436) places Charlotte Knobloch and Marina Weisband's addresses at 11:00; [19/205 XML](https://dserver.bundestag.de/btp/19/19205.xml) starts at 13:00 and contains neither speaker marker. Their XML SHA-256s are `d0c3f85460d2042677d12fda72983483fb12301bb2af036006de919088de218c` and `4a4cb1ffa3d682d6d424143ab64c846da5c157bd9636146aad8328bf92fb510b`. These examples establish a source-coverage gap, not a universal absence of guests. No guest body or universal guest detector was invented; broader ceremony acquisition remains separate work.

## Replay, acquisition and output boundaries

A census of all 290 cached report/XML pairs found one source-association refusal: 21/50's old report had 19 TOPs against 26 in its XML. The report and XML were reacquired together through the existing official DIP path into scratch, retaining all 26 TOPs. Other report associations replayed. XML/report hashes normalize CR/CRLF to LF consistently at fresh acceptance and replay; XML treats these transport endings equivalently. SHA mismatches beyond that normalization, missing/extra/ambiguous TOPs and wrong documents fail before accepted report mutation or staged-store promotion. Existing summary fingerprint invalidation is retained.

Bounded official DIP acquisition also succeeded for 18/13 and 19/13, exercising proceedings, positions and activities. Profiles were deliberately limited to one person. Ten-page historical roll-call scans exhausted their budget; those reports remain explicitly partial and cannot certify historical coverage. The 21/50 scan reached its date boundary. This is validation sampling, not A3 acquisition.

Per-protocol `speech_rule_inputs` records the actual persisted input version; all protocols must be current before facts, export or store-consuming rendering. Tests cover missing/stale inputs, staged failure retaining the old store, direct output refusal before writes, distribution retention and unchanged schema/key versions. A version certifies the rule basis, not snapshot equality. Low-level schema/open/persistence remains usable for repair.

All DIP Kurzintervention/Erwiderung differences remain structured and are emitted in `data/a1-classification-diagnostics.json`; one actionable build warning points to the full list. The final 290-report cohort retains 93 sitting/kind differences across 57 sittings (42 Kurzintervention, 51 Erwiderung); [all rows are preserved](a1-dip-diagnostics.json). No arbitrary mismatch threshold suppresses evidence or forces labels to equal DIP totals.

## Automated and scratch checks

Python: `/opt/miniconda3/bin/python3.13`; system Python 3.9 is unsupported. The final supported suite passed **1,082 tests** in 56.368 seconds. The isolated current A1+A2 snapshot passed **1,099 tests** in 71.791 seconds, with one reference-only test skipped because the snapshot has no reference cache. Source-backed focused tests exercise real parser/SQLite/render/export contracts rather than only mocked labels. Stable key vectors remain unchanged.

Scratch roots: `/tmp/poliwatch-a1-work/site` and `/tmp/poliwatch-a1-work/combined-validation`. Reference cache/store/pages were never repersisted or rendered into. The first 290-report replay took 165.1 seconds; the unchanged second took 193.4 seconds and retained the database (`replaced=False`). Integrity was `ok`; FK checks were empty. Dossiers, eligible person pages and all 25 CSV tables plus distribution SQLite were rendered/exported in scratch; the missing scratch `protocols/` directory initially stopped rendering and was fixed in the harness. The reference's old catalog cannot certify complete periods; scratch fact rows remain nonpublishable.

Source capture took 37.53 seconds at baseline and 39.54 seconds currently (about 5% overhead, single unisolated measurements). Extraction uses source walks and one sitting candidate index. A separate child-process resource measurement reported peak RSS of 79,364,096 bytes at baseline and 83,382,272 bytes currently (about 4 MB additional). Those runs took 43.69/54.24 seconds while other validation was running; timings are unisolated observations, not performance guarantees. Final grouping/export receipts follow below.

## Architecture and review

Existing architecture JSON/HTML was regenerated using the archify skill. Showcase validation passed 9/9 checks with zero errors/warnings. Chrome DevTools inspected light and dark endpoint themes and containment at 1440×900, 1600×1000, 1920×1080 and 2048×1320; scroll bounds matched every viewport. The large desktop composition was visually inspected. This is manual Chrome evidence; the skill's separate automated `visual-check` was not run, and no automated browser pass is claimed. Artifact bindings: specification SHA-256 `26ad7f95b002d82d817eb7f7be58571e9f11bcbf9e720a1f8687930ae0e71e11`; HTML SHA-256 `36f621bb8f44d5f046331f0d963b56117ce3e374100132608b68a9953d3e6ff3` (735,578 bytes).

Primary implementation review covered source refusal, nested identity, text ownership, TOP mapping, actual-input provenance, write ordering and coherent vote receipt selection. It caught a missed valid pending grant, a later explicit refusal, missing nested-D4 handling and omitted sitting-level profile traversal; these were corrected and regression-tested. No independent clean-review credit is claimed. The old frozen planning review history is preserved in the plan.

## A2 coordination and final gate

[A1/A2 contract](a1-a2-contract.md): schema 3, key version 1 and existing native/flat keys remain unchanged; new nested/annex locators pass through the existing contribution key function. A1 does not edit registry internals or A2's `upsert_mp` work. Claude's uncommitted `right-counts` changes were overlaid in an isolated scratch checkout, including its registry evidence tests; the overlapping persistence hunk applies cleanly. Combined tests and scratch checks validate that snapshot, not a completed/merged A2 branch. Final A2 commit, combined merged validation and A3 readiness remain pending.

The user requested finishing A1 without waiting for Claude's three-day usage reset. Final merged A2 validation is therefore deferred explicitly to `TODOS.md`, not silently claimed or omitted. No A1 identity/schema change requires a new registry policy; the remaining coordination risk is that unfinished A2 changes may alter grouping/page assignments.

## Final combined scratch receipt

[Machine-readable receipt](a1-scratch-validation.json). The 290-report A1+A2 snapshot has 26,271 Reden and 16,799 Beiträge (1,448 nested Zwischenfragen; 859 written submissions, 301 without a proven TOP). Fresh and half-then-full builds yield identical person groupings: 4,263 source records, 3,370 groups, fingerprint `24791838f6ff23d902d87390b205bdbacba797071feb9e9cca295416e97dfce3`. The second full rebuild retains exact database bytes. Integrity is `ok`; FK checks and dangling person references are empty. Seven read-out questions retain nullable person attribution (2,515 characters); 16,792 contribution occurrence bindings are present.

The exported gzip SQLite was decompressed and checked: integrity `ok`, no FK violations, all 290 persisted rule inputs at version 2, registry/provenance preserved. The first harness attempted to open gzip as SQLite; this was corrected and the historical harness error remains recorded separately from passing checks.

Final real report/person rendering produced 2,223 HTML pages. All 90,540 checked person/contribution/containing-speech links resolve, and all 16,799 contribution anchors exactly match the store. Generic site navigation was not treated as a full publication audit: this scratch render contains dossiers/person pages, not a deployed full site. The person-page harness initially lacked its `data/` directory; pages had already been written and were then audited directly. Mobile Chrome inspection found and corrected a contribution-header overlap by using the existing summary grid structure.

The enriched historical 18/13 and 19/13 reports also persisted after adding the explicit source role `Staatssekretär im Bundeskanzleramt` from 19/13, Redner `999990013` (source-backed marker fixture). Their separate store has 87 Reden, 343 Beiträge and two persisted proceeding positions; integrity/FKs pass. Those positions are the linked subset, not all raw DIP positions. The interim task-only source digests were verified against acquired XML and normalized before semantic replay; final fresh/replay line-ending behavior is regression-tested. Historical vote acquisition remains partial as stated above.

The receipt distinguishes initial major-module hashes from end hashes: the long replay imported modules before final presentation/receipt/role/line-ending refinements. Final source capture confirms the same 311-source semantic snapshot; final suite and real-output audit cover the last files. No final merged-A2 or independent reviewer approval is implied.
