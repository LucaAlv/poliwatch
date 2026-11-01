# TODO batch 7: puls.html outward (next Sitzungswoche, week radar as data)

Status: PLAN ONLY, not implemented. Written 2026-11-01 on `claude/todos-batching-subagents-aa0a61` (main 69ade54).
Reviews: eng review and design review, see "Review log" at the end (the plan is updated in place after each).

## Items

| # | TODO heading (TODOS.md, section Puls) | Effort | New module |
|---|---|---|---|
| 1 | "Nächste Sitzungswoche" in the puls.html header | M | `scripts/sitzungskalender.py` |
| 2 | Week radar as data: `data/week-radar.json` and an RSS feed | M | `scripts/week_radar_feed.py` |

Both items add logic in new modules. The existing big files get hook lines only (listed per file under "Conflict surface vs A3").

## Summary

Item 1 adds a small fetcher for the Bundestag Sitzungskalender. It reads the official `.ics` files linked from the calendar page and keeps a cache, `data/sitzungskalender.json`. Only an online build that persists may refresh the cache, and only when it is due. The fetch is fail-soft: an error leaves the old cache in place. `--offline` reads the cache only, and a build without the cache renders puls.html byte-identical to today.

puls.html then carries the planned Sitzungswochen from the shown week onward, embedded in the header. A tiny inline script picks the right line for the reader's date in Europe/Berlin. The fallback text without script is the same line, computed for the build date.

Item 2 adds a second renderer over `week_topic_rows()`. It writes a versioned JSON file with the newest 12 weeks (the selected week and the 11 weeks before it). It also builds an RSS 2.0 feed with one item per finished week, GUID `2026-W43`. RSS needs absolute URLs and there is no domain yet. So the renderer is built and tested now, but the build writes `feeds/week-radar.xml` only when the operator sets `BUNDESTAG_PULSE_SITE_URL`. That needs no `parse_args` change.

## What the sample fetch showed (2026-11-01)

The planning run made two content fetches through WebFetch. An earlier `curl` attempt failed at the TLS handshake ("unable to get local issuer certificate"). That was the sandbox's proxy path, not the source: the repo already fetches www.bundestag.de pages in normal builds. No third fetch was made, and the 2027 `.ics` was not fetched.

1. `https://www.bundestag.de/parlament/plenum/sitzungskalender` (index page)
   - It covers 2026 and 2027, with "Stand: 01.11.2026" and the intro sentence "Der Ältestenrat legt die Sitzungswochen fest …".
   - Each year has an HTML sub-page (`/parlament/plenum/sitzungskalender/bt2026-1084980`, `…/bt2027-1158140`), a PDF and an `.ics` "Kalenderimport":
     - 2026: `/resource/blob/1103938/Parlamentstermine_2026_ics.ics`
     - 2027: `/resource/blob/1193892/Parlamentstermine_2026_ics-1-.ics`. **The 2027 file's name says 2026.** Blob ids change per year, so the parser must discover links on the index page and take the year from the event dates, never from the URL.
   - Footer "© Deutscher Bundestag". There is no licence text on the page itself.
2. The 2026 `.ics` (as summarised by the WebFetch model, so the bytes are not verified):
   - Header: `VERSION:2.0`, `PRODID:-//ical.marudot.com//iCal Event Maker`, `X-WR-CALNAME:Sitzungswochen Deutscher Bundestag 2026`, `CALSCALE:GREGORIAN`. There is no VTIMEZONE.
   - 22 VEVENTs, all with `SUMMARY:Sitzungswoche Deutscher Bundestag`. Each has only `DTSTAMP`, `UID`, `DTSTART;VALUE=DATE:…` and `DTEND;VALUE=DATE:…`, with no DESCRIPTION.
   - One event covers one whole week, Monday to Friday. DTEND is exclusive, so the next Saturday is the end value. Example: `DTSTART;VALUE=DATE:20260112` / `DTEND;VALUE=DATE:20260117`.
   - Weeks from October 2026 on, with the start date and the exclusive end date:

     | Start | End (exclusive) |
     |---|---|
     | 2026-10-05 | 2026-10-10 |
     | 2026-10-12 | 2026-10-17 |
     | 2026-11-02 | 2026-11-07 |
     | 2026-11-09 | 2026-11-14 |
     | 2026-11-23 | 2026-11-28 |
     | 2026-12-07 | 2026-12-12 |
     | 2026-12-14 | 2026-12-19 |

   - CRLF, line folding and BOM were not visible through the summary. The parser must tolerate all three (RFC 5545 unfolding: a line that starts with a space or tab continues the previous one).

The calendar marks **weeks**, not sitting days. The page must never say "Sitzungen am …" from it. CONTEXT.md defines a Sitzungswoche as exactly this plan, so "Sitzungswoche" is the right word for the new line. The rest of the page keeps "Woche mit Sitzung" (TODOS Completed: "Say 'Woche mit Sitzung', not 'Sitzungswoche', for the reporting period").

The test fixture is **synthetic**: `tests/fixtures/sitzungskalender/` holds a small hand-written `index.html` and two `.ics` files, built from the facts above, with CRLF, one folded line and a BOM in one file. A comment line labels them synthetic, not a copy of the source. No downloaded file is committed.

## Item 1: "Nächste Sitzungswoche" in the puls.html header

### What "opened during" means on a static page

The build date (`resolve_today`: `--today`, else `SOURCE_DATE_EPOCH`, else today) decides everything the page renders today: the h1, "Woche läuft", the age line and the stale flag. A page built on Friday and read three weeks later would show a stale "next week" if the line were fixed at build time. So:

- **At build time** the page embeds every planned Sitzungswoche whose Friday is on or after the Monday of the shown week, up to the end of the cache. That is at most about 44 entries, each one preformatted.
- **At read time** an inline script takes the reader's date in Europe/Berlin and picks the line.
- **Without script** the same line is rendered for the build date. It names a concrete date range ("2.–6. November 2026"), so a stale fallback reads as visibly past, never as false.
- The script changes the new line only. The h1, the facts line and the stale flag stay as rendered, anchored by "Auswertung vom …".

### States of the line

Definitions:
- `R` is the reader's date (the build date for the fallback).
- `S` is the shown week (the page's ISO week).
- `W` is the first planned week whose Friday is on or after `R`.

| Case | Line |
|---|---|
| Cache missing or empty, or no planned week ends on or after the shown week's Monday | no line, no script, no data attribute. The page is byte-identical to today's. |
| No `W` for this `R` (R is past the last listed week) | line `hidden` (past the last listed week the list says nothing, so the page says nothing) |
| `W` is `S` and R lies within it (the page shows the running week) | line `hidden` |
| R lies within W, and W is not S (a Sitzungswoche is running, the page shows an earlier week) | „Sitzungswoche läuft: 2.–6. November 2026 (KW 45), laut Sitzungskalender" |
| R lies before W's Monday (a sitzungsfreie week, or the weekend) | „Nächste Sitzungswoche: 2.–6. November 2026 (KW 45), laut Sitzungskalender" |
| Optional clause (D4): planned weeks lie strictly between S and the week holding R | a second sentence: „Seit KW 43 lagen laut Sitzungskalender 2 weitere Sitzungswochen; sie sind hier noch nicht ausgewertet." (1: „1 weitere Sitzungswoche; sie ist …") |

