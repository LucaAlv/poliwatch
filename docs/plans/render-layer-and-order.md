# Render layer and Stage 2 order: A4 slices 2 to 11 against the DESIGN.md rollout

Status: **decided, 2026-11-10.**
- The owner accepted L1 to L5 on the condition that an adversarial review agreed. Five reviews, one per decision, all returned "agree with changes", and none disagreed. Their changes are applied below.
- Two choices inside the changes were made under that delegation: merging move and port in L1, and the calendar exception in L4. The owner confirmed both in chat on 2026-11-10: "Keep both".
- Planning only: no renderer code changes here.

Frame: `/gstack-plan-eng-review` on the architecture brief in `docs/plans/v1-scope-review.md` ("What this means for the design and architecture sessions", "Architecture session"). That ledger (Q2, Q3, Q7) wins over older plans. Owner decisions went to the owner in chat, not through AskUserQuestion, because a global hook can auto-answer gstack briefs.

Decisions are numbered **L1 to L6**, to stay apart from Q1 to Q17 and N1 to N10 (scope review), D1 to D10 and R1 to R18 (A4 plan) and roadmap C1.

Settled, not reopened:
- the static site generator no-go (`docs/plans/frontend-go-no-go.md`);
- Q2: slices 2 to 11 before the public site, none for the data release;
- Q3: main and stable releases, and the site reads the latest main release;
- Q7: both raw dumps dropped;
- Q12: no new third-party data in the release;
- D8 to D10 as decided;
- R1 to R9 of the A4 plan;
- DESIGN.md v0.34.1.0.

Stage 1, the data release, comes first and needs nothing in this plan.

## Evidence

Measured on `main` at ed6847c (v0.36.0.0), 2026-11-10, unless a row says otherwise. Code figures come from an AST script, a heuristic: it counts string literals inside `<style>` or `<script>` and multi-line strings that read as CSS or JS. The brief's figures were pre-A3 census numbers, and this table replaces them.

| # | Fact | Value | Source |
| --- | --- | --- | --- |
| M1 | `scripts/build_dip_pulse_site.py` (B) | 14,950 lines, 294 top-level functions. 54 of those contain markup, 4,413 lines in all | measured |
| M2 | `scripts/render_dip_pulse_html.py` (R) | 4,327 lines. 31 functions contain markup, 2,149 lines in all | measured |
| M3 | CSS in Python strings | 1,685 lines in B, 1,237 in R, 2,926 in all. Each of the 21 pages carries its own `<style>` block | measured, heuristic |
| M4 | JS in Python strings | 551 lines in B, 308 in R, 39 in `sitzungskalender.py`, about 900 in all | measured, heuristic |
| M5 | Page writers (`<!doctype html>`) | 21: 20 in B, 1 in R (`render_html`, the dossier, 1,248 lines, 923 of them CSS) | measured |
| M6 | `esc()` calls | 597: 412 in B, 122 in R, 56 in `features/votes.py`, 7 in `week_radar_feed.py` | measured |
| M7 | Page shell | `page_head` (R:1199) returns only the theme bootstrap script. Every page writes its own `<head>`, header call, footer and scripts | static read |
| M8 | Class names shared by DESIGN.md's inventory and today's CSS | `.site-nav` (11 rules), `.panel` (10), `.field` (3), `.filters` (2), `.primary`, `.vote-lead`. Both stylesheets also style bare elements (`body`, `h1`, `a`, `table`) | measured |
| M9 | Tests | 2,208 test functions | measured |
| M10 | Tests with HTML-shaped strings | 448 in all. 114 are in parser test files, where the HTML or XML is input. That leaves 351, of which 156 carry a `class=`, mostly to scope a match rather than to pin the class. Two hand checks (20 and 24 tests) found 20 to 25 % that assert no rendered HTML. So **about 250 to 285 assert on rendered HTML** [estimated] | measured, heuristic |
| M11 | Tests on CSS text | 42 by the heuristic, 19 of them overlapping M10, with a few false hits. So **about 35** [estimated] | measured, heuristic |
| M12 | Browser checks | 6 scripts under `tests/`. Only the votes archive check and the chip controls key on `data-*`. The bills, week comparison, radar and next-sitting checks select by class, and two pin layout (grid track count, per-row borders) | static read, review |
| M13 | Open PRs | none. No unmerged branch changes B or R beyond squash-merge residue | `gh pr list`, `git diff main...<branch>` |
| M14 | Inline `<style>` in the built site | 96 MB of 1,397 MB in 6,750 files | **A3 build, 2026-10-28** (scope review E8), not re-measured |
| M15 | Release manifest on a build | Every build with a store writes one tagged `local` (B:4419, B:4251 "lokaler Export"). `--data-manifest` overrides it (B:4907, B:13385). Pages still read the local store either way until slice 10 | static read, review |
| M16 | Direct test calls into B | 42 test files import B. `render_front_page` is called 21 times, `render_votes_archive_index` 17, `render_site` 15 | review |
| M17 | Full-site oracle cost | A repersist with render and export takes about 27 minutes per side, and the diff is clean only after normalising generation names, timestamps, the build revision and export hashes (A4 "Slice 0 result") | A4 plan |

