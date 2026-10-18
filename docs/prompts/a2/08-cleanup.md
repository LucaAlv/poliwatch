# Remaining mechanical A.2 cleanup

Run after 07. Own narrow mechanical simplifications from “A.2 review leftovers”, third-round (5), (6), registry follow-ups (4), and second-round (3) only where they are not subsumed by larger architecture tasks.

1. Inventory production callers before removing `reconcile(full_build=False)`, `vacated`, `_load_rows`'s bound set or making `occurrence` mandatory. Keep a mode/state only if a current production contract needs it; adjust tests to exercise supported production paths. Coordinate liveness with 01–03.
2. Replace the `facts_report` empty-dict/out-parameter ambiguity with an explicit computed-result contract. Empty facts results still mean computed, not recompute. Pin once-per-rebuild behavior and the offline handoff.
3. Consolidate repeated `built` selection and retire the single-report refusal CLI only if no documented entry point needs its helpful diagnostic. Simplify correction loading/cache only if it improves deterministic reload behavior.
4. Replace facts goldens tied to SHA-ordered IDs with assertions derived from source/expected domain outcomes, preserving real tie-break coverage.
5. Leave identity helper consolidation, canonical-map redesign, registry writes into `mps`, `collect_abgeordnete` extraction and `after_persist` removal to the existing “One Persons module”, store ownership and feature-selection tasks. Reference those owning TODOs instead of starting another broad refactor.

Done when supported behavior is unchanged, dead branches are verified against production callers, scoped tests pass, and the integration full suite is green. Record which cleanup subitems were subsumed or remain deferred; do not close a whole TODO heading for partial work.
