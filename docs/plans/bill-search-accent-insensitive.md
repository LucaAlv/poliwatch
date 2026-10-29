# Make bill search accent-insensitive

Status: implemented, 2026-10-27.

## Scope and evidence

Implement the search portion of “Bill overview polish: same-day step ties,
diacritic-insensitive search” in `TODOS.md`. Both explicit examples are required:
`fur` finds `für`, and `strasse` finds `Straße`.

`render_bills_index()` in `scripts/build_dip_pulse_site.py` builds `data-search`
from the title and every associated document number, previously NFC-normalized
and lowercased. `render_bill_script()` normalizes the query the same way, splits
it into whitespace-separated terms, and requires every term to match. Its
`apply()` path serves typing, initial URL state, and history restoration.

The production caller is `write_bill_pages()`; unit tests and the browser fixture
writer also call the renderer directly. No caller signature changes are needed.
The existing `_title_sort_key()` has related folding logic but also owns numeric
title ordering; leave it intact rather than coupling search to sorting.

## Matching contract

Apply the same operations to metadata and the query: lowercase, replace `ß`
with `ss`, canonically decompose with NFD, then remove Unicode marks (general
category `M`). Lowercasing first also handles capital `ẞ`. Use Python's existing
`unicodedata` import and native JavaScript; add no dependency or search framework.

Use `unicodedata.category(ch).startswith("M")` for Python mark detection and
`/\p{M}/gu` in JavaScript. Avoid using Python `casefold()` with JavaScript
lowercasing: full case folding changes additional characters that the query
side would not change. Keep the transformations local to the two existing
normalization sites.

| Query | Stored title or metadata | Expected |
| --- | --- | --- |
| `anderung`, `ÄNDERUNG`, decomposed `A\u0308nderung` | composed or decomposed `Änderung` | Same two fixture rows |
| `fur`, `für`, `FU\u0308R` | `für` | Same matching rows |
| `strasse`, `straße`, `STRAẞE` | `Straße` | Same matching rows |
| `cafe`, `café`, `cafe\u0301` | `Café` | Same matching rows |
| `Gésetz 04` | `Gesetz 04` | Match: accented queries also find plain text |
| `fur strasse` | A title containing both words | AND matching retained |
| `21/9876` | A secondary document number | Existing exact punctuation retained |

Escapes in this table denote actual Unicode characters in tests. Folding affects
matching only. Keep original visible titles, `data-title`, document numbers,
the input value, URL `q`, and the displayed search criteria. Retain current
trimming, filters, ordering, pagination, focus, reset, and failure behavior.

This deliberately broadens matches: `fur` and `für`, or `Masse` and `Maße`, can
no longer be distinguished by this search. German `ae/oe/ue` transliteration,
fuzzy matching, and general transliteration such as `ø` to `o` are out of scope.

## Implementation

1. In `scripts/build_dip_pulse_site.py`, replace the metadata and query
   normalization with the matching contract above. Preserve HTML escaping and
   the original query state. Replace the obsolete NFC-only script comment.
2. In `tests/test_bills.py`, replace `test_search_metadata_is_nfc` with assertions
   for folded metadata, including composed/decomposed umlauts, other accents,
   `ß`/`ẞ`, and associated document numbers. Also assert that visible titles and
   `data-title` retain their source spelling. Extend existing fixtures without
   changing the 41-row count, special document numbers, year distribution, or
   the two `Änderung` rows used for sorting assertions.
3. In `tests/bills_browser_check.js`, exercise the acceptance cases against
   generated HTML and assert result IDs, rather than checking script text.
   Include accented queries against plain metadata and plain queries against
   accented metadata. Assert that an accented query keeps its original spelling
   in the field, URL and criteria; exercise initial URL state and Back/Forward
   restoration with folded matches using the existing browser harness. Preserve
   its desktop/mobile runs and existing filter, pagination, focus and reset checks.
   Change `tests/run_bills_browser_check.mjs` only if needed to load an overview
   with an initial `q`; reuse its current browser and fixture generation.
4. After verification, split the completed search work from the bundled TODO,
   link this plan, and leave the same-day step-ranking requirement open. Update
   the search rule in `docs/designs/gesetzesvorhaben.md` to include accent/ß
   folding. Record implementation results here.

No schema, exports, acquisition, configuration, bill detail pages, other search
surfaces, or generated artifacts need changes. Rebuild the static site to make
the updated metadata and script available together.

## Validation and completion

From the repository root:

```sh
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests -p test_bills.py
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests
node tests/run_bills_browser_check.mjs /opt/miniconda3/bin/python3.13
git diff --check
```

The browser runner requires Node 22+ and Chrome/Chromium, as documented in
`CONTRIBUTING.md`. Existing CI covers Python 3.11–3.13 and browser checks on its
Python 3.13 lane. No additional test runner is needed.

Done when both normalization sites implement the contract, the acceptance cases
pass through real generated-page interactions, original spelling survives URL
and history round trips, and the existing validation remains green.

Planning evidence: source and caller inspection, existing tests, TODO and design
contract, plus Context7 documentation for [Python Unicode normalization and
categories](https://docs.python.org/3/library/unicodedata.html),
[JavaScript normalization](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/normalize),
and [Unicode property escapes](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Unicode_character_class_escape).
Planning baseline: all 29 existing bill unit tests passed on Python 3.13.
The full suite and browser checks were not run for the planning-only change.

## Implementation results

Completed 2026-10-27. Metadata and queries now lowercase, replace ß with ss,
decompose with NFD and remove all Unicode marks at the two existing sites.
Visible titles, `data-title`, document numbers and query state retain their
original spelling. No dependencies or caller signatures changed.

The 41-row fixture retains its document numbers, years and two equivalent
Änderung titles; another title now covers für, Straße, Café and capital ẞ.
Unit assertions check folded metadata and original title spelling. Browser
checks assert result IDs for the acceptance matrix on desktop and mobile.
An initial decomposed `FU\u0308R` query and a typed `café` query retain their
spelling in the field, URL and criteria through Back and Forward restoration.

Verification passed:

- Bill unit tests: 29 passed on Python 3.13.
- Full unit suite: 1,554 tests, OK with two skips.
- Existing browser runner: all scenarios passed, including desktop/mobile
  accent matching and initial URL/history checks (Node 24, Chrome).
- Script compilation and `git diff --check` passed.
- Zero-network static demo rebuilt at `/tmp/quick-todos-accent-demo` and passed
  publication validation. This checkout has no cached `.context/dip-pulse-site`
  to rebuild; generated artifacts are outside the repository.

The design search rule and TODO now reflect completion. Same-day step ranking
remains open. Matching deliberately merges accents and ß/ss; ae/oe/ue, fuzzy
matching and general transliteration remain outside this change.
