# Render layer and Stage 2 order: A4 slices 2 to 11 against the DESIGN.md rollout

Status: **draft, 2026-11-10. Owner decisions L1 to L6 are open.** Planning only: no renderer code changes here.

Frame: `/gstack-plan-eng-review` on the architecture brief in `docs/plans/v1-scope-review.md` ("What this means for the design and architecture sessions", "Architecture session"). That ledger (Q2, Q3, Q7) wins over older plans. Owner decisions go to the owner in chat, not through AskUserQuestion, because a global hook can auto-answer gstack briefs.

Decisions are numbered **L1 to L6**, to stay apart from Q1 to Q17 and N1 to N10 (scope review), D1 to D10 and R1 to R18 (A4 plan) and roadmap C1.

Settled, not reopened:
- the static site generator no-go (`docs/plans/frontend-go-no-go.md`);
- Q2: slices 2 to 11 before the public site, none for the data release;
- Q3: main and stable releases, and the site reads the latest main release;
- Q7: both raw dumps dropped;
- D8 to D10 as decided;
- R1 to R9 of the A4 plan;
- DESIGN.md v0.34.1.0.

Stage 1, the data release, comes first and needs nothing in this plan.

## Evidence

Measured on `main` at ed6847c (v0.36.0.0), 2026-11-10, unless a row says otherwise. Code figures come from an AST script, a heuristic: it counts string literals inside `<style>` or `<script>` and multi-line strings that read as CSS or JS. The brief's figures were pre-A3 census numbers, and this table replaces them.

| # | Fact | Value | Source |
| --- | --- | --- | --- |
| M1 | `scripts/build_dip_pulse_site.py` | 14,950 lines, 294 top-level functions. 54 of those contain markup, 4,413 lines in all | measured |
| M2 | `scripts/render_dip_pulse_html.py` | 4,327 lines. 31 functions contain markup, 2,149 lines in all | measured |
| M3 | CSS in Python strings | 1,685 lines in B, 1,237 in R, 2,926 in all. Each of the 21 pages carries its own `<style>` block | measured, heuristic |
| M4 | JS in Python strings | 551 lines in B, 308 in R, 39 in `sitzungskalender.py`, about 900 in all | measured, heuristic |
| M5 | Page writers (`<!doctype html>`) | 21: 20 in B, 1 in R (`render_html`, the dossier, 1,248 lines, 923 of them CSS) | measured |
| M6 | `esc()` calls | 597: 412 in B, 122 in R, 56 in `features/votes.py`, 7 in `week_radar_feed.py` | measured |
| M7 | Page shell | `page_head` (R:1199) returns only the theme bootstrap script. Every page writes its own `<head>`, header call, footer and scripts | static read |
| M8 | Class names shared by DESIGN.md's inventory and today's CSS | `.site-nav` (11 rules), `.panel` (10), `.field` (3), `.filters` (2), `.primary`, `.vote-lead`. Both stylesheets also style bare elements (`body`, `h1`, `a`, `table`) | measured |
| M9 | Tests | 2,208 test functions | measured |
| M10 | Tests with HTML-shaped strings | 448 in all. 114 are in parser test files, where the HTML or XML is input. That leaves 351, of which 156 pin a `class=` attribute. A hand check of 20 of the 351 found 4 that assert no rendered HTML (XML input, a message string), so **about 280 assert on rendered HTML** [estimated] | measured, heuristic |
| M11 | Tests on CSS text | 42 by the heuristic. A few false hits (codebook, compare script), so **about 35** [estimated]. The brief said about 36 | measured, heuristic |
| M12 | Browser checks | 6 scripts under `tests/` (votes archive, bills, radar, week comparison, next sitting, recipe copy) | static read |
| M13 | Open PRs | none. No unmerged branch changes the two build files beyond squash-merge residue | `gh pr list`, `git diff main...<branch>` |
| M14 | Inline `<style>` in the built site | 96 MB of 1,397 MB in 6,750 files | **A3 build, 2026-10-28** (scope review E8), not re-measured |
| M15 | The release manifest reaches the build | `--data-manifest <datenstand.json>` (B:4907, B:13385) | static read |

Computation still on the render paths: inventory by a read-only subagent, 2026-11-10. It is summarised under L4 below.