Computation still on the render paths: inventory by a read-only subagent, 2026-11-10, corrected by the L4 review. It is summarised under L4.

## L1. Order: A4 slices 2 to 11 against the redesign

The rule to keep: **never restyle and port a page in one PR**, so the strict HTML diff oracle (A4 D1, D3) stays usable for every port.

Why the A4 plan puts slice 11 after slice 10: the plan gives no reason in its slice map. TODOS ("Split the dataset from the site") says the file split "follows from" moving data into the store, and the export note there says that moving code before rewriting it "would only relocate the code". Neither argument is a data dependency. A move-only change does not care whether a renderer still reads `entries`.

Options:
- **A. As planned.** Slices 2 to 10 in order, then the whole restyle, then slice 11. About 10 PRs. Every restyle works inside the 15k-line file, which is the iteration pain `frontend-go-no-go.md` "Limits" names.
- **B. Per page group:** move-only, then port, then restyle, each its own PR. About 28 PRs. Slice 11 dissolves into the moves.
- **B′ (decided). B, with move and port merged where that is safe.** For each page group:
  1. **Move and port**, one PR:
     - The page's renderer leaves B and R for a module of its own.
     - An AST check shows each moved function's body is unchanged before the port edits it, and that commit is separate.
     - The A4 slice then ports the module, checked by the strict oracle.
  2. **Restyle**, its own PR, checked by the content oracle and the browser check (L5).

  A separate move-only PR remains for the two large renderers, the dossier (`render_html`) and `puls.html`, and for any move that carries shared helpers. There the move gets the AST check plus a normalised render-only diff on one store clone. Slice 11 dissolves into these moves, and one closing PR moves what is left. This cuts B's PR count by about a third.
- **C. Whole-file split first, one PR.** Possible, because no PR is open (M13). But Stage 1 is still changing B, so a 15k-line move conflicts with every branch in flight, and it moves code that slices 2 to 9 then delete. B′'s early moves carry some such code too, but a page at a time and just before its port.
- **D. Restyle first, then port.** Q2 rejected this shape: every renderer would be redesigned and then moved.

**Shared helpers get a home first.**
- Pages share helpers inside B: `period_sort_key` B:216, `format_int`, `esc`, `publication_selection`.
- They also share them across modules: `features/votes.py`'s badge, document links and vote lead serve the archive, the dossier panels and `puls.html`.
- A moved page module that imports back from B would be circular. So step 1 creates a common-helpers module, and helpers move there as their first moving page needs them.
- A shared component is restyled with its last consumer. Until then, a converted page uses a new component and leaves the old helper to the unconverted callers. The fork is named in the PR.

**Tests move with the code.** M16: test files call renderers in B directly. Each move re-points their imports in the same PR, with no shim (CLAUDE.md pre-release rule).

**The order.** Each line is one page group. Moves and ports follow the A4 slice dependencies.

