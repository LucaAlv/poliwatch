# TODOS

Reassessed against the code, the live store and the generated site on 2026-09-19 (after PR #59, v0.4.0.0; rebased onto PR #60, v0.5.0.0). Nothing below is done; corrections from that pass are inline. The Daten section was re-checked against the code and the 2026-09-19 store on 2026-09-24 (database state review): five findings, four new open items and a Python version floor now completed; `protocol_acquisition` raised to P2.

## Daten

### Take namentliche Abstimmungen from the official XLSX instead of the chart markup

**What:** `parse_roll_call_list_page()` / `parse_fraction_votes()` (`scripts/validate_dip_protocol.py`) read `data-chart-values` from bundestag.de HTML: four numbers (Ja, Nein, Enthaltung, nicht abgegeben) summing to the seat count, and `vote_counts_from_csv` keeps only the first four numbers it finds. The Bundestag also publishes one XLSX per namentliche Abstimmung (list: `/ajax/filterlist/de/parlament/plenum/abstimmung/liste/462112-462112`, e.g. `https://www.bundestag.de/resource/blob/1217428/20260925_3-xls.xlsx`) with columns `Wahlperiode, Sitzungnr, Abstimmnr, Fraktion/Gruppe, Name, Vorname, Titel, ja, nein, Enthaltung, ungültig, nichtabgegeben, Bezeichnung, Bemerkung`. Ingest that instead (or alongside), store ungültig as its own Stimme value and keep Bemerkung.

**Why:** Ungültig is an official Stimme value we cannot represent; if it ever occurs, the chart numbers either hide it or shift it into another category, silently. Bemerkung gives the stated reason for some uncast Stimmen (30 most recent votes, 2026-09-25: "gesetzlicher Mutterschutz" 42×, "Geburt eines Kindes" 1×), which the site could show next to "nicht abgegeben". The XLSX also carries Sitzungnr/Abstimmnr, a sturdier join to the Sitzung than matching by date.

**Context:** Sample of 30 XLSX files (18,895 Stimmen) had zero ungültig, so today's counts are not wrong in practice; this is about not being able to tell. HTML scraping of the filterlist also breaks whenever bundestag.de changes its markup.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Parse the "Entschuldigte Abgeordnete" appendix of each Plenarprotokoll

**What:** Every Plenarprotokoll XML has an `<anlage>` headed "Entschuldigte Abgeordnete" (confirmed in 21/84) listing the MdBs excused for that Sitzung. Parse it into a per-Sitzung, per-MdB table and show "entschuldigt" next to a Stimme "nicht abgegeben" where it applies.

**Why:** It is the only published statement about an MdB's absence (CONTEXT.md: entschuldigt). Without it the site can only say "nicht abgegeben", which readers may still read as skipping the vote.

**Context:** Needs the Person identity merge to map listed names to MdBs (the appendix gives names and Zusammenschluss, check whether it carries redner ids). Never derive "anwesend" from it: not being excused does not mean present.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Persist per-sitting acquisition state in the store (`protocol_acquisition`)

**What:** A `protocol_acquisition(protocol_id, component, state, fetched_at)` table written at persist time from each report's acquisition states (votes: `acquisition_state` as consumed by `render_vote_summary`; XML parsed or not; AI summaries), exported with the Daten CSVs; the facts engine and the Daten page read it instead of re-deriving it.

**Why:** The store cannot tell "no roll-call vote happened" from "votes were not fetched"; the state lives only in the report JSON. The facts engine (A1) gates week completeness from the in-memory `entries` and A0's replay re-derives the same map from the cached JSON, so two derivations of "complete" exist and can drift, and the download keeps a silent gap. Chosen at the eng review 2026-09-19 (D10: gate from entries now, schema later; D17: record).

**Context:** Needs a stable state vocabulary per component (`complete`, `partial`, `failed`, `not_requested` already exist for votes in `scripts/features/votes.py`). Natural B / Daten-pilot item.

**Update 2026-09-24 (v0.6.0.0 ship, adversarial review):** the D10 gap this item exists to close now has a concrete repro. `week_is_complete()` (facts.py) only iterates `week.protocols` - the protocols actually present in the store - so a sitting whose dossier fetch fails (`build_dossiers_with_progress`'s `dip.DipError` -> `continue` path, a real path, not synthetic) is invisible to the completeness check rather than failing it. Repro: seeding 1 of several expected sittings for a period yields `complete=1, publishable=1`. Self-heals once the missing sitting is later acquired (`compute()` recomputes fully every build), but a wrong winner can publish and poison later baselines before that happens. Flagging the repro here in case it changes the priority math — see the database state review update below, which raises this to P2.

**Update 2026-09-24 (database state review):** raised to P2. Since A1 shipped, the facts engine publishes on every build, so this is now a live path to a wrong published card, not a hypothetical. A cheaper first slice than the full table: have `build_dossiers_with_progress` record the protocol ids it skipped on `dip.DipError`, and make `week_is_complete()` fail any week containing one.

**Update 2026-09-29 (fix-votes-completeness):** the repro above is fixed. Facts periods are judged against the DIP catalog (`facts.sitting_gaps`, `period_gaps`), so a sitting whose dossier failed or was never built keeps its period incomplete, and reports without acquisition metadata count as unknown. What remains for this item is the duplicate derivation of "complete" (build entries vs the cached JSON) and the silent gap in the Daten download, so priority drops to P3.

**Effort:** M
**Priority:** P3
**Depends on:** None (A1 works without it)

### Roll-call member rows link to external profiles, never to our own MP pages

**What:** In `render_vote_summary` (`scripts/features/votes.py`, member rows), link each member to their `/abgeordnete/<id>.html` page when `mp_lookup`/`canonical_by_mp_id` resolves them. Fall back to the external `profile_url` only when no page exists.

**Why:** Today the member name always links to `member["profile_url"]` (bundestag.de or abgeordnetenwatch), even though `upsert_mp` resolves every vote member to an internal `mp_id` at persist time. A reader on a vote panel can't reach the site's own MP page, which is the page that pools that person's speeches and votes.

**Context:** Speaker names in dossiers already link internally via `mp_lookup` (rerun of `write_report_files` after the roster step in `main()`), so reuse that path. Found in the 2026-09-24 database state review. Not previously tracked.

**Effort:** S
**Priority:** P2
**Depends on:** None (better after the `parties.name` item, which improves how many vote members merge)

### Document `--protocol-wahlperiode` in the README

**What:** Add `--protocol-wahlperiode` to the README's update/backfill section. Say plainly that when `--limit N > 0` is set, the catalog fetch is limited to WP 21 unless `--protocol-wahlperiode 0` is passed.

**Why:** The flag's help text says so (`scripts/build_dip_pulse_site.py:9235`, applied in `fetch_protocols` at :309), but the README never mentions it (`grep -c wahlperiode README.md` = 0). Someone doing a bounded backfill of WP 20 by following the README gets WP 21 only, with no warning. Originally noted as Task 2 of `docs/audit-remediation-plan.md` (2026-08-18) and never moved here.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Line-by-line audit of the ingestion modules

**What:** Review `scripts/validate_dip_protocol.py` (XML parsing, roll-call scraping, DIP enrichment) and `scripts/abgeordnetenwatch.py` line by line, adding fixture tests for every parse branch that has none. Include the roll-call `fetch_html` path, which has a 60 s timeout but no retry/backoff, unlike `ApiClient.get_json`.

**Why:** `docs/audit-remediation-plan.md` (2026-08-18, "fog of war", Task 8) named these two modules, then at 56% and 40% coverage, as never audited, and they do all the acquisition and identity work. The `SPDSPD` doubled-`<redner>` bug under `parties.name` is the kind of source quirk such an audit finds. No evidence it was done, and it was never mirrored here.

**Effort:** M
**Priority:** P3
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

### Recipe result CSVs and `DATA.md`

**What:** Per-recipe result CSVs and a `DATA.md` in the release.

**Why:** Scoped out of PR #59 as an Approach-C follow-up once the data path has real usage. This item used to also cover a "Kopieren" clipboard button on each recipe's SQL block and a "Daten" link in dossier footers; both shipped in v0.6.6.0 (2026-09-26), leaving only the CSV/`DATA.md` half open. The other former part of this item, externalising `data/plenarprotokoll-*.json` links, moved into the site-hosting TODO above.

**Effort:** S–M
**Priority:** P3
**Depends on:** None

### Validate remote-manifest recipes before showing their SQL

**What:** `validate_manifest` checks `recipes[]` only for a string `id` and a list `rows`; `render_daten_recipes` then shows each recipe's `title` and `sql` straight from the manifest (`build_dip_pulse_site.py`, `manifest["recipes"]` loop), and an unknown id silently gets `{}` from `RECIPES_BY_ID`. Reject unknown recipe ids, and either take `title`/`sql` from the local `RECIPES` by id or require the manifest's SQL to match it. Done when a manifest with an unknown id or altered SQL fails validation with a clear error.

**Why:** Found by the adversarial review of the recipe "Kopieren" button (2026-09-26). HTML escaping already stops XSS, but a tampered or mistaken remote `--data-manifest` could present any text as SQL, including sqlite3 dot-commands such as `.shell`, and the copy button makes pasting it one click. The gap predates the button; only reachable through an explicit remote manifest.

**Context:** Choosing between "pin to local" and "verify equal" touches the manifest contract: a newer remote export may legitimately ship newer recipe SQL whose `rows` no longer match the local SQL.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Recipe copy: compare the selection by range, not by text

**What:** `recipe_copy_runtime_script` (`build_dip_pulse_site.py`) now guards both the success and rejection handlers with `copy !== latestCopy` (fixed in b6e1f8a), but the rejection's "did the reader select something else" check still compares the selection's text. Selecting *identical* text in another recipe passes that comparison, so a late rejection still replaces that selection with its own SQL. Compare the selection's range endpoints instead of its text. Done when a rejection that settles after the reader selected matching text elsewhere leaves that selection alone.

**Why:** Final-round Codex review of v0.6.6.0 (2026-09-26), reproduced with controlled promise settlement. Deferred per the ship's review-round limit; the common cases (rejection with nothing in between, newer click, different selection) are fixed and verified live.

**Effort:** S
**Priority:** P3
**Depends on:** None


### Credit a Zwischenfrage to the MdB who asked it, and keep Gastansprachen out of speech counts

**What:** A Rede's stored text is now only its Redner's (Sitzungsleitung and Zwischenfragen no longer leak in). Two things are left. (1) The words of an MdB who asks a Zwischenfrage (a `<p klasse="redner">` with another `redner id` inside the `<rede>`) are dropped, not stored: credit them to the asker as a Zwischenfrage of their own (CONTEXT.md: Zwischenfrage). `speech_text_and_paragraphs` (`scripts/validate_dip_protocol.py`) already walks the segments; it only returns the Redner's. (2) Detect Gastansprachen (CONTEXT.md: shown with the Sitzung, never counted as a Rede) and keep them out of speech counts.

**Why:** Zwischenfragen are still counted for nobody, so an MdB who mostly asks questions shows fewer contributions than they made. Gastansprachen still count as Reden.

**Context:** Measured on the 2026-09-29 store: 55 Zwischenfrage blocks in 8 sittings, all followed by the Redner's own marker or by a Präsident `<name>`; no text had an undeterminable speaker (`speeches.unattributed_char_count` is 0 everywhere). Kurzinterventionen and the Befragung/Fragestunde are their own items (#68, #70).

**Effort:** M
**Priority:** P3
**Depends on:** None

### Detect Kurzinterventionen and Erwiderungen, and stop counting them as Reden → #68

### Stop counting the Fragen and Antworten of the Befragung and Fragestunde as Reden → #70

### Harden the vote acquisition and catalog completeness paths (open review findings)

**What:** Findings from the /ship review rounds of fix-votes-completeness (2026-09-29) that were accepted, not fixed:
(1) `source_stale` (`validate_dip_protocol.enrich_with_api`) holds a genuinely vote-free sitting of the last 14 days partial when the list head is older, delaying its week's and month's vote Fakt by up to two weeks; (2) the judged range starts at the earliest stored sitting, so one old cached dossier turns `--backfill-incomplete` into a job of hundreds of sittings and nothing prints the range; (3) the `numFound` check in `fetch_protocols` hard-stops every build if DIP's count ever includes unretrievable documents, with no override; (4) report JSON, SQLite and the catalog file are written at different points, so a build interrupted between them leaves `--offline` judging completeness from new reports against an old store; (5) a build whose every refresh was skipped exits 0; (6) the build-wide roll-call page cache is a snapshot, and list pagination can shift under a long build (duplicates a boundary entry); (7) `namenslisten_entries()` has no outage cooldown, so an outage costs about 3 minutes per vote; (8) an empty list page after page 1 counts as the end of the list; (9) catalog entries in range with no usable number or date only warn instead of failing closed, and duplicate document numbers keep the last; (10) `api_records.matched_roll_call_votes` and `roll_call_vote_candidates` describe the fresh scan while `agenda_items[].votes` may be cached after a no-scan run; (11) some date checks use the wall clock, not `--today`; (12) a failed vote-detail page stops matching for the rest of that sitting; (13) an uncaught `JSONDecodeError` from the DIP API aborts a build; (14) the offline build trusts the cached catalog with no age check; (15) the in-progress ISO week can be judged complete.

**Why:** Each is a place where a build can publish a slightly stale fact, waste a long backfill, or stop. None was reproduced as a wrong published fact on the reference copy; they were found by reading the code. Codex adversarial and structured reviews of the final tree were unavailable (usage limit), so this list has Claude-only coverage.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Match roll-call votes to a TOP when Drucksache numbers fail

**What:** `enrich_with_api` (`scripts/validate_dip_protocol.py`) attaches a roll-call vote to a TOP only when their Drucksache numbers overlap. A candidate that matches none is logged, counted (`validation_summary.unmatched_roll_call_vote_count`) and, since fix-votes-completeness, makes the sitting's votes `partial` (`unmatched_candidate`). Match by title or vote date where numbers fail, or store the vote against the Sitzung without a TOP.

**Why:** After the 2026-09-29 backfill of the reference copy, 23 candidates in 15 sittings (e.g. 21/83 vote 1008, 21/40 votes 977 and 978) matched no TOP, so those votes are in no dossier and not in the store, and those sittings, with the weeks and months holding them, stay incomplete until this is fixed.

**Effort:** M
**Priority:** P2
**Depends on:** None

### A Drucksache reference can be a URL fragment

**What:** The XML parser reads `88/739016` from a syriahr.com URL in 20/206 as a Drucksache (`xml_drucksachen`). Only the link is dropped now (`render_source_links`); the reference itself is still stored and shown as a plain Drucksache number.

**Why:** Found when it aborted the reference store's offline rebuild; the crash is fixed, the false positive is not. Belongs with the other Plenarprotokoll extraction fixes.

**Effort:** S
**Priority:** P3
**Depends on:** None

## Protokoll-Dossier

### Rename the "Aufmerksamkeitsrang" sidebar and fix its description

**What:** The dossier sidebar is headed "Aufmerksamkeitsrang" (`scripts/render_dip_pulse_html.py`), and sources.html calls it "Aufmerksamkeitsranking … aus extrahierter Redenanzahl und extrahierten Redetext-Zeichen" (`scripts/build_dip_pulse_site.py`), but it sorts by number of Reden only. Rename the heading and the back link (e.g. "Meiste Reden"), keep the `#aufmerksamkeitsrang` anchor or redirect it, and make the sources.html entry say it ranks by Reden while the second bar shows Textanteil.

**Why:** CONTEXT.md (Rangfolge nach Reden, 2026-09-25): the number of Reden mostly follows the debate length agreed in advance, so "Aufmerksamkeit" claims more than the ranking measures.

**Effort:** S
**Priority:** P3
**Depends on:** None


### Say "Dossier" consistently, and say when a count covers only Sitzungen mit Dossier

**What:** (1) Public copy uses "Sitzungsseite" for a Dossier (the Daten/Methodik "Erzeugtes JSON" bullet in `scripts/build_dip_pulse_site.py`) and the component list calls it "Protokoll-Dossiers" (`scripts/features/__init__.py`); say "Dossier". (2) Wherever a published count (Puls, Fakten, Abgeordnete, Daten recipes) spans a range for which the catalog lists more Sitzungen than have a Dossier, say so, e.g. "in 60 von 94 Sitzungen (nur Sitzungen mit Dossier)". First check which pages already disclose this; not audited.

**Why:** CONTEXT.md "Sitzung mit Dossier": every count covers only Sitzungen mit Dossier, because the store is rebuilt only from Dossier entries (`rebuild_database_from_entries`). A build with `--detail-limit` silently reports a subset as if it were the whole Wahlperiode.

**Effort:** S
**Priority:** P3
**Depends on:** None

## Puls

The week radar shipped in 0.3.0.0 (#58, 2026-09-18), so the remaining items are no longer blocked by it. The weekday comparison is completed below.

### Say "Woche mit Sitzung", not "Sitzungswoche", for the reporting period

**What:** Replace "Sitzungswoche" wherever it names this project's reporting period with "Woche mit Sitzung" or plain "Woche": 32 occurrences on 29 lines in `scripts/`. That includes the Wochenradar notes (among them "ein Vergleichswert folgt mit der nächsten Sitzungswoche"), the Fakt der Woche card footer "Vergleich: N Sitzungswochen" (`baseline_comparison_line()`), the erste-reden card sentence "mehr als in … der Sitzungswochen", the Methodik's "mindestens N Sitzungswochen", and the build log line that also counts months as "Sitzungswochen". No current use means the official Sitzungskalender, which the site does not read at all. Update the 13 test lines that assert these strings. Done when no copy calls a Kalenderwoche a Sitzungswoche.

**Why:** CONTEXT.md (Sitzungswoche, Kalenderwoche, 2026-09-25): a Sitzungswoche is the Ältestenrat's plan, and the site counts Kalenderwochen with at least one Sitzung. A week with only a Sondersitzung counts for us but is sitzungsfrei in the Sitzungskalender, so the current copy overstates it.

**Context:** The card footer and the erste-reden sentence are on the Karten, so this re-renders published Karten; see the footer fix under Fakten.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Redeanteil heading and Textanteil (puls.html and Daten recipes), the UI half of ADR 0001

**What:** The data half is done: puls.html's Redeanteil shows Bundesregierung, Bundesrat and weitere Sprechrolle as their own rows in the denominator, no row is called "Regierung", and the Daten recipes r1/r2 follow the same rule. What is left is wording: head the puls.html card "Redeanteil der Fraktionen und Gruppen" (Gruppen are still headed as "Fraktionen"), and rename r2 "Redeanteil je Fraktion nach Zeichen" to a Textanteil sorted by characters, not by Reden. Done when no share by characters is called Redeanteil.

**Why:** CONTEXT.md (Redeanteil, Textanteil, Redeanteil je Zusammenschluss, 2026-09-25).

**Context:** The three sides sit in the same list as the Zusammenschlüsse in `week_stats`; a card that wants them "outside the Zusammenschlüsse" needs a visual split as well as the heading.

**Effort:** S
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

**What:** Generate a short neutral topic label (about five words) per TOP once, cached alongside the KI-Zusammenfassung, and use it as the radar row's headline — and as the dossier Aufmerksamkeitsrang row title, replacing the deterministic boilerplate-stripped fallback now used there.

**Why:** The DIP Vorgang title is up to 200 characters and, for Antrag-only groups, the lead title is one Fraktion's slogan chosen by DIP ordering. A generated neutral label reads in five seconds and sidesteps the lead-title problem; the Vorgang title stays as the deterministic fallback.

**Context:** The summaries pipeline (`--summary-mode`) already calls an LLM per TOP with receipts; add one more field to its output. Dossier ranking rows now strip boilerplate when they use an XML heading; radar rows still prefer the DIP Vorgang title and otherwise truncate the raw XML heading. The generated label would replace both display paths. Of 459 ranked top-5 rows in the cache, the 61 without a DIP title are Einzelpläne, Regierungserklärungen and "Zur Geschäftsordnung", all already subject-first.

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

### Debattenprofil counts Tagesordnungspunkte, and "Wieder auf der Tagesordnung" replaces "Verfahren, die zurückkehren"

**What:** `week_stats` (`scripts/render_dip_pulse_html.py`, `vorgangstyp_counts`) adds 1 per Vorgangsposition. Count each Tagesordnungspunkt once for each distinct Vorgangstyp among its positions instead, and compare against the Wochenvergleich week the same way. On the real store, TOP 7 of Sitzung 21/50 bundles 26 Petition positions with 1 Rede and currently adds 26 to "Petition". 70 TOPs carry 6 or more positions. Change the card note ("Vorgangspositionen nach Art") and the sources.html glossary intro ("zählt die Vorgangspositionen der Sitzungswoche") to say Tagesordnungspunkte and Kalenderwoche. Rename the card heading "Verfahren, die zurückkehren" to "Wieder auf der Tagesordnung" and drop "Verfahren" from its notes. The `returning_vorgaenge` rule itself already matches the glossary. Done when a bundled TOP adds at most 1 per Vorgangstyp and no Puls text says "Verfahren" for a Vorgang.

**Why:** CONTEXT.md (Vorgangstyp, mitberatener Vorgang, Debattenprofil, wiederkehrender Vorgang, 2026-09-26).

**Context:** Only the Puls card and its week view read `vorgangstyp_counts`; facts.py and the Daten page do not (checked 2026-09-26).

**Effort:** S
**Priority:** P2
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

### Fakt der Woche, copy fixes from the glossary review

**What:** Three copy corrections. (1) `_render_fact_sources` (`scripts/build_dip_pulse_site.py`) heads a Fakt's citation list "Quellen"; rename it "Belege", matching the Daten export's "Belege je Fakt", whose description should also name Tagesordnungspunkte. (2) The withheld reason for a monthly Kennzahl reads "diese Woche nicht messbar"; make it period-aware. (3) The footer "Spätere Sitzungswochen ändern frühere Karten nicht; nur eine Korrektur an den Rohdaten kann es" understates what changes a Karte: every build re-renders them, so a rule change (threshold, Mindestwert, wording) changes them too, and a Karte whose Beleg no longer resolves disappears. Say so, or make Karten immutable via the publication ledger.

**Why:** CONTEXT.md (Beleg, zurückgehalten, Karte, 2026-09-25). "Quellen" is the site-wide name of sources.html, so the same word names two things on one page.

**Effort:** S
**Priority:** P3
**Depends on:** None; (3) interacts with the publication ledger item

### Fakt der Woche, stop crediting a bundled TOP's Reden to one Vorgang (`meistdiskutierter-vorgang`)

**What:** `meistdiskutierter-vorgang` (`scripts/facts.py`) credits every speech of a Tagesordnungspunkt to its lead Vorgang (`LEAD_PROCEEDING_CTE`: first Gesetzgebung by `proceeding_positions.id`, else lowest id). Decide how the metric handles a Tagesordnungspunkt that deals with several Vorgänge: skip bundled TOPs, count per Tagesordnungspunkt instead, or count only TOPs whose Vorgang set is a single Vorgang. Done when no Vorgang can win on Reden given under a TOP it merely shares.

**Why:** CONTEXT.md (Vorgang, Thema, 2026-09-25): a Rede addresses its Tagesordnungspunkt and is never attributed to a Vorgang; the lead Vorgang is a naming rule only. Example: a verbundene Beratung of two competing Anträge credits all its Reden to whichever Antrag DIP gave the lower position id.

**Context:** The two lead rules disagree today. The Wochenradar (`topic_identity`, `scripts/render_dip_pulse_html.py`) also reads `mitberaten` twins and has no lead at all for `equal_weight` TOPs (Final Gate 2026-09-15); the SQL always picks one. Check whether `proceeding_positions` holds the twins; if not, the SQL also misses the 40 TOPs where the only Gesetzgebung is a twin. Any fix changes past monthly winners, so it needs a metric version bump.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Fakt der Woche, Approach B: site-wide facts layer (full implementation)

**What:** On top of A1: MP-level metrics via `mp_canonical` (a TEMP table from the in-memory `canonical_by_mp_id`, as the export does, or persisted; B decides) (first speech in the Bundestag, longest speech of the WP, lone dissent against the own Fraktion; never attendance rankings), proceeding-level metrics (see Approach C), badge hooks in the dossier and MP renderers ("in dieser Woche: knappste Abstimmung der Wahlperiode", "hielt die längste Rede der 21. Wahlperiode") that read from `facts`, and an Open Discourse-compatible export view/CSV variant (their column names for `speeches`, `contributions`, `politicians`, `factions`, `electoral_terms`) so WP20/21 slots into existing notebooks. Done when every badge on a rebuilt site resolves to a `facts` row and the compatibility CSVs load in an Open Discourse notebook unchanged.

**Why:** A0/A1 prove the rule on a side page; B is the distinguishing feature on every page ("every number on this site knows how unusual it is") and the "build on my work" surface. Decided at office hours 2026-09-19: A is the test run, B is the full implementation, not discarded.

**Context:** Adding a metric is a registry entry plus a test once A's shape exists. The badge hooks touch `render_vote_summary` (`scripts/features/votes.py`) and the MP page renderer; keep the fixed Fraktion order and the "kein Redebeitrag" rule from the Plenarwatch-Lücken items. Open Discourse's `contributions` parsing is the reference for the Zwischenrufe item below. feed.json/RSS stay behind the Daten pilot gate.

**Effort:** L
**Priority:** P2
**Depends on:** A1 shipped and A0's pass criteria met

### Fakt der Woche, Approach C: proceeding-trajectory metrics and a timeline page

**What:** A third metric family over the joins (returns of a proceeding to the plenary, speech volume across its debates, final roll-call margin) with a `fakt/<year>-W<ww>.html` card that opens a per-proceeding timeline (debates → speakers → documents → votes). Done when the timeline renders for a proceeding with ≥3 plenary appearances and the card states "seit Beginn unserer Abdeckung (Januar 2022)" wherever a count is censored by the store's start date.

**Why:** Codex's lateral at office hours 2026-09-19: the joins are the asset the corpora lack, and a card that opens a story beats a number. Deferred behind A and B because it needs a bill/timeline page that does not exist and better proceeding titles (see "LLM five-word topic label per Tagesordnungspunkt" under Puls).

**Effort:** L
**Priority:** P3
**Depends on:** Approach B; a bill/timeline page; the LLM topic-label item

## Gesetzesvorhaben

## Abgeordnete

### The Bundestag XML gives one Redner-ID to two people (11005304)

**What:** `<redner id="11005304">` is Alexander Föhr (CDU/CSU) and Dirk-Ulrich Mende (SPD) in 22 Reden of WP 20 (20/91 to 20/190). Where the element is intact the id is the only thing that tells the Reden apart, so all 22 are attributed to one Person (abgeordnetenwatch's Föhr profile, found by ext_id); 6 of them carry a merged element ("SPDCDU/CSU", "Dirk-UlrichAlexander Mende Föhr") that `parse_redner` now repairs from the printed label. Detect an id whose Redner name (or printed label) changes between Reden and split it by name and Zusammenschluss, or report it to the Bundestag.

**Why:** 9 Reden by Mende stand on Föhr's Personenseite. It is the same defect class as the doubled id of Svenja Schulze, but here the id itself is shared, so no derivation from one Rede can spot it.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Store DIP `person_roles` so a Rede without a Zusammenschluss uses the Zugehörigkeit of its Wahlperiode

**What:** ADR 0001 says a Rede whose Plenarprotokoll names no Zusammenschluss counts for the speaker's Zugehörigkeit on the date of the Sitzung. The store keeps no membership history: `mps.person_roles_json` is DIP's `funktion` list, and `compact_person` drops DIP's `person_roles` (fraktion and Wahlperiode per role). The Rede therefore counts for the speaker's party as the store holds it. Keep `person_roles`, and let `derive` pick the role of the Rede's Wahlperiode.

**Why:** Measured 2026-09-29: only 1 Rede (20/109 ID2010905000) has neither a Zusammenschluss nor a Sprechrolle, so the approximation costs almost nothing today; `compare_store_values.py` reports the count so it stays visible.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Call only current MdBs "Abgeordnete" on the Personenseiten

**What:** Every Person with a Mandat or at least one Rede gets a page under `abgeordnete/`, including members of the Bundesrat and the Bundesregierung without a Mandat. On the list and each page, show only Persons with a current Mandat as Abgeordnete; show everyone else as a Redner with the Sprechrolle they spoke in (and a former Mandat where one exists). Decide whether the list keeps them in one filterable list or a separate group. The URL path can stay.

**Why:** CONTEXT.md (MdB, Personenseite, 2026-09-25): "Abgeordnete" for anyone who speaks is on the MdB entry's avoid list.

**Effort:** S
**Priority:** P3
**Depends on:** None

## Design

### DESIGN.md, tokens and a typeface decision via /design-consultation

**What:** Write a DESIGN.md (tokens, type scale, spacing, component vocabulary, focus/visited/selection rules) and decide the site's typeface. Name once the tokens individual pages had to invent, including the Daten page's light `--surface-2`/`--surface-3`.

**Why:** Every page carries its own `:root` token block and the only typeface is Inter / ui-sans-serif / system-ui; every design review re-derives the tokens and flags the default font stack. The Daten page (after the dossier) was the second page to have to invent tokens a shared system would already provide. No `DESIGN.md` exists as of 2026-09-19 (`docs/design/bundestag-pulse-design.md` is the product design doc, not a design system).

**Context:** The week-radar plan writes the radar's tokens into the plan instead. Start with `/gstack-design-consultation`; migrate per-page `:root` blocks to the shared header styles afterwards (the `:visited`/`:focus-visible` item under Daten is the first slice of that migration). Merged from two earlier entries (Daten and Design sections).

**Effort:** M
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

### Global header nav links to a page a build didn't write when its feature is off

**What:** `render_global_header` (`scripts/render_dip_pulse_html.py`) accepts a `features: Selection` parameter but never uses it to filter `NAV_ITEMS` — every nav item renders unconditionally. `bills`, `abgeordnete`/`mp-pages`, `fakten`/`facts`, `database`/`store`, and now `votes` all skip writing their page when their feature is deselected (`write_pages`/`write_*_pages` returning early), so a build that deselects any of them still links every page's header to a file that was never written — a sitewide dead link for that nav entry.

**Why:** Found by Claude's adversarial `/ship` review (2026-09-27) while checking the `votes` nav entry this branch adds; the same gap already existed for the other four items before this diff, so this is a pre-existing pattern the branch extended consistently rather than introduced. The real published site always builds with every feature enabled (`publication_selection() = all_selection()`), so this has never actually produced a dead link in production.

**Context:** Fix once for all five items: filter `NAV_ITEMS` by a nav-key → component-id map (`votes`→`votes`, `bills`→`bills`, `abgeordnete`→`mp-pages`, `fakten`→`facts`, `database`→`store`) and call `features.enabled(component_id)` per item before rendering.

**Effort:** S
**Priority:** P3
**Depends on:** None

## Community

### Contribution governance: SECURITY.md, conduct rules, issue forms, contact channels

**What:** Implement ADR 0003 D5:
- `SECURITY.md` with a scope section, and GitHub private vulnerability reporting switched on.
- `/.well-known/security.txt` on the site.
- Short German conduct rules (no party politics in issues, no disparaging statements about people), linked from `CONTRIBUTING.md`.
- `.github/ISSUE_TEMPLATE/` with the „Datenfehler" and „Fehler auf der Seite" forms, auto-applying triage labels, and `config.yml` with `blank_issues_enabled: false` and a contact link to the Impressum e-mail for private matters.
- The site's `issues_url` link pre-fills the page URL in the Datenfehler form.

Done when a new issue can only be opened through one of the two forms and `security.txt` is served by the preview.

**Why:** Data-error reports are the most valuable contribution and need structure. Private requests (GDPR, corrections from the people concerned, press) need a non-public channel. On a political site, the conduct risk is party-political debate, which a generic code of conduct does not address.

**Context:** Decided 2026-09-29 ([ADR 0003](docs/adr/0003-licences-and-impressum.md), D5). E-mail is answered at the owner's discretion and only for matters that cannot be public. `security.txt` needs the final domain and the dedicated e-mail address, both also needed by the Impressum item.

**Effort:** S
**Priority:** P3
**Depends on:** Domain and contact address (Impressum item)

## Plenarwatch-Lücken

Gap list against [plenarwatch.de](https://plenarwatch.de/) (Plenarwatch GbR, München; 169 posts for WP 21 as of 2026-09-19). Their counting rules live on [/methodik/](https://plenarwatch.de/methodik/); read it before touching any item below rather than re-deriving the rule here. Coverage audit of our code on 2026-09-19: their vote tallies, per-sitting summaries, MP pages and bill tracking we already have (`scripts/features/votes.py`, `summaries.py`, `mp-pages`, `bills`); everything else in their nav (Feed, Zwischenrufe, Präsenz, Muster, Bundestag, Methodik) is a gap or partial. Excluded on purpose: Telegram/YouTube/Instagram and the "Unterstützen" page (distribution, not product).

### Inverted-vote reading for Beschlussempfehlungen ("Ja = Antrag ablehnen")

**What:** When the voted document is a committee recommendation to reject a motion, the panel states the reversal in one procedural sentence, prints the legend `Ja = Antrag ablehnen · Nein = Antrag annehmen`, and derives each fraction's position ("für den Antrag" / "gegen den Antrag" / "geteilt") from its `leading_vote`; raw counts stay untouched. Done when the Übergewinnsteuer-style case (plenarwatch post `ablehnung-eines-antrags-zur-uebergewinnsteuer-2026-04-24`) renders the derived positions and a test pins the inversion.

**Why:** Without the inversion the outcome badge from the previous item reads "Angenommen" on a vote whose political meaning is "Antrag abgelehnt", the single most misleading state a vote panel can be in. "Beschlussempfehlung" appears in our code only as glossary prose (`scripts/render_dip_pulse_html.py:59-188`).

**Context:** Detection signal: the DIP `vorgang`/Drucksache title of the voted document starts with "Beschlussempfehlung" and the recommendation text contains "abzulehnen"; DIP's `/drucksache` endpoint carries the title, so no PDF parsing. Store as a boolean on `votes`; render in `render_vote_summary`.

**Effort:** M
**Priority:** P1
**Depends on:** Vote outcome badge

### Majority rule for derived vote outcomes (Art. 79(2), 67, 68 GG)

**What:** `validate_dip_protocol.vote_result` derives "Angenommen"/"Abgelehnt" from a plain yes>no majority of votes cast. A Grundgesetz amendment needs two thirds of the members (Art. 79(2) GG); Kanzlerwahl, konstruktives Misstrauensvotum and Vertrauensfrage need an absolute majority of the members (Art. 63, 67, 68 GG). Thread the applicable threshold (from the Vorgang/Drucksache type) into `vote_result`, or return unknown for those vote types when no official result was scraped. Done when a test pins a GG amendment with yes>no but below two thirds of members as "Abgelehnt".

**Why:** Found by the /ship red-team review of the badge (2026-09-26). Latent: every Grundgesetz vote in the real store is labelled correctly today, but a high-absence sitting would mislabel one silently.

**Context:** The official-result scrape already wins when bundestag.de states the outcome; the gap is only in the derived fallback.

**Effort:** S
**Priority:** P2
**Depends on:** Vote outcome badge

### A tally-less neighboring decision with no document number of its own can still steal the official badge

**What:** `scrape_official_vote_result`'s document-number cross-check (this item's own commit) only refuses when the attributed text names a *different*, specific document number. A neighboring, tally-less decision (e.g. a unanimous show-of-hands item, which needs no "Gesamt"/"Ja: N" marker) that names NO number at all is indistinguishable from this vote's own legitimate number-less outcome sentence, and its outcome word can still be adopted as this vote's official result. Done when a fixture or live page demonstrating this shape is found and a fix (e.g. requiring positional/structural confirmation, not just absence-of-mismatch) is verified against it without regressing the fixture or any of the 8 real votes already pinned in the test suite.

**Why:** Found by the /ship red-team review (2026-09-27), same family as the Beschlussempfehlung-inversion badge caveat already shipped in 85411a4 ("acceptable only while the site is not public"). Latent: every real "Beschluss" narration checked so far — the project's own fixture and every live bundestag.de page fetched during this and the prior review round — attaches a document number to every decision it mentions, including tally-less ones, so this specific shape has not been observed on real data. A cheap fix was explored and rejected: requiring a document-number match whenever the lookahead line starts with a proposition keyword (Gesetzentwurf/Beschlussempfehlung/Entschließungsantrag/...) also rejects the fixture's own legitimate "Gesetzentwurf angenommen" case, which has the identical shape.

**Context:** The badge already discloses "(berechnet)" for any non-official result, so a bleed here would show a false-confidence "Laut Beschluss auf bundestag.de" label with the wrong outcome rather than the honest derived caveat — worse than the inversion caveat, which at least states the right raw counts.

**Update (2026-09-28):** narrowed: the outcome is now only read from the line directly under the tally (a blank "<br/><br/>" line ends the block), which closes the blank-line-separated shape. Still open: two decisions with no blank line between them.

**Effort:** S
**Priority:** P3
**Depends on:** None

### `2/3-Mehrheit` phrasing can spuriously trip the document-number mismatch check

**What:** `_DOCUMENT_NUMBER_RE` (`\b\d{1,2}/\d{1,6}\b`) also matches a fractional-majority phrase like "2/3-Mehrheit". If such a phrase appears in the attributed outcome text and doesn't happen to equal one of the vote's own document numbers, `scrape_official_vote_result` refuses (falls back to derived) even though the actual outcome word is correct. Require at least 3 digits before the slash for a document number, or exclude common fraction phrases (`1/2`, `2/3`, `3/4`) from the pattern used by this specific check.

**Why:** Found by the /ship red-team review (2026-09-27); not verified against real bundestag.de wording (live pages checked so far spell out "Zweidrittelmehrheit", not "2/3-Mehrheit"). The failure direction is always safe — a spurious refusal falls back to the derived yes>no rule, never produces a wrong official value — so this is a false-negative/coverage gap, not a correctness bug.

**Effort:** S
**Priority:** P3
**Depends on:** None

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

### Impressum, Datenschutz and licence files before the site goes public

**What:** Implement [ADR 0003](docs/adr/0003-licences-and-impressum.md):
- `impressum.html`: Luca Veh as a private person; postal address and e-mail; citing § 5 DDG and § 18 MStV; the same person named as Verantwortlicher under § 18 Abs. 2 MStV.
- `datenschutz.html`.
- Both linked from every footer.
- `LICENSE` (MIT, code only, pointing to `LICENSE-DATA.md` for data).
- The short string from `docs/data-license.md` set as the default `--data-license`.
- The `lizenz` item on `sources.html` (the "Die genaue Lizenzformulierung … steht noch aus" placeholder in `scripts/build_dip_pulse_site.py`) replaced by the layer table.
- The site's machine-generated summaries labelled as such.

Done when `grep -rn "steht noch aus"` over the generated site is empty and every footer links Impressum and Datenschutz.

**Why:** Name and address are required for any non-private Telemedium (§ 18 Abs. 1 MStV). The DIP terms require naming the source and marking changes on redistribution. Hosting can't ship without either.

**Context:**
- Decisions are made (ADR 0003).
- Before launch, the ADR's open questions go to a lawyer, first of all whether a c/o address is enough under § 18 MStV. That answer decides which address goes in `impressum.html`.
- Re-check § 5 DDG and DIP no. 4d if donations are added.
- Blocks the hosting item, not the other way round.

**Effort:** M
**Priority:** P2
**Depends on:** Lawyer answer on the address (ADR 0003, question 1)

### Tag the abgeordnetenwatch MP columns with their real source

**What:** Move `birth_year`, `gender`, `profession`, `wahlkreis` and `bundesland` from `_COLUMN_SOURCE_DIP_ROSTER` to `_COLUMN_SOURCE_ABGEORDNETENWATCH` (`scripts/build_dip_pulse_site.py`), with a test that pins the tags. Afterwards, delete the "Known gap" paragraph in `docs/data-license.md`.

**Why:** The roster build fills all five from the abgeordnetenwatch resolver (`profile_resolver.resolve` / `fetch_bio`), but the manifest claims `dip`. The per-column licence in `docs/data-license.md` depends on these tags: the columns are CC0, not DIP-terms data. The MP-page footer already credits abgeordnetenwatch.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Cite protocols as „BT-PlPr." per DIP no. 4c

**What:** Change the „BT-PlPr" source labels (e.g. the bill-event `source` built in `scripts/build_dip_pulse_site.py`) to „BT-PlPr." plus number, and check the other citation strings against DIP no. 4c („BT-Drs.").

**Why:** DIP no. 4c prescribes the abbreviations exactly.

**Effort:** S
**Priority:** P3
**Depends on:** None

### Settle the roll-call source for redistribution

**What:**
- Check whether the Plenarprotokoll's „Endgültiges Ergebnis" also lists non-voters, or only Ja/Nein/Enthalten.
- Ask parlamentsdokumentation@bundestag.de whether the roll-call XLSX lists may be redistributed.
- If the answer is no, or only the XLSX carries the non-voters, source per-member votes from the protocol XML or from abgeordnetenwatch (CC0) instead.

**Why:** bundestag.de's default terms are private use only. The Open Data page calls the XLSX lists open data but names no licence (ADR 0003, open question 5).

**Effort:** S (check and e-mail); M if the source must change
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

### Vote outcome badge, linked Drucksache and XLSX source on the vote panel

**Completed:** v0.7.0.0 (2026-09-26). Badge ("Angenommen"/"Abgelehnt") from `result_raw`/`result_source` (official bundestag.de wording when scrapable, otherwise derived with a tie counting as rejected), every `document_numbers` entry linked to its Drucksache via the XML/DIP objects that already matched the vote, and a scraped XLSX link (bundestag.de publishes it on a separate Namenslisten page, matched by date and title — never a derived URL). Real store (2026-09-26): 217/217 votes backfilled as derived (166 accepted, 51 rejected, 0 ties); 12/217 XLSX links matched from one live Namenslisten fetch.

### Votes archive across sittings (`votes/index.html`)

**Completed:** v0.7.0.0 (2026-09-26). Reverse-chronological, grouped by month, with client-side Fraktion chips (majority "yes" position); gated by the `votes` feature and added to `NAV_ITEMS`. Row count verified equal to `SELECT count(*) FROM votes`.

### Current-TOP highlight in the ranking sidebar

**Completed:** v0.6.6.0 (2026-09-26). `IntersectionObserver` on `.top-card` plus a frame-throttled scroll/resize re-pick sets `aria-current="true"` on the matching `.attention-row`, styled through `[aria-current]` (screen only); off wherever the aside is static (`ATTENTION_STATIC_LAYOUT_QUERY`). "Reached" is measured against the cards' scroll-margin-top, the lowest visible card wins at the end of a scrolling page, and the row-reveal scrolls only `.attention-list`, instantly (a running smooth list scroll made Chrome drop row-click jumps). Ships alongside the copy-button half of the recipe TODO above.

### Weekday-matched Wochenvergleich when sitting counts differ

**Completed:** 2026-09-25 (v0.6.5.0). Compared shared weekdays by summed counts and recomputed Redeanteil from the matched sittings, with a visible basis note and n/a when no weekday overlaps.

### Enforce the Python version floor

**Completed:** v0.6.4.0 (2026-09-25). Added a Python 3.11 startup check to the build scripts and documented the supported version in the README.

### CONTRIBUTING.md

**Completed:** v0.6.4.0 (2026-09-25). Added a concise command index with README links and the `.env.local` empty-key warning.

### Regenerate the architecture diagram for the Daten export step

**Completed:** v0.6.4.0 (2026-09-25). Updated the diagram to include the Fakten engine, Daten export, generated data paths, manifest override, and Daten page.

### Move the hidden dev-view API dump below the dossier content

**What:** In explicit `--include-dev-view` builds, the `protocol_dev_sections` block (raw API JSON and people list; `.dev-only`) is emitted between the page header and `.layout`. Emit it after `<main>`, or — preferably, given the hosting maths — render it into a separate file loaded on demand.

**Why:** Measured on plenarprotokoll 20/103: 952 KB of hidden markup precede the Aufmerksamkeitsrang aside and the first TOP card, so on a slow connection nothing above the fold can paint until ~1 MB has streamed. Found while placing the aside's toggle script adjacent to the aside (2026-09-14). Added 2026-09-19: across 285 dossiers that is roughly 270 MB of `protocols/` (584 MB total), and the site without `data/` is 1.11 GB — the on-demand variant is the single biggest lever for getting under a 1 GB host cap (see the site-hosting TODO). Note (post-#60, v0.5.0.0): those figures were measured on a build that still emitted the dev block; ordinary publications now omit `dev-view` entirely (`--include-dev-view` refuses to write to the publication directory), so the hosting lever only applies to explicit dev builds — re-measure the public site before relying on it.

**Context:** `render_html` in `scripts/render_dip_pulse_html.py` still interpolates `{protocol_dev_sections}` before `{session_summary_sections}` and `<main>` (2026-09-19). Moving it after `</main>` changes nothing visible (it is `display:none` until toggled) but check `tests/test_render_dip_pulse_html.py::DossierLayoutTests`, which pins the order of `.dev-top-details` inside cards, and the dev-toggle script that reveals `.dev-only`.

**Completed:** 2026-09-25. Verified the existing S variant: protocol dump follows main and ordinary builds omit it; explicit dev builds show `.dev-only` by default and have no dev-toggle (existing behavior retained by user decision).

### Dossier h1 shows the session, "Bundestag-Puls" moves to the eyebrow

**What:** On `protocols/*.html` make the session title the `h1` and demote the product name to an eyebrow/kicker.

**Why:** Every one of the 285 dossiers has the identical `h1 "Bundestag-Puls"`; the page's actual subject is a muted 15px subtitle. Hierarchy should serve the page, not the brand (flagged in the 2026-09-13 design review).

**Context:** the `<h1>Bundestag-Puls</h1>` block in `render_html`'s page template (`scripts/render_dip_pulse_html.py`). puls.html already made this exact move in 0.3.0.0 (`header["h1"]` = "Was der Bundestag in KW … verhandelt hat" with an eyebrow; `render_front_page` in `scripts/build_dip_pulse_site.py`), so copy that pattern. Check `test_global_header.py` expectations before changing the `h1`.

**Completed:** 2026-09-25. Verified the existing session h1/product eyebrow and added explicit title, escaping and fallback regression coverage.

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

### Check that roll-call votes are still being acquired after June 2026

**What:** Confirm whether bundestag.de published namentliche Abstimmungen after 2026-06-12, and find why the vote scan missed them.

**Completed:** v0.8.0.0 (2026-09-29). Cause: vote scraping was opt-in (`features.json` ships an empty `enrich` list), so every update since June recorded votes as `not_requested`. Votes are now a default enrichment (`--no-votes` opts out). Backfilled into a scratch copy of the reference store: votes 217 -> 232, newest 2026-06-12 -> 2026-09-25 (2026-06-25 1, 07-08 1, 07-09 1, 07-10 8, 09-24 1, 09-25 3).

### One Zusammenschluss per `parties` row

**What:** `parties` had `SPDSPD`, `SPDCDU/CSU`, `BSW`, `BSW (Gruppe)`, `Die Linke (Gruppe)` beside `Gruppe BSW`/`Gruppe Die Linke`, and the Die Linke row mixed the WP 20 Fraktion, the WP 20 Gruppe and the WP 21 Fraktion.

**Completed:** v0.9.0.0 (2026-09-29). `derive.zusammenschluss` maps every spelling to one name and `upsert_party` routes every name through it. A WP 20 Rede from 2023-12-06 on naming "Die Linke" is a Gruppe Die Linke Rede (`derive.speech_zusammenschluss`; 383 Reden move). The merged Bundestag records are read from the printed label (`parse_redner`) or, in cached reports, drop their Fraktion. Reference store: 15 parties -> 9 (10 after this item, 9 after the Regierung item). The cause was not only the table of contents: the merged `<redner>` elements sit inside the `<rede>` too.

### Credit a Rede's text only to its Redner

**Completed:** v0.9.0.0 (2026-09-29). `speech_text_and_paragraphs` keeps only what the Redner said (a `<name>` is the Sitzungsleitung, a `<p klasse="redner">` marker names the speaker); the Redner resumes under an explicit marker, so no resumption is inferred (checked on 961 Reden of 8 sittings, WP 20 and 21). Reference store: 126.300.719 -> 121.793.810 characters (-4.506.909), 21/84 349.531 -> 333.888 (89 of 99 Reden change), `laengste-rede` 54 periods (35 lower value, 4 newly and 5 no longer publishable). The Zwischenfrage and Gastansprache remainder is tracked above.

### Say "nicht abgegeben", never "Abwesend", and stop inventing a Mehrheitsvotum

**Completed:** v0.9.0.0 (2026-09-29). `derive.majority_vote` is the plurality among Ja/Nein/Enthaltung and None on a tie or when nobody voted; persist and the pages derive it from the counts and ignore a cached value. Reference store: 37 `vote_fractions` rows lose their Mehrheitsvotum (29 fraktionslos Ja/Nein ties that read "yes", 3 shared tops, 5 "absent"). The Abgeordnete page and the vote panel say "nicht abgegeben".

### One Abweichung rule: exclude fraktionslose MdBs from `r3-abweichler`, drop "Linie" from the wording

**Completed:** v0.9.0.0 (2026-09-29). `r3-abweichler` excludes `fraktionslos` (381 -> 371 rows, 806 -> 648 Abweichungen; the old top entry was a fraktionsloser MdB with 81), and the recipe title, the `meiste-abweichler` unit, caveat and Karte caption say "anders als die Mehrheit der eigenen Fraktion oder Gruppe".

### Sprechrolle per Rede, no "Regierung" party (ADR 0001, data half)

**Completed:** v0.9.0.0 (2026-09-29). `speeches.sprechrolle` (bundesregierung, bundesrat, weitere) from `SPRECHROLLE_RULES` in `scripts/derive.py`; an unmapped role fails persist with one `ERROR [sprechrolle]` naming all of them. Reference store: Bundesregierung 5.394 Reden, Bundesrat 61, weitere 8; 1.556 Reden of MdBs in a government role leave their Fraktion's Redeanteil. The wording half is tracked above.

### Make the Namensabgleich unique, and stop treating name-found ids as proof

**Completed:** v0.9.0.0 (2026-09-29). Only an abgeordnetenwatch id looked up by the Redner-ID (`match` = ext_id) is a Personenkennung (`mps.aw_match`); Zusammenführung joins by shared Personenkennung (ext_id) or by a unique 1+1 name+party bucket (unique_name), titles ignored, and every Personenseite records its merges. Reference store: five wrong-person matches undone (92 Reden moved to their own Personenseite, 2 new pages), 640 ext_id and 861 unique_name merges, 322 + 397 name buckets left split; Personenseiten 1.040 -> 1.045. A name-found id equal to the trusted id of a same-named record joins the two (`corroborated_name`, 6 merges): the six people with two Redner-IDs are one Personenseite again and debut once in `erste-reden`; Personenseiten 1.039. Follow-up: the shared Redner-ID 11005304.

### Only Gesetzgebungen on the bills pages, and call them "Gesetzesvorhaben"

**Completed:** v0.9.0.0 (2026-09-29). `is_gesetzgebung` (Vorgangstyp) replaces the keyword test; Entschließungsanträge and the like are listed as "Weitere Vorgänge zu diesem Tagesordnungspunkt" on the page of each Gesetzgebung of the same agenda item; labels say Gesetzesvorhaben. Reference store: 903 -> 594 bill pages. The old figures (839 -> 551) were measured on a smaller store.
