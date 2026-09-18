# TODOS

## Protokoll-Dossier

### Ranking row titles that skip the "Beratung des Antrags der Abgeordneten …" boilerplate

**What:** Shorten `.attention-row` titles (and the KI-summary/lede rows that reuse `short(heading, 78)`) so the first visible words identify the topic, not the procedural prefix.

**Why:** Real TOP headings are boilerplate-first ("Beratung des Antrags der Abgeordneten Nicole Höchst, Dr. Götz Frömming, Dr. M…", "Beratung der Beschlussempfehlung und des Berichts des Ausschusses für Umwe…"). At the 78-char cut most rows in the Aufmerksamkeitsrang never reach the subject, so the ranking ranks things the reader cannot tell apart. This is also the prerequisite for any denser (one-line) row design, which two independent reviewers proposed on 2026-09-13 and which was rejected only because of this.

**Context:** Titles come from `item["heading"]` in the `attention_rows` loop of `render_html` (`scripts/render_dip_pulse_html.py`) via `short()`. Options: strip a known prefix list ("Beratung des Antrags der Abgeordneten … ", "Beratung der Beschlussempfehlung und des Berichts des Ausschusses für …", "Erste/Zweite und dritte Beratung des von der Bundesregierung eingebrachten Entwurfs eines Gesetzes …") and show the remainder, or prefer the linked Drucksache title when one exists. Keep the full heading in a `title` attribute. Check the puls.html lede (`build_dip_pulse_site.py` ~2241) uses the same helper.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Move the hidden dev-view API dump below the dossier content

**What:** On `protocols/*.html` the `protocol_dev_sections` block (raw API JSON, people list; `.dev-only`, hidden unless the Dev-Ansicht Baustein is on) is emitted between the page header and `.layout`. Emit it after `<main>` (or render it into a separate file loaded on demand).

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

### Guard the remaining external hrefs with `safe_href`

**What:** Route every href taken from DIP or abgeordnetenwatch payloads through `safe_href()` the way v0.2.3.0 did for the PDF/XML source links: MP profile URLs (`profile["url"]`, `mp["profile_url"]`), roll-call `vote.get("detail_url")`, linked-document `doc.get("url")` and event `event.get("url")` sinks in `scripts/render_dip_pulse_html.py` and `scripts/build_dip_pulse_site.py`.

**Why:** Same trust-boundary class as the links guarded in 0.2.3.0: `esc()` escapes quotes but does not stop a `javascript:` scheme, and these values come from upstream APIs. Real data is all https today, so this is defence in depth, not a live bug.

**Context:** Flagged by the 0.2.3.0 adversarial review as out of that PR's scope. `safe_href()` returns None for non-http(s) values; each sink needs a plain-text fallback. One negative test per sink, mirroring `DossierSourceLinkTests` and `SourceLinkGuardTests`.

**Effort:** S
**Priority:** P2
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
**Depends on:** summaries Baustein; puls.html week radar shipped

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

## Completed
