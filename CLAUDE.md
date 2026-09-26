## Project stage: pre-release

Nothing is published. No reader, citation, or downstream user depends on any current figure, ranking, URL, export format, or schema. Judge every decision on accuracy and quality alone: a change that shifts figures, renames fields, or reworks a whole feature costs only the work itself. Change things in place and drop the old shape rather than carrying compatibility shims or migration paths. When a fix moves a number, report the old and new values and why the new one is more correct.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /gstack-office-hours
- Strategy/scope → invoke /gstack-plan-ceo-review
- Architecture → invoke /gstack-plan-eng-review
- Design system/plan review → invoke /gstack-design-consultation or /gstack-plan-design-review
- Full review pipeline → invoke /gstack-autoplan
- Bugs/errors → invoke /gstack-investigate
- QA/testing site behavior → invoke /gstack-qa or /gstack-qa-only
- Code review/diff check → invoke /gstack-review
- Visual polish → invoke /gstack-design-review
- Ship/deploy/PR → invoke /gstack-ship or /gstack-land-and-deploy
- Save progress → invoke /gstack-context-save
- Resume context → invoke /gstack-context-restore
- Author a backlog-ready spec/issue → invoke /gstack-spec

## Agent skills

### Issue tracker

GitHub Issues on LucaAlv/poliwatch for specced work; TODOS.md stays the gstack backlog for small/deferred items. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five labels (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
