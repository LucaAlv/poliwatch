# Clean up empty week comparisons

Status: implemented and validated, 2026-10-26.
Backlog: `TODOS.md`, completed “Week comparison with no basis still draws every n/a slot”.

Keep the current week's totals and fraction shares when no eligible comparison
week exists. Remove the repeated `n/a` metric footers and fraction delta chips,
and collapse the unused fraction delta column. The existing heading and note
already explain why comparison values are unavailable.

The scope is the `comparison is None` state: a single recorded sitting week,
an explicitly selected earliest week, or a prior week outside `MAX_WEEK_GAP`.
An existing comparison whose `basis` is `None` because no sitting weekdays
overlap keeps its per-row `n/a`, as the TODO explicitly requires. A zero prior
value also keeps its unavailable percentage delta. Selection, aggregation,
completeness rules, counts, share calculations and the 12-week limit stay as
they are.

## Implementation

1. **Remove unavailable comparison markup only in the missing-week state.**
   In `scripts/build_dip_pulse_site.py`, remove the `.week-metric-foot` element
   from the missing-comparison branch of `render_week_comparison_section()`.
   Keep each metric's label and current value, the incomplete-text exclusion,
   the fraction shares and completeness note, and the optional votes card.
   Continue omitting the sparkline and comparison-only cards in this branch.

   In `scripts/render_dip_pulse_html.py`, add a keyword-only
   `show_deltas: bool = True` parameter to `render_share_shift()`. When false,
   omit the delta span and add a `week-list-current-only` class to the list.
   Pass `show_deltas=False` only from the missing-comparison branch. Leave the
   comparison branch and `render_delta(None)` unchanged, including comparisons
   with no shared weekdays or zero assigned speeches in the prior week. This
   avoids changing the meaning of the existing `previous=None` argument, which
   the no-shared-weekday branch also uses.

2. **Collapse the reserved column at every existing breakpoint.**
   In the weekly page's CSS in `scripts/build_dip_pulse_site.py`, scope the
   three-column row layout to `.week-list-current-only .week-row`: fraction
   label, bar, percentage. Match the existing label/bar proportions on desktop
   and below 700px. At 460px and below, use two columns for label and percentage,
   retaining the existing full-width bar on the following row. Account for
   selector specificity so the narrow-screen override wins. Other lists and
   comparison layouts retain their existing grids. Omitting metric footers
   removes their margin naturally; no metric-height override is needed.

3. **Update focused regression coverage and documentation.**
   In `tests/test_build_dip_pulse_site.py`, update
   `WeekRadarPageTests.test_no_comparison_state_renders_the_current_week_without_deltas`
   to assert no delta spans or metric footers within the comparison section,
   while retaining its current assertions for missing text, fraction coverage,
   share rows and absent sparkline. Assert current counts and percentages too,
   so hiding the entire card cannot satisfy the test.

   Reuse the existing complete-text single-week fixture in
   `SittingWeekComparisonTests.test_single_week_has_no_comparison` to check
   current-only markup with all three metric values. Extend
   `test_gap_guard_suppresses_an_unrelated_week` with the same absence checks.
   Add one compact helper regression for `render_share_shift()` using the
   same counters with the default argument and `show_deltas=False`: identical
   labels, widths and percentages; only the latter omits delta spans and adds
   the layout class. Include an empty-current case to preserve the existing
   readable empty state.

   Retain the existing `n/a` assertions in
   `SittingWeekComparisonTests.test_running_week_shows_no_delta_without_shared_weekday`
   and
   `test_no_shared_weekday_keeps_complete_current_text_without_incomplete_previous_text`.
   Keep the matched-weekday and equal-sitting-count delta tests passing. Check
   an eligible comparison with a zero prior metric or no assigned prior
   fraction speeches still renders its unavailable delta; reuse an existing
   fixture or add a small case if needed.

   On implementation, amend the no-comparison paragraph in
   `docs/designs/puls-wochenradar.md` (around line 242), which explicitly
   prescribes `n/a` today. Record the change in `CHANGELOG.md` and mark only
   the matching TODO completed after validation, linking this plan. No new
   fixture files, configuration, dependencies, exports or data migration are
   required.

## Validation and acceptance

After implementation, run from the repository root:

```sh
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p test_build_dip_pulse_site.py
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests
```

Render the existing synthetic test fixtures to a temporary directory for a
single week, a gap beyond 12 weeks, an ordinary comparison and a comparison
with no shared weekdays. Inspect at 1440px, 700px and 375px using Chrome DevTools
MCP, discovered before selecting a driver per the repository instructions.
If unavailable, state that and use an available browser driver. Verify current
values remain readable, no empty delta track or footer spacing remains in the
missing-week states, the mobile bars span their row, and real comparisons
retain their chips. Check print rendering for the current-only fraction rows.
Browser inspection is needed because source assertions alone cannot establish
that the responsive grid has collapsed.

Done means missing-week panels show their existing explanation and current
values with no repeated unavailable-delta markers, while partial and ordinary
comparisons retain their current behavior. Preserve `#wochenvergleich`, the
heading association and all receipt links.

## Planning evidence and limits

Inspected the TODO, both share-renderer callers, the delta helper and its
callers, week selection and comparison construction, responsive grid rules,
the relevant unittest classes, design instructions, contribution instructions
and CI. A read-only subagent checked test and layout scope; its findings were
checked against the source, including the actual test class names.

This task changes presentation only. The main regression risk is accidentally
treating every missing numeric delta as a missing comparison week; the explicit
rendering option and retained partial-week assertions guard that boundary.

No implementation, test execution, browser inspection, release bump or
publication was performed during planning. No live data or external library
documentation was needed.

## Implementation receipt, 2026-10-26

Missing-week panels now omit metric footers and call `render_share_shift()` with
`show_deltas=False`. Its current-only list uses three columns on desktop and at
700px, then two columns with a full-width bar on the next row at 375px. Existing
comparisons retain the default delta rendering, including unavailable values.
The design paragraph, changelog and matching TODO are updated.

Validation:

- Focused Python 3.13 suite: 219 tests passed.
- Full Python 3.13 suite: 1,523 tests ran, two skipped, all others passed.
- Script compilation and `git diff --check` passed.
- Chrome DevTools inspected synthetic single-week, gap-guarded, ordinary and
  no-shared-weekday pages at 1440px, 700px and 375px. Missing-week panels retain
  totals and shares with no delta track or footer; mobile bars span their row.
  Ordinary chips and all five no-shared-weekday `n/a` markers remain. No horizontal
  overflow was found. An explicitly selected earliest week also passed a render
  check for current values and absent delta markup.
- A headless Chrome print to PDF was visually checked on both pages: current-only
  fraction labels, bars and percentages remain readable with no reserved delta
  column.

No live data, dependencies, configuration, exports or stored data changed. No
release bump or publication was performed.

### Ship verification

The ship coverage audit identified the responsive grid as a manual-only check.
The user requested automated layout tests. The existing browser runner now
generates current-only and ordinary comparison fixtures and checks actual grid
columns at 1440px, 700px and 375px, full-width mobile bars, viewport overflow,
exact current values and shares, absent metric footers, and retained ordinary
comparison delta chips. The check lives in
`tests/week_comparison_browser_check.js` and runs with
`node tests/run_bills_browser_check.mjs python3.13` in the existing CI lane.
