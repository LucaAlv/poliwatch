# A.2 implementation handoffs

Prepared against `origin/main` at `4818b4c`. A.2's core is complete; these prompts cover its remaining follow-ups. Start each agent with: **Read `docs/prompts/a2/README.md`, then implement `docs/prompts/a2/<selected-file>.md`.** Paths are relative to the repository root.

## Execution order and ownership

| Prompt | Priority | Run after | Main ownership |
|---|---|---|---|
| [01 Deterministic evidence](01-deterministic-evidence.md) | P2 | — | Registry evidence and matching |
| [02 Partition removal](02-partition-removal.md) | P2 | 01 | Correction lifecycle |
| [03 Identity edge cases](03-identity-edge-cases.md) | P2 | 02 | Bindings, roster and merge edge cases |
| [04 Stable source keys](04-stable-source-keys.md) | P2 | 03 | Document and roster key contracts |
| [05 Robustness](05-robustness.md) | P2 | 03 | CLI errors, writer lifecycle and page writes |
| [06 Regression coverage](06-regression-coverage.md) | P2 | 01–05 | Remaining tests |
| [07 Performance](07-performance.md) | P3 | 06 | Recipes, digests and binding costs |
| [08 Cleanup](08-cleanup.md) | P4 | 07 | Remaining mechanical simplifications |

Use one branch/worktree per task, based on the integrated predecessor. 04 and 05 can run concurrently in separate worktrees after 03; they share persistence/build files, so review their merge together. Run the rest sequentially: they share registry code, fixtures and contracts. Shared-file edits in one worktree require explicit coordination. Agents are not alone in the codebase: preserve others' edits and adapt to integrated changes. Keep `TODOS.md` updates narrowly scoped to the completed subitems.

## Instructions for every agent

1. Read repository instructions, `CLAUDE.md`, `CONTEXT.md`, `docs/stable-ids.md`, and your task's referenced TODO headings. Re-check current source before treating a recorded finding as open. Use Graphify only when installed and its graph exists; otherwise search source.
2. Reproduce each behavior issue with a focused regression before changing it. Use Python 3.11+ (`python3.13` exists in the authoring environment; default `python3` was 3.9). Use synthetic fixtures and scratch stores. The real store/cache remains read-only.
3. Implement within the assigned responsibility. Follow local skill routing for diagnosis and architecture decisions. Use Sol for identity/design decisions, Luna for bounded mechanical work. Delegate only when the verification cost justifies it.
4. Keep source evidence intact, hard-ID conflicts and partition boundaries conservative, issued keys durable where their contract promises continuity, and aliases resolvable. Test incremental versus fresh grouping separately from issued-key continuity: a fresh registry need not recreate historical allocation ordinals.
5. Preserve staged atomic store replacement, writer locking, foreign-key/integrity validation, unchanged-replay reuse and persisted assignments used by facts/exports/pages. For schema/key changes, implement the explicit replay path and update the contract. The project is pre-release: prefer one correct shape over compatibility scaffolding, while honoring deliberate registry continuity.
6. Run affected tests, the three focused A.2 suites, and `git diff --check`. The integration owner runs the full suite once after the correctness/test wave and once after the optimization/cleanup wave. Broaden testing sooner if cross-cutting changes require it. If a reference cache is available, replay a scratch copy and report changed grouping/counts with reasons; otherwise state that limitation.
7. Update the exact TODO subitems and relevant contract docs. Mark already-fixed or accepted behavior accurately. Commit/push/PR only when requested by the session's user.

Deliver: changed files, decisions, reproductions and passing commands, changed figures/keys if any, and explicitly deferred subitems. Completion requires every item in the selected prompt to be implemented, verified as already fixed, or explained as a documented decision with evidence.

## Known exclusions

- Combined Redner-ID corrections already use `derive.first_redner_id`; retain the regression.
- Export now derives the person mapping from its distribution snapshot and checks for a store swap during copying; verify existing coverage rather than reimplementing the old two-connection mapping fix.
- Stale-roster partner matching and render-on-copy behavior are implemented.
- A corrected occurrence's old person URL losing its page without a redirect is an accepted policy; preserve it.
- Reviewed assignments/splits remain disabled until a real correction requires them. Their redesign is outside these handoffs.
- The larger “One Persons module”, store ownership, feature-selection removal and dataset/site split are separate roadmap tasks. 08 should leave their subsumed cleanups with those tasks.
