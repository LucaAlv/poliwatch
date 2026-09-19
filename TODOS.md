# TODOS

## Daten

### `parties.name` holds Python-list-repr duplicates of the same party

**What:** On the real store, `parties` has both clean rows (`'AfD'`, `'CDU/CSU'`, `'BÜNDNIS 90/DIE GRÜNEN'`, `'SPD'`, `'DIE LINKE'`, `'fraktionslos'`) and duplicate rows whose `name` is a Python list repr of the same value (`"['AfD']"`, `"['CDU/CSU']"`, `"['BÜNDNIS 90/DIE GRÜNEN']"`, `"['fraktionslos']"`, `"['Die Linke (Gruppe)']"`, `"['FDP']"`, `"['BSW (Gruppe)']"`), plus at least two rows that look like two names concatenated (`'SPDSPD'`, `'SPDCDU/CSU'`). Some `mps.party_id` foreign keys point at the dirty rows (e.g. Stephan Brandner → `"['AfD']"`, Lisa Paus → `"['BÜNDNIS 90/DIE GRÜNEN']"`).

**Why:** Found while building the Daten page's R1/R2/R3 recipes (`fraktion` column), which are the first place on the site to render `parties.name` verbatim rather than through a display helper — so this is very likely older than this branch, not introduced by it. It also means R2's "Redeanteil je Fraktion" percentages can undercount a party split across a clean and a dirty row, and any future feature that trusts `parties.name` as a display string inherits the bug.

**Context:** Almost certainly a party-name-normalization bug in `persist_dip_pulse_store.upsert_party` or a caller passing a list instead of a string (`str(["AfD"])` → `"['AfD']"`) at some point in the ingestion history; the concatenated names (`SPDSPD`) suggest a second, separate bug appending instead of matching. Needs a repro against `validate_dip_protocol`/`persist_dip_pulse_store` call sites, then a migration to merge the duplicate `parties` rows and repoint `mps.party_id`/`vote_fractions.party_id`/`vote_members.party_id`.

**Effort:** M
**Priority:** P1
**Depends on:** None

### Regenerate the architecture diagram for the Daten export step

**What:** `docs/bundestag-puls-architecture.html`/`.json` still describe `database.html` as a 12-row sample explorer with no export step. Regenerate them so the diagram shows `export_distribution_data()` between the store and `render_site`, the `data/exports/g-<hash>/` + `datenstand.json` generation switch, and the `--data-manifest` override path.

**Why:** Deferred from the fix-datenbank plan at the ship gate (2026-09-19) to keep the 0.4.0.0 PR focused; the CHANGELOG's "Known stale docs" entry discloses the gap. Deferred from plan: `~/.gstack/projects/LucaAlv-poliwatch/fix-datenbank-plan.md` (CEO task T22).

**Context:** The pipeline comment block at the top of `scripts/build_dip_pulse_site.py` (steps 1-7 and the file table) is already updated and is the source for the diagram text.

**Effort:** S
**Priority:** P1
**Depends on:** None

### Stop persisting `speeches.paragraphs_json`

**What:** A migration dropping the column from the live schema (duplicate of `speeches.text`, ~115 MB on the current store, no reader in site code — `collect_abgeordnete` and every dossier renderer read `snippet`/`char_count`/`text`, never `paragraphs_json`); then remove the export-time `DROP COLUMN` from `export_distribution_data` since it would no longer be needed.

**Why:** Halves the store size; the distribution copy already drops the column at export time, so the schema change is pure cleanup at this point, not a data-loss risk.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Site hosting plan for the 2.4 GB generated site

