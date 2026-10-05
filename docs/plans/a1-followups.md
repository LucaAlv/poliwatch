# A1 follow-ups: implementation planning

Date: 2026-10-05
Branch: `a1-followups`
Base: `4818b4c`
Review target: the A1 follow-ups in `TODOS.md`.
Status: T1–T8 implemented and validated; final merged A2 integration explicitly deferred by the user and tracked in TODOS.md. Original planning record follows. Planning status: implementation plan complete; D1, D3 and D4 approved; outside review unavailable (CLI authentication). The planning-only restriction described the preceding review session; the user subsequently authorized implementation.

## Goal and boundaries

Finish A1 counting and contribution ingestion, its classifier and replay follow-ups, and documentation before the A3 full backfill. Claude is handling A2 separately. Preserve A2 ownership of person reconciliation, corrections, registry internals and the stable-ID contract; coordinate any required contribution identity changes with that work. Implementation evidence is recorded in [a1-validation.md](a1-validation.md).

Historical WP 18/19 sampling belongs in A1 validation; acquiring every historical sitting remains A3. Broad parser/person/store architectural refactors, vote acquisition hardening, site hosting and public releases remain separate work.

The roadmap records the 2026-09-30 decision that written submissions are a kind of their own, not Reden. The copied TODO below predates that decision and must be reconciled during planning.

## Original backlog baseline (unchanged excerpts)

The following excerpts preserve the original proposal. They are not claims that every listed defect still exists. Completed clauses must be checked against current code and regression tests before implementation.

### Credit a Zwischenfrage to the MdB who asked it, and keep Gastansprachen out of speech counts

**What:** A Rede's stored text is now only its Redner's (Sitzungsleitung and Zwischenfragen no longer leak in). Two things are left. (1) The words of an MdB who asks a Zwischenfrage (a `<p klasse="redner">` with another `redner id` inside the `<rede>`) are dropped, not stored: credit them to the asker as a Zwischenfrage of their own (CONTEXT.md: Zwischenfrage). `speech_text_and_paragraphs` (`scripts/validate_dip_protocol.py`) already walks the segments; it only returns the Redner's. (2) Detect Gastansprachen (CONTEXT.md: shown with the Sitzung, never counted as a Rede) and keep them out of speech counts.

**Why:** Zwischenfragen are still counted for nobody, so an MdB who mostly asks questions shows fewer contributions than they made. Gastansprachen still count as Reden.

**Context:** Measured on the 2026-09-29 store: 55 Zwischenfrage blocks in 8 sittings, all followed by the Redner's own marker or by a Präsident `<name>`; no text had an undeterminable speaker (`speeches.unattributed_char_count` is 0 everywhere). Kurzinterventionen and the Befragung/Fragestunde are their own items (#68, #70).

**Effort:** M
**Priority:** P1 (raised 2026-09-30: every series and release count depends on it)
**Depends on:** None

### A1 classifier precision: measure and tighten the Kurzintervention and Fragestunde rules

**What:** Four open findings from the /ship review of PR 1 (2026-09-30), each reproduced on synthetic strings only. (1) `announces_kurzintervention` (`scripts/speech_kinds.py`) accepts the next Redner's surname in any of the three sentences after the Kurzintervention wording, so "Damit ist die Kurzintervention beendet. Das Wort hat als Nächste die Kollegin Meier." types Meier's Rede as a Kurzintervention (the Rede leaves `speeches`); the Fraktion branch has the same shape. Require the signal in the same sentence, or exclude closing forms (beendet, erledigt, beantwortet, möglich), with a word-boundary surname match. (2) The Fragestunde asker pairing uses a plain substring test, so 'Ott' matches 'Gottschalk'; use word boundaries, and try a name-plus-party lookup for a question whose asker has no Nachfrage instead of leaving `mp_id` NULL. (3) `announced_asker` keeps the party ("Dr. Gottfried Curio (AfD)", "..., CDU/CSU", "... von Bündnis 90/Die Grünen") in `contributions.speaker_name`, which the export publishes; cut it at the party. (4) A Fragestunde turn whose Redner has neither `<rolle>` nor `<fraktion>` is dropped with no warning or counter; keep it or count it into `validation_summary`.

**Why:** A false-positive Kurzintervention removes a Rede from every count and gains a wrong `parent_rede_id`. The reference store already holds one Kurzintervention more than DIP in 4 sittings, so some exist. Measure before changing: parse the 285 cached XMLs (`data/xml/`) with old and new rules and report the moved counts per kind against DIP's `aktivitaetsart`.

