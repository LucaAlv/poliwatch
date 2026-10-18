# Close remaining A.2 regression gaps

Run after 01–05. Own tests/fixtures; production edits are limited to defects actually exposed and necessary to make the tested contract correct.

Read “A.2 test follow-ups”, third-round findings (12), registry follow-ups (3), and `docs/a2-validation.md`. Inventory existing tests first: reorder allocation, vote-only eligibility, combined IDs, and stale roster behavior already have partial coverage.

Cover remaining distinct contracts:

- Online `main()` roster wiring when `mp-roster` is absent from the selection; reconcile with current fixed publication selection and test the reachable production contract.
- Rebuild forwarding `built`, `full_build=True`, `today` and facts results; offline facts handoff and no redundant computation.
- Historical page eligibility with no current `mps` row, former roster disappearance, vote-only history and redirect policy.
- `p-NNNNNN` allocation under input permutations, digest order independence, and table-driven occurrence keys for votes, sampled people and preserved roster.
- `_inputs_hash`, `compare_store_values._zusammenfuehrung` values/totals, exact manifest `stable_keys`, and export snapshot/swap guards.
- Live-only partition evidence in `_guess_merges`; all registry tables missing in offline CLI; `--repersist` rebuild failure diagnostic.
- Stale `-journal`/`-wal`/`-shm` sidecar cleanup and paths requiring `glob.escape`; `mps` FK violations and final rebuild integrity/FK checks retaining the original store.

For each, write the expected user/data behavior and a meaningful regression. Tests should fail when the guarded production handoff/check is removed, not merely assert implementation details. Use narrow mutation checks where inexpensive; avoid duplicate tests for a contract already pinned. Keep online tests network-free with deterministic doubles.

Done when each recorded gap is mapped to an existing/new test or a documented unreachable/retired contract. Update TODO subitems precisely and report full-suite results without claiming a live reference replay was performed unless it was.