| Step | Page group | PRs | Needs | Why here |
| --- | --- | --- | --- | --- |
| 0 | Surface cuts | one | none | Delete `api-sitzungen.html`, `settings.html` and the Fakt der Woche pages, their nav entries, and the 333 KB sitting list on `sources.html` (Q5, Q7). Also the Fakt references: `features/__init__.py:43`, the landing row B:5736, `test_features.py:21`, the Fakt page tests in `test_facts.py`. This removes `render_catalog_page` (361 lines, linked only from the overview button), `render_settings_page` and the three Fakt renderers before anyone ports or restyles them, and takes the catalog page out of slice 2. Oracle: the cut pages are gone, and elsewhere only the nav and the removed links differ, recorded |
| 1 | Shared layer | one | none | L2, plus the common-helpers module and `compare_page_content.py` (L5). No existing page changes. Oracle: normalised full-site diff empty apart from new files under `assets/` and the dev view |
| 2 | **Pilot:** `votes/index.html` | restyle | 1; Stage 1 "Check that vote links are right" | Already on the store (slice 1). L2 limits what the pilot changes |
| 3 | Abgeordnete (index, detail) | move, restyle | 1; Stage 1 registry items | Reads the store, except `publication_domains`, which comes from the JSON-derived manifest. That input moves in slice 9, so the restyle keeps it as it is |
| 4 | Static pages: `bundestag.html`, Impressum, Datenschutz | restyle | 1 | No figures. They exercise the shell at depth 0 |
| 5 | Sitzungen (`overview.html`) and the store half of `index.html` | move and port (slice 2), restyle `overview.html` | Stage 1 done in B; the vote outcome decision (L4) | Slice 2 builds `weekly.py` for the landing page (L4). The landing restyle waits for step 12 |
| 6 | Dossiers | move, then slices 3, 4 (vote panels), 5, then restyle | "One module that counts Reden and Beiträge" before slice 5 | The speech component needs the paragraphs slice 5 persists (DESIGN.md Speech). Slice 5 also adds position order and position-to-item links (L4) |
| 6a | New per-vote pages | new | slice 4; DESIGN TODO states (a) to (g) settled with the owner | DESIGN.md has a vote's page (verdict, wall, Zitieren line) that does not exist today. A new page is built on the layer from the store, with no oracle. The dossier panel and the vote lead then link to it |
| 7 | Aktuell (`puls.html`), with the puls votes card that slice 4 lists | move, then slice 6 and the slice 4 votes card, then restyle | 4, 5 | Return mode and the vote lead. Adopts `weekly.py` |
| 8 | Gesetzesvorhaben | move and port (slice 7), restyle | 5 | D10's dump goes in slice 7 |
| 9 | Quellen und Methode | move and port (slice 8), restyle | 2, 3 | |
| 10 | Daten, export, Abgeordnete `publication_domains` | slice 9 (the export module), restyle Daten | "One Persons module" plus the Reden module | Release blocks and the CSV control |
| 11 | Release-only build | slice 10 | 1–9 | The proof. It compares two builds of the new layer |
| 12 | Home, two doors | restyle | the first analysis (roadmap Stage 2 item 3) | Analysen pages are new and built on the layer |
| 13 | Close | one | all | Rest of slice 11: CLI and acquisition leave B, and the old shell, `global_header_styles` and the last inline CSS go. Slice 10's compare runs again on this tip |

The reader test (Q16) comes after step 13.

**Stage 1 overlap.** Stage 1 does not clear steps 0 to 4 outright:
- Step 0 edits the same regions of B as Stage 1's "`facts` tables leave the release" (B:173-175, B:3285, B:4124, B:12966). Land one, then rebase the other.
- Step 2 waits for "Check that vote links are right", and step 3 for the registry items.
- Step 4 is independent.
- From step 5 on, all of Stage 1's changes to B must have landed.

**Decided: B′.**
- Every port keeps the strict oracle, and every restyle changes a small module instead of the 15k-line file.
- Slice 11's benefit comes early, without a 15k-line conflict.
- Merging move and port where an AST check covers the move keeps the PR count near A's.

**Answer (owner, 2026-11-10):** "All five sound plausible to me … run each question and recommendation through a quick adversarial review agent. Come back to me if any of them disagrees with your recommendation. If not proceed automatically." The review agreed with changes. B′ is its proposed refinement of B, adopted under that delegation and confirmed by the owner: "Keep both".

## L2. The shared layer, built before the first restyle

**Where it lives.** A package `scripts/render/`. It must not be called `site`, because that is a standard-library module loaded at interpreter start, so `import site.markup` fails. Nor `html`. Page modules go under `scripts/render/pages/`, created by the moves. Tests reach it as they reach `scripts/features/` today, through `tests/_support.py`.

