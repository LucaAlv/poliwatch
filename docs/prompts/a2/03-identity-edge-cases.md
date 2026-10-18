# Binding, roster and merge edge cases

Implement remaining identity findings in “A.2 third ship round: deferred findings” (4), (8), (9), after 02 lands.

Own registry binding/merge logic, roster source-identity construction in `persist_dip_pulse_store.py`/`build_dip_pulse_site.py`, and focused tests. Roster key type normalization belongs to 04.

1. Corrected vote-member profile: reproduce an existing occurrence whose profile URL changes. Keep its record/person continuity when this is enrichment, while a changed official ID still moves the occurrence. Require equivalent current grouping for incremental and fresh replay; explain any intentionally retained historical rows.
2. Missing roster IDs: reproduce two distinct DIP roster rows with no ID. Determine whether other trustworthy evidence permits distinct identities; otherwise reject/skip with a clear diagnostic rather than collapse unknown persons. Missing roster IDs must not fabricate one shared occurrence. Pin behavior with fixtures.
3. `aw_match`: test successive occurrences where an earlier trusted match is absent or contradicted later. Define deterministic aggregation of trust from actual source evidence; distinguish supported record-wide trust from accidental inheritance. Align with 01's aggregation rule.
4. Conflicting guess groups: reproduce one contradicting pair suppressing all otherwise valid guesses. Select a conservative, order-independent rule; merge a safe subset only when its uniqueness is supportable. Preserve the whole-person rule and reviewed/hard-ID merges. If the safe outcome is to keep the group split, document and test that decision instead of guessing.
5. Overlapping reviewed merges with the same survivor: reorder corrections and require the same resolved aliases/persons, or reject ambiguous correction graphs with one deterministic diagnostic before replacement.

Done when each case has a focused regression or documented conservative policy, aliases remain acyclic, and both fixed-point and incremental/fresh invariants pass.