**Context:** The detector prefers precision (636 of DIP's 682 Kurzinterventionen, 581 of 646 Erwiderungen); tightening (1) lowers recall further, so tune both together. Also found by the adversarial review and not fixed in PR 1: (5) Kurzinterventionen the wording misses stay counted as Reden (68 sittings differed from DIP before the review fixes, 59 after), e.g. 20/112 "Sie möchten eine Kurzintervention machen? - Bitte schön.", and a warning on about one sitting in five on every build will be ignored, so decide what the warning threshold is; (6) the rules were tuned on WP 20 and 21 only: run the parser and the DIP comparison over WP 18 and 19 XML before the v1 backfill (the Regierungsbefragung exists since WP 19; the T_* paragraph classes and headings may differ); (7) `announced_asker` returned a garbage name ("Ihnen", 21/81 TOP 2), `KIND_LABELS[kind]` raises KeyError on an unknown kind in a cached report, `fetch_missing_xml` accepts any URL scheme, `reparse_cached_xml` lets exceptions other than ParseError/OSError/UnicodeDecodeError/ValueError escape as a traceback, and `--fetch-xml` counts a report with an empty document number as already cached. The unclassifiable-speaker question in a Befragung (no `<rolle>`, no `<fraktion>` stays a Rede) belongs here too: decide what such a turn is and pin it with a test.

**Effort:** M
**Priority:** P1
**Depends on:** None

### Stale derived data after `--offline --repersist`

**What:** Two findings from the same review. (1) `reparse_report_xml` (`scripts/validate_dip_protocol.py`) replaces `xml_speakers` but keeps the cached `llm_summary`, which cites chunks by `rede_id`; for a Befragung or a TOP with Kurzinterventionen the summary still shows 'Belegstellen' quoting turns that are now Beiträge, and the anchor link is silently dropped. Recompute `summary_source_fingerprint` over the new speeches and clear the summary when it no longer matches. (2) `build_report` writes `data/xml/<sitting>.xml` before the report is accepted; if `keep_cached_dossier_when_votes_failed` then keeps the old JSON, the XML is newer than the report it pairs with and a later repersist attaches Reden of one version to positions and votes of another. Write the XML next to the JSON, or store its sha256 in the report and skip the re-parse on a mismatch. Also pair agenda items by `top_id` and heading, not by `index` alone, and validate fetched XML before writing it. Fixed in PR 1 (final merge review): a reparse did not refresh `heading`; `xml_top_fields` now carries every XML-derived item key and a test compares a reparse with a fresh build. Two latent items from the same review (3): the rewritten vote queries in `scripts/facts.py` take `MIN(p.id)`, `MIN(p.document_number)` and `MIN(p.date)` separately (the old bare-column query took all three from one row, and the text minimum sorts "21/10" before "21/9"), harmless unless a vote is ever linked to agenda items of two protocols; and `persist_votes` (`scripts/persist_dip_pulse_store.py`) is dead since `persist_report` calls `persist_vote` directly, so drop it or keep the `ctx` hook in `scripts/features/votes.py` pointing at one entry point.

**Why:** After a repersist the pages can show an AI summary that contradicts the counts on the same page. Rare (only a reissued protocol or a failed vote scan triggers (2)) but silent.

**Context:** Found by the red team and the data-migration specialist; the stale-store guard itself shipped in PR 1 (`speech_kinds_version` on every parsed report, a warning in every build mode, a heading fallback for `is_question_format`). A hard refusal to export or post Fakten over an unparsed store was offered and not chosen; revisit it with A3. The marker lives on the report JSON only, not on the store or export: an online run that writes every report and then stops before the store rebuild, or `--no-persist`, leaves an old store next to all-fresh reports and nothing warns. Stamp `speech_kinds.VERSION` in the store (`PRAGMA user_version` or a `datenstand` row) and compare it in the offline path and the export step. Coverage caveat for the whole A1 branch: Codex adversarial and structured reviews were unavailable (usage limit), and the final tree (review fixes plus the merge of v0.10.0.0) had one Claude review of the merge only, so treat it as Claude-only coverage.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Regenerate the architecture diagram for the Rede/Beitrag split

**What:** `docs/bundestag-puls-architecture.{html,json}` do not show `scripts/speech_kinds.py`, the `contributions` kinds, the `--fetch-xml` and `--repersist` re-parse path, or the `speech_kinds_version` stale-store warning. Add them to the parse and persist stages, the same way the Daten export step was added in v0.6.4.0.

**Why:** The diagram is the one picture of the pipeline; today it shows the parser as one step that yields Reden only.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Zu Protokoll gegebene Reden: decide what they are, then store them

**What:** Some Plenarprotokolle carry Reden that were handed in in writing rather than delivered ("zu Protokoll gegebene Reden"). They sit under `<anlagen>`, which `parse_protocol_xml` (`scripts/validate_dip_protocol.py`) never reads. 19/239 has 29 such Reden next to 38 delivered ones, 18/100 has 35 next to 104, and 18/200 has 11 next to 35 (checked 2026-09-30; 21/84 has none, WP 20 and 21 not sampled). First decide in CONTEXT.md whether they are Reden (the user's first intuition on 2026-09-30: they count, but it is not decided and needs a /domain-modeling session) (and count toward Redeanteil and term series) or a kind of their own, shown and counted separately. Then parse them, with their TOP, Redner and a flag, and count them in each WP.

**Why:** Today they vanish without a trace, so a researcher who counts Reden per TOP from the release gets a smaller number than the protocol, with no flag saying why. The late-night Sitzungen that use them are also where most of the text on some topics lives.

**Effort:** M
**Priority:** P1
**Depends on:** A glossary decision (/domain-modeling)


## Proposed arrangement for scope review

Extend the existing boundaries, without introducing new modules or services:

- Classification and kinds: `scripts/speech_kinds.py`.
- XML extraction, report construction and replay matching: `scripts/validate_dip_protocol.py`.
- Persisted contributions and speech-rule metadata: `scripts/persist_dip_pulse_store.py`.
- Replay orchestration, offline/export guards and person contribution summaries: `scripts/build_dip_pulse_site.py`.
- Dossier contribution display: `scripts/render_dip_pulse_html.py`.
- Vote fact receipt source-row selection: `scripts/facts.py`.
- Dead vote persistence callback cleanup: `scripts/features/votes.py`.
- Contribution identity: `scripts/stable_ids.py` only if the existing key contract cannot safely represent multiple nested contributions; coordinate with A2 before changes.

Extend the existing classifier, parser, replay, persistence, rendering, facts, export and stable-ID tests and add source-backed fixtures as needed. Update `CONTEXT.md`, ADR 0002, README, the architecture artifacts and `TODOS.md` alongside the completed behavior.

Estimated changed scope: 7–8 existing production files, at least 8 existing test files plus fixtures, and related documentation; zero new production classes/services. An exact count depends on the source-sample audit.

Sequential implementation because extraction, kind definitions, report fields, persistence and replay share contracts. Keep A2 in its separate checkout and use scratch data directories; do not repersist or render into the reference site during development.

## Scope record

Feature scope: finish the A1 follow-ups listed in the original baseline, using the existing counting decisions.
Structure: D1 = A, user's reply “A” on 2026-10-05. Extend the existing module boundaries, with zero new production modules or services.
Scope challenge result: scope accepted as-is. Reuse the existing XML speaker walk, kind registry, contribution table and replay staging; do not rebuild the parser or person registry.
Resolved policies: D3=A refuses stale persisted rules at output boundaries; D4=A rejects genuinely unresolved question-format turns after explicit source recovery. Retain structured DIP mismatches and aggregate actionable warnings without suppressing mismatches behind an arbitrary frequency threshold. D1 approves arrangement only.
Read-back: the approved arrangement preserves the full A1 feature list and keeps the A2/A3 boundaries above.

## Backlog reconciliation

Audited against base `4818b4c`, with a read-only subagent audit checked by the primary agent. Source inspection and bounded probes support the statuses below; historical frequencies still need measurement.

| Original finding | Current status | Remaining work |
|---|---|---|
| Closing Kurzintervention wording turns the next Rede into a Beitrag | Closing case fixed; general grant detection remains partial | Preserve existing closing/Bitte-schön regressions; tighten ambiguous possibility wording and positive surname boundaries after measuring changed labels. |
| Fragestunde surname substring pairing | Fixed | Existing whole-surname matching includes hyphen boundaries; extend the table only for uncovered regressions. |
| Silent Fragestunde asker has no person link | Open | Extract name and party separately; resolve only a unique source-backed candidate within sitting/WP scope, with ambiguity left explicit. Use A2's existing resolution boundary; do not invent trusted IDs or global name merges. |
| Announced name retains party or becomes a pronoun | Open | Probes reproduce `(AfD)`, `, CDU/CSU`, and `von Bündnis 90/Die Grünen` in names. Preserve genuine name particles; reproduce the reported 21/81 pronoun case before changing its rule. |
| Unplaced Fragestunde marker disappears silently | Fixed | The parser reports `fragestunde_unplaced_turns`; existing regression covers marker/text boundaries. |
| 20/112 Bitte-schön grant is missed | Fixed | Existing real-case regression covers it; do not treat the old TODO example as a remaining defect. |
| Classifier recall and diagnostic policy | Open | Compare old/new source identities and labels with DIP; manually inspect movements instead of treating DIP totals as ground truth. Preserve all structured mismatches; aggregate by sitting/kind with details in an audit artifact and one actionable build summary. No numerical suppression threshold; DIP disagreement alone does not reject a parse. |
| WP 18/19 validation | Open | Source-backed historical sample must exercise Befragung, Fragestunde, Aktuelle Stunde, interruptions, annexes and guest-address cases. Exercise DIP enrichment and votes on a bounded subset. |
| Unknown cached kind, unsafe fetch URL, missing document number, expected replay errors | Open | Validate kinds before rendering; validate XML fetch URLs with existing publication source validation; report missing numbers as acquisition failures; catch documented input errors, without swallowing programming errors. |
| Unknown Befragung speaker counts as Rede | Latent fallback; no observed case in audited sources | D2 investigation found recoverable historical role/heading defects first. Recover explicit source evidence before considering a residual fallback policy; see the investigation report. |
| Stale summary after replay | Fixed | Keep fingerprint invalidation and its existing regression. |
| XML cached before report acceptance / invalid fetched XML | Fixed on the ordinary acceptance path | Preserve acceptance and document-identity regressions. Review interrupted paired writes separately; do not claim whole-site atomicity. |
| Replay matches TOP by index alone | Open | Validate/map source TOP identity before mutating the report; handle repeated/continued top IDs and legitimately refreshed headings. Refuse ambiguous matches and require reacquisition. |
| Vote fact receipt combines independent MIN fields | Open | Select one deterministic protocol source row and take all receipt fields from it. |
| Dead `persist_votes` wrapper and callback | Open | Remove the unused wrapper/hook after confirming production call sites; coordinate with the A2 branch if it touches this code. |
| Speech-rule marker exists only in reports | Open; D3=A approved | Persist the rule version with a successful staged rebuild and compare it in offline/facts/export paths. Do not use `PRAGMA user_version`: it identifies distribution copies here. |
| Zwischenfragen text discarded | Open | Reuse the speaker walk to preserve the asker's segments and link each contribution to its containing source unit. |
| Gastansprachen counted as Reden | Backlog conflicts with current glossary | CONTEXT says sampled guest addresses are absent from the XML. Extend historical evidence before adding a detector or claiming universal absence. |
| Written annex speeches absent | Open; counting decision already recorded | Preserve as their own non-Rede kind, with source identity, speaker, page and evidence-backed TOP association. Unresolved TOP association must not lose the text. |
| Architecture diagram | Open | Update it with the completed parser, contribution kinds, replay and store/export rule checks. |

Validation performed during planning: 29 classifier tests and 28 replay tests pass on `/opt/miniconda3/bin/python3.13`. The system `python3` is Python 3.9 and cannot run the supported pipeline; the initial replay test import failed there, then passed on the supported interpreter. No production code was changed.

## Implementation sequence

Implement T1–T8 within the approved existing module arrangement. Policy decisions are resolved; this session does not implement production changes.

| Step | Work | Principal files | Depends on |
|---|---|---|---|
| T1 | Freeze the current-label baseline; add small source-backed historical fixtures and an audit record | existing classifier/parser tests and fixtures; validation documentation | — |
| T2 | Recover occurrence-specific printed government roles; recognize historical question-format heading and question-text classes | `speech_kinds.py`, `validate_dip_protocol.py`, existing classifier/parser/replay tests | T1 |
| T3 | Tighten high-confidence Kurzintervention signals and announced asker extraction; use a unique source-backed silent-asker lookup | `speech_kinds.py`, `validate_dip_protocol.py`, existing contribution persistence boundary if needed | T1; T2 before measuring final movement |
| T4 | Preserve nested Zwischenfragen as contributions with distinct source identities and a containing-source link | parser, kind registry, persistence, stable IDs and renderers | T2; A2 coordination for identity changes |
| T5 | Preserve explicitly typed written annex submissions as a separate non-Rede kind; keep unresolved TOP association at sitting level | parser/report fields, contribution persistence, kind labels, dossier/person renderers and exports | T4 contribution representation; source annex sample |
| T6 | Harden replay TOP identity matching and expected input failures; stamp actual persisted speech-rule provenance and refuse stale-rule output (D3=A) | existing replay/persistence/export/facts boundaries | T2–T5; D3 policy and metadata design |
| T7 | Select one protocol source row for each vote-fact receipt; remove the dead vote persistence wrapper/callback | `facts.py`, `persist_dip_pulse_store.py`, `features/votes.py`, existing tests | coordinate overlapping files with A2 |
| T8 | Replay a scratch copy; verify changed counts, identities, exports, links, failures and idempotence; reconcile TODOs and update domain/architecture docs | validation docs, README, CONTEXT/ADR, architecture artifacts, TODOS | T2–T7; A2 merged for the final combined validation |

Do T2–T6 sequentially: they share the source-evidence and contribution contracts. T7 is independent in behavior but touches shared files, so keep it sequential in this checkout. Do not modify A2's registry internals or independently increment its schema/version contracts before comparing with Claude's final branch.

### Acceptance gates

- Preserve one opening report and distinguish questions/answers in source-backed 18/13 and 18/84 fixtures; include lowercase/uppercase question text, heading-class variants, and ordinary debates about Regierungsbefragung rules.
- Use one effective-role helper in an existing module for both `speaker_class` and `parse_redner`; do not mutate cached XML or assign a person's government role to all their occurrences.
- Preserve known Kurzintervention/Erwiderung positives and expose any changed source labels in the full available-cache comparison. DIP totals are comparison evidence, not an automatic target.
- Nested questions retain the asker's text; chair text and comments never become that person's contribution. Multiple questions inside one source rede cannot collide with each other or their parent, nor remint existing source IDs.
- Annex selection requires an explicit written-submission type. `Erklärungen nach §31 GO` and other annex material stay distinguishable. Keep source text and speaker when TOP/page evidence is absent; do not invent an agenda item or source page. Written submissions stay outside all Rede figures.
- Replay verifies source TOP association before changing any cached item, preserves DIP/vote association only when supported, refreshes legitimate XML-derived headings, and refuses ambiguous remapping before replacing the store.
- The store's speech-rule marker describes persisted input, not the running program alone. D3=A requires refusal on missing/stale provenance before fact generation and export writes; the recovery command is explicit repersist. Distribution-copy identification remains intact.
- Preserve existing summary fingerprint invalidation and XML-acceptance regressions; test interrupted/mismatched sources separately without promising whole-site atomicity.
- Demonstrate `PRAGMA integrity_check`, `foreign_key_check`, unchanged second replay, generated contribution/person/source links, and incremental-versus-fresh grouping once A2 is available.
- Run the supported Python test suite and focused changed-boundary regressions. Real-cache comparisons must use scratch data and report old/new values with reasons. Incomplete historical sampling cannot be presented as full WP18/19 coverage.

## Architecture review

Scope Challenge: no additional scope issues found. The existing stateful XML speaker walk, kind registry, contribution storage and staged replay cover the required boundaries. Disposition: retain the full requested A1 scope; keep unrelated architecture work separate (original user request, D1=A).

[P1] (confidence: 10/10) `scripts/speech_kinds.py:325` — an unknown Befragung speaker reaches `RedeLabel({MEMBER: BEFRAGUNG_FRAGE, OFFICIAL: BEFRAGUNG_ANTWORT}.get(who or ""))`. The mapping returns `None`; `scripts/validate_dip_protocol.py:551-552` then executes `if label.kind is None: speeches.append(unit)`. This is current behavior, not proof of its historical prevalence. Disposition: recover explicit occurrence evidence in T2, then reject genuinely unresolved format turns under D4=A; no new unknown kind.

## Decision ledger

### R1: Existing module arrangement

State: approved.
Actual answer: D1=A, user reply “A” on 2026-10-05.
Accepted scope: extend the existing modules; retain the full A1 scope and zero new production modules/services. This approves arrangement only.

### R2: Source recovery before unknown-turn fallback

Finding: the hypothetical fallback is still present in code, but the premise of the original D2 question was too broad. Source investigation found no actual role/faction-less question-format marker in the inspected sources.
Plan baseline: original A1 TODO requires investigation and a tested counting policy; D1 approves module arrangement only.
Runtime evidence: census of 290 WP20/21 cached XMLs plus a 21-protocol WP18/19 sample. In 18/13, explicit government roles are present in printed marker text but missing from structured role fields; in 18/84, the heading class `T_ohne_NaS` is ignored and question text uses uppercase `P`.
Recommendation: recover these explicit source signals before choosing a catch-all unknown kind. Keep classification and persisted speaking-role evidence consistent; retain occurrence-specific evidence and established Rede/Beitrag definitions.
Scope: deeper bounded investigation was explicitly requested by the user; its source census, official-PDF verification and in-memory recovery probes are complete. This grants no implementation or fallback-policy approval.
Evidence: [A1 turn investigation](a1-turn-investigation.md).
State: investigation completed; residual policy resolved by R4.
Actual answer: user requested deeper investigation instead of choosing an original D2 option; later D4=A settles the residual failure behavior.
Accepted scope: source-backed recovery required by the A1 classifier task, with D4 refusal afterward. Neither original D2 option was approved; the original catch-all kind recommendation remains withdrawn.

#### History: original D2 and its unapproved options

The following preserves the question and alternatives previously presented; it is historical, not the current recommendation or an approved remedy.


Finding: Architecture P1, confidence 10/10, `scripts/speech_kinds.py:325` and `scripts/validate_dip_protocol.py:551-552`; primary reviewer.
Plan baseline: the original A1 TODO requires this policy to be decided and tested; no option was previously approved.
Runtime evidence: missing role/faction yields `RedeLabel(None)` and a speech row. A census of the cached WP20/21 question-format markers and a 21-protocol WP18/19 sample found zero markers lacking both role and faction. Historical sources instead expose ignored printed-role and heading-class evidence; see the linked investigation.

| Commitment | Current | A | B |
|---|---|---|---|
| Unknown turn storage | `speeches` | `contributions`, explicit `befragung_unbestimmt` kind | `speeches` |
| Count toward Rede figures | Yes | No | Yes |
| Preserve printed speaker and text | Yes | Yes | Yes |
| Mark uncertainty | No dedicated diagnostic | Counter plus actionable warning | Counter plus actionable warning |
| Recognized opening reports/questions/answers | Existing classification | Existing classification | Existing classification |
| Stale-store publication policy | Pending | Pending | Pending |
| Diagnostic aggregation policy | Pending | Pending | Pending |
| A2 identity/merge policy | A2-owned | Unchanged | Unchanged |

Question D2:
**D2 — How should an unclassified Befragung turn count?**

Project: A1 completion on `a1-followups`.
ELI10: In a Befragung, a speaker sometimes has neither a faction nor a role in the XML. The parser cannot tell whether the turn is a question, an answer or an opening report, and currently counts it as a Rede. We have verified this fallback in code; its frequency in historical protocols is still being measured.
Stakes: keeping the fallback can inflate Rede counts; excluding an actual opening report can undercount them until its source is resolved.
Recommendation: A because it preserves the source text and makes uncertainty explicit without silently asserting that it is a Rede.
Note: options differ in kind, not coverage — no completeness score.

Header: Unknown Befragung turn
Options:
A) Preserve as unclassified (recommended)
Store the turn under a separate non-Rede contribution kind and report the unresolved classification. Its text and printed speaker remain available, and uncertain turns stay out of Rede figures. This adds one kind to the data/glossary and can temporarily exclude a genuine opening report. Estimated human: ~1–2h / CC: ~15–30min including focused tests and documentation.
B) Keep Rede with warning
Retain the current counting rule and add an explicit diagnostic. This preserves current totals and avoids another contribution kind. It continues counting unresolved questions or answers as Reden until their source is resolved. Estimated human: ~1h / CC: ~10–20min including focused tests and documentation.