| Part | What | Notes |
| --- | --- | --- |
| `render/markup.py` | `Html`, a `str` subclass for markup that is already safe, with `__html__`. `__add__` and `__radd__` escape a plain `str` operand and return `Html`. `esc()`. A `Template` class compiled once at import from a literal (`string.Formatter().parse`): it checks its field names, fails at import on a stray brace, and escapes every value that is not `Html`. Also `join()`, whose separator is a literal, `href()`, which refuses any scheme other than http, https, mailto and relative, and `trusted()` for legacy helper output | L3. Precompiling removes the measured slowdown |
| `render/common.py` | Helpers several pages share, moved out of B and R as their first page moves (L1) | Breaks the circular import a moved page would have |
| `render/shell.py` | `page(...)`: doctype, `lang="de"`, meta, title, the stylesheet link at the right depth, header, the seven-link nav (Q6), the page head (back link, `heading-1`, Stand line, optional Zitieren line), footer with the provenance key and four links, the script tag | Replaces the 21 hand-written heads and `page_head`. The theme bootstrap and toggle come from the one existing implementation in R, not a copy: same `localStorage` key and `data-theme`. The nav list lives once, with Analysen behind a flag until the first analysis exists |
| `render/components/*.py` | One small module per DESIGN.md inventory group: `votes` (strip, totals, wall, wall as text, verdict, vote lead), `provenance` (slip, source line, origin line, gap), `lists`, `tables`, `controls`, `releases`, `charts` (small multiples drawn as SVG in Python, like arm A of the chart prototype) | Each takes plain values and returns `Html`. No store access, and no figure beyond L4's rule. Each emits `data-component` for tests (L5). The vote wall is one function, with geometry in CSS variables only (DESIGN.md "Held Open") |
| `render/assets/site.css` | The one stylesheet. Its `:root` light and dark token blocks are generated from DESIGN.md's front matter and committed; a test checks they are current (L5). Then the inventory classes, and any legacy helper rules a converted page still needs | A real `.css` file in the repository |
| `render/assets/fonts/` | Five WOFF2 files and the OFL texts, under stable file names. D-DIN unmodified. Before committing the Fontsource Latin subsets of Atkinson, read the OFL header of each family for Reserved Font Names: a subset is a modification. DESIGN.md says only D-DIN has them, which is unchecked | DESIGN.md "Loading". No `package.json` |
| `render/assets/site.js` | Theme toggle, the data age (DESIGN.md "Age and overdue"), filter chips | The overdue gap waits for a due-date rule, which needs "Scheduled data-release workflow". The pilot ships the age only |
| Asset writer | In `render_site`, so `build_demo_site.py` and test builds get it. Copies `assets/` to `<out>/assets/`, with a content hash in the CSS and JS file names only, and deletes older hashed copies. The shell links by relative path at every depth | Deploy is `rsync -a` of the output directory (README), so no new step. `validate_public_output` is extended to scan `.css` and `.js` |
| Dev specimen page | `dev/komponenten.html` renders every component in its states, in light and dark. It needs a new writer gated on `include_dev_view`, since `devview.py` only adds dossier sections | The browser checks and the owner's eye run against it. Exempt from slice 10's compare |

**Coexistence during the rollout.**
- A converted page links `site.<hash>.css` and carries no inline `<style>`. An unconverted page keeps its inline CSS and does not link the new file. **A page never loads both**, because the two stylesheets share class names and both style bare elements (M8).
- Legacy helpers that a converted page still calls, such as the result badge, document links and Politikfeld tags, emit old classes. The PR either converts the helper for every caller, or adds those rules to `site.css` and names them.
- A test asserts per page: either the stylesheet link or inline CSS, never both.
- The old shell and per-page style functions are deleted page by page, the last of them in step 13. Two looks side by side are acceptable, because nothing is public before step 13.

**Stand line and Zitieren line.**
- **Release slot.** Until slice 10, pages read the local store whatever manifest is passed (M15). A Stand line that named a passed release would name one the rows were not read from. So until slice 10 the release slot reads "lokaler Build" on every build. From slice 10 on, it names the release the build read.
- **Newest Sitzung.** Taken from the store's protocols (the manifest's `protocols.last` and `protocols.to` where present, B:4865), passed into the page writer. A page writer with no store, such as a test calling the renderer directly, omits it. The newest vote's date is never used in its place, because it can be months older than the newest Sitzung.
- **Age.** Computed in `site.js` from `<time datetime>`. The overdue gap waits for the due-date rule (see `site.js` above).
- **Zitieren line.** It needs what the release work does not yet supply: which Sitzungen stable holds, a per-record comparison against stable, and a rebuild when a release is marked stable (TODO "Apply DESIGN.md to the site", Context). The shell has the slot, and pages omit the line until "Main and stable releases" provides those three. It never prints "unverändert" without the comparison.
- **Build clock.** `STALE_AFTER_WEEKS`, "Woche läuft" and "Auswertung vom" are deleted, not moved (L4 bucket 4).