**What:** Make the HTML deployable under a capped static host (e.g. GitHub Pages' 1 GB limit): extend `--data-base-url`-style externalisation to `data/plenarprotokoll-*.json` (602 MB) and `data/bills.json` (386 MB), or a deploy profile that excludes `data/`, or a host without the cap.

**Why:** The Daten page and `--data-base-url` (this branch) make the *data* shippable to a public audience; the *site* itself is still 2.4 GB and cannot go to a capped host today. Both outside voices in the `/autoplan` review flagged this; the user's go/no-go framing ("ship to a larger audience in a few weeks") depends on the site being public, not only the download.

**Effort:** L
**Priority:** P1
**Depends on:** This branch (the base-URL pattern already exists for the two export files)

### Scheduled data-release workflow

**What:** A GitHub Actions workflow on a schedule: online build → export → immutable dated release tag → upload assets → `--offline` rebuild with the release's `--data-base-url` → deploy.

**Why:** The design doc's own constraint is "must stay current automatically"; `scripts/publish_dip_pulse_data.sh` (PR2, manual) is upkeep a solo maintainer will eventually miss. The user's explicit decision at the Final Gate keeps PR2 manual for now; this is the follow-up once that has been exercised a few times.

**Effort:** M
**Priority:** P2
**Depends on:** PR2 (`scripts/publish_dip_pulse_data.sh`), a `GITHUB_TOKEN` with release-upload scope as a repo secret

### Pilot gate: decide keep/remove for the Daten page

**What:** 8 weeks after the first public data release, decide keep/remove using `gh release view --json assets` download counts, any inbound question or citation, and whether the builder himself used the downloaded file for anything.

**Why:** The user's own go/no-go framing ("if it doesn't work for v1, that is not a deal breaker"); the audience ("developers and researchers") is chosen, not demand-tested, so this is the cheap way to find out without a demand study.

**Effort:** S
**Priority:** P2
**Depends on:** First public release (PR2)

### Recipe SQL copy buttons, base URL for report JSON, recipe result CSVs / DATA.md / dossier "Daten" footer link

**What:** (a) A "Kopieren" clipboard button on each recipe's SQL block. (b) Extend `--data-base-url`-style externalisation to `data/plenarprotokoll-*.json` links on `puls.html`/dossiers (folds into the site-hosting TODO above). (c) Per-recipe result CSVs, a `DATA.md` in the release, and a "Daten" link in dossier footers.

**Why:** All three were scoped out of this branch (no new script per the design doc; b is outside `build_dip_pulse_site.py`'s Daten-page blast radius; c is an Approach-C follow-up once the data path has real usage).

**Effort:** S–M
**Priority:** P3
**Depends on:** None

### DESIGN.md via `/design-consultation`

**What:** Name the site's type scale, tokens (including the light `--surface-2`/`--surface-3` this branch had to invent), and focus/visited/selection rules once, in one place.

**Why:** Every page redefines its own `:root` today; this branch is the second page (after the dossier's) to have had to invent tokens a shared system would already provide.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Site-wide `:visited` and `:focus-visible` rules in `global_header_styles`

**What:** Move this branch's `.recipe a:visited`/`.file a:visited` (teal) and `:focus-visible` outline rules up into the shared stylesheet so every link-dense page (catalog, dossiers, MP pages) gets them too.

**Why:** Those pages have the same link-density gap this branch closed only for the Daten page.

**Effort:** S
**Priority:** P3
**Depends on:** This branch (proves the rules)

## Protokoll-Dossier

### Ranking row titles that skip the "Beratung des Antrags der Abgeordneten …" boilerplate

**What:** Shorten `.attention-row` titles (and the KI-summary/lede rows that reuse `short(heading, 78)`) so the first visible words identify the topic, not the procedural prefix.

**Why:** Real TOP headings are boilerplate-first ("Beratung des Antrags der Abgeordneten Nicole Höchst, Dr. Götz Frömming, Dr. M…", "Beratung der Beschlussempfehlung und des Berichts des Ausschusses für Umwe…"). At the 78-char cut most rows in the Aufmerksamkeitsrang never reach the subject, so the ranking ranks things the reader cannot tell apart. This is also the prerequisite for any denser (one-line) row design, which two independent reviewers proposed on 2026-09-13 and which was rejected only because of this.

**Context:** Titles come from `item["heading"]` in the `attention_rows` loop of `render_html` (`scripts/render_dip_pulse_html.py`) via `short()`. Options: strip a known prefix list ("Beratung des Antrags der Abgeordneten … ", "Beratung der Beschlussempfehlung und des Berichts des Ausschusses für …", "Erste/Zweite und dritte Beratung des von der Bundesregierung eingebrachten Entwurfs eines Gesetzes …") and show the remainder, or prefer the linked Drucksache title when one exists. Keep the full heading in a `title` attribute. The puls.html radar no longer shows headings as titles (it names rows by DIP Vorgang title, heading only in `title=`), so this is dossier-only now.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Move the hidden dev-view API dump below the dossier content

**What:** In explicit `--include-dev-view` builds, the `protocol_dev_sections` block (raw API JSON and people list; `.dev-only`) is emitted between the page header and `.layout`. Emit it after `<main>` (or render it into a separate file loaded on demand).

**Why:** Measured on plenarprotokoll 20/103: 952 KB of hidden markup precede the Aufmerksamkeitsrang aside and the first TOP card, so on a slow connection nothing above the fold can paint until ~1 MB has streamed. Found while placing the aside's toggle script adjacent to the aside (2026-09-14).

**Context:** `render_html` in `scripts/render_dip_pulse_html.py` interpolates `{protocol_dev_sections}` before `{session_summary_sections}` and the layout. Moving it after `</main>` changes nothing visible (it is `display:none` until toggled) but check `tests/test_render_dip_pulse_html.py::DossierLayoutTests`, which pins the order of `.dev-top-details` inside cards, and the dev-toggle script that reveals `.dev-only`.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Current-TOP highlight in the ranking sidebar

**What:** Mark the TOP currently in view in the desktop sidebar (`IntersectionObserver` on `.top-card`, `aria-current="true"` on the matching `.attention-row`), optionally scrolling the row into view inside `.attention-list`.

**Why:** On 2–3 MB dossier pages the reader loses their place; the sidebar is the page map, but today it does not say "you are here".

**Context:** Hooks exist after the 2026-09 sidebar fix: `#attention-list` wraps the rows, `#top-{index}` ids on cards, `attention_runtime_script()` owns the toggle behaviour. Respect `prefers-reduced-motion` for any scrolling; keep the highlight off on ≤1120px where the aside is static.

**Effort:** M
**Priority:** P3
**Depends on:** Aufmerksamkeitsrang sidebar fix (branch fix-aumerksamkeitsranking)

### Dossier h1 shows the session, "Bundestag-Puls" moves to the eyebrow

**What:** On `protocols/*.html` make the session title the `h1` and demote the product name to an eyebrow/kicker.

**Why:** Every one of the 285 dossiers has the identical `h1 "Bundestag-Puls"`; the page's actual subject is a muted 15px subtitle. Hierarchy should serve the page, not the brand (flagged in the 2026-09-13 design review).

**Context:** the `<h1>Bundestag-Puls</h1>` block in `render_html`'s page template (`scripts/render_dip_pulse_html.py`). Check `test_global_header.py` expectations before changing the `h1`.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Escape the pre-existing `index` interpolation in the dossier renderer

**What:** Wrap `item["index"]` with `esc()` at the remaining pre-existing site in `scripts/render_dip_pulse_html.py` (the `top-card` `id="top-{item['index']}"` in `render_html`).

**Why:** Hygiene. `index` is an int from the XML validator today, so there is no exploit; the `attention_rows` href and the new code added in 2026-09 already escape it, and the last site should match.

**Context:** Pure consistency change; add nothing else. One test asserting anchors still resolve covers it.

**Effort:** S
**Priority:** P3
**Depends on:** None

## Puls

### Weekday-matched Wochenvergleich when sitting counts differ

**What:** Compare the current sitting week with the previous one weekday by weekday when the two weeks have different sitting counts, instead of dividing totals by sitting count.

**Why:** Which weekday it is explains roughly 60% of how big a sitting looks (Wednesday median 163 speeches vs Friday 80). A Wednesday-only running week divided by one sitting is still compared against a Wed-Fri average, so the deltas read as movement that is really weekday mix.

**Context:** `week_comparison()` in `scripts/render_dip_pulse_html.py` normalises per sitting when counts differ. The week-radar plan (docs/designs/puls-wochenradar.md) meanwhile renders the Wochenpuls delta chips as "n/a" on normalised weeks and keeps the Redeanteil pp column with a caveat. Start: pair sittings by weekday (`datum` → weekday), compare the intersection, fall back to n/a when no weekday overlaps. Rewrite `test_running_week_is_labelled_per_sitting` accordingly.

**Effort:** M
**Priority:** P3
**Depends on:** puls.html week radar shipped

### "Nächste Sitzungswoche" in the puls.html header

**What:** Show the next planned sitting week from the Bundestag Sitzungskalender when the page is opened during a non-sitting week.

**Why:** The Bundestag sits about 21 weeks a year; most visits land in a non-sitting week and today the page can only say how old the last week is ("vor 13 Wochen · Auswertung vom …").

**Context:** Needs a fetch of the Sitzungskalender and a cache field; the offline rebuild must keep working without it. Header wording and placement are specified in the week-radar design doc (stale-archive state). Start: `scripts/build_dip_pulse_site.py` fetch step + `render_front_page` header.

**Effort:** M
**Priority:** P3
**Depends on:** puls.html week radar shipped

### LLM five-word topic label per Tagesordnungspunkt

**What:** Generate a short neutral topic label (about five words) per TOP once, cached alongside the KI-Zusammenfassung, and use it as the radar row's headline.

**Why:** The DIP Vorgang title is up to 200 characters and, for Antrag-only groups, the lead title is one Fraktion's slogan chosen by DIP ordering. A generated neutral label reads in five seconds and sidesteps the lead-title problem; the Vorgang title stays as the deterministic fallback.

**Context:** The summaries pipeline (`--summary-mode`) already calls an LLM per TOP with receipts; add one more field to its output. Supersedes the earlier idea of a boilerplate stripper for untitled XML headings (of 459 ranked top-5 rows in the cache, the 61 untitled ones are Einzelpläne, Regierungserklärungen and "Zur Geschäftsordnung", all already subject-first).

**Effort:** L
**Priority:** P3
**Depends on:** summary data available; puls.html week radar shipped

### Five-reader comprehension test of the week radar

**What:** Sit five intended readers in front of the week radar and a plain weekly index of the same week; ask what happened, what changed, where they would verify it; measure correct answers and time.

**Why:** The plan verifies rendering and numbers, not whether a citizen understands the week better (Codex CEO-review challenge). The June design doc's "honest test" is the builder's own use.

**Context:** No code. Use a frozen build (`--today`/`--week`) so every reader sees the same page. Record answers per section (header, rows, Außerdem, Wochenvergleich).

**Effort:** M
**Priority:** P3
**Depends on:** puls.html week radar shipped

### Week radar as data: `data/week-radar.json` and an RSS feed

**What:** Emit the radar rows (titles, shares, Fraktion split, trace, links) as JSON and as an RSS item per sitting week.

**Why:** The week's five topics reach readers without a visit; `week_topic_rows()` is already the data product, so this is a second renderer over the same rows.

**Context:** Add to `render_site()` next to the existing `data/` outputs; keep the offline rebuild path. Feed item = one sitting week; GUID = ISO week key.

**Effort:** M
**Priority:** P3
**Depends on:** puls.html week radar shipped

## Design

### DESIGN.md and a typeface decision via /design-consultation

**What:** Write a DESIGN.md (tokens, type scale, spacing, component vocabulary) and decide the site's typeface.

**Why:** Every page carries its own `:root` token block and the only typeface is Inter / ui-sans-serif / system-ui; every design review re-derives the tokens and flags the default font stack.

**Context:** The week-radar plan writes the radar's tokens into the plan instead. Start with `/gstack-design-consultation`; migrate per-page `:root` blocks to the shared header styles afterwards.

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
## Completed

### Guard external payload links with shared source validation

**What:** Route public hrefs from DIP, Bundestag, and abgeordnetenwatch payloads through shared scheme-and-host validation, with safe omission or plain-text fallback for rejected links.

**Completed:** v0.5.0.0 (2026-09-19)
