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

## Completed