Wording rules (design review DR1, DR3):
- The **date range comes first** and the KW follows in parentheses, because citizens read dates and not KW numbers.
- "Sitzungskalender" appears once, as the link to `https://www.bundestag.de/parlament/plenum/sitzungskalender` (the receipt). There is no second "Sitzungskalender ↗" link and no icon.
- Month names are written out: "2.–6. November 2026". A week across a month boundary reads "30. November – 4. Dezember 2026". The year always shows, so a stale no-JS fallback reads as visibly past.
- "ausgewertet" matches the page's own clock label, "Auswertung vom".
- Each date sits in a `<time datetime="YYYY-MM-DD">` element, the convention `week_header_facts` follows ("every date in a <time> element"). The server fallback uses `time_html`. The script builds the same elements with `createElement`/`textContent`, so it never uses `innerHTML`.

The optional clause covers a real gap: a build whose archive stops at KW 43 but is read in KW 47. It is listed as a scope decision (Open owner decisions, D4).

### Markup and script

- Markup goes under the facts line in the header, after `{undated_note}` (`render_front_page`, main line 6709):
  `<p class="next-sitting" data-sitzungswochen='[…]' data-shown-week="2026-10-19"><span data-next-sitting-lead>Nächste Sitzungswoche:</span> <span class="next-sitting-range" data-next-sitting-range><time datetime="2026-11-02">2.</time>–<time datetime="2026-11-06">6. November 2026</time></span> (KW 45), laut <a href="https://www.bundestag.de/parlament/plenum/sitzungskalender">Sitzungskalender</a><span data-next-sitting-gap></span></p>`
  The script fills the three `data-next-sitting-*` slots and leaves the link alone.
- Whenever the page carries at least one planned week (first row of the table does not apply), the `<p>`, its data and the script are always emitted. Only the `hidden` attribute and the span text differ between the states. So a page built during a running week, where the fallback is hidden, still shows the next week to a reader one week later (eng review A3).
- Each entry in the data is `{"mon": "2026-11-02", "fri": "2026-11-06", "kw": "KW 45", "start": "2.", "sep": "–", "end": "6. November 2026"}`. A month-boundary entry is `"start": "30. November", "sep": " – ", "end": "4. Dezember 2026"`. The script builds `<time datetime=mon>start</time>sep<time datetime=fri>end</time>` from those parts. Python does all the formatting, and the script only compares ISO date strings. There are no two formatters to keep in step.
- The script lives in a constant `NEXT_SITTING_SCRIPT` in the new module and goes out next to `page_scripts(features)` at the end of the page (main line 6722), the same way `RADAR_FILTER_SCRIPT` goes out.
  - It reads the reader's date with `new Intl.DateTimeFormat('en-CA', {timeZone: 'Europe/Berlin'}).format(new Date())`.
  - It sets `textContent` and `hidden`, never `innerHTML`.
  - On any exception it leaves the fallback in place.
- Style (design review DR2):
  - `.next-sitting { margin:8px 0 0; max-width:860px; font-size:15px; line-height:1.5; color:var(--muted); }`
  - `.next-sitting-range { color:var(--ink); font-weight:650; white-space:nowrap; }`
  - The muted base keeps it below the facts line in the header's order (h1, stale flag, chips, facts, next week). The date range in ink is what a scanning eye picks up.
  - It is not amber and not a chip: it is information, not a warning, and the amber flag stays reserved for "Nicht aktuell".
  - Only existing tokens are used, so the `:root[data-theme="dark"]` overrides (render_dip_pulse_html.py:627) cover dark mode with no new rule.
  - Breakpoints at 980, 700 and 460 px: the line wraps as prose, and only the date range does not break. The longest range, "30. November – 4. Dezember 2026", is about 30 characters (≈220 px at 15 px), which fits a 320 px viewport less the 14 px gutters.
  - The inline link is exempt from the 44 px target size under WCAG 2.5.8 (inline in a sentence).
  - The script runs once at load, before reading, so the line needs no `aria-live`. `hidden` removes it from screen readers too.
  - It stays visible in print.

### Module `scripts/sitzungskalender.py` (new)

- `INDEX_URL = "https://www.bundestag.de/parlament/plenum/sitzungskalender"` and `CACHE_NAME = "sitzungskalender.json"` (stored under `data/`, next to the other caches).
- `discover_ics_urls(index_html) -> list[str]`: `href`s ending in `.ics` under `/resource/blob/`, made absolute with `urljoin`. Duplicates are dropped and at most 4 are kept.
- `parse_ics(text) -> list[tuple[date, date]]`:
  - Strips a BOM, accepts CRLF or LF, and unfolds continuation lines.
  - Keeps the VEVENTs whose SUMMARY contains "Sitzungswoche", with `DTSTART`/`DTEND` as `VALUE=DATE` (or a bare `YYYYMMDD`).
  - Validates every event: start on a weekday, `end - 1 day` in the same ISO week, and `end > start`.
  - Raises `CalendarParseError` on structural garbage.
- `load_cache(output_dir) -> dict | None`: tolerant of a missing file. A damaged file gives a warning and None, and is left in place.
- `refresh_if_due(output_dir, *, now=None, fetch_html=dip.fetch_html, fetch_text=dip.fetch_text, max_age_days=7) -> None`:
  - `now` is wall-clock UTC (`datetime.now(timezone.utc)` when None). It is never the build date: `--today` and `SOURCE_DATE_EPOCH` pin the page clock, and a frozen build must not decide whether a fetch is due (eng review A1).
  - Due when the cache is missing, or its `fetched_at` is older than 7 days, or (it lacks the year after `now`, `now` is past 1 October, **and** `fetched_at` is older than 1 day). The last condition is bounded: until bundestag.de publishes next year's calendar, each online build would otherwise fetch again, 5 requests at a time (advisor review).
  - Makes 1 request for the index and at most 4 for `.ics` files (about 3 today).
  - Merges per calendar year, taking the year from the DTSTART dates.
  - A year is replaced only by a parse with at least 10 weeks, all inside that year. Otherwise the cached year stays and a warning is printed.
  - Prints the added and removed weeks to stderr, so a changed plan (a moved week) is visible in the log.
  - Writes with `dip.write_text_atomic`.
  - **Never raises on a source failure.** It catches `dip.DipError` (HTTP, network and UTF-8 decode errors from `_fetch_page`), `CalendarParseError`, `OSError` and `ValueError`. Each becomes one `warning: [sitzungskalender] …` line, and the build goes on. It does not catch bare `Exception`, so a programming error still fails the tests (eng review C2).
- Cache shape, version 1: `{"version": 1, "fetched_at": "<UTC ISO>", "source": INDEX_URL, "ics_urls": [...], "years": {"2026": [["2026-01-12", "2026-01-16"], …]}}`. Dates are stored inclusive, Monday to Friday. `fetched_at` is wall-clock time, but it is never rendered: the page derives only from `years` and `today`, so builds stay reproducible.
- `page_weeks(cache, shown_week) -> list[dict]`: the preformatted entries, Friday on or after the shown week's Monday.
- `render_next_sitting(weeks, *, shown_week, today) -> str`: the `<p>`, or `""`. Pure, so the server-side fallback and the table above can be unit-tested.