Net: explicit uncertainty outside Rede counts versus keeping today's totals while warning that they may be wrong.

State: pending.
Actual answer: unanswered.
Accepted scope: none for R2; D1 arrangement remains approved. Stale-store and diagnostic policies remain pending independently.
History: no earlier R2 answer.

### R3: Build behavior when persisted speech rules are stale

Finding: [P1] (confidence: 10/10) `scripts/build_dip_pulse_site.py:1289` checks `(entry["report"].get("validation_summary") or {}).get("speech_kinds_version") != speech_kinds.VERSION`; this examines reports, not the store. `export_distribution_data` currently calls `pulse_store.require_current_schema(source)` at the store boundary, with no speech-rule provenance comparison. A fresh set of reports does not prove the persisted counts are fresh.
Plan baseline: original TODO requests a persisted marker and comparisons; a hard refusal was previously considered and not selected. No new refusal policy is approved by D1.
Runtime evidence: the marker lives in report validation_summary; plain offline and `--no-persist` paths can read a store that was not rebuilt from those reports. Full stale-snapshot behavior beyond counting-rule version is not proven or promised by this remedy.

| Commitment | Current | A | B |
|---|---|---|---|
| Store-side speech-rule provenance | Absent | Record actual persisted rule version | Record actual persisted rule version |
| Missing/outdated provenance | Report-level warning may miss it | Fail the build before facts/export or affected output writes | Warn; continue existing counts/outputs |
| Automatic replay/network requests | None | None | None |
| Recovery | Existing explicit replay | Explicit `--offline --repersist`; fetch XML separately if missing | Same command recommended |
| Reports overwrite the store marker without persistence | Not applicable | Forbidden | Forbidden |
| Unknown-turn fallback after source recovery | Pending | Pending | Pending |
| Diagnostic aggregation policy | Pending | Pending | Pending |
| A2 registry policy | A2-owned | Unchanged | Unchanged |

