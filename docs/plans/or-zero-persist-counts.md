# Plan: no `or 0` on the stored Rede, Beitrag and withheld counts

Scope: the eight `int(x.get(k) or 0)` writes in `scripts/persist_dip_pulse_store.py` (persist_speeches 1436-1437, persist_contributions 1500, persist_withheld 1533-1534 and 1551), and their 8 entries in `tests/code_rules_baseline.json` `or_zero` (78 -> 70). Out of scope: `_repoint_party` (766), `clean`, and every other baseline entry.

## 1. Who produces each count

Every dict these blocks read comes from the parser in `scripts/validate_dip_protocol.py`. The parser always sets every count as an int computed with `len()` or `word_count()`, never None:

| Count (block) | Producers (all set the key) |
|---|---|
| speech `paragraph_count`, `char_count` (persist_speeches) | the Rede unit at 1941-1953 (`len(paragraphs)`, `len(text)`), copied key-for-key into `xml_speakers` by `xml_top_fields` 3896-3897 (`speech["..."]`, so it would fail if the key were missing) |
| contribution `char_count` (persist_contributions, per TOP and sitting-level via 1965) | `contribution_unit` 1425 (Zu-Protokoll annex 1580, nested Zwischenfragen 2007/2016, the sitting-level `unassigned` list that becomes `report["xml_contributions"]` at 4088); the Rede-as-Beitrag copy `{**unit, ...}` at 2030, which inherits 1946; Fragestunde turns 2061 |
| unit `char_count`, `word_count`, `nested_word_count` (persist_withheld) | `withheld_record` 1662-1664, the only producer (called at 1965 and 2020) |
| turn `char_count`, `word_count` (persist_withheld) | `withheld_record` 1658 |

Cached reports replayed offline are not separate producers:
- `repersist_cached_reports` re-reads every report with `reparse_cached_xml` -> `reparse_report_xml`, which replaces all `xml_*` fields with `xml_top_fields` output. `require_parsed_reports` refuses only stale reports (`stale_causes`); a report without cached XML is skipped by `reparse_cached_xml` and persisted with its stored fields. Such a report is current (speech_kinds VERSION 9, matching reviewed digest), so `xml_top_fields` wrote those fields.
- The online route re-parses stale reports and refuses any that stay stale.
- The read-only scan of the reference store reports found no missing, None or non-int key (below).

Checked in the reference store (read-only scan of `.context/dip-pulse-site/data/plenarprotokoll-*.json`):
- All 801 reports are VERSION 9.
- 61,284 speeches, 44,193 TOP contributions, 1,196 sitting contributions, 102 withheld units and 170 turns: not one key is missing, None or a non-int.
- Stored zeros: speeches paragraph_count and char_count 2 each, contributions char_count 2, withheld_units nested_word_count 5. These are real zeros.

## 2. Decision per count

All eight: a direct lookup that fails loudly, `int(speech["char_count"])` and so on.
- None goes to NULL: the columns are `INTEGER NOT NULL DEFAULT 0`, and no producer omits a value. NULL would be a data-model change.
- None stays in the baseline.
- A future parser change that drops a key now stops the persist (`KeyError`, wrapped as "<sitting> did not persist: 'char_count'", previous store untouched); a None value raises `TypeError` from `int(None)`. Today both silently store 0.

## 3. Tests (failing first)

1. `tests/test_persist_dip_pulse_store.py`: for each (block, key) of the eight, a minimal report with that key deleted raises KeyError naming the key, and with that key set to None raises TypeError; in both cases no row is written (the `with conn:` transaction rolls back). subTest over the 8 pairs x 2 cases. Fails on main (main stores 0).
2. Same file: a real zero (char_count 0, paragraph_count 0, unit with no turns) is stored as 0.
3. Producer contract in the parser tests: parse `withholding/18-10-top3.xml`, `speech-kinds-befragung-fragestunde.xml` and `reden-outside-tops/18-44.xml` (or equivalents) through `xml_top_fields`; for each producer path (Rede, contribution_unit, Rede-as-Beitrag, Fragestunde turn, sitting-level contribution, withheld unit, withheld turn) assert at least one unit exists, then that each count key holds an int.
4. `test_code_rules.test_no_or_zero_beyond_the_baseline` fails until the 8 entries are removed.

Fixture churn: hand-built speeches in test builders lack `paragraph_count`/`char_count`. Fix the fixture builders (derive the counts from the text), not the persist code.

## 4. Store check

On APFS clones under the batch's store directory, never writing to `.context/dip-pulse-site`:
1. Clone to `baseline`, copy `mdb-stammdaten.*` into `.baseline.private/`, and run `--offline --repersist --output-dir baseline` on main e869391, so the baseline reflects today's replay logic.
2. Clone the replayed baseline to `after` (private directory included) and repersist it on the branch.
3. `scripts/compare_store_values.py baseline after` (and `--cohort all`): expect nothing to move.
4. Direct column check by id on `speeches(paragraph_count, char_count)`, `contributions(char_count)`, `withheld_units(char_count, word_count, nested_word_count)`, `withheld_turns(char_count, word_count)`: both EXCEPT directions empty, row counts and zero counts unchanged.

Stop and report, without adding a fallback, if the repersist fails with "did not persist: '<key>'" or any compared value differs.

## 5. Risks and out of scope

- A hand-made report fed to `persist_report` without a count now fails instead of storing 0. That is the intent; `tests/fixtures/report.json` and the demo fixture already carry every key.
- Out of scope: the other 70 baseline entries, page-side `char_count or 0` reads, `clean`, schema nullability, `unattributed_char_count`.
