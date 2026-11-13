# Coverage gate PR 2: withhold refused Reden (W3-W8)

**Status:** plan, 2026-11-13. Not built.
**Parent:** `TODOS.md` "Coverage gate before the first data release", steps 1, 3, 4, 6, 7; `docs/plans/v1-scope-review.md`, "Eng review: the withholding build, T3" (D1-D10, tasks W3-W8). Those decisions are settled and not reopened here.
**Base:** origin/main a4acab0 (v0.37.0.0 with PR 1 #147, and W1's audit #148). Line numbers below are on that commit.
**Expected result on real data:** `docs/plans/withholding-preflight/report.md`. 71 of the 85 excluded sittings parse once 90 Reden are withheld (94,707 words). 13 parse as they are. 18/20 stays rejected.

## Order against ADR 0004: PR 2 first (owner, 2026-11-13)

The ADR 0004 presidium-kinds plan (`docs/plans/adr-0004-presidium-kinds.md` on local branch `claude/correctness-gate-fixes-b22045`, dac62b8, unpushed) asked for PR 1, then ADR 0004, then this PR. That plan is unbuilt, its census has not run and its O1-O12 wait on the owner. **Owner decision, 2026-11-13: "A: hold-back first".** PR 2 lands before ADR 0004.

So PR 2 creates three things and takes rule 8, schema 12 and export 17:
- the typed `LocatedRefusal`;
- the per-Rede commit-on-finish lists;
- `scripts/reviewed_units.json` with a `kind` field, holding only `withhold`.

ADR 0004 lands after PR 2, extends those three pieces and takes the next free version numbers. Its plan already covers this order: O6 (withhold P2's refusal), O11 (one file), T20 (its statuses in the reconciliation). **18/215 stays blocked at persist** (an unmapped presidium role, `check_sprechrollen`) until ADR 0004 lands. Its parse passes once its refused Rede is withheld, so this matters only when T4 restores it.

The table keeps both orders for the record:

| Shared point | If PR 2 goes first | If ADR 0004 goes first |
| --- | --- | --- |
| Typed located refusal | PR 2 defines `LocatedRefusal`; ADR 0004's P2 raises it (its O6) | ADR 0004 raises a plain `ValueError` for P2; PR 2 switches it to `LocatedRefusal` and decides O6 |
| Per-Rede output | PR 2 builds the commit-on-finish lists; ADR 0004's nested Ansprache units append to them | PR 2 wraps ADR 0004's nested Ansprache units in the same lists |
| `scripts/reviewed_units.json` (O11) | PR 2 creates it with kind `withhold`; ADR 0004 adds `ansprache` and `sitzungsleitung` | ADR 0004 creates it; PR 2 adds `withhold` |
| Version numbers | PR 2: rule 8, schema 12, export 17; ADR 0004 takes the next | the reverse |
| `REDE_STATUS` | PR 2 adds `withheld` | ADR 0004 adds its two rows; PR 2 adds `withheld` after them |

The key of a reviewed entry is the unit id the parser emits after `split_nested_reden`. For a Rede that was not split, that is the source id. That fits both uses. ADR 0004's entries name the owner's part, which keeps the source id. A `withhold` entry may name a split part `ID…:n` (D4).

## T4: not needed

PR 2 does not need the 85 sittings' votes, TOPs and links. They stay on the exclusion record until T4 acquires them online with `--include-document-number`. Two things change for them in PR 2. Each gets a real reason instead of "excluded" (W5). And PR 2 proves their outcome at parse level on W1's XML (`~/agent-runs/w1/xml/`): 71 parse once withheld, with the same 90 Reden and 94,707 words; 13 parse unchanged. The fresh 718-sitting store holds no sitting with a located refusal, so after PR 2 it holds 0 withheld units. Its replay moves `speeches.sequence` only (D3).

## Design

### W3: parser (`scripts/validate_dip_protocol.py`, `scripts/speech_kinds.py`, new `scripts/reviewed_units.py` and `scripts/reviewed_units.json`)

**Typed refusal.** `class LocatedRefusal(ValueError)` carries `rede_id`, `marker` and `reason` (`refused_nested_contribution` or `refused_nested_question_speaker`). It is raised at the two located sites (`:1717`, `:1724`) with the same message text, so existing handlers and tests keep working. The per-Rede loop catches only this type. Every other refusal still refuses the sitting: classification, Befragung turns, Fragestunde markers, conflicting roles, "nested contribution needs a source rede id", and reconciliation.

**Commit-on-finish.** Pass 2 (`:1675-1752`) collects each Rede's output in local lists: its speech or Beitrag, its nested units, and its pass-2 diagnostics (`merged_zwischenfrage`). These join the TOP's lists only when the Rede finishes. `open_exchange` already resets per Rede, so `nested_units[-1]` in the same-asker merge (`:1730`) always refers to the Rede's own list. The page reference stays in the TOP's page span on purpose: the withheld Rede is printed there (outside voice 5).

**Withheld record.** When a Rede is withheld, by `LocatedRefusal` or by a reviewed entry, the TOP's `withheld` list gains:
`{rede_id, sequence, reason, reason_detail, speaker (parse_redner), source_page, paragraph_count, char_count, word_count, text, paragraphs, nested_turns, nested_word_count}`.
- `sequence` is its position among the TOP's `<rede>` elements after the split, the same space speeches use (D3).
- `reason_detail` is the refusal message, or the reviewed entry's `reason`.
- `text` and `paragraphs` are the Rede speaker's own words after pass 1, defined as `speeches.text` is. That includes text pass 1 merged into it (`attachments`, Scope Challenge 5). `char_count` and `word_count` measure them.
- `nested_turns` are the other speakers' segments pass 1 left (`remaining`), in marker order: `[{marker, xml_redner_id, speaker_name, fraktion, text}]`. `nested_word_count` measures them. They are kept apart from `text` because `speech_segments` returns own paragraphs as one flat list, so the interleaving cannot be recovered. Kept apart, no Zwischenfrager's words are filed under the host's name or Fraktion.
- A segment pass 1 moved out (`merged_rede`, `merged_erwiderung`) stays where it went and is in neither field (D7). A segment pass 1 ruled procedural (chair, election acceptance) is not speech and is in neither.
- Words are `\S+` tokens, as W1 counted them. W1's 94,707 is own plus nested words. The replay checks the sum `word_count + nested_word_count` against it and explains any difference.
- The N9 shares compare `word_count` with the words of `speeches.text`: own words against own words. Nested words are reported beside them, not in the share.
- A withheld Rede binds no person (Scope Challenge 6).
- Its pass-1 diagnostics stay (D7). A diagnostic of another Rede that targets a withheld Rede keeps its target id.
- A Beitrag whose `parent_rede_id` names a withheld Rede keeps it. DATA.md says such an id may be found in `withheld_units`.

**Reviewed list (N7, W8).** `scripts/reviewed_units.json`: `{"entries": [{"sitting", "rede_id", "redner_id", "kind", "reason"}]}`, with `kind` in {`withhold`} for now. `reviewed_units.load()` reads and checks it once per process and caches it. A malformed file raises `ReviewedUnitsError(Exception)`, not a `ValueError`, so it does not read as "source rejected" for every sitting (ADR 0004 plan, P1). It is loaded **eagerly** at the start of `build_dip_pulse_site.main`, `validate_dip_protocol.main` and `extract_demo_fixture`, before any sitting is touched. The dossier loop's bare `except Exception` (`build_dip_pulse_site.py:289`) re-raises it, so a lazy load can never be swallowed as one failed sitting either. `parse_protocol_xml(xml, reviewed=None)` defaults to the file's entries for that sitting. The D6 script passes its own entries. In pass 2, a listed unit is withheld with reason `reviewed` before it is emitted. An entry whose unit the sitting does not hold, or whose `redner_id` differs from the owner marker's first id, refuses the sitting (`ReconciliationError`).

**Reconciliation.** `REDE_STATUS` gains no kind. Instead, `record_status(statuses, rid, "withheld")` is recorded at the withhold point. The status set grows by `withheld`. Under D7, a source whose text pass 1 moved and that is then withheld reconciles as `withheld`; the moved segments are recorded in diagnostics, which already name their target. That is how this PR carries D7's "partly merged into X, rest withheld": one status plus the diagnostics, not a compound status. DATA.md and the ADR say so. `reconcile_reden` is unchanged.

**Report shape.** Each agenda item gains `xml_withheld` (the records above) through `xml_top_fields`. `xml_speakers` entries gain `sequence`. `validation_summary` gains `withheld_rede_count` and `withheld_word_count`. Readers that compute a speech's sequence with `enumerate(xml_speakers)` switch to the carried value: `persist_dip_pulse_store.py:1261`, `build_dip_pulse_site.py:7870` and `render_dip_pulse_html.py:3085`. `render_dip_pulse_html.py:1879` uses the index for anchors only and stays as it is. The value only matters for a synthetic id, and the store has none.

**Speech rule 7 → 8.** Stored output changes (sequence), so `require_current_speech_rules` forces the replay.

### W4: store and export

- **Schema 11 → 12.** New table `withheld_units`: `id` (`withheld_occurrence_id(protocol_id, rede_id)` in `stable_ids.py`), `protocol_id`, `agenda_item_id`, `rede_id`, `sequence`, `reason`, `reason_detail`, `xml_redner_id`, `speaker_name`, `fraktion` (as printed), `page`, `page_quadrant`, `char_count`, `word_count`, `text` (own words), `nested_word_count`, timestamps. Nested turns go to table `withheld_turns` (R2 A): `id`, `withheld_unit_id`, `protocol_id`, `marker`, `xml_redner_id`, `speaker_name`, `fraktion` as printed, `word_count`, `char_count`, `text`, exported as `withheld_turns.csv`. `UNIQUE(protocol_id, rede_id)`. No `mp_id`. `speeches` and `contributions` are unchanged (D2).
- **`speeches.sequence`** is the parser's source position (D3). `UNIQUE(agenda_item_id, sequence)` still holds.
- **Export format 16 → 17.** The export adds `withheld_units.csv`, and the meaning of `speeches.sequence` changes. `scripts/data_dictionary.json` gets the table and the new sequence text. DATA.md and the Daten page get a coverage section (N9): per year, sittings in the catalog, held and excluded (with reasons); Reden stored and withheld; words in stored Reden, words withheld and the withheld share. The withheld share also goes per Fraktion and year, and per sitting for every sitting with a withheld Rede. Words of stored Reden are `\S+` tokens of `speeches.text`, counted at export.
- **`compare_store_values.py`** reports withheld units per protocol (added, removed, changed). **`validate_store_gate.py`** counts the table and checks that no `withheld_units.rede_id` is also in `speeches` or `contributions`.
- **Dossier.** A TOP with a withheld Rede shows one line per Rede: printed speaker and Fraktion, "zurückgehalten, nicht mitgezählt" and the reason, without the text. The Dossier must not silently drop a speaker. The wording follows DESIGN.md's tone. No new component.

### W5: release behaviour (D5, D9) and exclusion reasons (gate step 4)

- **Run summary.** After a rebuild, the build prints each withheld unit the new store holds and the previous store did not, with sitting, Rede, speaker and reason.
- **Manifest.** `datenstand.json` lists the withheld units under `withheld_reden`: protocol, `rede_id` and reason.
- **Release.** `release_changes.py` derives `withheld_reden_added` and `withheld_reden_released` from the previous manifest into `changes.json` and `CHANGES.md` (D5). `publish_dip_pulse_data.py` refuses a release that adds more than `WITHHELD_CAP = 2` newly withheld units (D9), unless `--confirm-withheld` names each of them. The initial release has no previous manifest: it lists every withheld unit, and the cap does not apply. A previous manifest without the field (export format 16 or older) counts as holding no withheld units. `previous_manifest_problem` (`publish_dip_pulse_data.py:80`) accepts it. `docs/data-changelog.md` documents both.
- **Exclusion reasons.** An entry of `coverage-exclusions.json` needs `reason` from a fixed set plus a non-blank `reason_detail`. The set is `source_defect`, `not_narrowable`, `awaiting_rule` and `awaiting_acquisition`. The loader refuses "excluded", a missing reason or an unknown one. `--exclude-document-number` takes `--exclusion-reason CODE` and `--exclusion-detail TEXT`. The Daten page and DATA.md list each excluded sitting with its reason. The PR ships the 86 reasons for the current record as `docs/plans/coverage-gate-pr2/coverage-exclusions.json`, a drop-in copy of the record with reasons: copy it to `OUTPUT_DIR/data/` once (built so; first planned as a separate reasons file plus a merge command). The preflight groups give: 18/20 `source_defect`; ADR 0004's seven, 18/62 and 18/90 `awaiting_rule`; the other 75 of the 85, including N7's four, `awaiting_acquisition`. That makes 85. The record holds 86: the 86th is 21/106, which joined on 2026-11-12, and W1 did not fetch its XML. Its refusal is located (`ID2110609100:4` marker 2), so it too gets `awaiting_acquisition`, with the detail "parser gap; expected back with one withheld Rede". Whether a release may go out while `awaiting_acquisition` entries remain is gate step 8's call, not PR 2's.

### W6: regression contract (D6)

- **Store replay.** Base a4acab0 and the PR tip, each run with `--offline --repersist --today 2026-11-12` on a `cp -cR` clone of `.context/dip-pulse-site`, then `compare_store_values.py --cohort shared`. Expected: 718 protocols, 0 refused, 0 moved values except `speeches.sequence`, counted old and new, and 0 withheld units.
- **Parse-level diff** of all 718 cached XML at base and tip. Expected: only `sequence` on speeches, the new empty `xml_withheld` and the summary keys differ.
- **W1's 84 XML at the tip.** Expected: 71 parse with 90 withheld Reden and 94,707 words (any difference explained); 13 parse with results identical to base; 18/20 is not in the set.
- **Withhold-one script** `scripts/check_withhold_one.py`. For every WP 18/19 sitting held, it picks, per TOP, one Rede; one next to a Kurzintervention/Erwiderung pair; and one next to a resumed pair (outside voice 7). It parses again with that Rede forced through `reviewed`, and asserts that every other unit's id, text, speaker, kind and sequence are unchanged, with nested Beiträge compared by id. Run before ship. A unit test covers its compare function on a fixture.

### W7: docs and retirement (D10)

- **New `docs/adr/0005-withhold-refused-reden.md`.** It states:
  - the grain: the refused part after the split (D4);
  - the cost: no refused marker is a Rede's first, so each withheld Rede includes an opening nobody questioned; 18/1's Alterspräsident Rede for a one-sentence acceptance is the worked example;
  - the moved-text rule (D7);
  - storage (D2), sequence (D3) and the reasons;
  - the reviewed list;
  - the cap (D5, D9);
  - the exclusion bar.
- **`CONTEXT.md`** gets "Zurückgehaltene Rede". **`docs/data-methods.md`** gets the withheld status in the reconciliation paragraph and the coverage definition.
- **Retirement.** `scripts/audit_offline_turns.py`, `tests/test_audit_offline_turns_cli.py` and the test cases in `tests/test_a1_followups.py` and `tests/test_reden_outside_tops.py` that drive the script are deleted. Their parser assertions move to the new tests where they cover a path. Plan docs that cite the script get a one-line note pointing to `withheld_units`. `docs/plans/withholding-preflight/fetch_and_audit.py` imported the script and is deleted with it (built so; first planned to stay with a docstring note). Its run is recorded in `preflight.json` and `report.md`, and both scripts are in git history up to a4acab0.

### W8: reviewed entries for N7

The four sittings' known wrong units are documented in `a3-wp18-19-round2-result.md:104-111,127`:
- 18/2: Haßelmann and Korte, whole Reden counted as Zwischenfragen;
- 18/29: Groth `ID1802902700:2`, a §31 Erklärung split as a Rede;
- 18/83: Weinberg as a Zwischenfrage, and Tempel's Kurzintervention merged at `ID1808302100:2:2:2`;
- 19/25: `ID192507100`, the swapped Keul/Röttgen Rede.

Located on W1's XML at a4acab0 (each entry is keyed by the unit the parser emits; for a Rede-shaped Zwischenfrage that is its host Rede):

| Sitting | Entry `rede_id` | Holds |
| --- | --- | --- |
| 18/2 | `ID1800202300` | `nested:…:2` Haßelmann (4,209 chars) and `nested:…:3` Korte (5,099), Reden as Zwischenfragen |
| 18/29 | `ID1802902700:2` | Groth's §31 Erklärung split as a Rede (1,935 chars) |
| 18/83 | `ID1808301300:3` | `nested:…:2` Weinberg (11,401 chars), a Rede as a Zwischenfrage |
| 18/83 | `ID1808302100:2:2:2` | `nested:…:6` Tempel's Kurzintervention merged into his Zwischenbemerkung |
| 19/25 | `ID192507100` | Keul's Zwischenfrage counted as a Rede, with Röttgen's Rede nested in it (4,459 chars) |

Withholding a host withholds its speaker's own speech with it, which matches the Rede grain (D4). The ADR states it. The entries stay inert until T4 acquires the sittings. N8's review adds more later.

## Tests

New `tests/test_withholding.py`, with inline XML modelled on `tests/test_rede_reconciliation.py`. It covers:
- both located classes withheld, with the run continuing;
- every other refusal class still refusing;
- rollback of nested units and the `merged_zwischenfrage` diagnostic;
- text merged into a withheld Rede goes with it;
- a withheld resumed Rede (D7);
- a refused split part withholds only that part (D4);
- a reviewed entry withheld, a stale entry refused and a wrong `redner_id` refused;
- a malformed list raises `ReviewedUnitsError`;
- the sequence is the source position;
- the record keeps own words and nested turns apart, and moved or procedural segments stay out of both;
- reconciliation with a `withheld` status;
- replay equals fresh (the list is a repository file).

Extended files:
- `tests/test_daten_export.py`: the CSV, the DATA.md coverage section and the data dictionary;
- persist tests: the table, no person bound, sequence;
- `tests/test_backfill.py`: exclusion reasons;
- release tests: the cap, `--confirm-withheld` and the changelog;
- render tests: the Dossier line and the Daten coverage.

Suite runs on 3.13.18 and 3.11.18.

## Failure modes

| Path | Failure | Handling |
| --- | --- | --- |
| Located refusal | A withheld Rede leaks units | commit-on-finish, rollback test, withhold-one script |
| Reviewed list | stale or misapplied entry | refusal naming the entry |
| Reviewed list | malformed file | `ReviewedUnitsError`, the run stops |
| New WP 21 refusal | silently withheld | run summary, changelog, cap of 2 |
| Exclusion record | bare "excluded" | the loader refuses, naming the entry |
| Sequence switch | a reader relied on 1..n | readers use it only to order (T3 review); the replay counts the moves |

## NOT in scope

- T4: the DIP metadata, votes, TOPs and links of the 85, and restoring them.
- The N8 and T7 reviews, and the N9 minimum.
- Withholding for refusals that cannot be narrowed to one Rede.
- ADR 0004's kinds and its census.
- Refusing a release while `awaiting_acquisition` exclusions remain (gate step 8).

## Build notes (2026-11-13)

Where the build departs from the plan above, or found something it did not expect:
- **`build_dip_pulse_site.py:289` already re-raises.** Its `except Exception` prints "Failed" and then raises, so the Sonnet check's concern (a swallowed `ReviewedUnitsError`) does not hold. The list is still loaded eagerly in all three entry points.
- **The reason table lives in `speech_kinds.WITHHELD_REASONS`**, with a short label for the Dossier and the long text for the data dictionary. `validate_dip_protocol.WITHHELD_REASONS` derives from it, and a test pins the data dictionary's code list to it (red flag 8).
- **Fallbacks for hand-built reports.** Persist and the readers take `speech["sequence"]` and `protocol["reviewed_digest"]` when present. When absent they fall back to the enumerate position and the current file's digest. Every rule-8 parse sets both, and a report without them carries rule 7, which `require_current_speech_rules` refuses downstream. So the fallback reaches no store a reader may use. It spares about 100 hand-built test reports.
- **`reviewed_units.ReviewedUnitsError` covers both a malformed file and a stale entry.** Neither is a `ValueError`, so neither reads as a refused source on the online or offline path (outside voice 3).
- **The release cap is a function**, `publish_dip_pulse_data.withheld_cap_problem`, so it is tested apart from a real release directory.
- **19/36 newly refuses for reconciliation.** Once its located refusal is withheld, PR 1's reconciliation reaches an unread `<rede>`: the Zu-Protokoll Rede `ID193616800` in a second annex block titled „Liste der entschuldigten Abgeordneten“. W1 could not see it behind the earlier refusal. It is a source shape for a named annex rule, which needs the owner's yes, so 19/36 stays out with `awaiting_rule` (TODOS.md).
- **18/173 and 18/193 also wait on ADR 0004.** They parse once withheld, but each holds a presidium `<rede>` ("Präsident", no Fraktion) that `check_sprechrollen` refuses at persist, like 18/215. The parse-level check ran `derive.check_sprechrollen` on all 84 W1 reports.
- **The 18/10 fixture** (`tests/fixtures/withholding/18-10-top3.xml`) is the one TOP of the official 18/10 XML that holds `ID1801002600`. It is the real case of a refused split part (D4), since no existing fixture has one.

## Replay (2026-11-13)

**Corpus.** The fresh 718-sitting store (`.context/dip-pulse-site`, built 2026-11-12 at 28799ac). Every run used a `cp -cR` clone under `~/agent-runs/pr2/` with `--today 2026-11-12`. Base is a4acab0, tip is this branch. The tip clone got `docs/plans/coverage-gate-pr2/coverage-exclusions.json` first, since the loader refuses the old bare "excluded" (the operator step this PR documents).

**Store replay (D6).** `--offline --repersist` ran at base (rc 0) and at the tip (rc 0, "718 cached reports persisted; store replaced"). `compare_store_values.py --cohort shared` gives:

| Quantity | Base (a4acab0) | Tip |
| --- | ---: | ---: |
| Protocols | 718 | 718 |
| Speeches | 54,937 | 54,937 |
| Contributions | 42,724 | 42,724 |
| Withheld Reden | n/a (no table) | 0 |
| Vote totals changed | | 0 |
| Fakt values moved | | 0 of 1,922 |
| `speech_rule_inputs.version` | 7 | 8 (all 718) |

**Every stored column, row by row.** Speeches, contributions, agenda items, protocols, votes, vote members, documents and agenda item documents were compared by id, every column but the timestamps. The only moved value is `speeches.sequence`: **5,556 of 54,937 speeches in 425 sittings**. Old: the position among the TOP's stored speeches. New: the position among the TOP's `<rede>` elements, the space Rede-based Beiträge already use (D3). A speech after a Kurzintervention, Erwiderung, Befragung turn or procedural Rede now skips that slot, for example 21/105 `ID2110505700` moves 12 → 14. The new value is more correct because it is a source position: withholding or releasing a neighbour, now or in a later parser round, no longer renumbers a speech.

**Parse-level diff.** All 718 cached XML were parsed at base and tip: 0 refused, 0 differences beyond the fields PR 2 adds (`sequence` on speeches, empty `withheld`, `reviewed_digest`).

**Withhold-one (D6).** `scripts/check_withhold_one.py` ran on all 718 sittings, not only WP 18/19. It withheld 5,719 middle Reden, 960 Kurzinterventionen, 871 Erwiderungen and the one resumed pair (21/43, both sides), each pick set in a parse of its own, with 1 Rede per TOP. Failed checks: **0**.

**W1's 84 XML at the tip** (`~/agent-runs/w1/xml`):

| | W1 preflight (28799ac, audit script) | PR 2 tip (parser) |
| --- | ---: | ---: |
| Parse once Reden are withheld | 71 | 70 |
| Located Reden withheld | 90 | 89 |
| Words withheld (own + nested) | 94,707 | 93,572 (own 72,272, nested 21,300) |
| Parse with no located refusal | 13 | 13 (N7's four now withhold 5 reviewed units: 3,701 own and 4,079 nested words) |
| Refused | 18/20 not fetched | 19/36 (reconciliation) |

The differences, each explained:
- **19/36 (−1 sitting, −1 Rede, −1,125 words):** behind its located refusal, the reconciliation now reaches the unread annex `<rede>` (Build notes).
- **−10 words:** 18/10 `ID1801002600:2` holds a 10-word Sitzungsleitung segment. W1 counted every segment; the withheld record leaves out what pass 1 rules procedural (plan, W3).
- **89 of the 90 Reden match W1 by id**, and 88 match it word for word.

**Persist check for T4.** `derive.check_sprechrollen` ran on the 84 tip reports. Twelve sittings stop at persist on an unmapped presidium or guest role: ADR 0004's seven, 18/62, 18/90, 18/215, 18/173 and 18/193. So T4 can restore 71 of the 85 plus 21/106.

## Eng review (2026-11-13)

**Target:** this file, `docs/plans/coverage-gate-pr2.md`, as of the owner's order answer (PR 2 before ADR 0004). D1-D10 of the T3 review are binding and not reopened.

**Pre-review check:** a Sonnet subagent checked the plan's own decisions P-A to P-I (2026-11-13). It agreed with seven. It changed two:
- P-A: load the list eagerly, and re-raise its error past the dossier loop's `except Exception` at `build_dip_pulse_site.py:289`.
- P-C: own words and nested turns kept apart, and the N9 share on own words.

It also found four contradictions: the 85/86 count with 21/106's reason, `previous_manifest_problem` with a manifest that lacks the field, a fourth `enumerate` reader, and D7's status wording. All six are folded into the sections above. Under the owner's rule (Sonnet agrees, go ahead), the plan's other decisions stand: P-B (W8 entries now), P-D, P-E, P-F, P-G, P-H and P-I.

### Reality rows

| Premise | Receipt | Verdict |
| --- | --- | --- |
| The two located refusals are raised per Rede in pass 2 | `scripts/validate_dip_protocol.py:1717,1724` | true |
| Exchange state resets per Rede, so `nested_units[-1]` refers to the Rede's own units | `:1684-1686`, `:1727-1730` | true |
| `xml_speakers` carries no sequence; three readers `enumerate` it | `validate_dip_protocol.py:3620-3632`; `persist_dip_pulse_store.py:1261`; `build_dip_pulse_site.py:7870`; `render_dip_pulse_html.py:3085` | true |
| `speeches.sequence` is `UNIQUE(agenda_item_id, sequence)` | `persist_dip_pulse_store.py:321` | true |
| The exclusion record writes reason "excluded" | `build_dip_pulse_site.py:803` | true |
| The dossier loop has a bare `except Exception` | `build_dip_pulse_site.py:289` (Sonnet check) | true |
| The 718 held sittings parse at base with no refusal | `~/agent-runs/pr2/base-718.jsonl`: 718 of 718 `error: null` [measured 2026-11-13] | true |
| Of W1's 84 XML, 13 parse and 71 refuse at base | `~/agent-runs/pr2/base-w1.jsonl`: 13 `error: null` [measured] | true |
| 90 Reden and 94,707 words are withheld in the 71 | `docs/plans/withholding-preflight/preflight.json` summary | true, re-measured at the tip |
| The record holds 86 sittings | the fresh store's `data/coverage-exclusions.json`: 86 entries [measured] | true |
| The N7 units are the five in W8 | W1 XML parsed at a4acab0 [measured]; `a3-wp18-19-round2-result.md:104-111` | true |

REALITY: premise-table pass 11 premises, unverified=0 `scripts/validate_dip_protocol.py:1717`
REALITY: already-done pass `git log origin/main --since=2026-11-09` on the named files shows only #141, #143, #147 and #140; no withholding exists `scripts/validate_dip_protocol.py:1505`
REALITY: surface-check pass `--offline`, `--repersist`, `--output-dir`, `--today`, `--include-document-number`, `--exclude-document-number` in `build_dip_pulse_site.py --help`, `--cohort` in `compare_store_values.py --help`; `--exclusion-reason`, `--exclusion-detail` and `--confirm-withheld` are new in this plan `scripts/build_dip_pulse_site.py:13703`
REALITY: binding-decisions pass `gstack-decision-search --scope branch` empty; D1-D10 (T3 review), the owner's order answer (2026-11-13) and N1, N7, N8, N9 bind `docs/plans/v1-scope-review.md:552`
REALITY: numbers pass 718, 84, 13, 71 and 86 [measured above]; 90 and 94,707 [measured: preflight.json]; efforts [estimated] `docs/plans/withholding-preflight/report.md:7`
REALITY: deferred-asks pass no linked issue; the brief's asks (ADR, docs and DATA.md, tests, replay with old and new figures) are all in scope `docs/plans/coverage-gate-pr2.md:1`
REALITY: pr-count pass no `.gstack/ship-policy.json`; one PR (D1 below) `docs/plans/coverage-gate-pr2.md:1`

### Scope Challenge

**What already exists:** the per-Rede loop and its per-Rede state reset (`:1684-1686`); PR 1's ledger (`record_status`, `reconcile_reden`); `ReconciliationError` as the precedent for a typed `ValueError`; `person_corrections.json` as the reviewed-list pattern; the version gate (`require_current_speech_rules`); `compare_store_values.py`; `release_changes.py`'s manifest diff; and W1's numbers as the oracle.

**Complexity:** about 20 changed files, of which 4 are new (`reviewed_units.py`, `reviewed_units.json`, `check_withhold_one.py`, ADR 0005), plus the new `tests/test_withholding.py` and docs. Two new exception classes. The gate trips.

D1 (structure): **Original arrangement**, one PR. Answered 2026-11-13 by the owner's adjudicator hook: "the 85 sittings stay excluded until T4, so no release can carry a withheld Rede before both halves exist. A second PR would cost another full ship gate."

**Scope record:** feature answers: none proposed; structure: A (D1, adjudicator, 2026-11-13); accepted scope: W3-W8 as this plan lists them, in one PR; pending remedies: none (R2 answered A). Scope Challenge result: scope accepted as-is.

**Findings:**
1. [INFORMATIONAL] (confidence: 8/10) `build_dip_pulse_site.py:678-700`: once the loader refuses "excluded", the next run on the current store stops until the 86 reasons are applied. That is intended pre-release. The refusal names the file and the shipped reasons file as the fix. Recorded, no decision.
2. [INFORMATIONAL] (confidence: 8/10) data model of the nested turns: the plan put them in a JSON column, but a CSV with JSON in a cell is awkward, and turns are queried by speaker. Decision R2.
3. [INFORMATIONAL] (confidence: 7/10) W8 runs ahead of the task list's "after the N8 review pass". Settled under the owner's rule with a Sonnet AGREE (P-B). Recorded.

### Section 1: Architecture

```
parse_protocol_xml(xml, reviewed=None)              validate_dip_protocol.py
  raw_rede_inventory (PR 1)
  reviewed = reviewed_units.for_sitting(wp/nr)      NEW (list loaded eagerly at startup)
  per TOP: split, classify, pass 1 (unchanged; all Reden present)
    pass 2, per Rede:
      listed? ------------------------------------> withheld(reason=reviewed)
      emit into local lists (unit, nested, merged_zwischenfrage diagnostics)
        LocatedRefusal ---------------------------> drop local lists; withheld(reason=refused_*)
        any other ValueError ---------------------> sitting refused (unchanged)
      commit local lists; record_status(rid, speech|beitrag|procedural|withheld)
    unmatched listed entry -> ReconciliationError
  reconcile_reden (PR 1, unchanged)
report: xml_speakers[].sequence, xml_withheld[] (own words + nested_turns)
  -> persist: speeches.sequence = source position; withheld_units; withheld_turns
  -> export: withheld_units.csv, withheld_turns.csv, DATA.md coverage (N9), manifest withheld list
  -> build run summary: withheld units new against the previous store (D5)
  -> publish: cap 2 newly withheld against the previous manifest, --confirm-withheld (D9)
```

**Design-twice (new module `reviewed_units.py`).** Shape A: a module of its own that owns the file. It exposes `load()` (eager, cached, `ReviewedUnitsError`) and `for_sitting(document_number)`, and hides the shape checks, the key rules and the kinds. Shape B: the loader inside `validate_dip_protocol.py` (4,418 lines) next to the parser. Pick A. One owner for the list. ADR 0004 adds its kinds there without touching the parser's loader code. Two calls hide all the validation. Under B, the next agent copies the loader pattern into the 4,400-line parser module.

Red flags screened:
- **Hand-synced list (flag 8).** The withheld reason codes and the exclusion reason codes live in code and again in `data_dictionary.json` and DATA.md. Fix: one module-level table per code set, holding the German description, and a test that fails when the data dictionary's listed codes differ from it. Required with the approved behavior; no question.
- **Two ways to do one task (flag 6).** A speech's sequence comes from `enumerate` in three readers. Fixed by the plan: all three read the carried value.
- None of the other six apply. The parser keeps one owner for unit output (commit-on-finish), and the list is read only through `reviewed_units`.

Findings:
1. [INFORMATIONAL] (confidence: 8/10) The run summary diffs the new store's `withheld_units` against the previous store's. The first run after schema 12 has no previous table: treat it as empty, and still list every withheld unit. Required; recorded.
2. [INFORMATIONAL] (confidence: 7/10) `build_dip_pulse_site.py:289`: the bare `except Exception` turns any exception into one failed sitting. `ReviewedUnitsError` is re-raised there (folded in from the Sonnet check). Recorded.

Dispositions: both required by approved work; no question.

### Section 2: Code quality

1. [INFORMATIONAL] (confidence: 8/10) `validate_dip_protocol.py:1727-1737`, quoted: `first = nested_units[-1]` / `nested_units[-1] = contribution_unit(`. The same-asker merge mutates the last nested unit. Under commit-on-finish it must mutate the Rede-local list, or a merge could reach a committed unit of an earlier Rede. Today `open_exchange` resets per Rede (`:1686`), so it cannot. The local list makes that explicit. Required; test.
2. [INFORMATIONAL] (confidence: 7/10) A reviewed entry that names an annex Rede or a Fragestunde turn never meets the per-Rede loop. It refuses as "names no Rede of a TOP". Required; test.
3. [INFORMATIONAL] (confidence: 7/10) A withheld Rede that is the `parent_rede_id` of a later Beitrag: the Beitrag keeps the id unchanged, and DATA.md says it may point into `withheld_units`. Required; test.
4. [INFORMATIONAL] (confidence: 7/10) A TOP whose every Rede is withheld: `speeches` is empty and the page range still spans the printed Reden (outside voice 5 of T3). The Dossier shows the withheld lines instead of "Keine Reden". Test.
5. [INFORMATIONAL] (confidence: 8/10) `docs/plans/withholding-preflight/fetch_and_audit.py` imports `audit_offline_turns`, which D10 deletes. Its docstring says to run it from 28799ac's `scripts/`. Recorded.

Dispositions: all are required parts or proof of approved behavior; no question.

### Section 3: Tests

Framework: `unittest`, run as `uv run --python 3.13.18 python -m unittest discover -s tests` plus 3.11.18.

```
CODE PATHS                                                   STATUS
W3 LocatedRefusal at :1724 -> withheld, run continues          [GAP] new (test_a3_rule5 pins the raise today)
   LocatedRefusal at :1717 -> withheld                         [GAP] new
   other refusals still refuse the sitting                    [★★ TESTED] test_a1_followups, test_speech_kinds; extend with one row each
   rollback: nested units, merged_zwischenfrage diagnostic     [GAP] new
   text merged into a withheld Rede goes with it              [GAP] new
   resumed Rede withheld; moved text stays (D7)               [GAP] new
   split part refused -> only that part (D4)                  [GAP] new
   reviewed: listed unit withheld                             [GAP] new
   reviewed: stale entry / wrong redner_id / annex id refuse  [GAP] new
   reviewed: malformed file -> ReviewedUnitsError, not swallowed at :289  [GAP] new
   record: own words apart from nested turns; moved/procedural out  [GAP] new
   reconcile: withheld status; a dropped withheld unit refuses [GAP] extend test_rede_reconciliation
   sequence = source position; parent_rede_id kept           [GAP] new
W4 persist: withheld_units, withheld_turns, no person bound    [GAP] new
   export: two CSVs, data dictionary, DATA.md coverage        [GAP] extend test_daten_export
   reason-code tables equal the data dictionary               [GAP] new
   compare_store_values / validate_store_gate counts          [GAP] extend their tests
W5 run summary lists new withheld units (empty previous table) [GAP] new
   publish: cap 2, --confirm-withheld, initial exempt, old manifest  [GAP] extend release tests
   changelog: withheld_reden_added / _released                [GAP] extend release_changes tests
   exclusion loader refuses "excluded", missing, unknown code [GAP] extend test_backfill
W6 withhold-one compare function                              [GAP] new (fixture)
USER FLOWS
   researcher sums Reden per Fraktion: withheld absent         [GAP] export test
   Dossier TOP shows the withheld line, including all-withheld TOP  [GAP] render test
   Daten page coverage and exclusion reasons                  [GAP] render test
   operator replays after the version bump                   [★★ TESTED] require_current_speech_rules tests; extend
COVERAGE: 2/27 paths tested today | GAPS: 25, all required proof of approved behavior
```

Legend: ★★★ behavior + edge + error | ★★ happy path | [GAP] no test

Regression rule: D6 A (T3 review, approved 2026-11-09) is the exact regression contract and carries forward. Replays at base and tip: 0 moved values except `speeches.sequence`, counted; withhold-one per TOP. Plus parse-level checks on the 718 XML and W1's 84. No new question.

Tests made obsolete: `tests/test_audit_offline_turns_cli.py`, and the cases in `tests/test_a1_followups.py` and `tests/test_reden_outside_tops.py` that drive `audit_offline_turns` (D10).

### Section 4: Performance

1. [INFORMATIONAL] (confidence: 8/10) The withhold-one script parses each WP 18/19 sitting once per pick set, not once per TOP. Withholding writes no state another TOP reads for its units (`seen_formats` and `rid_pages` are not written by pass 2). `written_contributions` adds zu-Protokoll Beiträge to their target TOP at `max+1` of that TOP's own contributions, so the effect stays inside the TOP (corrected by outside voice 1). So one parse can withhold one Rede in every TOP at once, and the diff still catches any cross-TOP effect. Three pick sets × about 400 sittings ≈ 1,200 parses [estimated], against about 18,000 for one per TOP. That is an implementation of D6 with the same assertions; recorded.
2. [INFORMATIONAL] (confidence: 7/10) Word counts over about 55,000 `speeches.text` at export: one linear pass, negligible [estimated].

Dispositions: recorded; no question.

### Outside voice (2026-11-13)

Codex (`gpt-6-astra`, gstack plan-review role) ran and timed out at the five-minute limit while still reading `v1-scope-review.md` and `publish_dip_pulse_data.py`. It returned no review, so outside coverage is missing. The native fallback, a Plan subagent dispatched under a five-minute timer, reported in about 2 minutes with VERDICT: FINDINGS. It is not outside coverage.

OUTSIDE VOICE (Claude subagent), condensed. Each item was checked here:

| # | Severity | Finding | Checked | Disposition |
| --- | --- | --- | --- | --- |
| 1 | High | Dropping a withheld Rede's nested units renumbers later nested and zu-Protokoll Beiträge (`max+1`, `validate_dip_protocol.py:1789-1791`, `:1434`). The withhold-one "sequence unchanged" assertion would fail, and the "no state crosses TOPs" claim misses `written_contributions` reading target TOPs after the parse | Confirmed in code. D3's accepted scope already allows it: "nested Beiträge may renumber within the TOP, ids unchanged" | Factual correction, no reopening. W6 compares sequence for speeches and Rede-based Beiträge, and compares nested and zu-Protokoll Beiträge by id with sequence excluded. Section 4 item 1 corrected: zu-Protokoll sequences are TOP-local, so batching one withheld Rede per TOP stays valid. DATA.md says which sequences are source positions |
| 2 | High | An edit to `reviewed_units.json` forces no replay. `require_current_speech_rules` checks only `speech_kinds.VERSION` (`persist_dip_pulse_store.py:86-97`), so a stored sitting keeps a unit the list now withholds | Confirmed | **R3** |
| 3 | Medium | A stale entry raised as `ReconciliationError` reaches the operator on the offline path as "the `<rede>` elements … do not reconcile" (`build_dip_pulse_site.py:1986-1991`), and the generic branch says to re-fetch the XML | Confirmed | Required for the approved behavior (a stale entry refuses, naming the entry): `ReviewedUnitsError` covers both file and entry failures, it is not a `ValueError`, and its message names the entry and `scripts/reviewed_units.json`. `reparse_cached_xml` and the online path let it stop the run. Recorded |
| 4 | Medium | No end-to-end run of W4/W5 on data with a withheld unit: the store holds 0 after PR 2 | Confirmed (0 in the 718) | **R4** |
| 5 | Medium | "withheld" already names held-back fact cells (`facts.withheld`, `withheld_reason`, `facts.py:94,1402`; `compare_store_values.py:298`) | Confirmed | **R5** |

## Decision ledger

### R2: where the nested turns of a withheld Rede are stored
Finding: Scope Challenge 2, INFORMATIONAL, 8/10, `docs/plans/coverage-gate-pr2.md` W4, reviewer: this review
Plan baseline: the draft's `nested_turns` JSON column on `withheld_units`; D2 A approved the table `withheld_units` with "text"; the split of own and nested text came from the Sonnet check (P-C)
Runtime evidence: the export writes one CSV per table (`build_dip_pulse_site.py` export); no table has a JSON column today [code read]; W1 counted own plus nested words per Rede
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R2 nested turns storage | JSON column (draft) | table `withheld_turns`: one row per nested turn (`withheld_unit_id`, marker, `xml_redner_id`, speaker name, printed Fraktion, words, text), exported as `withheld_turns.csv` | JSON column `nested_turns` on `withheld_units`, inside `withheld_units.csv` |
| D2 `withheld_units` table | approved (D2 A) | unchanged | unchanged |
| Own words and the N9 share on own words | approved (P-C, Sonnet) | unchanged | unchanged |

Question D2:
D2 — How should the other speakers' turns inside a withheld Rede be stored?
Project/branch/task: claude/coverage-gate-holdback-84ea37, coverage gate PR 2, W4 storage.
ELI10: A withheld Rede often holds turns by other members, such as the Kurzintervention that caused the refusal. We keep them apart from the speaker's own words so nobody's words are filed under the wrong name. They can sit in one extra column as a JSON list, or in a small table of their own with one row per turn.
Stakes if we pick wrong: a researcher who opens the CSV either gets JSON inside a cell to unpack, or one more file to join.
Recommendation: A because a CSV reader can filter turns by speaker or Fraktion directly, and the project keeps fields that are queried on their own in their own columns.
Completeness: A=9/10, B=7/10
Pros / cons:
A) A table per turn (recommended)
  ✅ Each turn has its own speaker, Fraktion and word count, so it filters in any spreadsheet.
  ✅ No JSON inside a CSV cell: every export file stays flat and typed in the data dictionary.
  ❌ One more table, CSV and data-dictionary entry, and a join to read a Rede whole.
B) A JSON column
  ✅ One row per withheld Rede holds everything about it, with no join.
  ✅ Smallest change: one column in the table D2 already approved.
  ❌ CSV readers must parse JSON in a cell to see who spoke or count words per Fraktion.
Net: flat, filterable turns against one row per Rede with JSON inside.
Header: Turn storage
Options:
A) Table per turn (recommended)
New table `withheld_turns` (`id`, `withheld_unit_id`, `protocol_id`, marker, `xml_redner_id`, `speaker_name`, `fraktion` as printed, `word_count`, `char_count`, `text`), exported as `withheld_turns.csv` and described in DATA.md. `withheld_units` keeps `nested_word_count`. Effort: human ~2 h / CC ~15 min.
B) JSON column
`nested_turns` (JSON text) on `withheld_units`, exported inside `withheld_units.csv`. Effort: human ~1 h / CC ~5 min.