## L1. Order: A4 slices 2 to 11 against the redesign

The rule to keep: **never restyle and port a page in one PR**, so the strict HTML diff oracle (A4 D1, D3) stays usable for every port.

Why the A4 plan puts slice 11 after slice 10: the plan gives no reason in its slice map. TODOS ("Split the dataset from the site") says the file split "follows from" moving data into the store, and the export note there says that moving code before rewriting it "would only relocate the code". Neither argument is a data dependency. A move-only change does not care whether a renderer still reads `entries`.

Options:
- **A. As planned.** Slices 2 to 10 in order, then the whole restyle, then slice 11. Every restyle PR works inside the 15k-line file, which is the iteration pain `frontend-go-no-go.md` "Limits" names. Each page is touched three times: port, restyle, move.
- **B (recommended). Per page group, three PRs in a fixed order.**
  1. Move-only: the page's renderer, styles and script leave B and R for a module of their own. Check: the full-site diff is empty.
  2. Port, the A4 slice: strict oracle.
  3. Restyle on the shared layer (L2): content oracle and browser check (L5).

  Slice 11 dissolves into the move-only steps. One closing PR moves what is left (CLI, acquisition) and deletes the old shell and inline CSS. Pages that already read the store skip step 2.
- **C. Whole-file split first, one PR.** Move all renderers out now, checked by an empty site diff. It is possible, because no PR is open (M13). But Stage 1 is still changing B (N1 withholding, ADR 0004, the registry), so a 15k-line move conflicts with every branch in flight. It also moves code that slices 2 to 9 then delete (`entries` readers, inline CSS).
- **D. Restyle first, then port.** Q2 rejected this shape: every renderer would be redesigned and then moved.

**The order under B.** Each line is one page group. Moves and ports follow the A4 slice dependencies.

| Step | Page group | PRs | Why here |
| --- | --- | --- | --- |
| 0 | Surface cuts | one | Delete `api-sitzungen.html`, `settings.html` and the Fakt der Woche pages, their nav entries, and the 333 KB sitting list on `sources.html` (Q5, Q7; TODO "Apply the v1 surface list", page half). This removes `render_catalog_page` (361 lines), `render_settings_page` and the three Fakt renderers before anyone ports or restyles them, and takes the catalog page out of slice 2. Oracle: the cut pages are gone, and on every other page only the nav and the removed links differ, recorded |
| 1 | Shared layer | one | L2. No existing page changes. Oracle: full-site diff empty apart from new files under `assets/` and the dev view |
| 2 | **Pilot:** `votes/index.html` | move, restyle | Already on the store (slice 1), so no port follows the restyle. L3 |
| 3 | Abgeordnete (index, detail) | move, restyle | Already on the store |
| 4 | Static pages: `bundestag.html`, Impressum, Datenschutz | restyle | No figures. They exercise the shell at depth 0 |
| 5 | Sitzungen (`overview.html`) | move, slice 2, restyle | Slice 2 is small after step 0 |
| 6 | Dossiers | move, slices 3, 4, 5, restyle | The speech component needs the paragraphs slice 5 persists (DESIGN.md Speech). The largest renderer |
| 6a | New per-vote pages | new | DESIGN.md has a vote's page (verdict, wall, Zitieren line) that does not exist today. A new page is built on the layer from the store, with no oracle, once slice 4's store additions land. The dossier panel and the vote lead then link to it |
| 7 | Aktuell (`puls.html`) | move, slice 6, restyle | Return mode and the vote lead |
| 8 | Gesetzesvorhaben | move, slice 7, restyle | D10's dump goes in slice 7 |
| 9 | Quellen und Methode | move, slice 8, restyle | |
| 10 | Daten | slice 9 (the export module), restyle | Release blocks and the CSV control |
| 11 | Release-only build | slice 10 | The proof. It compares two builds of the new layer |
| 12 | Home, two doors | restyle | The Analysen door needs the first analysis (roadmap Stage 2 item 3). Analysen pages are new and built on the layer |
| 13 | Close | one | Rest of slice 11: CLI and acquisition leave B, and the old shell, `global_header_styles` and the last inline CSS go |

The reader test (Q16) comes after step 13.

