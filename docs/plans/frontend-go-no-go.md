# Frontend stack: go/no-go criteria for the chart prototype

Status: **decided: no-go, by the owner in chat on 2026-11-04,** after opening all three versions. The criteria were approved before anything was built.

Step 2 and 3 of TODOS.md "Decide the frontend stack". The question: is a static site generator worth reversing `PRODUCT.md:58` (stdlib only, no package manager, framework or build toolchain), judged on the one thing it was meant to deliver, interactive long-term charts?

The owner decides. The prototype produces evidence and a recommendation.

## The arms

The arms differ only in the thing being tested. All of them render the same data file and follow `DESIGN.md`.

| Arm | Stack | What it answers |
| --- | --- | --- |
| **A** | Python stdlib, hand-written SVG, a small own script | What today's stack can do |
| **B** | Python stdlib plus one chart library, vendored as a single file, no npm | What the library is worth without a generator |
| **C** | Astro 7 with the same chart library, installed under the strict npm policy (ledger R12) | What the generator adds |

- A against B shows the value of the library. B against C shows the value of the generator. Without B, a library win would look like a generator win.
- Library: Observable Plot (ISC), because it draws small multiples directly. Its weight counts against B and C.
- The hand-written drawing from the Stimmkarte preview is a head start for A. A must still reach the full feature list, and every arm gets the same polish, no more.

## The data, computed once

One Python script reads the full store read-only (`~/agent-runs/a3/full`, 716 Sitzungen, 2013 to 2026) and writes one JSON file. All arms read that file. The browser computes no figure.

- **Three provisional topics:** `klima*`; `migra*`, `flücht*`, `asyl*`; `rente*`, `renten*`. Per 10,000 words of Reden, per Fraktion, per quarter.
- **These are not the term lists.** They are unreviewed, unpublished and only exist to exercise the chart. The term-list decision and neutrality review stay separate and open. Every arm labels the figures as provisional.
- This store predates the latest schema changes. That does not matter for a chart test, and no figure from it is reported as a result.
- First check how the store separates Reden from Fragen and Kurzinterventionen (ADR 0001, 0002), so the unit is right or the gap is labelled.

## The feature list, identical for every arm