State: approved
Actual answer: A) Table per turn, answered 2026-11-13 by the owner's adjudicator hook: "a flat table lets a CSV reader filter and count them without parsing JSON … a reversible pre-release schema choice"
Accepted scope: new table `withheld_turns` (`id`, `withheld_unit_id`, `protocol_id`, marker, `xml_redner_id`, `speaker_name`, `fraktion` as printed, `word_count`, `char_count`, `text`), exported as `withheld_turns.csv`, in the data dictionary and DATA.md; `withheld_units` keeps `nested_word_count` and drops `nested_turns`; the report keeps `nested_turns` per withheld record as the source for persist
History: none

### R3: a changed reviewed list forces a replay
Finding: outside voice 2, High, confidence 9/10, `scripts/persist_dip_pulse_store.py:86-97`, reviewer: Claude subagent (native fallback), confirmed here
Plan baseline: P-A (Sonnet AGREE): the list is a repository file; replay equals fresh. Nothing ties a stored sitting to the list version
Runtime evidence: `require_current_speech_rules` compares `speech_rule_inputs.version` with `speech_kinds.VERSION` only
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R3 list staleness | none: an edited list leaves stored sittings as they were | `speech_rule_inputs` gains `reviewed_digest`, the SHA-256 of that sitting's entries (canonical JSON, empty list hashed too); `require_current_speech_rules` refuses facts, export and render when any protocol's digest differs, with the replay as the fix | a whole-file digest per protocol: any edit refuses every sitting |
| Schema | 12 (this PR) | 12, one column more | 12, one column more |
| P-A, D2, R2 | approved | unchanged | unchanged |