**Stage 1 overlap.** Steps 0 to 4 touch little that Stage 1 touches, so they may run while Stage 1 finishes. Steps 5 onward move code Stage 1 is still changing, so they wait for Stage 1's correctness items in B to merge.

**Recommendation: B.** It keeps every port on the strict oracle. It gives every restyle a small module to change instead of the 15k-line file. It brings slice 11's benefit forward without a 15k-line conflict, and touches each page a fixed three times, in an order that never moves code twice.

**Answer:** open.

## L2. The shared layer, built before the first restyle

**Where it lives.** A package `scripts/site/`. Page modules go under `scripts/site/pages/`, created by the move-only steps.

| Part | What | Notes |
| --- | --- | --- |
| `site/markup.py` | `Html`, a `str` subclass for markup that is already safe. `esc()` returns `Html` and leaves `Html` alone. `h(template, **values)` is `str.format` that escapes every value that is not `Html`. Also `join()`, and `trusted()` for output of legacy helpers | Measured in L3: 59 lines. It makes escaping the default instead of 597 manual calls. Not named `html.py`, which would shadow the standard library |
| `site/shell.py` | `page(...)`: doctype, `lang="de"`, meta, title, the stylesheet link at the right depth, the theme bootstrap, skip link, header, the seven-link nav (Q6), the page head (back link, `heading-1`, Stand line, optional Zitieren line), footer with the provenance key and four links, the script tag | Replaces the 21 hand-written heads and `page_head`. The nav list lives once, with Analysen behind a flag until the first analysis exists |
| `site/components/*.py` | One small module per DESIGN.md inventory group: `votes` (strip, totals, wall, wall as text, verdict, vote lead), `provenance` (slip, source line, origin line, gap), `lists` (list rows, Sitzung row), `tables`, `controls` (control, field, filters), `releases` (release, CSV control, citation, changes), `charts` (small multiples drawn as SVG in Python, like arm A of the chart prototype) | Each takes plain values and returns `Html`. No store access and no arithmetic beyond formatting (L4). The vote wall is one function, with geometry in CSS variables only (DESIGN.md "Held Open") |
| `site/assets/site.css` | The one stylesheet: tokens from DESIGN.md's front matter, light and dark blocks in the two-selector form, the inventory classes | A real `.css` file in the repository, not a Python string |
| `site/assets/fonts/` | Five WOFF2 files and the OFL texts. D-DIN unmodified | DESIGN.md "Loading". Committed, no `package.json` |
| `site/assets/site.js` | Theme toggle, data age and overdue gap (DESIGN.md "Age and overdue"), filter chips, small enhancements | No figure computed in the browser except the age, which DESIGN.md asks for |
| Asset writer | Copies `assets/` to `<out>/assets/` with a content hash in each file name (`site.3f9a1c2e.css`). The shell links by relative path at every depth | Settles "Stale stylesheet" in the DESIGN TODO |
| Dev specimen page | `dev/komponenten.html` in the exempt dev view renders every component in its states, in light and dark | The browser checks and the owner's eye run against it. Exempt from slice 10's compare |

**Coexistence during the rollout.** A converted page links `site.<hash>.css` and carries no inline `<style>`. An unconverted page keeps its inline CSS and does not link the new file. **A page never loads both**, because the two stylesheets share class names and both style bare elements (M8). The old shell, `global_header_styles` and the per-page style functions are deleted page by page, the last of them in step 13. Two looks side by side are acceptable, because nothing is public before step 13.

**Stand line and Zitieren line.** Both need the page's release. The build already takes the release manifest (`--data-manifest`, M15).
- The shell's Stand line reads the release identifier and the newest Sitzung from it.
- A build without a manifest (local, tests) says "lokaler Build" in the release slot and still shows the newest Sitzung from the store.
- The Zitieren line needs what the release work does not yet supply: which Sitzungen stable holds, a per-record comparison against stable, and a rebuild when a release is marked stable (TODO "Apply DESIGN.md to the site", Context). So the shell has the slot, and pages omit the line until "Main and stable releases" provides those three. It never prints "unverändert" without the comparison.
- Age and overdue come from script (DESIGN.md), which retires `STALE_AFTER_WEEKS`, "Woche läuft" and "Auswertung vom" (see L4, bucket 4).