The module imports `validate_dip_protocol` as `dip` only, for `fetch_html`, `fetch_text` and `write_text_atomic`. A3 keeps those three signatures: its `_fetch_page` hunk changes the body only, and its `XmlPacer` is for dserver.bundestag.de, not www.bundestag.de.

### Hooks

- `main()`, online branch: **two lines** between `log_politikfelder_summary(database_path, vorgang_cache)` (main 13427) and `try:` / `run_data_pipeline` (13428). The guard on 13426 also requires `database_path.exists()`, so the hook gets its own:
  `if not args.no_persist:` / `    sitzungskalender.refresh_if_due(output_dir)`.
  - `--no-persist` builds write no cache. That matches `refresh_vorgang_cache`, and it keeps the online `main()` tests, which all pass `--no-persist` (`_online_argv`), off the network.
  - `--offline` never fetches.
- `render_site`: the existing `render_front_page(...)` call (main 11862–11865) gains one keyword, `sitzungskalender_cache=sitzungskalender.load_cache(output_dir)`. The `render_site` signature is unchanged.
- `render_front_page`:
  - It gains a keyword parameter `sitzungskalender_cache: dict | None = None` (signature at 6206).
  - It calls `sitzungskalender.render_next_sitting(...)` once.
  - The markup gets one interpolation after `{undated_note}` (6709) and one after `page_scripts` (6722).
  - `week_header_facts` is unchanged.

## Item 2: week radar as data

### Route for the base URL (recommendation: JSON now, RSS behind an env var)

| Route | Pro | Con |
|---|---|---|
| A. `--site-url` flag, RSS only when set | discoverable in `--help`; reusable later for canonical links and a sitemap | a `parse_args` hunk plus threading through `render_site`, right where A3 inserts `catalog_full_fetched_at` (signature and both calls), so a conflict |
| **B. JSON now. RSS renderer built and tested, written only when `BUNDESTAG_PULSE_SITE_URL` is set** | no `parse_args` or signature change; the feed is ready the day a domain exists | an env var is less visible (README documents it); promote it to a flag after A3 merges |
| C. JSON only, RSS deferred | smallest | the feed work is redone later from scratch |
| D. Atom with relative links (`xml:base`) | no domain needed | `atom:id` must still be an absolute IRI, and readers resolve relative links unreliably |

Recommendation: **B**. The variable is read inside `week_radar_feed`. It must be an absolute `https://` URL ending in `/`, or the build prints a warning and writes no RSS. The build log says `week-radar: RSS übersprungen (BUNDESTAG_PULSE_SITE_URL nicht gesetzt)`. Follow-up TODO: a `--site-url` flag once A3 has merged.

### Output location (recommendation: `feeds/`, not `data/`)

`data/` holds caches and 1.4 GB of data. Whether it deploys is unsettled: TODO "Site hosting plan for the 2.5 GB generated site" pieces (a) and (b), and "Politikfelder: findings deferred from the B3 review" item 4. A feed URL must stay put and ship with the HTML whatever happens to `data/`. So: `feeds/week-radar.json` and `feeds/week-radar.xml`. The other choice is `data/week-radar.json`, as the TODO says, next to the existing presentation JSON (`data/bills.json`, `data/abgeordnete.json`). Owner decision D2.

### Module `scripts/week_radar_feed.py` (new)

- `build_payload(entries, *, today, week, vorgang_cache, dossier_href_for, weeks_back=12) -> dict`:
  - Groups with `pulse_html.group_entries_by_week`. The selected week is `week`, else the newest, exactly like `select_pulse_week`, so a `--week` build stays frozen.
  - Takes up to 12 weeks ending at the selected week.
  - Computes `occurrences = pulse_html.vorgang_occurrences(weeks, selected)` **once**. It holds every week up to the selected one, and `topic_row` keeps only occurrences with `o["week"] < current_week` (render_dip_pulse_html.py 2135–2136), so an older week's trace comes out the same as with its own index (eng review P1). A test pins this.
  - For each week: `pulse_html.week_stats` and `week_topic_rows(..., total=stats["speech_count"], dossier_href_for=…, vorgang_cache=…)`.
  - It does not import `build_dip_pulse_site`: `dossier_href` is passed in, so there is no import cycle.
- **Whitelist projection.** Rows carry `item`, `stats`, `speakers` and `Counter` objects, and these are never dumped. Schema 1:

```json
{
  "schema_version": 1,
  "stability": "Fields are only added within schema_version 1; a rename, removal or meaning change raises schema_version. Links are relative to the site root.",
  "build_date": "2026-11-01",
  "site_url": null,
  "weeks": [
    {
      "week": "2026-W43", "label": "KW 43/2026", "monday": "2026-10-19", "sunday": "2026-10-25",
      "running": false,
      "speech_count": 409, "top_count": 31,
      "sittings": [{"dokumentnummer": "21/84", "datum": "2026-10-23", "href": "protocols/….html"}],
      "rows": [
        {
          "href": "protocols/….html#top-32", "dokumentnummer": "21/84", "datum": "2026-10-23",
          "top_index": 32, "top_id": "TOP 32 a/b", "heading": "…",
          "type_label": "Gesetzgebung · 1. Beratung · mit 2 Anträgen",
          "lead_title": "…", "equal_weight": false, "titles": ["…"],
          "procedures": [{"vorgang_id": "…", "titel": "…", "vorgangstyp": "Gesetzgebung", "vorgangsposition": "1. Beratung"}],
          "speech_count": 42, "share_percent": 10.3,
          "speeches_by_group": [
            {"fraktion": "SPD", "sprechrolle": null, "speech_count": 9},
            {"fraktion": null, "sprechrolle": "Bundesregierung", "speech_count": 3}
          ],
          "attributed_speech_count": 42,
          "trace": {"vorgang_id": "…", "first_week": "2026-W30", "first_position": "1. Beratung", "first_href": "protocols/….html#top-5", "current_position": "2./3. Beratung"},
          "has_votes": true
        }
      ],
      "question_formats": [{"heading": "Befragung der Bundesregierung", "speech_count": 116, "share_percent": 28.4, "href": "…"}],
      "unranked": [{"dokumentnummer": "21/84", "href": "protocols/….html", "count": 12}]
    }
  ]
}
```