Question D3:
D3 — How should the store notice that the reviewed list changed?
Project/branch/task: claude/coverage-gate-holdback-84ea37, coverage gate PR 2, W3/W4.
ELI10: The reviewed list says which Reden to hold back. If someone adds an entry for a sitting the store already holds, nothing today makes the store re-read that sitting, so the Rede stays counted and published. The store can remember a fingerprint of the entries it used for each sitting, and refuse to build pages or exports until the sitting is re-read.
Stakes if we pick wrong: a Rede the owner decided to withhold stays in every count and release, silently.
Recommendation: A because it refuses only when a sitting's own entries changed, so an edit costs one replay and never hides.
Completeness: A=10/10, B=9/10
Pros / cons:
A) Per-sitting fingerprint (recommended)
  ✅ The check names exactly the sittings whose entries changed, so the fix is obvious.
  ✅ Entries for sittings not yet in the store (N7's four) change nothing until T4 acquires them.
  ❌ One more column and a canonical hash of a sitting's entries, with tests.
B) Whole-file fingerprint
  ✅ Simplest check: any edit to the file at all asks for a replay.
  ✅ Also catches edits that touch no stored sitting, such as a reworded reason.
  ❌ Every edit, even for an unacquired sitting, blocks pages and export until a full replay.
Net: a precise refusal against the simplest one that over-triggers.
Header: List staleness
Options:
A) Per-sitting fingerprint (recommended)
`speech_rule_inputs.reviewed_digest` holds the SHA-256 of the sitting's entries (canonical JSON; no entries hashes an empty list); `require_current_speech_rules` refuses when any stored protocol's digest differs from the current file, naming up to five sittings and the `--offline --repersist` fix. Effort: human ~2 h / CC ~15 min.
B) Whole-file fingerprint
`speech_rule_inputs.reviewed_digest` holds the SHA-256 of the whole file; any edit refuses until a full replay. Effort: human ~1 h / CC ~10 min.