| # | Feature |
| --- | --- |
| F1 | Three topics, six Fraktion panels on a shared axis (DESIGN.md small multiples) |
| F2 | Topic switch, with the choice in the URL so a view can be cited |
| F3 | Period control: a chosen range of Wahlperioden or years |
| F4 | Tooltip on hover and on touch |
| F5 | Tap a point to reach the Reden it counts, each with a link to its protocol page (the TODO's traceability rule; about 900 list pages or equivalent) |
| F6 | Chart readable and all values available in a table with JavaScript off |
| F7 | Works at 375 px and in dark mode |
| F8 | Nothing loads from another host; no island payload over 50 KB (R16) |

## Hard gates for the generator (any failure means no-go)

| # | Gate | How it is checked |
| --- | --- | --- |
| G1 | `npm ci --ignore-scripts` gives a working build | Fresh directory, run the commands. A needed install script counts as a failure unless the owner accepts it by name |
| G2 | No foreign requests from the built site, and no network use or telemetry during the build | Inspect the built output; run the build with network denied |
| G3 | Reaches F1 to F8 | The same checks as the Python arms |
| G4 | No figure computed in the browser | Read the page scripts; values come from the JSON |
| G5 | A site-sized build finishes in under 15 minutes on this machine | Scale probe: about 5,500 generated pages, of which 716 are dossier-sized from real speech text. Today's full repersist, render and export takes about 27 minutes for comparison |

## What gets measured, per arm

| # | Measure | Why |
| --- | --- | --- |
| M1 | **Change tasks.** Once all arms are done, make the same two changes in each and record changed hand-written lines and elapsed time: (a) switch quarters to months and add a fourth topic; (b) redesign the panel layout and tooltip | The original case for switching was iteration speed. This tests it directly |
| M2 | Hand-written lines, excluding vendored and generated files | Maintenance surface |
| M3 | JavaScript shipped and page weight, gzipped | What a phone pays |
| M4 | Test code needed to cover F1 to F8 | Ongoing cost |
| M5 | Transitive package count and install size (arm C); vendored bytes (arm B) | Supply-chain surface against R12 |
| M6 | Python arms only: where this would sit in the real code, which existing files change | A standalone page understates real integration |

Change-task times come from one agent working in sequence, so whichever arm goes first or second has an advantage. The order is rotated between tasks, and the line counts weigh more than the times.

## Decision rule

**Go** only if all of these hold:
1. All five gates pass.
2. Arm C beats the better Python arm on M1 by a clear margin: at least a third fewer changed lines across the two change tasks, and not slower overall.
3. The owner, having used all three, would rather keep working in arm C.

**A tie or a narrow win is no-go.** Switching has fixed costs that one chart cannot show: ADR 0005, npm and its upkeep, moving about 5,000 pages, 357 test functions in the render test files. The generator has to clearly earn them.

**If no-go:** the better Python arm becomes the way charts are built, `PRODUCT.md:58` stays (or gains one named exception if arm B wins, since a vendored file is still a dependency), and "Apply DESIGN.md to the site" carries on in Python.

## What this cannot measure

- **Migrating existing pages.** Before the decision, estimate it separately from the renderer census (about 170 places that choose copy from data state). A polished chart must not decide this alone.
- **Readers.** Nobody outside the project sees the prototype.
- **Long-term upkeep.** One chart says little about npm churn over years.
- **Other chart types.** Only line small multiples are tested.
- Outside-voice findings O4 to O11 (A4 plan) stay open and are resolved only if the answer is go.

## Where it lives

Throwaway, in a gitignored directory, archived in `~/.gstack/projects/LucaAlv-poliwatch/designs/chart-prototype-20261104/`. Only this file goes into the repository. Nothing here adds to the site build or the release.

## Result

Measured 2026-11-04 on astro 7.4.5, @observablehq/plot 0.6.18, jsdom 30.1.3, Node 24.15, against the A3 store. All three arms were built by one agent in one sitting. Same data checker and same browser script for every arm (`check_dist.py`, `browser.mjs`): after both change tasks, 2,709 pages, 6,600 table values equal to the data file and 8,245 internal links resolving, with 0 errors in each arm.

**Features**

| | A: Python, own SVG | B: Python, vendored Plot | C: Astro, Plot |
| --- | --- | --- | --- |
| F1 panels, F2 topic in URL, F3 period | yes | yes | yes |
| F4 tooltip, hover and touch | yes | yes | yes |
| F5 point to its Reden | yes | yes, through a link under the panel | yes |
| F6 chart without JavaScript | **yes** | **no: table only** | **yes** |
| F7 375 px and dark | yes | yes | yes |
| F8 no foreign host; inline data under 50 KB | yes, 42.1 KB | yes, 15.4 KB | yes, 41.8 KB |

**Hard gates for arm C: all pass, with conditions**

| # | Result | Evidence |
| --- | --- | --- |
| G1 | Pass | Fresh `npm ci --ignore-scripts` builds; output byte-identical to the first build (`diff -rq` empty). Only `fsevents`, an optional package, declares an install script |
| G2 | Pass, **if telemetry is turned off** | Build succeeded with the network denied and no denied request was reported. Astro's telemetry is on by default (endpoint in `@astrojs/telemetry`), so `ASTRO_TELEMETRY_DISABLED=1` would be required |
| G3 | Pass | Table above |
| G4 | Pass | `tip.js` only displays precomputed values |
| G5 | Pass | 5,500 pages, 716 of them full dossiers of real speech text, 290 MB: **Astro 42 s, Python 17 s** |

R12 and R14 would each need a named exception: Plot's documented server rendering requires `jsdom`, a third direct dependency beyond the allowlist, and inserting its SVG needs `set:html`.

**Measures**

| | A | B | C |
| --- | --- | --- | --- |
| M1 task (a): months, fourth topic, changed lines | 11 | 22 | 10 |
| M1 task (b): panels, peak, tooltip, changed lines | 19 | 15 | 17 |
| **M1 total changed lines** | **30** | 37 | **27** |
| M1 elapsed seconds, (a) + (b) | 69 + 77 | 73 + 42 | 26 + 63 |
| M2 hand-written lines (final) | 172 | 158 | 166 |
| M3 page plus JavaScript, gzipped | about 20 KB | about 173 KB | about 21 KB |
| M4 test code beyond the shared checks | none | none | none |
| M5 supply chain | none | 492 KB vendored | 3 direct, 266 installed, 177 MB |
| Build of the 2,709-page final version | about 4 s | about 4 s | about 20 s |

Line counts include the shared `tip.js` for A and C (2 lines per task). The fixed 50 KB budget forced real changes in every arm during task (a). Elapsed times are weak evidence: in task (a) arm C went last and reused a fix already worked out on A and B.

**Against the decision rule**
1. Gates: pass.
2. M1 margin: **fails.** C has 10 % fewer changed lines than A (27 against 30). The rule asks for at least a third (20 or fewer).
3. Owner's preference: not yet given.

**Reading:** the rule gives **no-go**. The chart features the switch was meant to unlock all work in plain Python, including touch tooltips and drill-down, at about the same page weight and code size. Arm B adds 8 times the weight and loses the chart without JavaScript, so a client-side library is not attractive either.

**Limits of this result**
- Only line small multiples were tested. A chart type that is hard to hand-draw (heatmap, beeswarm, many-scale facets) could favour a library. Revisit when a real chart needs one.
- An agent made every change. Developer comforts such as Astro's hot reload and component files are invisible in line counts, and a person may weigh them differently.
- A's 172 lines are a small clean module, not today's 14,556-line build file. The iteration pain the owner felt comes at least partly from that file's structure, which this result does not fix. New pages should be small modules like this one.
- Migration cost for existing pages was not estimated, because the rule already fails without it. It would add to the case against, not for.
- Figures are provisional and are not results: term lists unreviewed, and monthly values get noisy where a month has few sittings.

**Owner's decision:** no-go accepted, in chat, on 2026-11-04.

**What follows**
- `PRODUCT.md:58` stays: stdlib only, no package manager, framework or build toolchain. No ADR 0005.
- Charts are built as in arm A: small Python modules drawing SVG at build time, with a small script for the tooltip.
- The frontend plan in the A4 plan (R10 to R16) and outside-voice findings O4 to O11 are not applied. A4 continues as planned, in Python.
- **Revisit** when a real chart cannot reasonably be hand-drawn. Compare a library then, starting from arms B and C.

Prototype sources, checks and measurements are archived in `~/.gstack/projects/LucaAlv-poliwatch/designs/chart-prototype-20261104/`. Built pages and installed packages were not kept.