Question D3:
**D3 — Should an outdated speech-rule store stop a build?**
Project: A1 completion on `a1-followups`.
ELI10: Reports can be reparsed while SQLite still contains counts made under an older rule. Checking only the report files can therefore miss stale facts and exports. Both options record which counting rule actually produced the store and tell the operator how to rebuild it.
Stakes: continuing may publish counts under obsolete rules; stopping interrupts an offline build until an explicit replay succeeds.
Recommendation: A because this is a pre-release accuracy pass, and A3 should not start with a silently outdated counting basis.
Note: options differ in behavior, not coverage — no completeness score.

Header: Stale counting rules
Options:
A) Stop and require replay (recommended)
Fail before generating facts, exports or affected output when persisted counting-rule provenance is missing or outdated. The error names the mismatch and gives the explicit recovery command; it performs no automatic network requests or store rewrite. This prevents stale-rule outputs and exposes interrupted/missing persistence, but existing unmarked stores need one explicit replay. Estimated human: ~3–5h / CC: ~45–90min including metadata, boundary tests and documentation.
B) Warn and continue
Detect the same mismatch and print an actionable warning while continuing with existing outputs. This preserves the current forgiving build behavior and leaves the operator in control of replay timing. Obsolete counts can still appear in facts and exports, and warnings can be overlooked. Estimated human: ~2–4h / CC: ~30–60min including metadata, boundary tests and documentation.