State: approved
Actual answer: A) Per-sitting fingerprint, answered 2026-11-13 by the owner's adjudicator hook: "refuses only when a stored sitting's entries actually changed, and names those sittings … a reversible pre-release choice"
Accepted scope: `speech_rule_inputs.reviewed_digest` (schema 12) holds the SHA-256 of the sitting's entries as canonical JSON (an empty list hashed too); persist writes it; `require_current_speech_rules` refuses facts, export and render when any stored protocol's digest differs from the current file, naming up to five sittings and the `--offline --repersist` fix; tests for an added, a removed and an unrelated entry
History: none

### R4: an end-to-end test with a withheld unit
Finding: outside voice 4, Medium, confidence 8/10, plan W4/W5, reviewer: Claude subagent (native fallback), confirmed (0 withheld units in the 718)
Plan baseline: layer tests per W4/W5 (Section 3 coverage map), approved as required proof of D2, D5, D9, R2
Runtime evidence: after PR 2 the fresh store holds 0 withheld units; the 85 stay excluded until T4
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R4 end-to-end proof | layer tests only | plus one test on a fixture store: two small sittings, one with a located refusal; parse, persist, export, `datenstand.json`, `release_changes` and the publish cap against a previous manifest, with 1 and then 3 newly withheld units (3 refused unless confirmed) | layer tests only |
| Layer tests (Section 3) | required | unchanged | unchanged |

