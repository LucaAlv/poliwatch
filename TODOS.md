# TODOS

Reassessed against the code, the live store and the generated site on 2026-09-19 (after PR #59, v0.4.0.0; rebased onto PR #60, v0.5.0.0). Nothing below is done; corrections from that pass are inline.

## Daten

### `parties.name` still holds two concatenated names and three Gruppe spellings

**What:** After the list-repr fix and migration (A1 step 1, 2026-09-22) the store has 15 `parties` rows, of which five are still not one Fraktion each: `'SPDSPD'` (1 MdB) and `'SPDCDU/CSU'` (1 MdB), and the pairs `'BSW (Gruppe)'` (10) / `'Gruppe BSW'` (10) / `'BSW'` (0) and `'Die Linke (Gruppe)'` (16) / `'Gruppe Die Linke'` (29). Decide the canonical spelling for the two Gruppen, add it to `normalize_faction` (`scripts/validate_dip_protocol.py:593`), and drop or split the two concatenated rows.

**Why:** Same consequence as the list-repr bug the migration just fixed: anything grouping by `parties.name` — R2's "Redeanteil je Fraktion", the Fakten cards' Fraktion caption — splits one Fraktion across two rows. Left open deliberately when the migration landed, because neither residue comes from the list-repr bug and folding them in would have meant guessing.

**Context:** Causes established 2026-09-22, both different from the list-repr bug, which is why the migration does not touch them.
- `'SPDSPD'`/`'SPDCDU/CSU'` come from the **source XML**: `21045.xml` carries `<redner id="11005217 999990074"><name><vorname>SvenjaSvenja</vorname><nachname>SchulzeSchulze</nachname><fraktion>SPDSPD</fraktion></name></redner>` in an `ivz-eintrag`, i.e. two TOC entries merged into one element by the Bundestag. Two speakers are affected, across twelve protocols: redner `11005217 999990074` ("SvenjaSvenja SchulzeSchulze", SPDSPD) in 21/18, 21/24, 21/25, 21/28, 21/44, 21/45, and redner `11005304` ("Dirk-UlrichAlexander Mende Föhr", SPDCDU/CSU) in 20/91, 20/94, 20/96, 20/103, 20/114, 20/116. The earlier note in this file ("no current code path concatenates names, so just fold them into the migration") was wrong. Fix belongs in `parse_redner` (`scripts/validate_dip_protocol.py:313`): detect a doubled `<redner id>` and either split it or drop the entry, then the parties rows disappear on the next rebuild.
- The Gruppe spellings are two DIP surfaces disagreeing: `/person` returns `"Gruppe BSW"`/`"Gruppe Die Linke"` (via `ingest_mdb_roster`), the protocol's `sampled_people` return `"BSW (Gruppe)"`/`"Die Linke (Gruppe)"`, and `normalize_faction` has no rule for either. `'BSW'` (0 MdBs) is a third spelling with no rows behind it.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Persist per-sitting acquisition state in the store (`protocol_acquisition`)

**What:** A `protocol_acquisition(protocol_id, component, state, fetched_at)` table written at persist time from each report's acquisition states (votes: `acquisition_state` as consumed by `render_vote_summary`; XML parsed or not; AI summaries), exported with the Daten CSVs; the facts engine and the Daten page read it instead of re-deriving it.

**Why:** The store cannot tell "no roll-call vote happened" from "votes were not fetched"; the state lives only in the report JSON. The facts engine (A1) gates week completeness from the in-memory `entries` and A0's replay re-derives the same map from the cached JSON, so two derivations of "complete" exist and can drift, and the download keeps a silent gap. Chosen at the eng review 2026-09-19 (D10: gate from entries now, schema later; D17: record).

**Context:** Needs a stable state vocabulary per component (`complete`, `partial`, `failed`, `not_requested` already exist for votes in `scripts/features/votes.py`). Natural B / Daten-pilot item.

**Update 2026-09-24 (v0.6.0.0 ship, adversarial review):** the D10 gap this item exists to close now has a concrete repro. `week_is_complete()` (facts.py) only iterates `week.protocols` - the protocols actually present in the store - so a sitting whose dossier fetch fails (`build_dossiers_with_progress`'s `dip.DipError` -> `continue` path, a real path, not synthetic) is invisible to the completeness check rather than failing it. Repro: seeding 1 of several expected sittings for a period yields `complete=1, publishable=1`. Self-heals once the missing sitting is later acquired (`compute()` recomputes fully every build), but a wrong winner can publish and poison later baselines before that happens. Still P3/deferred per the original D10 call - flagging the repro here in case it changes the priority math.

**Effort:** M
**Priority:** P3
**Depends on:** None (A1 works without it)

### Regenerate the architecture diagram for the Daten export step

**What:** `docs/bundestag-puls-architecture.html`/`.json` (2026-09-06) is a seven-node runtime diagram (DIP API → Fetch & Extract → SQLite Store → `render_html()` → "Static Site Output · pages + data/ cache" → Preview Server) with no export step and no Daten page. Regenerate it so it shows `export_distribution_data()` between the store and `render_site`, the `data/exports/g-<hash>/` + `datenstand.json` generation switch, and the `--data-manifest` override path.

**Why:** Deferred from the fix-datenbank plan at the ship gate (2026-09-19) to keep the 0.4.0.0 PR focused; the CHANGELOG's "Known stale docs" entry discloses the gap. Deferred from plan: `~/.gstack/projects/LucaAlv-poliwatch/fix-datenbank-plan.md` (CEO task T22).

**Context:** Correction (2026-09-19): the diagram never described `database.html` as a "12-row sample explorer" as the CHANGELOG entry and the earlier version of this TODO claimed; it simply has no node for the export or the page. Fix the CHANGELOG wording when the diagram lands. The pipeline comment block at the top of `scripts/build_dip_pulse_site.py` (steps 1-7 and the file table) is already updated and is the source for the diagram text.

**Effort:** S
**Priority:** P1
**Depends on:** None


### Site hosting plan for the 2.5 GB generated site

**What:** Make the HTML deployable under a capped static host (e.g. GitHub Pages' 1 GB limit). Measured 2026-09-19: 2.5 GB total; `data/` 1.4 GB (`plenarprotokoll-*.json` 607 MB, `bills.json` 386 MB, `exports/` 91 MB); `protocols/` 584 MB for 285 dossiers. **Without `data/` the site is still 1.11 GB**, so a deploy profile that only excludes `data/` does not fit; the dossiers have to shrink too. Pieces: (a) extend `--data-base-url`-style externalisation to the `data/plenarprotokoll-*.json` links on `puls.html`/dossiers and to `bills.json` (the base-URL pattern exists for the two export files); (b) shrink dossiers — see "Move the hidden dev-view API dump" below: ~952 KB of hidden markup per dossier × 285 ≈ 270 MB, so rendering it into a separate on-demand file roughly halves `protocols/`; (c) or pick a host without the cap.

**Why:** The Daten page and `--data-base-url` make the *data* shippable to a public audience; the *site* itself cannot go to a capped host today. Both outside voices in the `/autoplan` review flagged this; the user's go/no-go framing ("ship to a larger audience in a few weeks") depends on the site being public, not only the download.

**Effort:** L
**Priority:** P1
**Depends on:** None (absorbs the former "base URL for report JSON" item)

### Scheduled data-release workflow

**What:** A GitHub Actions workflow on a schedule: online build → export → immutable dated release tag → upload assets → `--offline` rebuild with the release's `--data-base-url` → deploy.

**Why:** The design doc's own constraint is "must stay current automatically"; a manual `scripts/publish_dip_pulse_data.sh` is upkeep a solo maintainer will eventually miss. The user's explicit decision at the Final Gate keeps PR2 manual for now; this is the follow-up once that has been exercised a few times.

**Effort:** M
**Priority:** P2
**Depends on:** **Blocked** — PR2 (`scripts/publish_dip_pulse_data.sh`) is not written yet (2026-09-19: the script does not exist, `.github/workflows/` holds only `ci.yml`, no GitHub release exists); a `GITHUB_TOKEN` with release-upload scope as a repo secret.

### Pilot gate: decide keep/remove for the Daten page

**What:** 8 weeks after the first public data release, decide keep/remove using `gh release view --json assets` download counts, any inbound question or citation, and whether the builder himself used the downloaded file for anything.

**Why:** The user's own go/no-go framing ("if it doesn't work for v1, that is not a deal breaker"); the audience ("developers and researchers") is chosen, not demand-tested, so this is the cheap way to find out without a demand study.

**Effort:** S
**Priority:** P2
**Depends on:** **Blocked** — first public release (PR2); as of 2026-09-19 no release exists, so the 8-week clock has not started.

### Recipe SQL copy buttons, recipe result CSVs / DATA.md / dossier "Daten" footer link

**What:** (a) A "Kopieren" clipboard button on each recipe's SQL block. (b) Per-recipe result CSVs, a `DATA.md` in the release, and a "Daten" link in dossier footers (`footer_links` in `render_html`, `scripts/render_dip_pulse_html.py`, currently Katalog · API-Sitzungen · Gesetze · Quellen · Einstellungen).

**Why:** Both were scoped out of PR #59 (no new script per the design doc; b is an Approach-C follow-up once the data path has real usage). Checked 2026-09-19: no clipboard code, no `DATA.md`, no Daten footer link exist. The former item (b), externalising `data/plenarprotokoll-*.json` links, moved into the site-hosting TODO above.

**Effort:** S–M
**Priority:** P3
**Depends on:** None


## Protokoll-Dossier

### Ranking row titles that skip the "Beratung des Antrags der Abgeordneten …" boilerplate

**What:** Shorten `.attention-row` titles (and the KI-summary/lede rows that reuse `short(heading, 78)`) so the first visible words identify the topic, not the procedural prefix.

**Why:** Real TOP headings are boilerplate-first ("Beratung des Antrags der Abgeordneten Nicole Höchst, Dr. Götz Frömming, Dr. M…", "Beratung der Beschlussempfehlung und des Berichts des Ausschusses für Umwe…"). At the 78-char cut most rows in the Aufmerksamkeitsrang never reach the subject, so the ranking ranks things the reader cannot tell apart. This is also the prerequisite for any denser (one-line) row design, which two independent reviewers proposed on 2026-09-13 and which was rejected only because of this.

**Context:** Titles come from `item["heading"]` in the `attention_rows` loop of `render_html` (`scripts/render_dip_pulse_html.py`) via `short()`; still `short(item.get("heading"), 78)` as of 2026-09-19. The stripper now exists: `strip_heading_boilerplate()` / `agenda_topic()` in `scripts/render_dip_pulse_html.py`, built for the Fakten cards on 2026-09-22 (six openers, strips 2.238 of the archive's 2.727 headings). What is left here is calling it from the `attention_rows` loop and keeping the full heading in the `title` attribute. Keep the full heading in a `title` attribute. The puls.html radar no longer shows headings as titles (it names rows by DIP Vorgang title, heading only in `title=`), so this is dossier-only now. If the "LLM five-word topic label" item under Puls ships, the dossier ranking should reuse that cached label instead of a prefix stripper — decide between the two before starting either.

**Effort:** M
**Priority:** P2
**Depends on:** None (see the LLM topic label item)

### Move the hidden dev-view API dump below the dossier content

**What:** In explicit `--include-dev-view` builds, the `protocol_dev_sections` block (raw API JSON and people list; `.dev-only`) is emitted between the page header and `.layout`. Emit it after `<main>`, or — preferably, given the hosting maths — render it into a separate file loaded on demand.

**Why:** Measured on plenarprotokoll 20/103: 952 KB of hidden markup precede the Aufmerksamkeitsrang aside and the first TOP card, so on a slow connection nothing above the fold can paint until ~1 MB has streamed. Found while placing the aside's toggle script adjacent to the aside (2026-09-14). Added 2026-09-19: across 285 dossiers that is roughly 270 MB of `protocols/` (584 MB total), and the site without `data/` is 1.11 GB — the on-demand variant is the single biggest lever for getting under a 1 GB host cap (see the site-hosting TODO). Note (post-#60, v0.5.0.0): those figures were measured on a build that still emitted the dev block; ordinary publications now omit `dev-view` entirely (`--include-dev-view` refuses to write to the publication directory), so the hosting lever only applies to explicit dev builds — re-measure the public site before relying on it.

**Context:** `render_html` in `scripts/render_dip_pulse_html.py` still interpolates `{protocol_dev_sections}` before `{session_summary_sections}` and `<main>` (2026-09-19). Moving it after `</main>` changes nothing visible (it is `display:none` until toggled) but check `tests/test_render_dip_pulse_html.py::DossierLayoutTests`, which pins the order of `.dev-top-details` inside cards, and the dev-toggle script that reveals `.dev-only`.

**Effort:** S (move) / M (separate file)
**Priority:** P2 (P1 if the hosting TODO is picked up)
**Depends on:** None

### Current-TOP highlight in the ranking sidebar

**What:** Mark the TOP currently in view in the desktop sidebar (`IntersectionObserver` on `.top-card`, `aria-current="true"` on the matching `.attention-row`), optionally scrolling the row into view inside `.attention-list`.

**Why:** On 2–3 MB dossier pages the reader loses their place; the sidebar is the page map, but today it does not say "you are here".

**Context:** Hooks exist since the sidebar fix (#56, v0.2.2.0): `#attention-list` wraps the rows, `#top-{index}` ids on cards, `attention_runtime_script()` owns the toggle behaviour. No `IntersectionObserver` exists anywhere yet. Respect `prefers-reduced-motion` for any scrolling; keep the highlight off on ≤1120px where the aside is static.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Dossier h1 shows the session, "Bundestag-Puls" moves to the eyebrow

**What:** On `protocols/*.html` make the session title the `h1` and demote the product name to an eyebrow/kicker.

**Why:** Every one of the 285 dossiers has the identical `h1 "Bundestag-Puls"`; the page's actual subject is a muted 15px subtitle. Hierarchy should serve the page, not the brand (flagged in the 2026-09-13 design review).

**Context:** the `<h1>Bundestag-Puls</h1>` block in `render_html`'s page template (`scripts/render_dip_pulse_html.py`). puls.html already made this exact move in 0.3.0.0 (`header["h1"]` = "Was der Bundestag in KW … verhandelt hat" with an eyebrow; `render_front_page` in `scripts/build_dip_pulse_site.py`), so copy that pattern. Check `test_global_header.py` expectations before changing the `h1`.

**Effort:** S
**Priority:** P3
**Depends on:** None


## Puls

All five items below were gated on "puls.html week radar shipped"; that landed in 0.3.0.0 (#58, 2026-09-18), so none of them is blocked any more. None has been started (checked 2026-09-19).

### Weekday-matched Wochenvergleich when sitting counts differ

**What:** Compare the current sitting week with the previous one weekday by weekday when the two weeks have different sitting counts, instead of dividing totals by sitting count.

**Why:** Which weekday it is explains roughly 60% of how big a sitting looks (Wednesday median 163 speeches vs Friday 80). A Wednesday-only running week divided by one sitting is still compared against a Wed-Fri average, so the deltas read as movement that is really weekday mix.

**Context:** `week_comparison()` in `scripts/render_dip_pulse_html.py` normalises per sitting when counts differ. The week radar renders the Wochenpuls delta chips as "n/a" on normalised weeks and keeps the Redeanteil pp column with a caveat. Start: pair sittings by weekday (`datum` → weekday), compare the intersection, fall back to n/a when no weekday overlaps. Rewrite `test_running_week_is_labelled_per_sitting` (`tests/test_build_dip_pulse_site.py`) accordingly.

**Effort:** M
**Priority:** P3
**Depends on:** None

### "Nächste Sitzungswoche" in the puls.html header

**What:** Show the next planned sitting week from the Bundestag Sitzungskalender when the page is opened during a non-sitting week.

**Why:** The Bundestag sits about 21 weeks a year; most visits land in a non-sitting week and today the page can only say how old the last week is ("vor 13 Wochen · Auswertung vom …").

**Context:** Needs a fetch of the Sitzungskalender and a cache field; the offline rebuild must keep working without it. Header wording and placement are specified in the week-radar design doc (stale-archive state). Start: `scripts/build_dip_pulse_site.py` fetch step + `render_front_page` header.

**Effort:** M
**Priority:** P3
**Depends on:** None

### LLM five-word topic label per Tagesordnungspunkt

**What:** Generate a short neutral topic label (about five words) per TOP once, cached alongside the KI-Zusammenfassung, and use it as the radar row's headline — and as the dossier Aufmerksamkeitsrang row title (see the "Ranking row titles" item under Protokoll-Dossier, which this would supersede).

**Why:** The DIP Vorgang title is up to 200 characters and, for Antrag-only groups, the lead title is one Fraktion's slogan chosen by DIP ordering. A generated neutral label reads in five seconds and sidesteps the lead-title problem; the Vorgang title stays as the deterministic fallback.

**Context:** The summaries pipeline (`--summary-mode`) already calls an LLM per TOP with receipts; add one more field to its output. Supersedes the earlier idea of a boilerplate stripper for untitled XML headings (of 459 ranked top-5 rows in the cache, the 61 untitled ones are Einzelpläne, Regierungserklärungen and "Zur Geschäftsordnung", all already subject-first).

**Effort:** L
**Priority:** P3
**Depends on:** summary data available

### Five-reader comprehension test of the week radar

**What:** Sit five intended readers in front of the week radar and a plain weekly index of the same week; ask what happened, what changed, where they would verify it; measure correct answers and time.

**Why:** The plan verifies rendering and numbers, not whether a citizen understands the week better (Codex CEO-review challenge). The June design doc's "honest test" is the builder's own use.

**Context:** No code. Use a frozen build (`--today`/`--week`) so every reader sees the same page. Record answers per section (header, rows, Außerdem, Wochenvergleich).

**Effort:** M
**Priority:** P3
**Depends on:** None

### Week radar as data: `data/week-radar.json` and an RSS feed

**What:** Emit the radar rows (titles, shares, Fraktion split, trace, links) as JSON and as an RSS item per sitting week.

**Why:** The week's five topics reach readers without a visit; `week_topic_rows()` is already the data product, so this is a second renderer over the same rows.

**Context:** Add to `render_site()` next to the existing `data/` outputs; keep the offline rebuild path. Feed item = one sitting week; GUID = ISO week key.

**Effort:** M
**Priority:** P3
**Depends on:** None

## Fakten

Design doc: `docs/designs/fakt-der-woche.md` (office hours, 2026-09-19). The session chose Approach A (engine + two metrics + one weekly SVG card + Methodik, registry-shaped) as a **test run** of the concept; Approach A (A0 + A1, all eight metrics, weekly and monthly) shipped in v0.6.0.0. The items below are Approach B/C, the full implementation A was the test for. They are deliberately not discarded.

### Fakt der Woche, rasterize and post one card

**What:** Open a published Fakt der Woche card, rasterise it with `qlmanage` (or equivalent), and post it. The one A1 "done when" criterion that isn't code - split out on its own so it doesn't keep a fully-shipped engineering item sitting open.

**Why:** A1's design doc lists this as part of proving the cards are postable; intentionally not gated on the v0.6.0.0 ship (2026-09-24 ship decision D1: manual/promotional action, unrelated to code correctness).

**Effort:** S
**Priority:** P3
**Depends on:** A1 shipped (done)

### Fakt der Woche, publication ledger (`facts_published`)

**What:** A `facts_published` table (or a JSON file under `data/`) appended the first time a week's card is selected, preserved across online rebuilds the way roster rows are (`rebuild_database_from_entries`, `scripts/build_dip_pulse_site.py:716`), never overwritten; the week page shows "veröffentlicht als … / aktuell …" when they differ.

**Why:** A1 only promises "spätere Wochen ändern frühere Karten nicht"; data corrections and metric version bumps can still change an old card, and the changed-winners report only lands in the build log. The ledger makes a posted card reproducible forever and lets the site show its own corrections. Chosen at the eng review (D11: 11A now, ledger recorded) on 2026-09-19.

**Context:** Needs a preservation path through the rebuild (like `preserve_roster`) or a file outside the store, plus two-value rendering on the week page. Not worth building before a card has actually been posted.

**Effort:** M
**Priority:** P3
**Depends on:** A1 shipped and at least one card posted

### Fakt der Woche, Approach B: site-wide facts layer (full implementation)

**What:** On top of A1: MP-level metrics via `mp_canonical` (a TEMP table from the in-memory `canonical_by_mp_id`, as the export does, or persisted; B decides) (first speech in the Bundestag, longest speech of the WP, lone dissent against the own Fraktion; never attendance rankings), proceeding-level metrics (see Approach C), badge hooks in the dossier and MP renderers ("in dieser Woche: knappste Abstimmung der Wahlperiode", "hielt die längste Rede der 21. Wahlperiode") that read from `facts`, and an Open Discourse-compatible export view/CSV variant (their column names for `speeches`, `contributions`, `politicians`, `factions`, `electoral_terms`) so WP20/21 slots into existing notebooks. Done when every badge on a rebuilt site resolves to a `facts` row and the compatibility CSVs load in an Open Discourse notebook unchanged.

**Why:** A0/A1 prove the rule on a side page; B is the distinguishing feature on every page ("every number on this site knows how unusual it is") and the "build on my work" surface. Decided at office hours 2026-09-19: A is the test run, B is the full implementation, not discarded.

**Context:** Adding a metric is a registry entry plus a test once A's shape exists. The badge hooks touch `render_vote_summary` (`scripts/features/votes.py`) and the MP page renderer; keep the fixed Fraktion order and the "kein Redebeitrag" rule from the Plenarwatch-Lücken items. Open Discourse's `contributions` parsing is the reference for the Zwischenrufe item below. feed.json/RSS stay behind the Daten pilot gate.

**Effort:** L
**Priority:** P2
**Depends on:** A1 shipped and A0's pass criteria met

### Fakt der Woche, Approach C: proceeding-trajectory metrics and a timeline page

**What:** A third metric family over the joins (returns of a proceeding to the plenary, speech volume across its debates, final roll-call margin) with a `fakt/<year>-W<ww>.html` card that opens a per-proceeding timeline (debates → speakers → documents → votes). Done when the timeline renders for a proceeding with ≥3 plenary appearances and the card states "seit Beginn unserer Abdeckung (Januar 2022)" wherever a count is censored by the store's start date.

**Why:** Codex's lateral at office hours 2026-09-19: the joins are the asset the corpora lack, and a card that opens a story beats a number. Deferred behind A and B because it needs a bill/timeline page that does not exist and better proceeding titles (see "Ranking row titles that skip the boilerplate" under Protokoll-Dossier).

**Effort:** L
**Priority:** P3
**Depends on:** Approach B; a bill/timeline page; the ranking-title item

## Design

### DESIGN.md, tokens and a typeface decision via /design-consultation

**What:** Write a DESIGN.md (tokens, type scale, spacing, component vocabulary, focus/visited/selection rules) and decide the site's typeface. Name once the tokens individual pages had to invent, including the Daten page's light `--surface-2`/`--surface-3`.

**Why:** Every page carries its own `:root` token block and the only typeface is Inter / ui-sans-serif / system-ui; every design review re-derives the tokens and flags the default font stack. The Daten page (after the dossier) was the second page to have to invent tokens a shared system would already provide. No `DESIGN.md` exists as of 2026-09-19 (`docs/design/bundestag-pulse-design.md` is the product design doc, not a design system).

**Context:** The week-radar plan writes the radar's tokens into the plan instead. Start with `/gstack-design-consultation`; migrate per-page `:root` blocks to the shared header styles afterwards (the `:visited`/`:focus-visible` item under Daten is the first slice of that migration). Merged from two earlier entries (Daten and Design sections).

**Effort:** M
**Priority:** P3
**Depends on:** None

## Repo

### CONTRIBUTING.md

**What:** A short contributor guide with the three commands (tests, offline rebuild, update) and the `.env.local` sharp edge.

**Why:** A contributor today reads a nine-section README to find them; the `.env.local` empty-key behaviour (README §3) bites before the first fetch.

**Context:** README §2, §3, §4, §6 already hold the content; CONTRIBUTING.md is the index. Add issue templates only if outside contributions appear.

**Effort:** S
**Priority:** P3
**Depends on:** None
## Publication

### Add atomic/versioned publication promotion

**What:** Build a complete static publication in a staging directory, validate it, and atomically promote the validated version with a documented rollback path.

**Why:** The current in-place writer can leave a partial output tree after a late failure. The fixed-public release makes this safe by treating output as disposable and deployable only after exit 0 plus validation, but atomic promotion would prevent readers or deployment tooling from observing a mixed version at all.

**Context:** Start from `scripts/build_dip_pulse_site.py`, which writes many HTML/JSON files directly while SQLite alone uses temporary replacement. Design this together with the real deployment target: staging location, same-filesystem rename requirements, retained versions, cleanup, concurrent-build locking, and rollback semantics. Trigger this work when a deployment pipeline is added, the output directory is served while builds run, or concurrent writers become possible.

**Effort:** L
**Priority:** P3
**Depends on:** A concrete deployment/serving lifecycle

## Community

### Choose and document repository license and contribution governance

**What:** Make an explicit legal/product choice for the project license, contribution process, security reporting, conduct expectations, and support channel.

**Why:** A public repository without these files is difficult for outside contributors to use or redistribute confidently, even when its local developer experience is strong.

**Context:** This was identified during the developer-experience review but is deliberately separate from the fixed-public-experience migration. Begin with repository ownership and intended contribution model, obtain appropriate legal guidance for the license decision, then add the chosen `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, code of conduct, and issue templates consistently. Do not infer a license from code visibility alone.

**Effort:** M
**Priority:** P3
**Depends on:** Repository owner/legal product decision

## Plenarwatch-Lücken

Gap list against [plenarwatch.de](https://plenarwatch.de/) (Plenarwatch GbR, München; 169 posts for WP 21 as of 2026-09-19). Their counting rules live on [/methodik/](https://plenarwatch.de/methodik/); read it before touching any item below rather than re-deriving the rule here. Coverage audit of our code on 2026-09-19: their vote tallies, per-sitting summaries, MP pages and bill tracking we already have (`scripts/features/votes.py`, `summaries.py`, `mp-pages`, `bills`); everything else in their nav (Feed, Zwischenrufe, Präsenz, Muster, Bundestag, Methodik) is a gap or partial. Excluded on purpose: Telegram/YouTube/Instagram and the "Unterstützen" page (distribution, not product).

### Vote outcome badge, linked Drucksache and XLSX source on the vote panel

**What:** Each roll-call panel shows the whole-vote result ("Angenommen" / "Abgelehnt", derived from `yes_count` vs `no_count`), every entry of `document_numbers` as a link to its DIP Drucksache, and a second source link to the bundestag.de XLSX export next to the existing detail-page link. Done when all three render on every vote in an offline rebuild and a test covers a tie/abstention-heavy vote.

**Why:** `render_vote_summary` (`scripts/features/votes.py:12`) renders per-fraction tallies and a per-fraction `leading_vote` pill but never says whether the motion passed; Drucksache numbers are plain text (`votes.py:61-62`); `detail_url` is the HTML page (`roll_call_vote_url`, `scripts/validate_dip_protocol.py:584`), and `grep -rn xlsx` is empty. Plenarwatch leads every post with the badge and closes with the XLSX, and their Präsenz/Muster pages are built from that XLSX, so the link is also the receipt for items further down.

**Context:** Outcome logic is one function over `votes` columns; keep it in `validate_dip_protocol.py` next to `leading_vote` (line 564) so the store carries it. The XLSX URL pattern is visible on any bundestag.de Abstimmung page (the same page `fetch_roll_call_vote_detail`, line 711, already scrapes). Inversion of the badge for Beschlussempfehlungen is the next item, so name the column `result_raw`, never "passed".

**Effort:** S
**Priority:** P1
**Depends on:** None

### Inverted-vote reading for Beschlussempfehlungen ("Ja = Antrag ablehnen")

**What:** When the voted document is a committee recommendation to reject a motion, the panel states the reversal in one procedural sentence, prints the legend `Ja = Antrag ablehnen · Nein = Antrag annehmen`, and derives each fraction's position ("für den Antrag" / "gegen den Antrag" / "geteilt") from its `leading_vote`; raw counts stay untouched. Done when the Übergewinnsteuer-style case (plenarwatch post `ablehnung-eines-antrags-zur-uebergewinnsteuer-2026-04-24`) renders the derived positions and a test pins the inversion.

**Why:** Without the inversion the outcome badge from the previous item reads "Angenommen" on a vote whose political meaning is "Antrag abgelehnt", the single most misleading state a vote panel can be in. "Beschlussempfehlung" appears in our code only as glossary prose (`scripts/render_dip_pulse_html.py:59-188`).

**Context:** Detection signal: the DIP `vorgang`/Drucksache title of the voted document starts with "Beschlussempfehlung" and the recommendation text contains "abzulehnen"; DIP's `/drucksache` endpoint carries the title, so no PDF parsing. Store as a boolean on `votes`; render in `render_vote_summary`.

**Effort:** M
**Priority:** P1
**Depends on:** Vote outcome badge

### Votes archive across sittings (`votes/index.html`)

**What:** One page listing every roll-call vote in the store, reverse-chronological and grouped by month, each row with date, title, outcome badge, Drucksache and the procedure type; filter chips for Fraktion (majority position) and, once tags exist, Politikfeld. Done when the page is in `NAV_ITEMS` (`scripts/features/__init__.py:43-51`), gated by the `votes` feature, and lists the same count as `SELECT count(*) FROM votes`.

**Why:** Our votes are only reachable inside the sitting dossier or one MP's page; `render_votes_card` (`scripts/build_dip_pulse_site.py:2821`) aggregates the current week only. Plenarwatch's `/archiv/` (169 items, topic × Fraktion × procedure filters) is the page a reader lands on from search.

**Context:** Rows are a query over `votes` joined to `vote_fractions`; the dossier already renders the row body, so this is a second renderer over the same data, like the RSS item under Puls. Filters are client-side `data-*` attributes, no JS framework.

**Effort:** M
**Priority:** P2
**Depends on:** Vote outcome badge

### Politikfeld tags on Tagesordnungspunkte and votes

**What:** A fixed, closed list of 13 Politikfelder (Migration, Soziales, Wirtschaft & Finanzen, Energie & Klima, Verteidigung, Innere Sicherheit, Justiz, Digitales, Gesundheit, Bildung, Verkehr, Außenpolitik, Staat & Demokratie); one to three tags per TOP and vote, stored in the SQLite store and exported in the Daten CSVs; tag chips on the dossier, the votes archive and the week radar act as filters. Done when every vote in the store has ≥1 tag or an explicit `untagged` row, and the list is enforced by a test that rejects any other label.

**Why:** No taxonomy or filter exists (audit 2026-09-19); topic-level navigation is the main way plenarwatch's archive is browsed. A closed list is what keeps the LLM from inventing categories.

**Context:** Seed deterministically from DIP: `vorgang.sachgebiet` is a free field on every Vorgang the site already fetches, so map DIP Sachgebiete → the 13 fields in a lookup table and let the LLM fill only the gaps (plenarwatch: "assignment failure doesn't block publication"). Tag column on `agenda_items` and `votes`; add to `docs/data-license.md`'s export contract only after the pilot gate under Daten is decided.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Fraktionsblöcke: what each Fraktion argued, per Tagesordnungspunkt

**What:** Under every debated TOP, a block per Fraktion in the fixed order CDU/CSU, AfD, SPD, Bündnis 90/Die Grünen, Die Linke, fraktionslos (plus Bundesregierung when a minister spoke), each with up to three arguments paraphrased in indirect speech, each argument tied to a verbatim protocol quote ≤125 characters with a page anchor; a Fraktion without a speech gets the explicit line "kein Redebeitrag im Protokoll", never an empty block. Done when the order is enforced in code, every quote passes the verbatim check from the validators item, and the block renders on a full-week offline rebuild.

**Why:** Our summary is one neutral 2–3 sentence paragraph per TOP (`generate_top_summary`, `scripts/validate_dip_protocol.py:915-976`) with up to five receipt chunks; it says what was debated, never who stood where. Plenarwatch's "Was gesagt wurde" section is the part readers quote.

**Context:** The receipts pipeline already carries `speaker.fraktion`, `source_page` and 900-char chunks (`summary_source_chunks`, line 794), so the selection is a grouping over existing chunks: first verified mention per speaker, max three per Fraktion, sorted by protocol page; only the paraphrase is an LLM step. Render next to `render_llm_summary` (`scripts/render_dip_pulse_html.py:2241`), gated by `summaries`. The fixed order is a rule, never a prompt instruction.

**Effort:** L
**Priority:** P2
**Depends on:** Deterministic validators

### Deterministic validators that block LLM output before it renders

**What:** Four checks run on every generated summary/Fraktionsblock and fail the build item (falls back to "keine Zusammenfassung") when any fails: (1) vote-sum check, per-fraction `yes+no+abstain+absent == total_count` and fractions sum to the vote totals; (2) verbatim check, every quoted string is a substring of its cited chunk; (3) name check, MP surnames from `mps` appear in generated prose only inside an attributed quote; (4) link check, every generated or derived URL is well-formed and its Drucksache/protocol number matches the vote it sits under. Done when each check has a failing fixture test and the build log counts rejections per check.

**Why:** `parse_summary_response` (`scripts/validate_dip_protocol.py:846-873`) checks JSON shape and that cited chunk ids exist; nothing compares text to source, sums a vote, or looks for names. Plenarwatch lists exactly these as blocking checks on `/methodik/` and it is the basis of their "no interpretation" claim; the Fraktionsblöcke item is unsafe without (2) and (3).

**Context:** Pure functions in `validate_dip_protocol.py` next to `parse_summary_response`; (1) is independent of the LLM and can run at persist time on `vote_fractions`. Plenarwatch also splits writer and validator into two model calls with published prompts; keep that as a follow-up, the deterministic checks come first.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Fraktion seat counts in the store

**What:** A `party_seats` table (`party_id`, `wahlperiode`, `seats`, `valid_from`) filled from the mp-roster enrichment (count of roster rows per Fraktion) with a bundestag.de Sitzverteilung override; exported in the Daten CSVs. Done when `SELECT sum(seats)` for WP 21 equals the roster size and a per-seat column appears in recipe R2.

**Why:** `parties` has `id, name, created_at, updated_at` only (`scripts/persist_dip_pulse_store.py:71-76`); every per-Sitz or share-of-Fraktion number (Zwischenrufe, Präsenz, Redeanteil) needs a denominator, and the `parties.name` duplicate bug under Daten shows why it must be one clean row per Fraktion.

**Context:** Small; the roster count is already computable from `mps.party_id` once the duplicate rows are merged. Fraktionslose count as their own row.

**Effort:** S
**Priority:** P2
**Depends on:** `parties.name` holds Python-list-repr duplicates of the same party

### Zwischenrufe: parse `<kommentar>` and count reactions per Fraktion

**What:** Persist every `<kommentar>` element of the protocol XML (the parenthesised "(Beifall bei der SPD)", "(Lachen bei der AfD)", "(Zuruf des Abg. …)", "(Widerspruch …)", "(Unruhe)") as rows in a `reactions` table: sitting, speech, kind (Beifall / Lachen / Heiterkeit / Zuruf / Widerspruch / Unruhe / other), source Fraktion(en) parsed from the text, page. A `zwischenrufe.html` page then shows per-Fraktion counts with four views: absolut, kumulativ, pro Sitz, gleitender Schnitt over sittings, plus totals since a named cabinet date. Done when the reactions CSV is on the Daten page and the page's totals match a SQL recipe.

**Why:** `speech_text_and_paragraphs` (`scripts/validate_dip_protocol.py:314-322`) swallows kommentar text into the speech via `itertext()`, so the signal is already in hand but untyped and uncounted; `tests/fixtures/protocol.xml` has zero `kommentar` elements. Plenarwatch's Zwischenrufe tracker is their most-shared page.

**Context:** Element name per the Bundestag DTD `dbtplenarprotokoll.dtd` (`kommentar` inside `rede`); verify against a live cached protocol before writing the parser, since no XML is cached in `.context/` today. Fraktion attribution is a regex over a small closed vocabulary ("bei der", "bei Abgeordneten der", "des Abg."), keep an `unattributed` bucket rather than guessing. Stripping kommentar from speech text also cleans the summary chunks; note that as a side effect in the PR.

**Effort:** L
**Priority:** P3
**Depends on:** Fraktion seat counts in the store

### Präsenz: excused MPs from the protocol Anlage, participation per Fraktion over time

**What:** Parse the "Entschuldigte Abgeordnete" Anlage of each protocol into an `excused` table (sitting, mp, Fraktion), then a `praesenz.html` page with: share of each Fraktion that cast at least one roll-call vote per sitting (rolling average across WP 21), the latest vote split into abgestimmt / entschuldigt / weder noch, and the WP average. Done when every sitting with a roll-call vote has a row per Fraktion and the three buckets sum to the seat count.

**Why:** `parse_protocol_xml` (`scripts/validate_dip_protocol.py:325`) walks `sitzungsverlauf/tagesordnungspunkt` only; `grep -rni entschuldigt` is empty. Absent counts already sit in `vote_fractions`, so the page is the Anlage parser plus one query. Plenarwatch states the limit plainly ("weder noch" cannot separate absent from present-but-not-voting); copy that caveat onto the page.

**Context:** Anlage lives under `<anlagen>` in the same XML; verify the exact markup on a live protocol first (same caveat as Zwischenrufe). Sittings without a roll-call vote produce no data point, by design, say so on the page.

**Effort:** M
**Priority:** P3
**Depends on:** Fraktion seat counts in the store, Vote outcome badge

### Muster: agreement matrix, coalition patterns and Geschlossenheit

**What:** Three aggregates over all roll-call votes of WP 21: (1) Fraktion × Fraktion matrix, share of votes where both majorities voted alike (diagonal 100 %); (2) per-vote coalition pattern, which Fraktionen sided with the outcome, with "Koalition" meaning CDU/CSU + SPD; (3) Geschlossenheit per Fraktion, share of votes with a single vote value across all its members (one deviating member = "geteilt"). Ship first as three SQL recipes on the Daten page, then as `muster.html`. Done when the recipes run in the build and the page numbers equal the recipe output.

**Why:** The only adjacent metric is recipe `r3-abweichler` (`scripts/build_dip_pulse_site.py:1144-1170`), per-MP dissent counts. All three aggregates are queries over `vote_fractions`/`vote_members` that already exist; the page is a renderer.

**Context:** Recipes-first is the tracer bullet: the Daten page already executes SQL at build time and shows the result rows, so the numbers are public and checkable before any chart exists. Fraktionslose are excluded from the matrix and the coalition label, as on plenarwatch.

**Effort:** M
**Priority:** P3
**Depends on:** Vote outcome badge

### "So arbeitet der Bundestag" explainer page

**What:** A static `bundestag.html` in `NAV_ITEMS` answering, from GG and GOBT only with article/paragraph citations: who may bring a bill or motion; when the Bundestag sits (Sitzungswochen, Ältestenrat); how votes are taken (Handzeichen, Aufstehen, namentlich on request of a Fraktion or 5 %); whether MPs are bound (Art. 38 GG); what happens after a vote (three readings, Bundesrat, Vermittlungsausschuss). Done when every section cites its source and the site's existing Vorgangstyp glossary links to it.

**Why:** Our only explanatory surface is the Vorgangstyp glossary on `sources.html` (`VORGANGSTYP_GLOSSARY`, `scripts/render_dip_pulse_html.py:59-188`) and landing-page prose (`render_landing_page`, `build_dip_pulse_site.py:2742,2761`); the vote and Präsenz pages assume the reader knows what a namentliche Abstimmung is.

**Context:** Prose page, no data; write it once, link it from the vote panel's "namentlich" badge and from `bundestag.html` back to the glossary. Reference: [plenarwatch.de/bundestag/](https://plenarwatch.de/bundestag/) for the section set, GG/GOBT for the content.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Impressum and a final licence text before the site goes public

**What:** `impressum.html` (§ 5 DDG, name, address, contact) linked from every footer, and the placeholder "Die genaue Lizenzformulierung … steht noch aus" (`scripts/build_dip_pulse_site.py:6495-6499`, `docs/data-license.md` status "pending") replaced by the decided licence on `sources.html`, the Daten page and the export manifest. Done when `grep -rn "steht noch aus"` over the generated site is empty.

**Why:** Both are hard requirements the day the hosting plan under Daten ships; plenarwatch carries Impressum, Methodik and a GbR name in every footer. The licence question is already open in `docs/data-license.md`; this item ties its deadline to hosting.

**Context:** Content decision is the user's (which licence, whose name in the Impressum); the code change is a footer link and one string. Blocks the hosting item, not the other way round.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Debattenberichte: off-agenda topic mentions across a sitting week

**What:** A detector over speech text that, for a configurable term list, counts mentions per speaker, Fraktion and TOP, and emits a Debattenbericht row when a topic clears the threshold (≥10 speakers from ≥3 Fraktionen across ≥2 TOPs) while being on no TOP title; the report shows total / verified / unverified mention counts, first quote per speaker (max three per Fraktion, sorted by page) and the search terms used. Done when a fixture week with a planted off-agenda term produces exactly one report and a week without produces none ("a missing report is also a data point").

**Why:** Nothing counts topic mentions outside their TOP today (audit 2026-09-19). It is plenarwatch's distinctive post type, but a small share of their output (the Sachsen-Anhalt-Wahl report is the headline case), so it comes after the vote and Fraktion work above.

**Context:** Term list is data, not code (`data/debate-terms.json`); verification = the quote passes the verbatim validator. Reuse the Fraktionsblöcke quote-selection rule. Consider it a week-radar row type on `puls.html` rather than a new page.

**Effort:** L
**Priority:** P4
**Depends on:** Fraktionsblöcke, Deterministic validators

## Completed

### Site-wide `:visited` and `:focus-visible` rules in `global_header_styles`

**What:** Move the Daten page's `a:visited`/`.recipe a:visited`/`.file a:visited` (teal) and `a:focus-visible` outline rules (`scripts/build_dip_pulse_site.py`, Daten page CSS) up into `global_header_styles()` (`scripts/render_dip_pulse_html.py`) so every link-dense page (catalog, dossiers, MP pages) gets them too.

**Why:** Those pages have the same link-density gap the Daten page closed for itself. Checked 2026-09-19: `global_header_styles()` has neither rule; equivalents exist only on the Daten page, the radar rows and the week labels, each written locally.

**Completed:** 2026-09-25. Shared teal visited links and focus outlines; removed redundant Daten link rules, retaining control and radar/week-specific styles.

### Stop persisting `speeches.paragraphs_json`

**What:** A migration dropping the column from the live schema (duplicate of `speeches.text`, no reader in site code — the only references are the INSERT in `persist_dip_pulse_store.py` and the export-time `DROP COLUMN` in `export_distribution_data`); then remove that export-time `DROP COLUMN` since it would no longer be needed.

**Why:** Measured 2026-09-19: `paragraphs_json` is 114 MB and `text` 113 MB of a 305 MB store, so this saves roughly 37% (not "half"). The distribution copy already drops the column at export time, so the schema change is pure cleanup, not a data-loss risk.

**Context:** Three test fixtures insert into the column and need the same edit: `tests/test_build_dip_pulse_site.py` (~282), `tests/test_daten_export.py` (~144), `tests/_daten_fixture.py` (~133). `test_distribution_copy_drops_paragraphs_json_and_keeps_row_counts` becomes obsolete.

**Completed:** 2026-09-25. Removed schema/INSERT duplication; idempotent migration warns on SQLite < 3.35, and conditional export cleanup preserves legacy-store exports and row counts.

### Escape the pre-existing `index` interpolation in the dossier renderer

**What:** Wrap `item["index"]` with `esc()` at the remaining pre-existing site in `scripts/render_dip_pulse_html.py` (the `top-card` `id="top-{item['index']}"` in `render_html`; still unescaped 2026-09-19).

**Why:** Hygiene. `index` is an int from the XML validator today, so there is no exploit; the `attention_rows` href and the `top-jump` link already escape it, and the last site should match.

**Context:** Pure consistency change; add nothing else. One test asserting anchors still resolve covers it.

**Completed:** 2026-09-25. Escaped TOP card IDs; ranking anchors resolve for numeric and HTML-sensitive indices.

### `agenda_topic()`, the topic line for the Fakten cards

**What:** `agenda_topic(proceeding_title, heading)` and `strip_heading_boilerplate()` in `scripts/render_dip_pulse_html.py`: the DIP Vorgang title first, else the XML heading with its procedural opener stripped, else nothing.

**Completed:** v0.6.0.0 (2026-09-24). Spot check: 29 of the last 30 sitting weeks' longest speeches carry a topic, 27 of them from the clean Vorgang title.

### `parties.name` list-repr duplicates

**What:** `persist_sampled_people` unwraps DIP's list-valued `person.fraktion` (`unwrap_dip_faction`), and `initialize()` migrates existing stores: duplicate `parties` rows merged, `mps`, `vote_fractions` and `vote_members` repointed.

**Completed:** v0.6.0.0 (2026-09-24). On the 2026-09-19 store: 22 party rows → 15, no list reprs, no dangling `party_id`, vote counts unchanged. Residue tracked under Daten.

### Fakt der Woche, A0: read-only replay and sample cards (the test run)

**What:** `scripts/facts.py` with the metric registry, the rule as pure functions, receipts, and a `--replay N --cards DIR` entry point. No writes, no pages, no export.

**Completed:** v0.6.0.0 (2026-09-24), commit `7603e71`. Passed the five pass criteria in the design doc addendum (2026-09-20 result: Merz 6/30 failed criterion 1 on the first run, the rest passed; amendments folded into A1).

### Fakt der Woche, A1: engine in the build, pages, Methodik, export

**What:** `compute_and_store` runs on every build, snapshots `(fact_metrics, facts, fact_sources)` and writes only when the triple differs, the publication floor gates which facts post, `fakt/index.html`/`<period_key>.html`/`<period_key>-<metric_id>.svg`/`methodik.html`, the `facts` component and nav entry, the Daten export's three new CSVs and derived-data documentation.

**Completed:** v0.6.0.0 (2026-09-24), commits `decb17b`..`6449bcd`. Two of the three "done when" criteria verified (unchanged-store skip, byte-identical cards under rerun); the third (rasterise + post a card) split out below - not code, not gated on this ship.

### Fakt der Woche, four more weekly metrics

**What:** `laengste-debatte`, `laengste-sitzung`, `meiste-abweichler`, `erste-reden` - the remaining four of the six weekly metrics.

**Completed:** v0.6.0.0 (2026-09-24), commits `6aa9363`, `87cd883`.

### Fakt der Woche, the monthly post

**What:** A second period (`period_kind = 'month'`) with `aktivste-abgeordnete` and `meistdiskutierter-vorgang`.

**Completed:** v0.6.0.0 (2026-09-24), commit `6449bcd`. Verified against the real store: June 2026 = Alexander Dobrindt (40 Reden), GKV-Beitragssatzstabilisierungsgesetz (19 Reden).

### Guard external payload links with shared source validation

**What:** Route public hrefs from DIP, Bundestag, and abgeordnetenwatch payloads through shared scheme-and-host validation, with safe omission or plain-text fallback for rejected links.

**Completed:** v0.5.0.0 (2026-09-19)
