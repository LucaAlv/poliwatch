# B4 vote lead and Bundestag report link validation

2026-10-25 UTC. Implementation on `b4-vote-lead-and-article`, based on `7b62d98` (step 1). Scope: [the implementation plan](../plans/b4-vote-lead-and-article.md).

## Source verification

Live Bundestag pages were checked for votes 906, 1005 and 994. Fixtures retain only the tab/panel/video association tags and retrieval metadata (`tests/fixtures/vote_debate_*`); no editorial body is retained. The ID route `/dokumente/textarchiv/992936` redirects to the canonical Taurus report, and `/dokumente/textarchiv/1181880` to the shared family/education report. A real click from the rendered 906 panel reaches the former. Loading vote 1005 with `#debatte` leaves that panel hidden, so the implementation does not use that fragment as a fallback.

The current live-page check of all 217 reference vote IDs found **215 associated reports, 2 missing (784, 994), 0 ambiguous, 0 fetch failures**. Repeated article IDs are accepted; conflicting IDs, unsafe URLs, unrelated widgets and missing associations are covered by fixture tests. The report is supplementary context and never result evidence.

## Reference comparison

The original `~/agent-runs/b3-review-replay/site` was left untouched. A disposable `/tmp/b4-reference` copy contains 290 sitting reports and 217 unique votes. Its old reports lack the step-1 interpretation fields, so the comparison baseline interprets their votes using only the cached XML recommendation evidence and the existing shared interpreter. Adding the freshly acquired URLs leaves **all 217 interpretations and final totals identical** to that corrected baseline.

The rebuilt schema-7 store holds 217 votes and 215 report links. All **246 vote panels have a lead**; 244 have a report link (the two missing-article votes each appear once). Duplicates keep their existing single anchors. Export format 8 builds successfully.

All 217 votes agree across report JSON, the build store, downloadable SQLite and CSV for the URL, date, title, description, all four counts and interpretation/provenance fields. No source text or count changed during the URL refresh.

A second complete store rebuild from those prepared reports is stable: `replaced=False`; the existing database is left untouched.

The corpus check uses current-version cached speech snapshots and the existing store rebuild, dossier renderer and export functions. Full historical speech re-parsing was stopped in the existing `speech_segments` regex path; it is unrelated to this feature. The fixture integration does run the complete `--offline --repersist` path, including a second stable replay, nullable links, sparse/conflicting duplicates, fresh absence and the official application-scoped rejection for 996.

## Browser and automated checks

Chrome DevTools inspected real cached reports at 1440 px desktop and 390 px mobile widths, in light/dark themes. Cases: 906, 996, 1005, direct Gesetzentwurf 810, unknown outcome and missing committee 938, missing article 784. Leads, committee citations, result badges and raw Ja/Nein/Enthaltungen counts agree; no horizontal overflow or render-time XHR/fetch requests appeared. The old corpus still labels 996 as derived because it has never cached its official result; the integration fixture verifies that a freshly recorded application-scoped official rejection is not inverted again.

- Complete Python 3.13 unittest suite: **1,548 tests, one skipped, passed**. Focused rendering checks also passed after the final source-label wording adjustment.
- Script and feature-module compilation passed.
- `node tests/run_bills_browser_check.mjs /opt/miniconda3/bin/python3.13`: desktop/mobile, keyboard activation and recipe copy checks passed. One earlier run passed its assertions but hit a temporary-profile cleanup race; the rerun exited successfully.
- Zero-network demo build and publication validation passed; the development-marked demo was correctly rejected. Capability/configuration commands passed.
- `git diff --check` passed.