Question D4:
D4 — Should one test run withholding through the whole pipeline before T4?
Project/branch/task: claude/coverage-gate-holdback-84ea37, coverage gate PR 2, W4/W5 tests.
ELI10: After this PR the real store holds no withheld Rede yet: the sittings that need it come back only at T4. So the new table, CSVs, manifest list, changelog and the cap of 2 are tested piece by piece, and the first time they run together would be a real release. One test on a tiny made-up store can run all of it end to end now.
Stakes if we pick wrong: the cap that is meant to stop a bad release could be wired wrong and nobody notices until it matters.
Recommendation: A because the cap is the safety net D9 asked for, and only an end-to-end run proves the pieces hand data to each other.
Completeness: A=10/10, B=7/10
Pros / cons:
A) Add the end-to-end test (recommended)
  ✅ Proves parse, store, export, changelog and cap work together before any real release.
  ✅ Catches a field renamed in one layer and not the next, which layer tests miss.
  ❌ One slower test with a small fixture store to maintain (human ~3 h / CC ~30 min).
B) Layer tests only
  ✅ No extra fixture; each layer stays tested on its own.
  ✅ T4 will exercise the real path with 90 withheld Reden anyway.
  ❌ The first end-to-end run of the cap is a real release.
Net: one fixture test now against trusting the layers to fit until T4.
Header: E2E test
Options:
A) Add the end-to-end test (recommended)
One test in `tests/test_withholding.py` builds a fixture store from two small sittings (one with a located refusal), exports it, writes `datenstand.json`, runs `release_changes` and the publish cap against a previous manifest: 1 newly withheld passes and is listed, 3 refuse without `--confirm-withheld`. Effort: human ~3 h / CC ~30 min.
B) Layer tests only
Keep the per-layer tests of Section 3; no end-to-end fixture.