**Pilot: `votes/index.html` (recommended).**
- It already reads the store, so a restyle is never followed by a port.
- At 89 lines plus the helpers in `features/votes.py` it is small.
- It uses most of the shell and several core components: list row, strip, Fraktion filter, Politikfeld filter, Stand line.
- It has a browser check that keys on `data-*` attributes, not classes.
- The DESIGN TODO already says "Votes pages first".

Alternatives: the Abgeordnete index, also on the store, which tests tables but is less central; or Impressum, which tests only the shell.

**Pilot gate**, recorded before step 3:
- changed lines;
- page bytes before and after;
- render time on the reference store (checklist class 12);
- content oracle (L5) clean apart from recorded copy changes;
- browser check at 375 px and dark;
- test churn, counted as tests ported, deleted and added.

If the kit proves awkward on a real page, L3 is reopened before page two, not after ten.

**Answer:** open.

## L3. Templating: stdlib helpers or Jinja2

Measured on one real page. `render_votes_archive_index` (B:5992-6080) was ported twice in a scratch directory, both versions fed by the fixture rows of `tests/votes_archive_browser_fixture.py`:
- **Arm A** uses the stdlib kit from L2.
- **Arm B** uses Jinja2 3.1.6 with autoescape. It pulls in MarkupSafe 3.0.4, so two packages.

Both call the same legacy helpers (badge, document links, Politikfeld tags, header), so the comparison is about the page, not the helpers.

A change task followed in both arms: the row becomes DESIGN.md's `.vrow` with a strip and counts. Both arms produced identical output for it.

Throwaway, not committed. context7 is not authenticated in this session, so the CLAUDE.md rule to read the library's current docs could not be met. Jinja's API was checked against the installed 3.1.6 instead.

| | Today, f-strings | A, stdlib kit | B, Jinja2 |
| --- | --- | --- | --- |
| Output equal to today's page | | **byte-identical** | **not byte-identical**: MarkupSafe writes `&#34;` and `&#39;` where `html.escape` writes `&quot;` and `&#x27;`. Identical after normalising those two |
| Page code, non-blank characters | 4,390 | 4,141 | 4,441 (Python plus template) |
| Shared code | | 59 lines (`kit.py`) | 17-line base template, plus 14,425 lines of dependency |
| Explicit escapes in the page | 17 `esc()` | 0. 10 `trusted()` opt-outs for legacy helpers | 0. 9 `Markup()` opt-outs |
| Change task, changed characters | | 519 | 506 |
| Render, 620 rows, median of 15 | 15.7 ms | 36.0 ms | 27.2 ms |
| Dependency | none | none | Jinja2 532 KB and MarkupSafe 44 KB, BSD-3-Clause. MarkupSafe ships a platform C extension with a pure-Python fallback |

Reading:
- Both arms make escaping the default, which is Jinja's main argument against 597 manual calls. The kit's opt-outs disappear as the legacy helpers are converted to return `Html`.
- The change task costs the same (2.5 % apart).
- Jinja2 would break the byte-identical oracle on every move-only and port PR unless each one normalises entities.
- It needs a package install step, which is against `PRODUCT.md:58` "no package manager", and an exception the owner would have to name.
- What Jinja offers beyond this, template inheritance and files that non-programmers edit, does not apply to one operator and agents.
- The kit is slower than f-strings, at about 20 ms on 620 rows. If the pilot's whole-site render time moves noticeably, precompile the formats. That is not a reason to switch.

Options:
- **A (recommended).** The stdlib kit, no new dependency.
- **B.** Jinja2 and MarkupSafe as the first named exception to `PRODUCT.md:58`, vendored or pinned.
- **C.** Python 3.14 template strings (PEP 750), stdlib and autoescaping by design. This needs the floor raised from 3.11 to 3.14 and the CI matrix (3.11 to 3.13) dropped. Not now; worth a look when the floor next moves.

**Answer:** open.

## L4. Figures out of the renderers

Principle 6 and D9: renderers read only what is persisted. The votes archive, already on the store, still applies `merge_fractions`, `_fraction_position` and the Abweichler count at render time, and R5 accepted that. So "no computation in renderers" stated loosely has no end. The precise rule proposed:

> A page module or component may format a persisted value, and group, sort or filter persisted rows for display. Any figure it shows is either a persisted column, or the output of a named function in the derive layer (`scripts/derive.py`, or a new store-reading module beside it) whose inputs are release tables only, and which `DATA.md` or a release recipe documents so a reader can reproduce it. Renderers read no report JSON, cache or catalog file. Nothing depends on the build clock: age and overdue are computed in the browser from dates in the HTML.

The subagent inventory, sorted into buckets:

| Bucket | Where | What | Goes to |
| --- | --- | --- | --- |
| 1. Already persisted, only re-read | dossier: Reden per TOP (`item_stats` R:1378), characters, Drucksachen (`top_documents` R:2517), votes per sitting, Beiträge kinds, `verteildatum` | report JSON today | store queries in slices 3 to 5 |
| 1a. Cached counts that should be re-derived | dossier header TOPs and Reden from `validation_summary` (R:4276-4277), and overview cards likewise | the header Reden figure and the per-TOP sum come from different sources and may disagree | `COUNT` from the store in slice 5. **Report old and new values**: this can move a figure |
| 2. Rules on stored inputs | vote outcome, Abweichler count, Fraktion position, procedure type (`derive.vote_outcome`, `vote_abweichler_count`, B:5906, B:5889) | derived at render time, as R5 accepted | Keep as derive functions, called by a view function outside the renderer. Persist the outcome and the Abweichler count as columns where the release should carry them, since readers cite both and the Verdict and Vote lead read the outcome. Decided per figure in slice 4 |
| 3. Week aggregates | `puls.html`, the landing page and `week_radar_feed.py`: `week_stats` R:1495, `week_comparison` R:1644, `returning_vorgaenge` R:1742, radar ranking `week_topic_rows` R:2201, shares and sparklines | report JSON | One store-reading module, `weekly.py` in the derive layer, used by all three, with a release recipe for the week figures. **Slice 6 is not "probably none"**: DIP position order is not stored, and `proceeding_positions` overwrites `agenda_item_id` when two TOPs share a position (A4 census). Both are store additions |
| 4. Build clock | `week_header_facts` B:6634 (`STALE_AFTER_WEEKS`, "Woche läuft"), the landing page's "bisher erfasst", the next-sitting state | `resolve_today` B:6454 | Retired by DESIGN.md: dates in `<time>`, age and overdue in `site.js`. The next planned Sitzungswoche comes from the calendar at build time. A late release can then name a past week (DESIGN TODO item (g)): say so on the page |
| 5. Wrong-way imports | `facts.py:64` imports `agenda_topic`, `format_int`, `iso_week_key` and `speaker_party` from the renderer. `week_label` and `iso_week_key` are duplicated in `facts.py`. Persist and the renderer wrap the same party call twice | | Move into the derive layer in the move-only step that first touches them |
| 6. Not in the store yet | overview: catalog counts, Wahlperiode badges, warnings. Votes panel: acquisition state | catalog file, report `warnings` | `sittings` (slice 2), `protocol_acquisition` and validation counts (slice 3), as planned |

Options:
- **A (recommended).** Move each page's computations into the derive layer or the store in that page's A4 slice, under the rule above. The slice's strict oracle then checks the move.
- **B.** One early PR that moves every computation. It is out of step with the slices, which still read `entries`, and it touches every page at once.
- **C.** Leave rules and aggregates in the renderers once they read the store. This breaks D9 for buckets 3 and 4, and a reader could not reproduce week figures from the release.

**Answer:** open.

## L5. Tests

What survives a shared stylesheet and shell, by kind (M10 to M12):

