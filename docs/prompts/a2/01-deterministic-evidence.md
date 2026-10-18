# Deterministic registry evidence

Implement the remaining name/party evidence issue in “A.2 registry follow-ups from the third review pass” (2).

Own evidence construction/aggregation in `scripts/person_registry.py`, its persistence callers when necessary, and focused registry tests. Read `bind`, `_first_touch`, `_load_rows`, `_guess_merges` and representative biography selection.

1. Reproduce a source record with occurrences printing different names/parties, including a Fraktion switch and two Redner-IDs sharing a trusted aw ID. Reverse occurrence order within and across reports; compare grouping and displayed biography.
2. Choose and document a deterministic evidence rule. Prefer retaining the normalized name/party pair set for matching if that preserves the conservative identity rules; if choosing a newest representative, use source chronology plus a stable tie-break. Keep representative biography selection distinct from the evidence allowed to join persons. A union of evidence must not bridge contradictory hard IDs or partitions.
3. Aggregate current-build evidence independently of insertion order. Re-read evidence when source attributes disappear; retain only intentionally historical registry facts. Preserve `ever_mdb` semantics and occurrence continuity.
4. Test permutations, incremental versus fresh grouping, fixed-point replay, vanished/reappearing input, and partition/hard-ID conflict guards. Check that source JSON remains unchanged.

Done when identical current input produces identical evidence, grouping and representative selection regardless of persist order, without weakening conflict guards. Document any intentional change to matching and close only this TODO subitem.