State: approved
Actual answer: A) Add the end-to-end test, answered 2026-11-13 by the owner's adjudicator hook: "the cap (D9), manifest listing and changelog fields would never run together before a real release. One fixture test is cheap"
Accepted scope: one test in `tests/test_withholding.py`: a fixture store from two small sittings (one with a located refusal), exported, `datenstand.json` written, `release_changes` and the publish cap run against a previous manifest; 1 newly withheld passes and is listed, 3 refuse without `--confirm-withheld`
History: none

### R5: "withheld" names two things
Finding: outside voice 5, Medium, confidence 8/10, `scripts/facts.py:94,1402`, `scripts/compare_store_values.py:298`, reviewer: Claude subagent (native fallback), confirmed
Plan baseline: D2 A named the table `withheld_units` (2026-11-09); the plan adds a `withheld` status, report keys and changelog fields
Runtime evidence: `facts.withheld` and `facts.withheld_reason` mean a fact cell held back because a sitting is missing; DATA.md and the Daten page describe that today
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R5 naming | both meanings use "withheld" | keep the settled names; every new name says what is held back: `withheld_units`, `withheld_turns`, status `withheld`, report key `xml_withheld`, summary `withheld_rede_count`, changelog `withheld_reden_added`/`withheld_reden_released`; CONTEXT.md and DATA.md get two entries, "Zurückgehaltene Rede" and "Zurückgehaltener Fakt", each pointing to the other | rename the new concept "held back": `held_back_reden`, `held_back_turns`, status `held_back`, and so on |
| D2 table, R2 turns table | approved | names kept | renamed, same columns |

