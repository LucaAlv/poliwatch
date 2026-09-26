## Project stage: pre-release

Nothing is published. No reader, citation, or downstream user depends on any current figure, ranking, URL, export format, or schema. Judge every decision on accuracy and quality alone: a change that shifts figures, renames fields, or reworks a whole feature costs only the work itself. Change things in place and drop the old shape rather than carrying compatibility shims or migration paths. When a fix moves a number, report the old and new values and why the new one is more correct.

## Skill routing

Route by request type:
- Product ideas/brainstorming → /gstack-office-hours
- Strategy/scope → /gstack-plan-ceo-review
- Architecture → /gstack-plan-eng-review
- New design system → /gstack-design-consultation; review a design plan → /gstack-plan-design-review
- Full review pipeline → /gstack-autoplan
- Bugs/errors → diagnosing-bugs
- QA/testing site behavior → /gstack-qa (fixes) or /gstack-qa-only (report)
- Diff review before landing → code-review; pre-PR ship review → /gstack-review
- Visual polish → /gstack-design-review
- Ship/deploy/PR → /gstack-ship or /gstack-land-and-deploy
- Backlog-ready spec/issue → /gstack-spec

## Agent skills

### Issue tracker

GitHub Issues (LucaAlv/poliwatch) hold specced work; TODOS.md holds gstack's small/deferred items. Before opening an issue, grep TODOS.md and promote the match (`→ #NN`) instead of duplicating. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