Net: block obsolete-rule outputs versus preserve offline convenience with a visible warning.

State: approved.
Actual answer: D3=A, user reply “A” approving Stop and require replay.
Accepted scope: record actual persisted rule provenance; missing/outdated provenance stops facts, exports and affected output before writes, with actionable explicit replay instructions. No automatic replay, network request or store mutation is introduced by the guard.
History: original TODO says a hard refusal was previously offered and not chosen; D3=A in this session supersedes that earlier disposition for stale persisted counting rules.

### R4: A question-format turn remains unresolved after source recovery

Finding: [P1] (confidence: 10/10 for the code path, not prevalence) `speaker_class` returns `None` without role/faction evidence. Befragung maps that to a Rede, and Fragestunde can omit such a marker's text with only a counter. The inspected real sources have no such marker, so this is an explicit malformed/unseen-source policy, not a new observed historical defect.
Plan baseline: R2's investigation withdrew a catch-all kind as the first solution. Recover source labels and procedural evidence first. Neither original D2 option was approved.
Runtime evidence: 290 cached WP20/21 sources and a 21-protocol WP18/19 sample contain no observed role/faction-less question-format marker. Early WP18 government roles are recoverable from printed speaker labels; a genuinely unresolved future source remains possible.

| Commitment | Current | A | B |
|---|---|---|---|
| Source-role/heading recovery | Proposed from verified examples | Keep in plan | Keep in plan |
| Truly unresolved format turn | Implicit Rede or omitted text, depending on format | Reject acceptance of the affected sitting; replay errors before replacing store | Preserve source text and printed speaker as an explicitly unclassified non-Rede contribution |
| Certified speech-rule marker on failed interpretation | Not separately guarded | Do not stamp it | Marker can describe classification with explicit unknown kind |
| New contribution kind | None | None | One generic unclassified question-format kind, with format retained |
| Current recognized opening reports/questions/answers | Existing definition | Unchanged | Unchanged |
| Successful source recovery | Proposed correction | Normal processing | Normal processing |
| Stale-store refusal | D3=A | D3=A | D3=A |
| A2 identity policy | A2-owned | Unchanged | Unchanged |

Question D4:
**D4 — What if explicit source recovery still cannot classify a turn?**
Project: A1 completion on `a1-followups`.
ELI10: We can recover the real historical cases from printed roles and procedural structure. The remaining edge case is a future or malformed question-format turn with no reliable evidence after that recovery. We need an error policy so the implementation never silently turns it into a Rede or drops its text.
Stakes: refusing delays the affected sitting until its source is resolved; keeping an unknown row lets the build proceed with incomplete classification.
Recommendation: A because no real unknown specimen justifies a new domain kind, and the source is retained for diagnosis instead of certifying a guessed classification.
Note: options differ in behavior, not coverage — no completeness score.

Header: Unresolved source turn
Options:
A) Reject the sitting (recommended)
Report the sitting, source marker and missing evidence, and refuse to accept that sitting's parse. Explicit replay fails before replacing the store; successful source recovery continues normally. This preserves count accuracy and avoids inventing a new kind, but the affected source needs investigation before it can be accepted. Estimated human: ~1–2h / CC: ~15–30min including boundary tests and documentation.
B) Keep an unknown contribution
Preserve the text, speaker and question-format context in an explicitly unclassified non-Rede row. This keeps ingestion moving and makes uncertainty inspectable. It adds a new data/glossary kind and leaves that sitting's contribution classification incomplete; it must not be presented as a question, answer or opening report. Estimated human: ~2–3h / CC: ~25–45min including storage/rendering tests and documentation.

Net: require enough source evidence to accept the sitting versus publish a visibly incomplete contribution classification.

State: approved.
Actual answer: D4=A, user reply “A” on 2026-10-05.
Accepted scope: exhaust reliable occurrence-specific source evidence, then reject the affected sitting parse with source diagnostics. Replay fails before replacing the store; do not stamp provenance on rejected input. No unknown contribution kind. D1 and D3 remain fixed.
History: D2 prompted the source investigation; the original proposed unknown kind was withdrawn as the first remedy after zero observed specimens and concrete recoverable historical defects.

### Metadata implementation note for the approved D3 policy

Use a dedicated store-owned key/value table, such as `pipeline_metadata`, with a `speech_kinds_version` key. The full staged rebuild validates every input report, persists all entries, stamps the actual rule version, then computes facts and performs integrity checks before promotion. Do not certify the whole store from `initialize()` or one low-level `persist_report()` call. Preserve the marker through the distribution backup and document it as derived provenance.