Question D5:
D5 — Should the new "withheld Rede" concept keep that name next to the existing withheld facts?
Project/branch/task: claude/coverage-gate-holdback-84ea37, coverage gate PR 2, naming.
ELI10: The dataset already says "withheld" for a fact that is held back because a sitting is missing. This PR holds back whole Reden and was going to call that "withheld" too. Both will appear in the same coverage section and store comparison. We can keep the word but always say what is held back, with a glossary entry for each, or pick a different word for the Reden.
Stakes if we pick wrong: a reader mixes up a held-back fact with a held-back Rede and misreads coverage.
Recommendation: A because every new name already says "Reden", "units" or "turns", the glossary separates the two, and the settled table name stays.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Keep "withheld", qualify every name (recommended)
  ✅ Matches the settled table name and the plan, ADR and TODOS wording already in use.
  ✅ Two glossary entries that point at each other make the difference explicit for readers.
  ❌ The bare word still means two things; a careless reader of a single column can mix them.
B) Rename the Reden concept "held back"
  ✅ Two words for two things: no column or status can be confused with the facts one.
  ✅ Costs nothing in data: nothing is published yet, so names can change freely.
  ❌ Renames a settled name and splits English terms from the German "zurückgehalten" both use.
Net: one qualified word with glossary entries against two distinct words.
Header: Naming
Options:
A) Keep "withheld", qualify
Names: `withheld_units`, `withheld_turns`, status `withheld`, `xml_withheld`, `withheld_rede_count`, changelog `withheld_reden_added`/`withheld_reden_released`. CONTEXT.md and DATA.md get "Zurückgehaltene Rede" and "Zurückgehaltener Fakt", cross-referenced. Effort: human ~30 min / CC ~5 min.
B) Rename to "held back"
Names: `held_back_reden`, `held_back_turns`, status `held_back`, `xml_held_back`, and so on throughout the plan, ADR and docs. Effort: human ~1 h / CC ~10 min.

State: approved
Actual answer: A) Keep "withheld", qualify, answered 2026-11-13 by the owner's adjudicator hook: "Every new name carries 'Reden', 'units' or 'turns', and two cross-referencing glossary entries … separate it from the existing `facts.withheld` cell meaning"
Accepted scope: names `withheld_units`, `withheld_turns`, status `withheld`, `xml_withheld`, `withheld_rede_count`, `withheld_word_count`, changelog `withheld_reden_added`/`withheld_reden_released`, manifest `withheld_reden`; CONTEXT.md and DATA.md entries "Zurückgehaltene Rede" and "Zurückgehaltener Fakt", cross-referenced
History: none

### TODO decision