- Field rules:
  - **Naming (design review DR7).** Keys are English snake_case like the release's columns (`speech_count`, `char_count`, `yes_count` in `scripts/data_dictionary.json`). German appears only in values and in the DIP field names the release keeps (`dokumentnummer`, `datum`, `vorgangstyp`, `vorgangsposition`, `titel`). An earlier draft mixed in `reden`, `weitere` and `namentliche_abstimmung`; they became `speech_count`, `unranked` and `has_votes`.
  - `speeches_by_group` is CONTEXT.md's "Redeanteil je Zusammenschluss". Each entry splits the label into the release's own `speeches.fraktion` / `speeches.sprechrolle` columns: a label among `derive.SPRECHROLLE_LABELS` values goes to `sprechrolle`, and everything else (fraktionslos and Unbekannt included) goes to `fraktion`. The keys follow the release's column names. The schema does **not** promise that a row equals `GROUP BY fraktion, sprechrolle` on the release. The radar counts from report JSON (`item_stats`: `xml_speech_count`, `xml_speakers` via `speaker_party`), not from the store, and "One module that counts Reden and Beiträge" is still open in TODOS. T3 gate: on the demo store, compare the per-TOP JSON counts with the SQL counts. Report any difference as a finding, never paper over it with a mapping. Add the reproducibility sentence to the `stability` note only when the counts are equal.
    - Before T3 lands, check that the release's `fraktion` values for fraktionslos and Unbekannt match the radar labels. If they do not, map them in the projection and pin that with a test.
    - The list is sorted by count descending, then by label, so the order is deterministic.
  - Counts and the week denominator are both present. `share_percent` is `round(percent(...), 1)`, the figure the page shows.
  - There are no ranks: gate D17 says the radar has no ordinals, and row order is the page's order.
  - KI summaries are left out of version 1 (generated content would need its label in every consumer). Politikfelder tags are left out of version 1 as well. Both are additive later.
  - There is no wall-clock field: `build_date` is `today`. The output is serialised with `sort_keys=False`, a fixed field order, `ensure_ascii=False` and `indent=2`.
- `render_rss(payload, site_url) -> str` uses `xml.etree.ElementTree` (stdlib). Channel:
  - title: the page title, "Bundestag-Puls · Wochenübersicht"; the product name is still open, D6
  - link: `site_url + "puls.html"`
  - `language de`
  - `lastBuildDate` from `build_date`
- Items: **finished weeks only** (`running` false). A running week's content would change under the same GUID.
  - `guid isPermaLink="false"` is `2026-W43`.
  - title (design review DR5, owner decision D9): it leads with the week's top topic, so a feed list scans, instead of repeating one sentence per week.
    - Form: „KW 43/2026: <first row's title> und N weitere Themen".
    - The first row is the one with the most Reden, the same row puls.html shows first.
    - Its title is the row's lead title, or for an equal-weight group its type label („Antrag · Beratung · 4 Anträge gemeinsam"), so no Fraktion's Antrag title is promoted (gate D16).
    - The title is cut at 90 characters with "…".
  - link: the newest sitting's dossier of that week, absolute. There is no per-week page: puls.html shows only the newest week, so linking it would be a wrong receipt.
  - description, as escaped HTML (design review DR6):
    1. The date range and the denominator: „19.–23. Oktober 2026 · 409 Reden in 31 Tagesordnungspunkten".
    2. The rows as a list: „<title> — 42 Reden · 10,3 %". Each links its TOP anchor, absolute. Equal-weight rows show the type label and their titles, as on the page.
    3. The method note from the page: „Anteil an allen 409 Reden der Woche".
    4. The source line, which meets the § 63 UrhG source duty (ADR 0003): „Quelle: Deutscher Bundestag, Plenarprotokolle 21/82, 21/83, 21/84", each linking its dossier.
    - There are no KI summaries in the feed.
  - `pubDate`: the Monday after the week, 00:00 Europe/Berlin. It is deterministic, and it is never later than the build, because an item exists only once the build date is past the week's Sunday (eng review C4).
- `write(output_dir, entries, *, today, week, vorgang_cache, dossier_href_for) -> None`:
  - Writes the JSON always, with `"weeks": []` when no dated week exists.
  - Writes the RSS only with a valid env URL. **Otherwise it deletes an existing `feeds/week-radar.xml`**, so a later build without the variable cannot leave a stale feed to be deployed (eng review A2).
  - Logs one line.

### Hooks

- `render_site`: **one call** right after the `pulse_path.write_text(...)` block (main 11861–11867), where `entries`, `today`, `week` and `vorgang_cache` are already in scope:
  `week_radar_feed.write(output_dir, entries, today=today, week=week, vorgang_cache=vorgang_cache, dossier_href_for=dossier_href)`.
- `publication_state.validate_public_output`: add `feeds/week-radar.json` and `feeds/week-radar.xml` to the scanned presentation files (main line 370–374), so the denylist runs over them.
- `import sitzungskalender` and `import week_radar_feed` go into the import block of `build_dip_pulse_site.py`, after `import release_version` (main line 118). A3's import hunks are at the stdlib block (merge-base 93/106, main 92–97).

## Files and functions touched

| File | Change |
|---|---|
| `scripts/sitzungskalender.py` | new |
| `scripts/week_radar_feed.py` | new |
| `scripts/build_dip_pulse_site.py` | 2 imports; `render_front_page` signature (+1 param), 2 interpolations, 1 helper call; `render_site` (+1 kwarg on the `render_front_page` call, +1 call); `main()` (+2 lines: guard and call) |
| `scripts/publication_state.py` | 2 entries in the presentation-file set |
| `tests/test_sitzungskalender.py`, `tests/test_week_radar_feed.py` | new |
| `tests/fixtures/sitzungskalender/` | new synthetic fixture |
| `tests/next_sitting_browser_check.js` and one line in `tests/run_bills_browser_check.mjs` | new browser check. CI runs it (`.github/workflows/ci.yml`: `node tests/run_bills_browser_check.mjs python`). Local port binding is blocked in the agent sandbox, so locally the owner runs it. |
| `README.md` §7 "Hosting the generated site elsewhere" | `feeds/`, `BUNDESTAG_PULSE_SITE_URL`, `data/sitzungskalender.json` |
| `docs/designs/puls-wochenradar.md` | a short amendment: the next-Sitzungswoche line state |

Not touched: `parse_args`, the `render_site` signature, `week_header_facts`, `render_dip_pulse_html.py`, TODOS.md, VERSION, CHANGELOG and DATA.md. The feed is not part of the release, so the codebook does not describe it; its stability note lives in the JSON and in README §7.

## Conflict surface vs A3

`git diff main...worktree-a3-plan` numbers hunks from the merge-base, about 40 lines before main. The positions below are main lines, found by grepping each hunk's context string in main.

**`scripts/build_dip_pulse_site.py`**
- Imports:
  - A3: stdlib block (`from collections import Counter`, `from zoneinfo …`), main 92–97.
  - Ours: after `import release_version`, main 118. Twenty lines apart.
- `render_front_page`, main 6199–6730:
  - A3: no hunk between merge-base 4606 (`_daten_page_styles`) and 7962 (`ingest_mdb_roster`), which is main ≈4650–8000.
  - Ours: all edits in this range. Clear.
- `render_site`:
  - A3: `+catalog_full_fetched_at` after `authoritative_catalog: bool = False,` (main 11714), and `catalog_payload(...)` replacing the catalog dict (main 11779).
  - Ours: the `render_front_page` call at 11862–11865 and one new call after 11867. The nearest is 83 lines from A3's catalog hunk. No signature change.
- `parse_args`:
  - A3: 6+ hunks.
  - Ours: none.
- `main()`:
  - A3: `roster_wahlperioden` right after `refresh_vorgang_cache(client, …)` (main 13353), and `catalog_full_fetched_at=` plus the acquisition summary at the online `render_site` call's tail (main ≈13461–13467).
  - Ours: two lines after main 13427 (`log_politikfelder_summary`), 63 lines after the first and 34 lines before the second. The offline branch (A3: `without_recorded_exclusions`, main ≈13118) is untouched.