Check provenance before store-dependent rendering, `run_facts_engine`, `export_distribution_data`, and standalone `facts.replay` including card writes. Keep read-only opening and schema/connect helpers able to inspect/rebuild stale stores; otherwise the recovery command would be blocked by its own guard. An online full rebuild and explicit repersist may repair stale provenance before consumers run. A path that does not consume the store is not blocked merely because an unrelated old store exists. Schema and report-version guards still apply to their own inputs. No global report/store atomicity or same-version snapshot guarantee is claimed by a rule-version marker alone.

## Concrete data and failure contracts

**Source recovery.** Share one effective-role helper in `speech_kinds.py`, consumed by classification and `parse_redner`. Prefer a valid structured role; use an explicitly recognized printed label suffix when structured evidence is absent. Preserve the printed evidence and provenance on that occurrence. Do not infer government office from a person's other turns. Contradictory structured/printed evidence receives a source diagnostic and must not silently certify incompatible question/answer labels; unresolved classification follows D4. Opening reports require chair/procedural evidence, not merely the first government speaker. Add exact historical format headings/classes; ordinary debates about the procedure stay ordinary debates.

**Nested questions.** Refactor the existing source-segment walk once, retaining current main-speaker text ownership. Only source/procedural evidence of a Zwischenfrage supports that kind; another marker alone can be a chair turn or a different contribution. Preserve all question paragraphs until a new marker; exclude comments/chair segments. A nested question has nullable native `rede_id`, a separate container source locator, raw speaker-marker ordinal, and containing source link. Its stable key uses protocol + enclosing native XML rede ID + raw marker ordinal; if the enclosing ID is absent use its source TOP/raw-unit ordinal. Never reuse the parent's native `rede_id`, fabricate one, or key by name/text/kind. Preserve existing IDs for existing cases. Presentation sequence is unique within an agenda item and independent of identity. The enclosing unit may itself be a Beitrag: preserve the source link even when it has no row in `speeches`. Coordinate any schema/stable-ID signature extension with A2; do not introduce a broken FK to a non-Rede container.

**Written submissions.** Recognize explicit `anlagen-text@anlagen-typ` singular/plural written-speech forms from the sampled sources. Use kind `zu_protokoll` and broaden the glossary's Beitrag definition to include explicitly recorded written submissions. Keep §31 declarations and other annex types separate. Native annex rede IDs retain the native contribution identity rule. Associate a TOP only from source evidence (including explicit annex heading/marker and verified TOC relationships); never invent one from nearest position alone. Use report-level `xml_contributions` for submissions with no supported TOP and nullable `agenda_item_id` in SQLite. Update fresh report construction, `xml_top_fields`/replay, summaries, person traversal, rendering and export together. Missing pages remain null. Sitting-level submissions appear in a visible annex section; people with only these contributions use A2's existing evidence/eligibility rules. All Rede totals, shares and term series exclude them.

**Guest addresses.** Test available historical source cases against XML/PDF evidence. If XML omits the guest address, record that coverage limit and reconcile the misleading TODO; do not invent text or classify everyone without party/role as a guest. If an actual guest unit is present, use evidenced role/procedure to exclude it from Rede figures and show it with the sitting under the established glossary. If additional acquisition is required, describe it as a separate evidenced gap rather than marking ingestion complete.

**Replay association and safety.** Precompute a one-to-one source TOP mapping for the entire report using supported source IDs, repeated-TOP continuation order and corroborating heading/source-unit evidence. Indices are not identity. Permit a refreshed heading when other evidence proves the same source TOP. Missing/extra/moved items cannot carry old DIP/vote enrichment across without a proven match: refuse and require reacquisition. Validate all mappings and D4 classifications before mutating accepted reports or promoting the staged store. Existing accepted-reference outputs survive failure. XML/report pair hashes may detect interrupted source replacement, but do not substitute for semantic mapping or promise whole-site atomicity. Catch expected source/input errors with sitting/path context; let programming errors remain visible. Reject invalid cached kinds before rendering. Use existing publication URL validation at XML acquisition; empty document numbers are failures, not cache hits.

**Persisted provenance.** Use `pipeline_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)` (or an equivalent existing store-owned metadata abstraction). Validate that every report entering a full staged rebuild has the current speech-rule version and is accepted. Stamp the store-wide version only after every report has persisted successfully, before guarded facts computation. Run SQLite integrity/FK checks before promotion. Low-level initialization/individual report writes cannot certify the whole store. Guard standalone facts/card writes, export before output-directory writes, and store-dependent offline rendering before reading counts/person summaries. Low-level open/connect/schema remain usable for inspection and repair. Reports-only paths may proceed when they do not consume the store. A rule version detects rule staleness; it does not prove identical report/store snapshots under the same version. Bump the rule version for these changed semantics; coordinate schema versions with A2, preserve distribution `PRAGMA user_version`, and retain metadata through distribution backup.

**Vote receipts.** Prefer the vote's authoritative `protocol_id` where present and valid; otherwise choose one deterministic associated protocol row using an explicit order. Obtain ID/document number/date from that same row. Cover both affected registry queries. Remove unused wrapper/callback only after confirming call sites against the final A2 branch.

### Failure modes: 0 critical gaps left without a planned disposition

| Failure | Required behavior | Work |
|---|---|---|
| Explicit recovery still leaves a format turn unknown/conflicted | Source diagnostic; reject sitting; no accepted parse or provenance stamp | T2, T6; D4 |
| Missing/ambiguous source TOP or wrong XML document | Refuse replay/reacquire; no promotion or enrichment reassignment | T6 |
| Missing XML, unsafe URL, empty document number, malformed cached kind | Actionable expected-input failure; retain accepted reference outputs | T6 |
| Missing/stale store rule metadata | Refuse affected consumer before writes; give explicit repair command | T6; D3 |
| Partial rebuild/facts/integrity failure | Discard staged result; old reference store remains usable for repair | T6, T8 |
| Silent asker lookup ambiguous | Keep source name/party, nullable person link; no speculative registry merge | T3 |
| Annex TOP/page unknown | Preserve sitting-level contribution with null association/page | T5 |
| Multiple nested questions or non-Rede parent | Distinct source IDs and valid containing-source link | T4 |

## Code quality review

CQ1 [P1, confidence 10/10]: `validate_dip_protocol.py:377` derives persisted role independently of classification. A printed-role fix in only one path would classify answers correctly but persist misleading speaking roles. Disposition: one shared occurrence-specific helper in T2; preserve evidence and test parity, no additional module.

CQ2 [P1, confidence 10/10]: `stable_ids.py:39` keys native contributions only by protocol/rede ID. Reusing a containing rede ID for nested questions would collide. Disposition: explicit container/marker identity in T4, backward-stable existing keys, A2-coordinated contract. Report/persistence/render iterators must include sitting-level annex contributions; avoid duplicating parser loops or hand-maintained kind switches where the existing registry can serve them.