D6 (TODO): **A) Add to TODOS.md.** Answered 2026-11-13 by the owner's adjudicator hook: "a missing-guard item, not a defect in a current figure … record it in TODOS.md rather than build it". The entry goes under coverage gate step 8: the first release refuses while any exclusion has reason `awaiting_acquisition` or `awaiting_rule`. Why: the bar allows only `source_defect` and `not_narrowable`. Depends on T4. It lands in this PR's TODOS.md edit.

Approval readiness: PASS. Checked:
- D1 (structure A);
- R2 (D2 A), R3 (D3 A), R4 (D4 A), R5 (D5 A) and the TODO (D6 A), each with the adjudicator's answer of 2026-11-13 recorded above;
- P-A to P-I under the owner's Sonnet rule (Sonnet AGREE, 2026-11-13);
- D1-D10 of the T3 review, approved 2026-11-09;
- the order (owner, 2026-11-13).

Every other accepted item is required work or proof of these. The regression contract is D6 A of the T3 review, carried forward.

### Required outputs

**NOT in scope:** as listed under "NOT in scope" above, plus the release refusal on awaiting exclusions (TODO, D6).

**What already exists:** listed under Scope Challenge. Reused:
- the per-Rede loop and its state reset;
- PR 1's ledger and `ReconciliationError` pattern;
- the version gate (extended with `reviewed_digest`);
- the reviewed-list pattern of `person_corrections.json`;
- `compare_store_values.py`;
- `release_changes.py`'s manifest diff.

Rebuilt: none. Retired: `audit_offline_turns.py` (D10).

**Failure modes** (added to the table above):

| Path | Failure | Handling | Users see |
| --- | --- | --- | --- |
| Reviewed list edited after persist | a stored sitting keeps a unit the list now withholds | `reviewed_digest` refusal (R3), naming the sittings | the run stops, loudly |
| Stale entry on the offline replay | the operator re-fetches good XML | `ReviewedUnitsError` names the entry and the file (outside voice 3) | the run stops, with the right fix |
| Release with 3 or more newly withheld units | parser drift reaches a release | cap of 2, `--confirm-withheld`, end-to-end test (R4) | the release is refused |
| Nested and zu-Protokoll sequences shift after a withhold | a reader treats them as source positions | DATA.md: only speeches and Rede-based Beiträge carry source positions (D3) | none expected |

Critical gaps: 0.

**Worktree parallelization:** sequential implementation, no parallelization opportunity. Every step reads the parser's report shape, which W3 changes first.

## Implementation Tasks
Synthesized from this review's findings. Each task derives from a specific finding above.

- [ ] **T1 (P1, human: ~1w / CC: ~3h)** — parser — W3: `LocatedRefusal`, commit-on-finish, withheld records with own words and nested turns, `reviewed_units.py` and `reviewed_units.json` (eager load, `ReviewedUnitsError`), `withheld` status, sequence on speeches
  - Surfaced by: plan W3; Sonnet P-A, P-C; Section 2 items 1-4; outside voice 3
  - Files: `scripts/validate_dip_protocol.py`, `scripts/speech_kinds.py`, `scripts/reviewed_units.py`, `scripts/reviewed_units.json`, `scripts/build_dip_pulse_site.py` (`:289` re-raise, offline message), `scripts/extract_demo_fixture.py`
  - Verify: `tests/test_withholding.py` parser cases; suite on 3.13.18 and 3.11.18
- [ ] **T2 (P1, human: ~2d / CC: ~2h)** — store/export — W4: schema 12 (`withheld_units`, `withheld_turns`, `speech_rule_inputs.reviewed_digest`), sequence from the parser, export format 17 (two CSVs, data dictionary, DATA.md coverage by words, glossary entries), compare and gate scripts, Dossier line
  - Surfaced by: D2, D3 (T3), R2, R3, R5; Section 1 red flag 8
  - Files: `scripts/persist_dip_pulse_store.py`, `scripts/stable_ids.py`, `scripts/build_dip_pulse_site.py`, `scripts/render_dip_pulse_html.py`, `scripts/data_dictionary.json`, `scripts/compare_store_values.py`, `scripts/validate_store_gate.py`
  - Verify: export, persist and render tests; reason-code tables equal the data dictionary
- [ ] **T3 (P1, human: ~1d / CC: ~1h)** — release — W5: run summary, manifest `withheld_reden`, changelog fields, cap of 2 with `--confirm-withheld`, exclusion reason codes with `--exclusion-reason`/`--exclusion-detail`, the shipped reasons file for the 86
  - Surfaced by: D5, D9 (T3); Sonnet P-E, P-F
  - Files: `scripts/build_dip_pulse_site.py`, `scripts/release_changes.py`, `scripts/publish_dip_pulse_data.py`, `docs/data-changelog.md`, `docs/plans/coverage-gate-pr2/exclusion-reasons.json`
  - Verify: release and backfill tests; end-to-end test (R4)
- [ ] **T4 (P1, human: ~1d / CC: ~1.5h plus run time)** — verification — W6: `scripts/check_withhold_one.py` (batched per TOP; nested and zu-Protokoll Beiträge compared by id), store replay base against tip, parse-level diff of the 718, W1's 84 at the tip
  - Surfaced by: D6 (T3); outside voice 1; Section 4 item 1
  - Files: `scripts/check_withhold_one.py`, `tests/test_withholding.py`
  - Verify: 0 moved values except `speeches.sequence` (old and new counted); 71 + 13 with 90 Reden and 94,707 words
- [ ] **T5 (P2, human: ~1d / CC: ~1h)** — docs — W7: ADR 0005, CONTEXT.md, `docs/data-methods.md`, retire `audit_offline_turns.py` and its tests, TODOS.md (step 6/7 status, the D6 TODO, the ADR 0004 order note)
  - Surfaced by: W7, D10, R5, D6 (TODO)
  - Files: `docs/adr/0005-withhold-refused-reden.md`, `CONTEXT.md`, `docs/data-methods.md`, `TODOS.md`, deleted script and tests
  - Verify: doc-link test; review checklist class 11
- [ ] **T6 (P1, human: ~2h / CC: ~20min)** — data — W8: five reviewed entries for 18/2, 18/29, 18/83 and 19/25, checked on W1's XML
  - Surfaced by: N7 A; Sonnet P-B
  - Files: `scripts/reviewed_units.json`
  - Verify: the four sittings parse with the five units in `xml_withheld`

**Unresolved decisions that may bite you later:** none in this review.

**Completion summary:**
- Step 0: Scope Challenge — scope accepted as-is
- Reality rows: 7/7 applicable rows emitted, 0 unverified premises
- Architecture Review: 2 issues found
- Code Quality Review: 5 issues found
- Test Review: diagram produced, 25 gaps identified
- Performance Review: 2 issues found
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 1 item proposed to user (D6, added)
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 0 in this review
- Outside voice: Codex timed out at 5 minutes (unavailable); native Plan fallback completed with 5 findings (3 became R3, R4 and R5; 1 factual correction; 1 required)
- Parallelization: 1 lane, 0 parallel / 6 sequential
- Lake Score: 2/3 (R2 at 9/10, R3 at 10/10, R4 at 10/10; D5 and D6 differ in kind)

**Suppressed findings (confidence under 5):** none.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run for this plan (T3's CEO review in `v1-scope-review.md` binds) | none |
| Outside Review | Codex via `/plan-eng-review` (timed out); native Plan fallback | Independent 2nd opinion | 1 | unavailable (Codex timeout); fallback completed | 5 findings: 3 decisions (R3, R4, R5), 1 factual correction, 1 required |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN | 34 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | not run | none |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | none |

- **OUTSIDE COVERAGE:** eng phase, 2026-11-13: Codex (`gpt-6-astra`) started and timed out at the five-minute limit with no review, so there is no outside coverage. The native Plan-subagent fallback completed with 5 findings. It does not count as outside coverage.
- **VERDICT:** no review is CLEAR. The eng review answered every decision (D1-D6) and mapped every finding to tasks T1-T6. Its status is ISSUES OPEN because those tasks are unbuilt. Ready to implement. Eng review required.

NO UNRESOLVED DECISIONS