**Pilot: `votes/index.html`.**
- **Why this page.** It already reads the store, so no port follows the restyle. It is small. It uses the shell, the list row, the Fraktion and Politikfeld filters and the Stand line. The DESIGN TODO says "Votes pages first".
- **What the pilot is.** A proof of the shell, assets, stylesheet and kit on a real page. It keeps today's content: the rows, today's result badge (which already says in words when no result exists, `features/votes.py:55`), the document links and the filters.
- **What waits.** The DESIGN.md strip and counts on each row wait until DESIGN TODO states (a), (c) and (e) are settled with the owner: NULL counts, `unknown` members, direction unknown, an outcome of None. That TODO already asks for this before vote pages are built, and adding counts is new content, which a pilot should not carry.
- **The fixture.** `tests/votes_archive_browser_fixture.py` writes the assets with the page, so the 375 px and dark checks run styled.

**Pilot gate**, recorded before step 3:
- changed lines;
- page bytes before and after;
- render time on the reference store (checklist class 12);
- content oracle clean;
- browser check at 375 px and dark;
- test churn, counted as tests ported, deleted and added;
- whether nested optional fragments read acceptably in the kit (L3's measurement did not cover that).

If the kit proves awkward on a real page, L3 is reopened before page two, not after ten.

**Answer (owner, 2026-11-10):** the delegation quoted under L1. The review agreed with changes, all applied above: the package name, the Stand line source, legacy helper markup, the pilot's scope, and the fixture, asset and font points.

## L3. Templating: stdlib helpers or Jinja2

Measured on one real page. `render_votes_archive_index` (B:5992-6080) was ported twice in a scratch directory, both versions fed by the fixture rows of `tests/votes_archive_browser_fixture.py`:
- **Arm A** uses a stdlib kit like L2's `markup.py`, but without the `+`, `Template` and `href()` changes.
- **Arm B** uses Jinja2 3.1.6 with autoescape. It pulls in MarkupSafe 3.0.4, so two packages.

Both call the same legacy helpers, so the comparison is about the page.

A change task followed in both arms: the row becomes DESIGN.md's `.vrow` with a strip and counts. Both arms produced identical output for it.

Throwaway, not committed. context7 is not authenticated in this session, so the CLAUDE.md rule to read the library's current docs could not be met. Jinja's API was checked against the installed 3.1.6.

The reviewer reproduced arm A at 620 rows (byte-identical, 407,137 bytes). It also fed a hostile row through arm A: a title of `x"><script>`, a `{evil}` procedure type and an `A'B` Fraktion name. The output was escaped correctly and injected nothing.

| | Today, f-strings | A, stdlib kit | B, Jinja2 |
| --- | --- | --- | --- |
| Output equal to today's page | | byte-identical | equal after normalising `&#34;` and `&#39;`. A `finalize=` hook makes it byte-identical, but then `\|e` and a literal `none` must be banned |
| Page code, non-blank characters | 4,390 | 4,141 | 4,441 (Python plus template) |
| Shared code | | 59 lines | 17-line base template, plus 14,425 lines of dependency |
| Explicit escapes in the page | 17 `esc()` | 0. 10 `trusted()` opt-outs for legacy helpers | 0. 9 `Markup()` opt-outs |
| Change task, changed characters | | 519 | 506 |
| Render, 620 rows, median of 15 | 15.7 ms | 36.0 ms. A precompiled template takes 3.3 µs per 5-field row, against 3.9 µs for f-strings | 27.2 ms |
| Dependency | none | none | Jinja2 532 KB and MarkupSafe 44 KB, BSD-3-Clause. MarkupSafe ships a platform C extension with a pure-Python fallback |

Reading:
- Both arms make escaping the default, which is Jinja's main argument against 597 manual calls.
- The change task costs the same (2.5 % apart).
- Jinja2 needs a package install step, against `PRODUCT.md:58` "no package manager", and an exception the owner would have to name. Its other offers, template inheritance and files non-programmers edit, do not apply to one operator and agents.
- The entity difference is not a real obstacle, since `finalize=` removes it, so it is no argument either way.
- The page is flat. Several levels of nested conditions, where Jinja's `{% if %}` reads better than assembling optional fragments, were not tested; the pilot gate checks it.

**Review changes, applied in L2:**
- `Html + str` escapes and stays `Html`. Without that, the natural fix for double escaping is `trusted()`, and opt-out creep would be the real hole.
- Templates are compiled and checked at import.
- A small `href()` checks schemes. Today external links go through `esc` only (R:2633, R:3015).
- `trusted(row["href"])` in arm A copies a latent unescaped attribute from today's code. It is not carried into the kit.

Options:
- **A (decided).** The stdlib kit, no new dependency.
- **B.** Jinja2 and MarkupSafe as the first named exception to `PRODUCT.md:58`.
- **C.** Python 3.14 template strings (PEP 750). They need the floor raised from 3.11 to 3.14, dropping two CI versions, and they give only a `Template`: the escaping renderer is still ours. Deferred. To keep the move mechanical, every template stays a literal and every value a named keyword argument, so `Template("…{x}").render(x=x)` can later become `html(t"…{x}")`.

**Answer (owner, 2026-11-10):** the delegation quoted under L1. The review agreed with changes, applied above.

## L4. Figures out of the renderers

Principle 6 and D9: renderers read only what is persisted. The votes archive, already on the store, still applies `merge_fractions`, `_fraction_position` and the Abweichler count at render time, and R5 accepted that. So the rule has to say where the line runs.

**The rule:**
- **What needs a definition.** A count, an aggregate or a rule outcome shown on a page has exactly one definition. It is either a persisted column, or a named function in the derive layer (`scripts/derive.py`, or a store-reading module beside it such as `weekly.py`) whose inputs are release tables only. `DATA.md` or a release recipe states it, so a reader can reproduce it.
- **What does not.** Plain arithmetic or formatting of figures already shown on the same page needs no further definition: a share of two shown numbers, rounding, sparkline scaling.
- **Selection rules.** Top-N with ties and similar rules live in the derive layer and are stated in one sentence on the page.
- **Inputs.** Renderers read no report JSON and no DIP or abgeordnetenwatch cache.
- **Two named exceptions:**
  - The data age is computed in the browser from dates in the HTML (DESIGN.md "Age and overdue").
  - The next planned Sitzungswoche comes from the Bundestag's Sitzungskalender (`sitzungskalender.py`, official `.ics` files), read at build time. It is a planned date, not a figure. Its source line names the calendar and its fetch date. The HTML carries every upcoming week as `<time>`, and `site.js` marks the next one, so the choice does not freeze when a release is late. Persisting the weeks in the release was the alternative; it would add data under Q12. The owner kept the exception.

**The inventory, sorted into buckets** (subagent inventory, corrected by the review):

| Bucket | Where | What | Goes to |
| --- | --- | --- | --- |
| 1. Already persisted, only re-read | dossier: Reden per TOP (`item_stats` R:1378), characters, Drucksachen (`top_documents` R:2517), votes per sitting, Beiträge kinds, `verteildatum` | report JSON today | store queries in slices 3 to 5 |
| 1a. Cached counts | dossier header TOPs and Reden from `validation_summary` (R:4272-4273). The same figures feed B:10846-47, B:11196-97 and B:12046-47. The header's Drucksachen (`distinct_document_count`) and Abstimmungen (`total_votes`, R:3113) are computed from report JSON at render time | The header Reden and the per-TOP sum come from one parsed list (`validate_dip_protocol.py:3495, 3530`). They differ only if a replay changes the items without refreshing the summary. Check whether the replay at validate:3650-3675 refreshes the Reden figure, and count any difference on the reference store before slice 5 | TODO "One module that counts Reden and Beiträge", which slice 5 needs. Report old and new values if any figure moves |
| 2. Rules on stored inputs | vote outcome, Abweichler count, Fraktion position, procedure type (`derive.vote_outcome`, `vote_abweichler_count` derive.py:729, B:5906, B:5889) | derived at render time, as R5 accepted. The release already defines the outcome (SQL in `docs/project-documentation.md:648-657`) and the Abweichler count (recipe `r3-abweichler`, B:3580, tested by `test_mehrheitsvotum.py:163`) | **Decide before slice 2**, because the landing page (slice 2) and Home and Aktuell show the Vote lead. Either persist both as columns and make the SQL snippet and the recipe read them, or keep the derive functions and prove they equal the SQL and the recipe. Never a third definition. `vote_abweichler_count` returns None unless every group is complete and covers the total, so check that against the recipe first |
| 3. Week aggregates | `puls.html`, the landing page and `week_radar_feed.py`: `week_stats` R:1495, `week_comparison` R:1644, `returning_vorgaenge` R:1742, radar ranking `week_topic_rows` R:2201, shares and sparklines | report JSON | One store-reading module, `weekly.py`, **built in slice 2** for the landing page, its first user. `puls.html` (slice 6) and the feed adopt it. A release recipe states the week figures |
| 3a. Position data | DIP position order (read at R:2054 and R:2601) has no column in `proceeding_positions` (persist:251-270). The upsert overwrites `agenda_item_id` when two TOPs share a position (persist:1171) | lossy store | **Slice 5** store additions; the A4 slice 5 row already lists positions and position-to-item links. Slice 6's row no longer reads "probably none" |
| 4. Build clock | `week_header_facts` B:6634-6672 (`STALE_AFTER_WEEKS`, "Woche läuft"), the landing page's "bisher erfasst", the next-sitting state | `resolve_today` B:6454 | "Woche läuft", `STALE_AFTER_WEEKS` and "Auswertung vom" are **deleted** (DESIGN.md log 2026-11-06): one wording for all states, readable without script. Age by script, the next week as in the exception above |
| 5. Wrong-way imports | `facts.py:64` imports `agenda_topic`, `format_int`, `iso_week_key` and `speaker_party` from the renderer. `week_label` is defined twice (facts.py:645, R:1468) | | Move into the derive layer in the move that first touches them. R's `speaker_party` (R:1364, with a role fallback) and persist's `speaker_party_name` (persist:694, None for role speakers) are **two different rules** and stay apart |
| 6. Not in the store yet | overview: catalog counts, Wahlperiode badges, warnings. Votes panel: acquisition state | catalog file, report `warnings` | `sittings` (slice 2), `protocol_acquisition` and validation counts (slice 3), as planned |

Options:
- **A (decided).** Move each page's computations in that page's A4 slice, under the rule above. The shared week module is built by its first user (slice 2), and the vote-figure question is settled before slice 2.
- **B.** One early PR that moves every computation. It is out of step with the slices, which still read `entries`.
- **C.** Leave rules and aggregates in the renderers. This breaks D9 for buckets 3 and 4.

**Answer (owner, 2026-11-10):** the delegation quoted under L1. The review agreed with changes, applied above. The calendar exception was chosen under the delegation over persisting the weeks, to stay within Q12, and the owner confirmed it: "Keep both".

## L5. Tests

What survives a shared stylesheet and shell, by kind (M10 to M12):

| Kind | Count | Fate |
| --- | --- | --- |
| Content: figures, labels, links, `data-*` attributes | most of the 250 to 285 rendered-HTML tests | **Survive** if they read the page through `tests/_page.py`, a stdlib `html.parser` helper: `text()`, `links()`, `data(attr)`, and `select()` for tag, `.class`, `[data-x]` and `[data-component]`. The private `HTMLParser` subclasses already in `test_bills.py` and `test_render_dip_pulse_html.py` are merged into it first. Port a test only when a change breaks it, and port it through the page writer or a built-site fixture, not a direct call into a renderer: otherwise a dead old function keeps its tests green |
| Markup scoped or pinned by class | 156 carry `class=`, mostly to scope a match | Port with `select()` and `data-component`. Delete those that pinned layout |
| CSS text | about 35 | Deleted with the inline CSS. Replaced by stylesheet tests:<br>- the generated token blocks in `site.css` are current with DESIGN.md's front matter (one source, no second copy of a value);<br>- every light token has a dark counterpart;<br>- no hex in Python or markup (DESIGN.md "no hex in renderers");<br>- no `:visited` rule;<br>- every class the component fixtures emit, in every variant, exists in `site.css`, with an allowlist of classes the script sets at runtime (`is-active`). No test pins a colour value or card size (DESIGN.md "Held Open") |
| Shell | 10 in `test_global_header.py`, plus scattered header assertions | Rewritten once as shell tests: skip link first, seven links in order, current-page marker, Stand line states, footer links |
| Browser checks | 6 | **Ported per restyle**, not kept as they are. Before its restyle, each page gets `data-*` hooks for what its check selects by class, and the check moves to them. Checks that pin layout (grid track count, row borders) are rewritten against DESIGN.md. A new check runs over the specimen page |
| Datenschutz checks | `test_demo_site.py:169-173` scans inline scripts for storage keys and hosts | Extended to `site.js` and `site.css` |
| Parser tests (input HTML or XML) | 114 | Unaffected |

**An oracle for every PR kind:**
- **Move, separate or merged.** An AST check that each moved function's body is unchanged. A separate move-only PR also gets a normalised render-only diff on one store clone with `SOURCE_DATE_EPOCH`, normalised as in A4 "Slice 0 result". No repersist is needed: a move changes no schema, and M17's 27 minutes per side cover repersist and export, not render. The first such PR measures the render-only time.
- **Port.** Strict diff (A4 D1, D3), only recorded (a) diffs.
- **Copy change.** A copy change that DESIGN.md asks for gets its own PR on the old styling, under the strict diff, before the restyle: Stand line wording, footer key, nav names, origin lines. Content and look never change in one PR.
- **Restyle.** `scripts/compare_page_content.py`, written in step 1. Per page it extracts:
  - the visible text, including `<details>` and `data-tip`;
  - every link target;
  - every `data-*` attribute;
  - every inline `style` value (bar widths);
  - the class tokens that carry meaning (result pill, `muted`, `aria-current`, `is-active`).

  It skips `script`, `style` and dev-only nodes, reports what it skipped, and normalises whitespace, `&nbsp;` and thin spaces. Since copy changes land first, **a pure restyle diffs empty**. Where copy and structure must change together, the PR says why, and the compare falls back to the multiset of numeric tokens, link targets and `data-*` values, ignoring words and order.
- **New page.** Component and fixture tests plus a browser check, since no old page exists.
- **After each restyle.** A dead-code pass (for example `/gstack-test-audit`) finds old functions and tests left behind.

**Departure from A4 D4.** D4 wrote no compare script until slice 10. This plan writes the content compare in step 1, because the restyles (a kind of PR D4 did not foresee) have no other oracle. Slice 10's full-site compare can start from it.

Options:
- **A (decided).** As above.
- **B.** Port all HTML tests to the helper up front: much churn on tests that may never break.
- **C.** Golden HTML snapshots. A4 D4 rejected these.

**Answer (owner, 2026-11-10):** the delegation quoted under L1. The review agreed with changes, applied above.

## L6. Roadmap changes

Applied to `TODOS.md` and the A4 plan with this file:
- **Roadmap Stage 2 items 1 and 2** point at this file's order table. "Apply DESIGN.md to the site" and "Apply the v1 surface list" stay as entries, with their order taken from here.
- **"Apply the v1 surface list"** splits:
  - the page cuts become step 0;
  - the nav change goes with the shell;
  - the `facts` tables leaving the release stay with the release work;
  - the Daten page goes to step 10.
- **A4 plan slice map:**
  - slice 11 dissolves into per-page moves and a closing PR;
  - slice 2 loses the catalog page and builds `weekly.py`;
  - slice 5 lists position order;
  - slice 6 no longer reads "probably none";
  - the vote-figure decision moves before slice 2.
- **"Apply DESIGN.md to the site":**
  - "Depends on" names the shared layer (step 1);
  - "Settle while applying" loses the stylesheet-cache item, which L2 settles;
  - votes pages beyond the pilot wait for states (a) to (g).
- **New TODO** "Persist or prove the vote outcome and Abweichler count", needed before slice 2.

## Failure modes

| Risk | Guard |
| --- | --- |
| Both stylesheets on one page break its layout | L2 coexistence rule and its per-page test |
| A legacy helper's markup renders unstyled on a converted page | Convert the helper for every caller, or carry its rules in `site.css`, named in the PR (L2) |
| A restyle moves a figure unseen | Copy changes land first; the content compare covers text, links, `data-*`, inline styles and meaning classes (L5) |
| A move changes behaviour | AST body check; separate moves also get the normalised render-only diff |
| A moved page imports back from B | `render/common.py` first (L1) |
| The pilot shows the kit does not scale | Pilot gate before page two. L3 reopens then |
| The Stand line names a release the page was not built from | "lokaler Build" until slice 10 (L2) |
| A Zitieren line says "unverändert" without a comparison | Pages omit the line until the release work supplies the comparison (L2) |
| A vote figure gets a third definition | Decided before slice 2: persist it and point the SQL and recipe at it, or prove equality (L4) |
| Stage 1 and Stage 2 edit the same functions | The "Needs" column and the Stage 1 overlap list in L1 |
| `trusted()` creep reopens escaping holes | `Html + str` escapes; review flags each new `trusted()` |

## NOT in scope

- Renderer code. This is a plan.
- The design itself: DESIGN.md is settled, and its open states (TODO "Apply DESIGN.md to the site", items (a) to (g)) are settled with the owner before the vote pages, as that TODO says.
- The release script, the stable comparison, hosting.
- WP 1 to 17, Fakt der Woche, AI summaries.

## Review frame

- Depth: architecture, from evidence measured on main.
- Codex cannot run in this sandbox (`codex-review-sandbox` memory). Instead, five adversarial reviewers (Sonnet subagents, one per decision) checked the draft (cb2eccf) against the code and the other plans. Each returned "agree with changes". The changes are applied in each section.
- The templating comparison is one flat page and one change task by one agent. Line and character counts weigh more than times.
- The test counts are heuristics with two hand checks.