**`scripts/publication_state.py`**
- A3: `"excluded"` in `FAILURE_CODES` (main 29–35), and the `local-path` regex in `DENYLIST` (main 357).
- Ours: the `is_presentation_json` set (main 370–374), 13 lines after A3's hunk and separated by `def validate_public_output`. Clear.

**`README.md`**
- A3: hunks at merge-base 9, 48, 104, 135, 152, 213, 278 and 362.
- Ours: §7 (main 413–424), 45+ lines after A3's last hunk.

**`docs/designs/puls-wochenradar.md`, `tests/run_bills_browser_check.mjs`**: A3 has no hunks. The new modules and tests do not exist on A3.

**`tests/test_build_dip_pulse_site.py`**: not edited. A3 edits it at 6, 92, 102 and 1260. Every new test goes in the two new files.

**Implementation-time gates**
- `git merge-tree --write-tree HEAD worktree-a3-plan` reports no conflict.
- After A3 merges first, rebase, and run the merge-tree check again on the new main.

## Tests (test first, each with the repo's `# Value: protects=… fails_when=… why_new=… seam=…` line)

`tests/test_sitzungskalender.py`:
- `parse_ics`: the synthetic fixtures with CRLF, folding and BOM; a non-"Sitzungswoche" event is ignored; a malformed DTSTART raises; a Tuesday-to-Friday week is accepted; an event that spans two ISO weeks is rejected.
- `discover_ics_urls`: a relative blob `href` becomes absolute; the "2026" filename of the 2027 file still yields 2027 weeks.
- `refresh_if_due`, with fake fetchers and an injected `now`:
  - not due: no call at all;
  - due by wall clock even when the build is frozen with `--today` (`refresh_if_due` takes no build date);
  - due: one index call and N ics calls;
  - a fetch error: cache unchanged and one warning, no raise;
  - a 3-week parse for a cached 22-week year: kept, with a warning;
  - added and removed weeks are logged.
- `render_next_sitting`: one test per row of the states table, at build dates 2026-10-28 (sitzungsfrei), 2026-11-04 (inside KW 45, shown week KW 42), the running shown week, and a date past the last listed week. Plus:
  - the month-boundary range format;
  - every date inside a `<time datetime>` element;
  - "Sitzungskalender" appears exactly once, as the link;
  - the D4 sentence in its singular and plural forms.
- `render_front_page`:
  - with `sitzungskalender_cache=None` the markup equals the call without the argument (no new bytes);
  - with a cache, exactly one `.next-sitting` and one script;
  - a running shown week: the `<p>` is `hidden` but carries the data and the script (A3).
- `main()` wiring, in the new file, with `render_site` and the fetch patched:
  - `--offline` never calls `refresh_if_due`;
  - an online `--no-persist` run never calls it.
  - The online persisting call is checked by the owner's real run: the log shows one `[sitzungskalender]` line. A unit test there would need the whole store pipeline mocked.
  - Checked 2026-11-01: no existing test reaches the online tail (main 13428) without `--no-persist`. Of the 20 `main()` calls in `tests/test_build_dip_pulse_site.py`:
    - `_online_argv` ones pass `--no-persist`;
    - the rest are offline (`load_cached_protocols` patched), exit early (`--list-capabilities`, `--include-dev-view`, a cached-input error), or patch `parse_args` and exit with 1 before `render_site` (line 2643).
    - So CI does not reach bundestag.de. Repeat this grep after A3 merges: A3 adds `tests/test_backfill.py` and others.

`tests/test_week_radar_feed.py`:
- Parity: for the selected week, the payload's row `href`s and `lead_title`/`titles` equal the radar rows in `render_front_page`'s markup on the same entries. There is one computation, `week_topic_rows`, and this test pins it.
- Whitelist: every key at every level belongs to the schema set, and nothing is a `Counter` or a raw item.
- `speeches_by_group`:
  - a Sprechrolle side such as Bundesregierung lands in `sprechrolle`, with `fraktion` null;
  - the counts sum to `attributed_speech_count`.
- RSS title: an equal-weight top row yields its type label, never one Antrag's title (D16); the title is cut at 90 characters.
- RSS description: it carries the denominator sentence and the source line naming every sitting.
- Determinism: two calls produce identical bytes; `SOURCE_DATE_EPOCH` changes `build_date` only.
- One occurrence index: each of the 12 weeks' traces equals the trace computed with that week's own `vorgang_occurrences(weeks, w)` (P1).
- RSS:
  - no env URL: no file and the log line;
  - a feed left by an earlier build is removed when the variable is unset (A2);
  - `pubDate` is never later than the build date (C4);
  - an invalid URL: a warning and no file;
  - a valid URL: the running week is absent, GUIDs are `YYYY-Www` and unique, every `link` is absolute, and the XML parses.
- `--week` freezes the payload's newest week.
- `validate_public_output` scans the two new files: a denylisted string planted in the JSON is reported.

`tests/next_sitting_browser_check.js`: the owner runs it with `node tests/run_bills_browser_check.mjs`, and CI runs it too.
- Mechanism: the runner builds one page from the seeded fixture cache, with a fixed `--today`. For each reader date it registers a `Date` override through CDP `Page.addScriptToEvaluateOnNewDocument` before loading (the script runs once at load) and reloads the page, then evaluates the check. This is more than the one runner line the radar check needed. T2 owns the runner change: a per-date loop and an injected-date helper, kept inside `run_bills_browser_check.mjs`.
- `Date` frozen at the build date: the text equals the fallback.
- At a date in a sitzungsfrei week: "Nächste …".
- Inside a later Sitzungswoche: "Laufende …".
- Past the list: the line is hidden.
- No console error.

## Check that no existing output moves

Pre-release rule: the only intended change to existing output is the new header line.

1. **Baseline determinism.** On unchanged main (69ade54), build the demo twice with a fixed clock:
   `SOURCE_DATE_EPOCH=1793404800 python3 scripts/build_demo_site.py --output-dir "$TMPDIR/base-a"` (and the same into `base-b`).
   `diff -r base-a base-b` must be empty. Name any file that differs, with the reason, before going on.
2. **Branch, no calendar cache.** The same build into `new-nocal`. `diff -r base-a new-nocal` may show only `Only in …: feeds` (and no `feed.xml` without the env var). Every HTML file, puls.html included, must be byte-identical.
3. **Branch, with the cache.** Copy the synthetic cache (as built by the fixture test) to `new-cal/data/sitzungskalender.json` before the build. `diff -r base-a new-cal` may show only `feeds/`, the cache file, and puls.html. `diff base-a/puls.html new-cal/puls.html` may show only the `.next-sitting` paragraph and the script block.
4. **Real store (owner).** Copy the output directory and run `--offline` into the copy before and after, with the same `--today`. The expected differences are the same as in steps 2 and 3. Write down the line counts in the PR.
5. Full suite: `python3 -m unittest discover -s tests` on local 3.13.2 and on uv 3.13.12 (memory: local html.parser differs from CI).
6. The merge-tree gate above.

## Open owner decisions

A global hook may answer gstack's questions. These are logged here either way, each with a recommendation.