CQ3 [P1, confidence 10/10]: `validate_dip_protocol.py:1933` creates a `by_index` map before replacing XML fields. Disposition: validate the entire source mapping first in T6 and retain the accepted store on failure. Retain existing summary fingerprint invalidation rather than rewriting the summary feature.

CQ4 [P2, confidence 10/10]: `facts.py:175–177` and `227–229` independently minimize receipt fields. Disposition: one selected row in T7; fixture with disagreeing lexical/chronological minima. Remove dead vote adapters instead of leaving two advertised persistence entry points.

## Test review and validation plan

Existing coverage is reused: the 29 classifier and 28 replay tests passed during planning. They cover previously fixed closing/Bitte-schön, surname boundaries, summary invalidation and XML acceptance. Those are preserved, not duplicated solely to mirror code. The missing coverage below verifies changed contracts across boundaries.

```text
Official XML / cached report
  ├─ explicit role + heading + paragraph evidence → same classifier/persisted role
  │    ├─ opening report / question / answer → original definitions
  │    └─ unresolved or conflicting evidence → reject sitting [D4]
  ├─ nested speaker segments → question text + stable container/marker identity
  ├─ typed annex → zu_protokoll → supported TOP or sitting-level/null page
  └─ validated document + one-to-one TOP map
       ├─ invalid/ambiguous → no accepted report/store replacement
       └─ accepted current-version reports → staged persistence
            ├─ failure → no certification/promotion
            └─ metadata → facts → integrity/FKs → promotion
                  ├─ stale/missing at consumer → stop before output [D3]
                  └─ current → counts, links, facts/cards, distributions
```

| Test family / existing boundary | Required assertion | Value card |
|---|---|---|
| Classifier/parser historical fixtures | 18/13 and 18/84 opening report + questions/answers, effective-role parity, uppercase P, exact historical headings; ordinary procedure debate negative | protects=historical meaning; fails_when=explicit source evidence is ignored or overgeneralized; why_new=historical cases absent from existing coverage; seam=none |
| Unresolved/conflicting format evidence | Diagnostic includes sitting/source marker; fresh acceptance and replay fail before promotion, old outputs unchanged | protects=certified counts; fails_when=unknown becomes Rede or disappears; why_new=D4 policy; seam=none |
| KI/name extraction | Preserve current positives; ambiguous possibility/closing and surname negatives; party suffixes separated; reported pronoun case reproduced; ambiguous/unique asker resolution | protects=counts and attribution; fails_when=grant/name evidence is guessed; why_new=uncovered source-backed extraction cases; seam=none |
| Segment/persistence/identity | Multiple nested questions, interruptions/comments/chair boundaries, non-Rede container, own-text preservation; no collisions; existing keys unchanged, second replay same | protects=text ownership and identity; fails_when=question dropped/duplicated or parent key reused; why_new=new stored source segment; seam=none |
| Annex/report/render/export | Explicit written types only; singular/plural, §31 negative; associated and unassigned TOP, absent page; contribution-only person, separate counts and links | protects=written evidence without Rede inflation; fails_when=source dropped or association invented; why_new=annex ingestion and top-level traversal; seam=none |
| Replay/source acquisition | Reordered/repeated TOP, changed heading with supported identity, ambiguous and extra/missing items; wrong document, unsafe URL, empty number, malformed cached kind; expected error context | protects=enrichment association and accepted outputs; fails_when=indices transfer old votes to another source; why_new=remaining replay/acquisition gaps; seam=none |
| Provenance/consumer guards | Missing/stale/current marker; partial rebuild cannot stamp; facts/cards/export/offline blocked before writes; low-level repair allowed; no-persist/online repair semantics; distribution retains marker and sentinel | protects=counting basis; fails_when=fresh reports certify stale store or guard blocks repair; why_new=D3 persisted provenance; seam=none |
| Vote facts | Associated protocols whose independent minima disagree; authoritative protocol wins; fallback selects one row; normal single source unchanged | protects=coherent fact receipts; fails_when=id/date/document derive from different protocols; why_new=latent SQL failure; seam=none |
| Scratch integration with A2 | Full suite; fresh/incremental grouping, unresolved attribution, FK/integrity, unchanged second replay, generated links, exports and updated counts | protects=combined A1/A2 completion; fails_when=new contribution shapes break registry/export consumers; why_new=integration depends on final A2 contract; seam=none |

No production dependency-injection seam is required. Keep mocks only at existing acquisition/network boundaries; use real XML/parser/SQLite for the semantic contracts. Tests to retire: none identified; remove dead-wrapper-only coverage if it has no independent behavior after T7.

**Validation execution:** use Python >=3.11 (`/opt/miniconda3/bin/python3.13` available), run focused changed tests followed by the full supported suite. Record baseline/current source-unit labels and text lengths across all available local XML (290 at investigation time), plus the bounded historical sample. Report changed units, counts per kind and DIP discrepancies with explanations; DIP activity totals are not ground truth. Preserve every structured mismatch; aggregate actionable operator diagnostics with a detailed artifact, without a frequency suppression threshold. Review intended movements and any unexplained regressions before closing T8. The classifier cannot be certified by simply matching DIP totals.

Work in a scratch cache/store/output directory. Replay twice, compare IDs/rows/text/counts and exports, check `PRAGMA integrity_check` and `foreign_key_check`, and exercise consumer rejection before output writes. Do not mutate the reference store/site or perform the A3 full acquisition. Historical counts in the investigation are bounded probes, not final expected whole-sitting totals (the P-class fix was not in those probes). Check guest source coverage explicitly and report remaining gaps honestly.

## Performance review

PF1 [P2, scale: 290 cached XML plus bounded historical samples; no benchmark measured]: new nested/annex extraction must reuse linear source walks, not reparse XML per contribution. Bound report memory to the current document; compare before/after parse/replay duration and peak memory on the same scratch sample. No hard timing budget is invented.

PF2 [P2, scale: number of report speakers/contributions; timing unknown]: build a sitting/WP candidate index once for silent-asker resolution; do not query/reconcile the global registry inside each paragraph. Provenance is one metadata read per consuming operation, not per rendered card. Vote receipt selection remains set-based SQL; examine its query plan on scratch data and reuse existing joins/indexes before adding an index.

PF3 [P2, scale: one staged full-cache rebuild plus SQLite backup/export]: retain explicit full replay and existing staging rather than auto-rebuilding on read. Measure staged disk usage and ensure failures do not promote a partial store. Whole-site atomic release is out of scope. These are acceptance checks in T8, not a new performance subsystem.

## Review completion and handoff

Architecture, code quality, tests and performance reviewed. Four-section findings: 8 (one architecture, four code quality, three performance), all mapped to T2–T8. Critical gaps without disposition: 0. Unresolved decisions: 0. No new feature or domain policy remains for a fresh implementer to choose; evidence-based parser mechanics must be validated during implementation. Scope Challenge accepted as-is (D1=A). Stale persisted-rule refusal (D3=A) and reject unresolved source turns (D4=A) are the exact user-approved policies.