| Kind | Count | Fate |
| --- | --- | --- |
| Content: figures, labels, links, `data-*` attributes | most of the about 280 rendered-HTML tests | **Survive**, if they read the page through a helper instead of raw substrings. `tests/_page.py`, stdlib `html.parser`: `text()`, `links()`, `data(attr)`, `section(landmark or id)`. Port a test only when a restyle breaks it |
| Markup pinned by class or structure | 156 tests carry `class=`, part of them content tests that also name a class | On a converted page, become component tests (render the component from fixture values, assert through the helper) or are deleted where they pinned layout |
| CSS text | about 35 | Deleted with the inline CSS. Replaced by a handful of stylesheet tests: the tokens equal DESIGN.md's front matter; every class a component emits exists in `site.css` and the reverse; no hex in Python or markup (DESIGN.md "no hex in renderers"); the dark block sets the same variables as the light one; no `:visited` rule. No test pins a colour value or card size (DESIGN.md "Held Open") |
| Shell | 10 in `test_global_header.py`, plus scattered header assertions | Rewritten once as shell component tests: skip link first, seven links in order, current-page marker, Stand line states, footer links |
| Browser checks | 6 | Keep. They key on `data-*` attributes. A restyle PR runs its page's check at 375 px and dark. One new check runs over the specimen page |
| Parser tests (input HTML or XML) | 114 | Unaffected |

**An oracle for every PR kind**:
- **Move-only:** full-site diff empty.
- **Port:** strict diff (A4 D1, D3), only recorded (a) diffs.
- **Restyle:** a content oracle, `scripts/compare_page_content.py`. It is written in step 1 and extracts per page the visible text, every link target and every `data-*` attribute, normalised for whitespace, then diffs old against new. Only copy changes the restyle names may differ, each listed in the PR. Every number on the page is in the visible text, so a restyle cannot move a figure unseen.
- **New pages:** component and fixture tests plus a browser check, since no old page exists to compare with.

Slice 10 still writes its own full-site compare with the dev view exempt (A4 D4), and can start from this script.

Options:
- **A (recommended).** As above: content helper, component tests, a few stylesheet tests, a content oracle for restyles.
- **B.** Port all HTML tests to the helper up front. Much churn before any page changes, on tests that may never break.
- **C.** Golden HTML snapshots. A4 D4 rejected these: they break on every copy change.

**Answer:** open.

## L6. TODOS.md changes that follow

If L1 to L5 are accepted as recommended:
- **Roadmap Stage 2 items 1 and 2** become one item, "Render layer and A4, page by page", pointing at this file's order table. "Apply DESIGN.md to the site" and "Apply the v1 surface list" stay as entries, with their order taken from here.
- **"Apply the v1 surface list"** splits:
  - the page cuts become step 0;
  - the nav change goes with the shell;
  - the `facts` tables leaving the release go to the release work (Stage 1);
  - the Daten page goes to step 10.
- **A4 plan slice map:** slice 11 reads "per page group, before each port; closing PR at the end". Slice 2 loses the catalog page. Slice 6 lists the two store additions in L4 bucket 3.
- **"Apply DESIGN.md to the site":** "Depends on" names the shared layer (step 1). "Settle while applying" loses the stylesheet-cache item, which L2 settles.

**Answer:** follows L1 to L5.

## Failure modes

| Risk | Guard |
| --- | --- |
| Both stylesheets on one page break its layout | L2 coexistence rule. A test asserts that a page either links `site.*.css` or carries inline CSS, never both |
| A restyle moves a figure unseen | L5 content oracle on every restyle PR |
| A move-only PR changes behaviour | Full-site diff must be empty |
| The pilot shows the kit does not scale | Pilot gate before page two (L2). L3 reopens then |
| The whole-site render gets slower with the kit | Pilot measures render time on the reference store (checklist class 12) |
| The Stand line names a release the page was not built from | It reads only `--data-manifest`, and without one says "lokaler Build" |
| A Zitieren line says "unverändert" without a comparison | Pages omit the line until the release work supplies the comparison (L2) |
| Stage 1 and Stage 2 edit the same functions | Steps 5 onward wait for Stage 1's changes to B |

## NOT in scope

- Renderer code. This is a plan.
- The design itself: DESIGN.md is settled, and its open states (TODO "Apply DESIGN.md to the site", items (a) to (g)) are settled with the owner before the vote pages, as that TODO says.
- The release script, the stable comparison, hosting.
- WP 1 to 17, Fakt der Woche, AI summaries.

## Review frame

- Depth: architecture, from evidence measured on main.
- No outside voice: Codex cannot run in this sandbox (`codex-review-sandbox` memory).
- The templating comparison is one page and one change task by one agent. Line and character counts weigh more than times.
- The test counts are heuristics with a stated hand-check error.