- **D1, the RSS route and base URL.** Recommendation: route B. JSON now. RSS is built and tested, and is written only when `BUNDESTAG_PULSE_SITE_URL` is set. A `--site-url` flag follows after A3 merges.
- **D2, where the feed files live.** Recommendation: `feeds/week-radar.json` and `feeds/week-radar.xml`, because the deployment of `data/` is unsettled. The alternative is `data/week-radar.json`, as the TODO says.
- **D3, the wording and placement of the new line** (after the design review). Recommendation:
  - wording: „Nächste Sitzungswoche: 2.–6. November 2026 (KW 45), laut Sitzungskalender", and „Sitzungswoche läuft: 2.–6. November 2026 (KW 45), laut Sitzungskalender", with "Sitzungskalender" as the one link;
  - placement: under the facts line, in the muted color with the date range in ink, not amber.
  - The week-radar design doc does **not** specify this. Despite the TODO's pointer, it specifies only the stale flag's place (right after the h1), so this is new copy. Once it is approved, the plan's amendment to `docs/designs/puls-wochenradar.md` records it.
- **D4, the "noch nicht ausgewertet" sentence** (planned weeks between the shown week and the reader's week). Recommendation: include it: „Seit KW 43 lagen laut Sitzungskalender 2 weitere Sitzungswochen; sie sind hier noch nicht ausgewertet." It is the honest-gap principle, and the script computes it from the same list.
- **D5, the licence of the new source.** Recommendation: no change to ADR 0003. The page shows dates of planned weeks (facts) with a link to bundestag.de. The cache holds only dates and URLs, and nothing enters the release or its licence layers. The sources.html status list is tied to publication-manifest domains (`publication_state.SOURCE_IDS`, which A3 edits), so listing the calendar there is deferred to a TODO. The receipt is the link on the line itself.
- **D6, the feed's channel title.** The product name is open (PRODUCT.md). Recommendation: reuse the page title „Bundestag-Puls · Wochenübersicht" so a rename touches one constant.
- **D7, the feed's scope.** Recommendation:
  - 12 weeks;
  - no KI summaries and no Politikfelder tags in schema 1;
  - the RSS item link goes to the week's newest dossier, because there is no per-week page; a per-week archive page would be a follow-up.
- **D8, cache refresh.** Recommendation: refresh at most every 7 days, online persisting builds only, fail-soft.
- **D9, the RSS item title.** Recommendation: topic-led, „KW 43/2026: <top row's title> und N weitere Themen". The top row is the most-Reden row, as on the page, and an equal-weight group is named by its type label. The alternative is the fixed „Was der Bundestag in KW 43/2026 verhandelt hat", which is neutral by construction but looks the same for every item in a feed reader.
- **D10, the JSON key names.** Recommendation: English snake_case like the release's columns, with `fraktion`/`sprechrolle` split as in `speeches`. This is public wording for researchers, so the owner confirms it before schema 1 is frozen.

## Deferred (would go to TODOS.md at ship time, not edited now)

- A `--site-url` flag, after A3 merges, replacing the env var. Canonical links and a sitemap would reuse it.
- The Sitzungskalender as a source row on sources.html (D5).
- A per-week radar archive page, so RSS items get a real permalink.
- The homepage's weekly entry still shows no age (`render_landing_page`, from TODOS Completed "Staleness of the 'Aktueller Puls' week …").
- Header parts fixed at the build date (the age line, the stale flag) do not follow the reader's date. Only the new line does.
- A frozen build (`--today`/`--week`, as the "Five-reader comprehension test of the week radar" TODO asks for) still runs the script against each reader's real date, so readers on different days can see different next-week lines. For that test, build without `data/sitzungskalender.json`. Note this in that TODO at ship time (eng review A4).

## Persistence notes

- The artefacts are this file only. Nothing was written under `~/.gstack/`. Both `gstack-review-log` calls failed: `…/LucaAlv-poliwatch/claude-todos-batching-subagents-aa0a61-reviews.jsonl: Operation not permitted`.
  - Not persisted for that reason: the eng-review Test Plan artifact and the tasks JSONL. Their content is kept in the Review log section below.
  - Not generated: the design mockups (the designer's output directory is under `~/.gstack/`).
- The sample fetch results are recorded above. No downloaded file was kept in the repo. The failed curl left an empty scratch directory under `$TMPDIR`.

## Review log

### Eng review (/gstack-plan-eng-review, 2026-11-01)

This run was a subagent with no AskUserQuestion tool. Per the batch brief, every decision took the recommended option, and each is logged here and under Open owner decisions.

- The gstack upgrade prompt (1.91.176.0 → 1.91.379.0) was skipped: it is out of scope, and `~/.claude/skills` is not writable from the sandbox.
- No design doc for this branch was found by gstack's lookup. The prerequisite /office-hours offer was skipped (recommended B, standard review). The relevant design record is `docs/designs/puls-wochenradar.md`, which was read.

**Scope Challenge.** The plan touches about 13 files (2 new modules, 3 hook files, 2 new test files, 3 fixture files, 1 browser check plus its runner line, README, design doc), so the complexity gate tripped.

- Structure question: **Original arrangement** kept (auto-decided recommendation). Seven of the 13 files are tests and fixtures. The production change is 2 new modules plus a few hook lines in 3 files. Merging the two modules would couple an unrelated fetcher to the feed renderer.
- Feature cuts: none taken. RSS stays in, built but gated, and the D4 clause stays, each as an owner decision.
- Result: scope accepted as-is.

Scope findings:
- S1 (P3, 9/10): TODOS.md:312 names `data/week-radar.json`, and the plan proposes `feeds/`. Deferred to the owner as D2.
- S2 (P3, 9/10): TODOS.md:282 says the wording is "specified in the week-radar design doc". `docs/designs/puls-wochenradar.md:75-79` specifies only the stale flag ("Nicht aktuell: …", right after the h1). Recorded as D3.

Reality rows:
- `REALITY: premise-table pass 9 claims checked with receipts (render_front_page build_dip_pulse_site.py:6199, week_topic_rows render_dip_pulse_html.py:2181, fetch_html validate_dip_protocol.py:446, write_text_atomic :3142, DipError from _fetch_page :256-290, esc quote=True render_dip_pulse_html.py:398, validate_public_output publication_state.py:362, CI browser check ci.yml, no CSP in scripts/); unverified=1 (ICS bytes: CRLF/folding/BOM seen only through a model summary) docs/plans/todo-batch-7-puls-outward.md "What the sample fetch showed"`
- `REALITY: already-done pass no sitzungskalender/feeds/week-radar code on main 69ade54 (grep scripts/ tests/) TODOS.md:276,312`
- `REALITY: surface-check pass build_demo_site.py --output-dir (scripts/build_demo_site.py:121), node tests/run_bills_browser_check.mjs (ci.yml), git merge-tree --write-tree (git 2.50.1), python -m unittest discover -s tests (ci.yml)`
- `REALITY: binding-decisions pass gstack-decision-search --scope branch returned nothing; CLAUDE.md pre-release and fix-or-defer rules applied CLAUDE.md:1-9`
- `REALITY: numbers finding [measured: WebFetch summary] 22 VEVENTs, 7 weeks from Oct 2026; [estimated] ≤44 embedded weeks, 12 feed weeks, ~300k occurrence-record iterations at v1 scale; A3 line distances [measured: grep of main] build_dip_pulse_site.py:11714,11779,13353,13427,13461`
- `REALITY: deferred-asks pass TODO "Week radar as data" asks for JSON and RSS: JSON built, RSS built but gated on the base URL (D1); TODO "Nächste Sitzungswoche" fully covered TODOS.md:276-322`
- `REALITY: pr-count pass one PR (no .gstack/ship-policy.json; default one PR per wave)`

**Section 1, Architecture**

- `[P2] (confidence: 8/10) docs/plans/todo-batch-7-puls-outward.md (refresh_if_due(today=build_today)), build_dip_pulse_site.py:5651 "def resolve_today(value … ) -> date: The build date: an explicit value, else SOURCE_DATE_EPOCH"`
  - **A1.** The due check was keyed on the build date, so a frozen `--today` build could fetch forever or never.
  - Disposition: **accepted**. The due check now uses wall-clock `now`.
- `[P2] (confidence: 8/10) plan write() (RSS only when env set)`
  - **A2.** A build without the variable left an older `feed.xml` in place, and that stale feed would be deployed.
  - Disposition: **accepted**. `write()` deletes it.
- `[P2] (confidence: 7/10) plan states table "W is S … line hidden"`
  - **A3.** The table was ambiguous. If the hidden case emitted nothing, a page built during a running week could never show the next week later.
  - Disposition: **accepted**. Data and script are always emitted when planned weeks exist, and only `hidden` and the text vary.
- `[P3] (confidence: 7/10) TODOS.md:300-310 five-reader test needs a frozen build`
  - **A4.** The script follows the reader's real date, even on a frozen build.
  - Disposition: **deferred**. It is noted under Deferred.

Failure scenario per new path:
- Calendar fetch: bundestag.de is down or returns a bot challenge. `_fetch_page` raises `DipError`, which becomes a warning, and the cache is kept. Covered by a test.
- A changed index layout yields no `.ics` links. The plan treats that as a parse failure: a warning, and the cache is kept. Covered by a test.
- Feed write: a hosting or deploy profile drops `feeds/`. That is D2.

**Section 2, Code quality**

- `[P2] (confidence: 8/10) plan "Markup and script" (render_next_sitting in Python + NEXT_SITTING_SCRIPT in JS)`
  - **C1.** The states table is implemented twice.
  - Disposition: **accepted as is**. A no-JS fallback needs the server copy. Both copies sit side by side in `sitzungskalender.py`, Python preformats every string so the JS only compares ISO dates, and the browser check asserts that the JS and the fallback agree at the build date and in every state.
- `[P3] (confidence: 7/10) validate_dip_protocol.py:261-290 (_fetch_page raises DipError for HTTP, OSError and decode)`
  - **C2.** "Never raises" would have meant a bare `except Exception`.
  - Disposition: **accepted**. Named exceptions only.
- `[P3] (confidence: 6/10) plan kwarg sitzungswochen= receives the whole cache dict`
  - **C3.** The name did not match what it carries.
  - Disposition: **accepted**. Renamed to `sitzungskalender_cache`.
- `[P3] (confidence: 7/10) plan pubDate "Monday after, 06:00"`
  - **C4.** The date could be later than a build made early on Monday.
  - Disposition: **accepted**. It is now 00:00.
- Shared code: `dip.fetch_html`, `dip.fetch_text`, `dip.write_text_atomic`, `pulse_html.week_topic_rows`, `group_entries_by_week`, `week_stats` and `vorgang_occurrences` are all reused. No new shared helper is proposed. The base-URL check is not shared with `--data-base-url`'s validator (build_dip_pulse_site.py ~12221), because importing it from the new module would create an import cycle, and the rule here is stricter (https only, trailing slash).

**Section 3, Tests**

```
CODE PATHS                                              USER FLOWS
[+] scripts/sitzungskalender.py                         [+] Reader opens puls.html in a sitzungsfreie week
  ├── parse_ics  CRLF/fold/BOM/filter/invalid           │   ├── [★★★ PLANNED] JS "Nächste …" (browser check)
  │   [★★★ PLANNED] test_sitzungskalender               │   └── [★★★ PLANNED] no-JS fallback (render test)
  ├── discover_ics_urls  relative, 2027-named-2026      [+] Reader inside a later Sitzungswoche
  │   [★★ PLANNED]                                      │   └── [★★ PLANNED] "Laufende …" (browser + render)
  ├── refresh_if_due  due/not-due/error/shrink/log      [+] Reader past the last listed week
  │   [★★★ PLANNED] fake fetchers, injected now         │   └── [★★ PLANNED] line hidden
  └── render_next_sitting  every state row              [+] Page built during a running week, read later
      [★★★ PLANNED]                                     │   └── [★★ PLANNED] hidden fallback, JS shows next (A3)
[+] scripts/week_radar_feed.py                          [+] Feed reader subscribes
  ├── build_payload  parity/whitelist/determinism       │   ├── [★★★ PLANNED] finished weeks only, unique GUIDs
  │   [★★★ PLANNED]                                     │   └── [★★ PLANNED] stale feed removed when unset (A2)
  ├── render_rss  absolute links, XML parses            [+] Operator: offline rebuild, no cache
  │   [★★★ PLANNED]                                     │   └── [★★★ PLANNED] byte-identical HTML (demo diff)
  └── write  JSON always, RSS gated                     
[+] build_dip_pulse_site.py hooks
  ├── main(): offline / no-persist never fetch [★★ PLANNED]
  └── main(): online persist fetches [GAP: owner real run, log line; unit test needs the full store mocked]
[+] publication_state.validate_public_output scans feeds [★★ PLANNED]

COVERAGE (planned): 15/16 paths | GAPS: 1 (online persisting fetch call, owner-run check)
```

Test plan (it would normally go to `~/.gstack/projects/…`, which is not writable from this sandbox, so it is kept here):
- Affected pages:
  - `puls.html` header: the new line in each state, with and without JS.
  - `feeds/week-radar.json` and `feeds/week-radar.xml`.
- Key interactions: the line text at the reader's date in Europe/Berlin; Sitzungskalender link opens bundestag.de.
- Edge cases:
  - a week across a month boundary;
  - a reader past the list;
  - a running shown week;
  - a missing or damaged cache;
  - the 2027 file named "2026";
  - a feed URL without a trailing slash.
- Critical path: offline rebuild without network or cache is byte-identical, `Value: protects=pre-release rule (no output moves); fails_when=a hook writes bytes without a cache; why_new=new hooks in render_front_page; seam=none; no_claim=real-store output (owner step 4)`.
- Tests to retire: none.
- Pending decisions: none on tests.

**Section 4, Performance**

- `[P3] (confidence: 8/10) render_dip_pulse_html.py:1676-1689 (vorgang_occurrences walks every week ≤ current) and :2135-2136 ("earlier = [o for o in occurrences.get(vorgang_id, []) if o["week"] < current_week]")`
  - **P1.** Computing the index once per feed week costs 12 passes over the archive. At v1 scale that is about 25k items, so about 300k record iterations [estimated].
  - Disposition: **accepted**. Compute it once for the selected week. Equivalence is pinned by a test.
- The fetch costs 1 + at most 4 requests to www.bundestag.de, at most once every 7 days, only on online persisting builds. It does not share dserver's `XmlPacer` budget. If it ever overlaps an A3 backfill run, that adds at most 5 requests.

**Outside voice:** skipped. This is a subagent run with network-restricted Bash, and the account has hit session limits on parallel model runs before (memory: ship-subagent-budget).

**NOT in scope:**
- A `--site-url` flag, until A3 merges.
- A sources.html row for the calendar: it goes through the `publication_state.SOURCE_IDS` domains that A3 edits.
- A per-week archive page.
- A Sitzungstage parse from the PDF or HTML.
- KI summaries and Politikfelder tags in the feed.

**What already exists:**
- `week_topic_rows` is the radar's one computation, and the feed reuses it.
- `dip.fetch_html` and `dip.fetch_text` give retry and error typing.
- `write_text_atomic`.
- The pattern of an inline script with a no-JS fallback (`RADAR_FILTER_SCRIPT`, build_dip_pulse_site.py:6069), and its browser-check harness (`tests/radar_browser_check.js`).

**Failure modes:**
- The calendar fetch fails: a warning, the cache is kept.
- A partial calendar parse: rejected for that year.
- The cache is missing: no line.
- The env var is unset: no feed, and the old feed is removed.

None is silent and untested, so there are 0 critical gaps.

**Parallelization:** two lanes.
- Lane A: `sitzungskalender.py` and its hooks.
- Lane B: `week_radar_feed.py` plus the `publication_state` entry.

Both add one line each to `render_site` and the imports of `build_dip_pulse_site.py`, so run them sequentially in one branch. That is cheaper than coordinating two worktrees over one 13k-line file.

**Implementation tasks**
- [ ] T1 (P2, human ~3h / CC ~20min): sitzungskalender: parser, discovery, refresh_if_due with wall-clock `now`, named exceptions. Files: `scripts/sitzungskalender.py`, `tests/test_sitzungskalender.py`, `tests/fixtures/sitzungskalender/`. Verify: `python -m unittest tests.test_sitzungskalender`.
- [ ] T2 (P2, human ~3h / CC ~20min): next-sitting line, render plus script (A3: always emit when there are weeks), and the browser check. Files: `scripts/sitzungskalender.py`, `build_dip_pulse_site.py` (`render_front_page`, `render_site` call), `tests/next_sitting_browser_check.js`, `tests/run_bills_browser_check.mjs`. Verify: the browser check, plus demo diff steps 2 and 3.
- [ ] T3 (P2, human ~3h / CC ~20min): week_radar_feed: payload (one occurrence index), RSS (pubDate 00:00, stale removal), publication_state scan. Files: `scripts/week_radar_feed.py`, `scripts/publication_state.py`, `tests/test_week_radar_feed.py`. Verify: `python -m unittest tests.test_week_radar_feed`.
- [ ] T4 (P2, human ~30min / CC ~5min): the main() hook and the README §7 and design-doc amendments. Verify: `git merge-tree --write-tree HEAD worktree-a3-plan`, then the full suite.

### Design review (/gstack-plan-design-review, 2026-11-01)

This was a subagent run with no AskUserQuestion. Each finding took the recommended option, and the public-wording ones are also listed as owner decisions D3, D4, D9 and D10.

- Mockups were skipped. The gstack designer writes under `~/.gstack/projects/…/designs/`, and the sandbox does not allow writes there. Outside design voices were skipped as well (subagent run, no network).
- There is no DESIGN.md (TODOS "DESIGN.md, tokens and a typeface decision via /design-consultation"), so alignment was checked against puls.html's own tokens (`--ink`, `--muted`, `--amber`, the dark overrides at render_dip_pulse_html.py:627) and the header's existing classes.
- Initial design completeness: **6/10**. The states and the no-JS fallback were specified. Missing were emphasis within the header, the date-element convention, the doubled link wording, wrapping on narrow screens, the feed item's scan value, and naming consistency with the release.
- After the fixes: **9/10**. The remaining point is that the wording is unconfirmed by the owner (D3, D4, D9, D10) and was not looked at in a rendered page. Rendered checks are the owner's: local port binding is blocked here.

Passes:
1. **Information architecture (7 → 9).** The header order is h1, stale flag, chips, facts, next week. The new line ranks below the facts line: it is context for "when does this page get new content", not the week's identity.
   - DR2: muted base with an ink date range, not amber and not a chip. **Accepted.**
2. **States (8 → 9).** All states are covered by the states table. A3 from the eng review (data always emitted) is reused.
   - DR4: the D4 sentence was reworded to the page's own "ausgewertet" vocabulary, and its singular form was specified. **Accepted.**
   - Empty state: no cache means no line at all. The page makes no claim it cannot source, which is right for principle 2.
3. **Journey (6 → 9).** A visitor in a sitzungsfreie week (most visits, per the TODO's 21-of-52 figure) now learns when new content comes, and a visitor reading an outdated build learns how far behind it is (D4). A feed subscriber sees one topic-led item per finished week.
   - DR5: the RSS title leads with the top topic. **Accepted**, as D9.
4. **AI slop risk (9).** One sentence of text, with no card, badge, icon or decorative arrow. The "↗" from the draft was dropped (DR1). No issues beyond that.
5. **Design system alignment (6 → 8).** No DESIGN.md exists. Only existing tokens are used, so dark mode is inherited.
   - DR3: every date in `<time datetime>`, matching `week_header_facts`. **Accepted.**
   - DR7: JSON keys in English snake_case, with `fraktion`/`sprechrolle` as in the release's `speeches` table. **Accepted**, as D10.
6. **Responsive and accessibility (6 → 9).**
   - DR2: `white-space:nowrap` on the date range only. The longest range (≈220 px) fits a 320 px screen less its gutters. The 980, 700 and 460 px breakpoints need no new rule.
   - The inline link is exempt from target size (WCAG 2.5.8).
   - No `aria-live` (the text is set at load), and `hidden` covers screen readers. **Accepted.**
7. **Unresolved decisions.** D3, D4, D9 and D10 are recorded under Open owner decisions. DR1 (date first, one link) and DR6 (RSS description with denominator, method note and source line) are **accepted**.

NOT in scope (design):
- a DESIGN.md (separate TODO);
- making the header's build-date parts (age line, stale flag) follow the reader's date;
- an "external link" icon convention, since the site has none today.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Review | none | Independent 2nd opinion | 0 | skipped | subagent run, network-restricted sandbox |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN (not persisted to log) | 9 issues, 0 critical gaps; 8 accepted into plan, 1 deferred |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | ISSUES OPEN (not persisted to log) | score: 6/10 → 9/10, 7 decisions (auto-decided to recommendation) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:** eng and design outside voices skipped (subagent run, network-restricted sandbox, account session limits on parallel model runs). Missing coverage, not a pass.
- **VERDICT:** No review is CLEAR. Eng and design findings are folded into the plan, and the owner decisions below are open. eng review required (re-run once the owner has answered D1–D10).

**UNRESOLVED DECISIONS:**
- D1–D10 under "Open owner decisions" were auto-decided to the recommendation (no AskUserQuestion in this subagent run); the owner confirms or overrides each.
- The `gstack-review-log` writes for both reviews failed (`~/.gstack/…reviews.jsonl: Operation not permitted`, sandbox), so neither review is on the gstack dashboard.