Independent challenge and terminal report follow. This is an implementation-ready plan, not completed A1 functionality. A1/A2 readiness for A3 requires completed tasks plus validation against Claude's final A2 branch.

## Implementation Tasks

These checkboxes implement the sequence above. Estimates assume existing boundaries and bounded source fixtures; uncertain historical semantics can increase research time. Human/team and agent times are planning estimates, not measured throughput. Sequential implementation, no parallelization opportunity inside A1 because all behavior crosses the existing pipeline modules. A2 remains an independent checkout; coordinate shared schema/identity contracts before T4/T6 and merge before T8 combined validation.

- [x] **T1 (P1, human: ~3–5h / CC: ~45–90min)** — Source fixtures: Freeze baseline labels and source-backed historical fixtures. Surfaced by: Backlog historical validation; T2 source investigation. Files: `tests`, `docs/plans/a1-turn-investigation.md`. Verify: the matching test family above; T8 runs the full supported suite and scratch acceptance gates.
- [x] **T2 (P1, human: ~4–6h / CC: ~45–90min)** — Classification: Recover occurrence roles, historical headings/classes and enforce D4. Surfaced by: Architecture P1; CQ1; D4. Files: `scripts/speech_kinds.py`, `scripts/validate_dip_protocol.py`, `tests`. Verify: the matching test family above; T8 runs the full supported suite and scratch acceptance gates.
- [x] **T3 (P1, human: ~3–5h / CC: ~45–90min)** — Classifier precision: Tighten grants and announced asker parsing/resolution. Surfaced by: Backlog classifier/name findings. Files: `scripts/speech_kinds.py`, `scripts/validate_dip_protocol.py`, `tests`. Verify: the matching test family above; T8 runs the full supported suite and scratch acceptance gates.
- [x] **T4 (P1, human: ~5–8h / CC: ~1–2h)** — Contributions: Persist nested questions with stable source locators and containing links. Surfaced by: CQ2; Zwischenfrage backlog. Files: `scripts/validate_dip_protocol.py`, `scripts/persist_dip_pulse_store.py`, `scripts/stable_ids.py`, `tests`. Verify: the matching test family above; T8 runs the full supported suite and scratch acceptance gates.
- [x] **T5 (P1, human: ~5–8h / CC: ~1–2h)** — Annex ingestion: Store and display written submissions, including unassigned TOPs. Surfaced by: Written-annex backlog; traversal contract. Files: `scripts/validate_dip_protocol.py`, `scripts/persist_dip_pulse_store.py`, `scripts/build_dip_pulse_site.py`, `scripts/render_dip_pulse_html.py`, `tests`. Verify: the matching test family above; T8 runs the full supported suite and scratch acceptance gates.
- [x] **T6 (P1, human: ~6–10h / CC: ~1–2h)** — Replay and provenance: Validate TOP mapping, harden inputs and enforce persisted-rule output guards. Surfaced by: CQ3; D3; D4. Files: `scripts/validate_dip_protocol.py`, `scripts/persist_dip_pulse_store.py`, `scripts/build_dip_pulse_site.py`, `scripts/facts.py`, `tests`. Verify: the matching test family above; T8 runs the full supported suite and scratch acceptance gates.
- [x] **T7 (P2, human: ~2–3h / CC: ~20–40min)** — Vote receipts: Select one receipt source row and remove dead persistence adapters. Surfaced by: CQ4; dead-wrapper backlog. Files: `scripts/facts.py`, `scripts/persist_dip_pulse_store.py`, `scripts/features/votes.py`, `tests`. Verify: the matching test family above; T8 runs the full supported suite and scratch acceptance gates.
- [x] **T8 (P1, human: ~5–8h / CC: ~1–2h)** — Validation and docs: Validate scratch replay and final A2 integration; reconcile docs/TODOs. Surfaced by: Test review; PF1–PF3; A1 acceptance. Files: `tests`, `docs`, `CONTEXT.md`, `README.md`, `TODOS.md`. Verify: the matching test family above; T8 runs the full supported suite and scratch acceptance gates.

## Independent challenge

Claude Code was attempted once with read-only `--access none` and a five-minute limit. Input contained the current plan (bounded to the first 30KB; historical alternatives omitted) and complete investigation. No review response was produced: authentication failed in this execution context. Provider diagnosis: “Claude Code authentication failed. Run claude interactively in this execution context to authenticate.” Repair is interactive authentication (`claude auth login`) before a future review; this is not a production blocker imposed by the plan. Native Plan/TaskOutput/TaskStop fallback capabilities are absent; no general agent was substituted. Outside coverage is unavailable, not clean. Session: `aab0534d-a924-4d7c-b3d3-1322f65e7805`; modelUsage `{}`; all reported token counts 0; model identity unknown.

## Approval readiness

PASS for planning: D1, D3 and D4 match the user's choices; original D2 alternatives remain history. No scope was cut. Eight engineering findings have concrete tasks, tests and failure dispositions; no critical gap or unresolved decision remains. Outside coverage is unavailable and explicitly disclosed. Implementation prompt: [a1-implementation-prompt.md](a1-implementation-prompt.md). Portable test plan: [a1-test-plan.md](a1-test-plan.md). Production fixes, full-suite verification and final A2 integration are pending implementation, not claimed by this planning report.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| CEO Review | /plan-ceo-review | Scope & strategy | 0 | Not run | No prior review record |
| Outside Review | Claude Code / plan-eng-review | Independent second opinion | 1 attempt | Unavailable | Authentication failure; no completed reviewer |
| Eng Review | /plan-eng-review | Architecture & tests | 1 | ISSUES OPEN (mapped work) | 8 findings; 0 unresolved decisions; 0 critical gaps |
| Design Review | /plan-design-review | UI/UX gaps | 0 | Not run | No prior review record |
| DX Review | /plan-devex-review | Developer experience gaps | 0 | Not run | No prior review record |

**OUTSIDE COVERAGE:** Claude Code, plan review, unavailable; native fallback unavailable. No independent clean-review credit.

**VERDICT:** Planning complete; ready to implement T1–T8. Eng review required on the resulting implementation before A1 completion. A3 readiness depends on verified A1 plus final A2 integration.

NO UNRESOLVED DECISIONS

## Implementation status (2026-10-05)

T1–T8 are implemented under D1/D3/D4. Source comparison, fixtures, tests, scratch replay, exports and architecture documentation are recorded in [a1-validation.md](a1-validation.md). Per the user’s 2026-10-05 instruction not to wait for Claude’s usage reset, final merged A2 validation is deferred to a P1 TODO before A3; an in-progress A2 snapshot is not final approval. Original planning/review excerpts above are preserved as history.
