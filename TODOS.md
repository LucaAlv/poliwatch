# TODOS

Reassessed against the code, the live store and the generated site on 2026-09-19 (after PR #59, v0.4.0.0; rebased onto PR #60, v0.5.0.0). Nothing below is done; corrections from that pass are inline. The Daten section was re-checked against the code and the 2026-09-19 store on 2026-09-24 (database state review): five findings, four new open items and a Python version floor now completed; `protocol_acquisition` raised to P2.

## Roadmap to v1 (2026-09-30)

The order of work toward the direction in PRODUCT.md (2026-09-30): a citable dataset for WP 18 to the present, and a site with two equal angles, the daily view and long-term analysis. Items are named by their headings below. Tracks A and B can run in parallel. C waits for A, because every count A changes moves every series C draws. D has to be finished before anything goes public.

**A. Get the counts right and the coverage in, in this order**
1. What counts as a Rede: #68 (Kurzinterventionen) and #70 (Befragung and Fragestunde) are done (PR 1, branch `a1-what-counts-as-rede`, see Completed). A1 follow-ups are implemented in v0.15.0.0 (see Completed): nested Zwischenfragen, written submissions as their own kind, and source-backed historical classification. Final merged A1/A2 validation remains required before A3; ceremony addresses absent from sampled plenary XML remain a separate acquisition gap.
2. "Stable ids for every row a release publishes" (done: A.2, see its Completed note).
3. "v1 coverage: every Sitzung from WP 18 to the present". Running it after 1 and 2 means the backfill is counted once, with ids that last.
4. "Split the dataset from the site: the site builds from a release alone". Start slice by slice alongside 1–3. The votes archive is the first slice.

**B. Abstimmungen (daily view), independent of A**
1. Completed v0.10.0.0 (2026-09-30): "Inverted-vote reading for Beschlussempfehlungen", "Majority rule for derived vote outcomes" and "Match roll-call votes to a TOP when Drucksache numbers fail".
2. Completed (2026-10-04): "Roll-call member rows link to external profiles, never to our own MP pages" (B.2, including vote-member reconciliation).
3. "Politikfeld tags on Tagesordnungspunkte and votes". This also feeds C.
4. "Abstimmungen for the daily view: what was decided, by topic, with dissenters".
5. "Take namentliche Abstimmungen from the official XLSX instead of the chart markup" can come later. It adds ungültig and Bemerkung but changes no count seen so far.

**C. Analysen (long-term view), after A1–A3**
1. "Fraktion seat counts in the store" (small; the denominator for per-seat figures).
2. "Diskursanalyse: precomputed term series per Zusammenschluss and month".
3. "Politikfelder over time: which Zusammenschluss emphasises what" (after B3).
4. "Zwischenrufe: parse `<kommentar>` and count reactions per Fraktion", which answers "who interrupts most".
5. Then "Muster" and "Präsenz".

**D. Before anything goes public**
- Legal and licence: "Impressum, Datenschutz and licence files before the site goes public", "Settle the roll-call source for redistribution", "Tag the abgeordnetenwatch MP columns with their real source".
- The release: "Write the release script", "Codebook (`DATA.md`) and recipe result CSVs in the release", "Public data changelog per release", "A DOI per release and a citation file".
- Hosting: "Site hosting plan for the 2.5 GB generated site". WP 18 and 19 make it larger.

**Later:** the LLM-content items (Fraktionsblöcke, deterministic validators, Debattenberichte), Fakt der Woche B/C, and the Puls and copy fixes, which stay at their own priorities. WP 1–17, which have no structured XML in the DIP catalog, come after v1.

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

### Codebook (`DATA.md`) and recipe result CSVs in the release

**What:** A codebook (`DATA.md`) in every release: each table and column with its meaning, unit, source (DIP, Plenarprotokoll XML, bundestag.de, abgeordnetenwatch) and licence layer; the counting rules (what counts as a Rede, Sitzung mit Dossier, completeness) quoted from CONTEXT.md and the ADRs; coverage per Wahlperiode; known gaps; how to cite. Also per-recipe result CSVs. Most of the explanatory prose on the Daten page today belongs here, so that it is versioned with the data it describes.

**Why:** A researcher needs the definitions of the release they cite, not of today's site (PRODUCT.md, 2026-09-30). Originally scoped out of PR #59 as an Approach-C follow-up once the data path has real usage. This item used to also cover a "Kopieren" clipboard button on each recipe's SQL block and a "Daten" link in dossier footers; both shipped in v0.6.6.0 (2026-09-26), leaving only the CSV/`DATA.md` half open. The other former part of this item, externalising `data/plenarprotokoll-*.json` links, moved into the site-hosting TODO above.

**Effort:** S–M
**Priority:** P2 (raised 2026-09-30: part of a citable release)
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


### Validate final merged A1/A2 before the A3 backfill

**What:** Finish Claude's paused A2 follow-ups on `right-counts`, review [the A1 identity/schema handoff](docs/plans/a1-a2-contract.md), merge the final A2 changes with `a1-followups`, and repeat combined suite, fresh/incremental grouping, unchanged replay, links and export checks. The current scratch overlay validates an uncommitted A2 snapshot; it is not final merged validation.

**Why:** Claude reached its usage limit on 2026-10-05. The user explicitly requested completing A1 without waiting and recording this gate. A1 preserves schema 3/key version 1 and needs no new registry policy, but later A2 edits may affect grouping and page links.

**Priority:** P1
**Depends on:** A2 completion; must pass before A3 readiness is claimed. [A1 validation receipt](docs/plans/a1-validation.md).

### Test the independently loaded historical parser and classifier

**What:** Add a regression test for the documented rule-4 comparison using an independently loaded historical parser and historical classifier pair.

**Why:** PR #87 review finding (`tests/test_audit_offline_turns_cli.py:59–65`): the test baseline calls the current parser and shares its classifier, so it cannot catch regressions in loading the separate historical pair. Incorrect historical counts could pass unnoticed.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Acquire ceremony addresses omitted from sampled plenary XML

**What:** If ceremony addresses are to be ingested, acquire an explicit ceremony source and define its sitting association. The inspected 2016 and 2021 memorial speeches precede their plenary sittings and are absent from the plenary XML; do not synthesize a guest unit or treat all role-less speakers as guests.

**Why:** A1's source-backed guest check corrects the original assumption that those guest addresses inflate delivered Rede counts, but cannot ingest text its source omits.

**Priority:** P2
**Depends on:** Separate source acquisition and evidence-backed association; see [coverage evidence](docs/plans/a1-validation.md).

### Harden the vote acquisition and catalog completeness paths (open review findings)

**What:** Findings from the /ship review rounds of fix-votes-completeness (2026-09-29) that were accepted, not fixed:
(1) `source_stale` (`validate_dip_protocol.enrich_with_api`) holds a genuinely vote-free sitting of the last 14 days partial when the list head is older, delaying its week's and month's vote Fakt by up to two weeks; (2) the judged range starts at the earliest stored sitting, so one old cached dossier turns `--backfill-incomplete` into a job of hundreds of sittings and nothing prints the range; (3) the `numFound` check in `fetch_protocols` hard-stops every build if DIP's count ever includes unretrievable documents, with no override; (4) report JSON, SQLite and the catalog file are written at different points, so a build interrupted between them leaves `--offline` judging completeness from new reports against an old store; (5) a build whose every refresh was skipped exits 0; (6) the build-wide roll-call page cache is a snapshot, and list pagination can shift under a long build (duplicates a boundary entry); (7) `namenslisten_entries()` has no outage cooldown, so an outage costs about 3 minutes per vote; (8) an empty list page after page 1 counts as the end of the list; (9) catalog entries in range with no usable number or date only warn instead of failing closed, and duplicate document numbers keep the last; (10) `api_records.matched_roll_call_votes` and `roll_call_vote_candidates` describe the fresh scan while `agenda_items[].votes` may be cached after a no-scan run; (11) some date checks use the wall clock, not `--today`; (12) a failed vote-detail page stops matching for the rest of that sitting; (13) an uncaught `JSONDecodeError` from the DIP API aborts a build; (14) the offline build trusts the cached catalog with no age check; (15) the in-progress ISO week can be judged complete.

**Why:** Each is a place where a build can publish a slightly stale fact, waste a long backfill, or stop. None was reproduced as a wrong published fact on the reference copy; they were found by reading the code. Codex adversarial and structured reviews of the final tree were unavailable (usage limit), so this list has Claude-only coverage.

**Effort:** M
**Priority:** P2
**Depends on:** None

### A Drucksache reference can be a URL fragment

**What:** The XML parser reads `88/739016` from a syriahr.com URL in 20/206 as a Drucksache (`xml_drucksachen`). Only the link is dropped now (`render_source_links`); the reference itself is still stored and shown as a plain Drucksache number.

**Why:** Found when it aborted the reference store's offline rebuild; the crash is fixed, the false positive is not. Belongs with the other Plenarprotokoll extraction fixes.

**Effort:** S
**Priority:** P3
**Depends on:** None

### v1 coverage: every Sitzung from WP 18 to the present

**What:** Acquire a Dossier for every Sitzung the catalog lists for WP 18, 19, 20 and 21, and keep the store current. Measured on 2026-09-30 against the reference copy (`~/agent-runs/poliwatch/.context/dip-pulse-site/`), counting only Bundestag entries in the cached catalog:

| WP | In the catalog | In the store | Missing |
|---|---|---|---|
| 18 | 245 (2013-10-22 to 2017-09-05) | 0 | all 245 |
| 19 | 239 (2017-10-24 to 2021-09-07) | 0 | all 239 |
| 20 | 214 | 201 | 13, from 2021-10-26 to 2022-01-26 |
| 21 | 87 up to 2026-06-26 | 84 | 3, plus every Sitzung after the catalog snapshot |

The catalog itself is from 2026-08-25, and the store was last updated on 2026-06-22. A newer scratch copy (302 Sitzungen, backfilled 2026-09-29, per the fix-stored-values work) was not found; re-measure against the current reference store before starting. Done when the numbers above read 0 missing on a fresh authoritative catalog, and the README, PRODUCT.md and the Daten page state the covered range.

**Why:** PRODUCT.md (2026-09-30) sets v1 coverage at the Wahlperioden with structured Plenarprotokoll XML, which the DIP catalog lists for WP 18 onward (every WP 18–20 Sitzung has an `xml_url`; no WP 1–17 Sitzung does). Every long-term analysis is only as long as this coverage. A trend that starts in 2022 says little about change over time.

**Context:**
- WP 18 and 19 XML parse with today's code. Test on 2026-09-30 with 18/1, 18/100, 18/200, 18/245, 19/1, 19/100 and 19/239 against `parse_protocol_xml`: every `<rede>` under `<sitzungsverlauf>` is parsed. A1 now ingests the 35 explicitly typed written submissions in 18/100 separately; the 11 annex units in 18/200 and 29 in 19/239 are §31 declarations and remain excluded. See the A1 validation record. Before running the full backfill, check a larger sample of WP 18 and 19, including Sitzungen with Befragung, Fragestunde and Aktuelle Stunde, and the DIP enrichment path (Vorgänge, Drucksachen, roll-call votes), which this test did not touch.
- Speakers from the Bundesregierung have no Fraktion in the XML (45 of 117 Reden in 19/100). Sprechrolle handles this already (ADR 0001).
- WP 18 and 19 roughly triple the Dossier count, so the 2.5 GB site grows accordingly. That makes the P1 site-hosting item harder.
- Budget about half a minute per Sitzung plus votes. `--backfill-incomplete` and `--protocol-wahlperiode` are the tools.

**Effort:** M (mostly running time and checking)
**Priority:** P1
**Depends on:** The Rede-counting items (#68, #70, Zwischenfragen and Gastansprachen) should land first, so the backfill does not have to be recounted.

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

**Update 2026-10-03 (architecture review):** fix the duplicated rule along with the metric. Compute a Tagesordnungspunkt's Thema/lead Vorgang once, at persist time, with `topic_identity`'s full rule (twins, `equal_weight`), and store it. `LEAD_POSITION_CTE`, `LEAD_PROCEEDING_CTE` and the TEMP tables in `build_dip_pulse_site._ensure_lead_position_tables` then read the stored value instead of re-implementing it in SQL. The CTE comment says "same rule topic_identity uses", and that is false. Until the rule exists once, the Wochenradar and a Fakt card can name different Themen for the same TOP.

**Effort:** S
**Priority:** P2
**Depends on:** None

### Fakt der Woche, Approach B: site-wide facts layer (full implementation)

**What:** On top of A1: MP-level metrics via `mp_canonical` (a TEMP table `facts.ensure_canonical` fills from the persisted `mps.person_id`) (first speech in the Bundestag, longest speech of the WP, lone dissent against the own Fraktion; never attendance rankings), proceeding-level metrics (see Approach C), badge hooks in the dossier and MP renderers ("in dieser Woche: knappste Abstimmung der Wahlperiode", "hielt die längste Rede der 21. Wahlperiode") that read from `facts`, and an Open Discourse-compatible export view/CSV variant (their column names for `speeches`, `contributions`, `politicians`, `factions`, `electoral_terms`) so WP20/21 slots into existing notebooks. Done when every badge on a rebuilt site resolves to a `facts` row and the compatibility CSVs load in an Open Discourse notebook unchanged.

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

**Completed:** v0.12.0.0 (2026-10-02, A.2). Version-controlled source partitions and six reviewed occurrences separate Alexander Föhr's 13 speeches from Dirk-Ulrich Mende's 9 before persistence. Their stable person URLs and speech links are distinct; the shared profile cannot merge them again. See [reference validation](docs/a2-validation.md).

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

**Update 2026-10-03:** superseded if "Delete the feature-selection axis" (Architektur) lands. Without a feature to switch off, there is no dead link to filter.

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

**Context:** Correction 2026-09-30: `sachgebiet` appears nowhere in `scripts/` or the cached report JSON, so the build does not fetch it today. It sits on DIP's `/vorgang` record, which has to be fetched per Vorgang; it can also be empty, as it was on a sampled Kleine Anfrage. The rest of this paragraph assumes that fetch. Seed deterministically from DIP: `vorgang.sachgebiet` is a free field on every Vorgang, so map DIP Sachgebiete → the 13 fields in a lookup table and let the LLM fill only the gaps (plenarwatch: "assignment failure doesn't block publication"). Tag column on `agenda_items` and `votes`; add to `docs/data-license.md`'s export contract only after the pilot gate under Daten is decided.

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

**Why:** Speech text no longer includes `<kommentar>` (`speech_text_and_paragraphs`, `scripts/validate_dip_protocol.py`, since the Rede-text fix; 6 of 34,771 stored Reden contain "(Beifall bei", checked 2026-09-30), so the signal is dropped entirely rather than typed and counted. It is the data behind the long-term question "who interrupts the debate most" (PRODUCT.md). Plenarwatch's Zwischenrufe tracker is their most-shared page.

**Context:** Element name per the Bundestag DTD `dbtplenarprotokoll.dtd` (`kommentar` inside `rede`); verify against a live cached protocol before writing the parser, since no XML is cached in `.context/` today. Fraktion attribution is a regex over a small closed vocabulary ("bei der", "bei Abgeordneten der", "des Abg."), keep an `unattributed` bucket rather than guessing. 

**Effort:** L
**Priority:** P2 (raised 2026-09-30: long-term angle, PRODUCT.md)
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

## Zitierfähiger Datensatz

PRODUCT.md (2026-09-30) makes the dataset a product in its own right: a source researchers and journalists cite. Citable means a reader can name a version, get exactly those rows back later, and look up what changed since. Stable ids are complete; the release script, release changelog and DOI remain. The licence files and the roll-call redistribution question (both under Plenarwatch-Lücken) block any public release that contains votes.

When the first release goes out, the "Project stage: pre-release" section of CLAUDE.md has to become a stability policy: what may change between releases, and how a change is recorded.

### Stable ids for every row a release publishes

**Completed:** v0.12.0.0 (2026-10-02, A.2). Schema 3 / export format 2 supplies stable text row keys, a durable person/occurrence registry, corrections and resolvable aliases. Explicit offline replay upgrades old stores under a writer lock with staged integrity checks; facts, recipes and person URLs consume persisted assignments. All 997 tests pass (2 skipped); a 285-report reference replay preserves shared-source content, groups records identically for an incremental and a fresh replay, and reuses an unchanged replay. See [key and backup contract](docs/stable-ids.md) and [validation](docs/a2-validation.md).

**Pinned by tests:**
- Two builds, one with one more Sitzung than the other, give the same id to every row they share.
- Correcting a person's name, party or profile URL keeps their person key; a source that names a different Redner-ID or DIP id moves the occurrence instead.
- A person whose abgeordnetenwatch match turns trusted in a later build keeps their person key.
- Merging two persons leaves the merged-away key resolvable as an alias. Only merges that rest on a shared Personenkennung and reviewed corrections are durable; name-based guesses are recomputed, so an incremental and a fresh replay group records identically.

**Why:** A paper that cites "speech 18234" or links to an MP page must still point to the same thing next month. Before A.2 it did not: ids were insertion-order surrogates.

**Effort:** L (the person registry is most of it)
**Priority:** P1
**Depends on:** None

### Write the release script: versioned, immutable data releases

**What:** `scripts/publish_dip_pulse_data.sh`, referenced as "PR2" since the Daten page (#59) but never written. It publishes the export (SQLite, CSVs, manifest, checksums) as an immutable, dated release with a version number, and the site's `--data-base-url` then points at that release. Decide the version scheme: a date, or semver where a schema change bumps the major version.

**Why:** Without a release, "the dataset" is whatever the last local build produced. Nothing can be cited or downloaded twice with the same result. "Scheduled data-release workflow" and the Daten items are blocked on this.

**Effort:** M
**Priority:** P1
**Depends on:** Stable ids; licence files (ADR 0003); settle the roll-call source before releasing votes

### Public data changelog per release

**What:** Each release carries a `CHANGES.md` (in the release and on the Daten page) listing what changed in the data since the previous release: schema changes, coverage added, and every correction that moved a published figure, with old value, new value and reason. That is the old/new report the project already writes into commit messages (CLAUDE.md), made public and tied to a release. Keep a machine-readable twin (`changes.json`) so a researcher can check whether a figure they cited was affected.

**Why:** A researcher who cited version N must be able to see whether a later fix touched their numbers. The Fakt der Woche publication ledger covers cards only, and CHANGELOG.md covers code.

**Effort:** S per release once the format exists
**Priority:** P2
**Depends on:** The release script

### A DOI per release and a citation file

**What:** A `CITATION.cff` in the repo and a DOI for every data release. Zenodo's GitHub integration archives the repository's source zip on each GitHub release, not the release's data assets. So archive the data files through Zenodo's upload API from the release script instead, which gives a concept DOI plus one DOI per version. Show "Zitieren als …" with the version DOI on the Daten page and in the codebook.

**Why:** A DOI is what journals and editors accept as a stable reference, and it survives a change of host or name. The product name is still open, which matters little here: the DOI stays.

**Effort:** S
**Priority:** P2
**Depends on:** The release script; the product name (for the record's title, which can be updated later)

## Analysen

The long-term angle of the site (PRODUCT.md, 2026-09-30). None of it exists yet. Every series here counts Reden, so it waits for the Rede-counting items (#68, #70, Zwischenfragen and Gastansprachen, zu Protokoll gegebene Reden) and the v1 coverage backfill. Each recount moves every point of every series.

### Diskursanalyse: precomputed term series per Zusammenschluss and month

**What:** An `analysen/` page, and a Daten recipe that produces the same numbers. For a published, fixed list of topics, each defined by a term list (`data/terms.json`, reviewed like code): mentions per 10,000 words of Reden, by Zusammenschluss and by month (or quarter), across all covered Wahlperioden. Rules to fix before building:
- **Matching:** German compounds need an explicit rule, for example prefix match on word stems (`klima*` catches Klimaschutz and Klimawandel), plus a list of exclusions. Case-insensitive, on word boundaries. The rule is printed on the page.
- **Unit:** Reden only, per ADR 0001 and 0002. Zwischenrufe, Sitzungsleitung, Kurzinterventionen and Befragung are excluded, or later shown as their own series.
- **Normalisation:** per 10,000 words, because raw counts mostly track how much was debated.
- **Coverage:** only periods whose Sitzungen are complete, or every point labelled as covering Sitzungen mit Dossier only.
- **Reproducibility:** the chart is the recipe's result. The page says plainly that free search over any term is possible with the SQLite download, and links a ready-made query for it.
- **Traceability:** each point links to the Reden it counts.

Done when the chart and the recipe give the same numbers on the same release, and a test pins the matching rule on a handful of compounds.

**Why:** Decided 2026-09-30: precomputed series instead of free search on a static site, with free search delegated to the SQLite download. Term lists instead of a topic model are confirmed only provisionally. The user wants to see a preview before deciding, so the first step is a throwaway prototype: three topics, run over the reference store, drawn as a static chart, shown to the user. Build the page only after that decision. Open Discourse's Diskursanalyse, the named reference, uses 73 LDA topics with yearly granularity from 1949 to 2020. Published term lists are weaker at catching synonyms, but anyone can check and recount them, which fits a neutral, research-grade dataset.

**Context:** Start with a small set of topics (Klimaschutz, Migration, and a few more) and a neutrality review of the term lists before publishing. A term list that uses one side's vocabulary ("Klimakrise" vs. "Klimawandel") frames the result. Also consider filters that Open Discourse offers and the store can support: gender and age group from the abgeordnetenwatch columns.

**Effort:** L
**Priority:** P2
**Depends on:** The Rede-counting items; v1 coverage; stable ids

### Politikfelder over time: which Zusammenschluss emphasises what

**What:** Using the Politikfeld tags, show per Zusammenschluss and per period the share of its Reden (and of its speaking time by characters) that falls under each Politikfeld, and how the share of each Politikfeld in the whole plenary changes over time. Ship as a recipe first, then as a page next to the term series.

**Why:** This answers "which party has which priorities" and "how does attention to a topic change" (PRODUCT.md) from the agenda side, without depending on vocabulary. The term series answers it from the language side. The two complement each other.

**Effort:** M
**Priority:** P2
**Depends on:** Politikfeld tags; the Rede-counting items; v1 coverage

## Abstimmungen

### Abstimmungen for the daily view: what was decided, by topic, with dissenters

**What:** Close the gap to the abgeordnetenwatch.de Abstimmungen (checked 2026-09-30: their vote pages carry a plain-language description of what was decided, topic tags, the committees involved, the source documents and the named dissenters; the list filters by topic and date). For us:
1. A short description of what the vote decided. DIP's Vorgang record has an `abstract` field (checked on the API 2026-09-30), but the build neither fetches the Vorgang record nor keeps it: no match in `scripts/` or the cached report JSON. Fetch and store it, and use it where it exists. Otherwise write a labelled AI sentence under the validators item.
2. Topic filter on `votes/index.html`, from the Politikfeld tags.
3. The named Abweichler per Fraktion on the vote panel. The data exists (recipe `r3-abweichler`).
4. The responsible committee, from the Beschlussempfehlung.

Done when a vote on the archive can be found by topic and its panel answers "what was decided, who voted how, who broke ranks, where is the source" without leaving the page.

**Why:** PRODUCT.md names this as the votes part of the daily view. The vote panel and archive (v0.7.0.0) already cover tallies, outcome badge and sources. They miss the "what does this mean" layer a citizen needs.

**Context:** Correctness items come first, above all the P1 "Inverted-vote reading for Beschlussempfehlungen". A plain-language description of a rejected Beschlussempfehlung that doesn't handle the inversion would be wrong.

**Effort:** M
**Priority:** P2
**Depends on:** Inverted-vote reading; Politikfeld tags (for 2); deterministic validators (only for the AI fallback in 1)

## Architektur

### Split the dataset from the site: the site builds from a release alone

**What:** Separate the two halves of the project in the code. On one side: acquisition, the store and the export (the dataset). On the other: the renderers, which read only a store or release. Today `scripts/build_dip_pulse_site.py` (10.7k lines) holds both, and the renderers do not read from the store. Checked 2026-09-30:
- **Read from in-memory report JSON (`entries`):** the Dossiers (`protocols/*.html`), `puls.html`, the bills pages and the votes archive.
- **Read from the store:** only `abgeordnete/*`, `fakt/*` (plus `entries` for completeness) and `database.html`.
- **In the JSON but not the store:** AI summaries and their receipts; acquisition states; validation warnings; per-TOP `xml_drucksachen`, `xml_speakers`, `api.positions` and `api.linked_drucksachen` (the store keeps a subset); raw vote payloads; the DIP API dumps shown in the dev view.
- **The store can't be rebuilt from the JSON alone:** it carries the MP roster over from the previous store.

The real work is therefore to move into the store everything the site shows, then point each renderer at the store. The file split follows from that.

Done when an offline build from a downloaded release SQLite, with no report JSON present, produces the same site as today's build. Dev-view API dumps are exempt.

**Why:** PRODUCT.md principle 6 (one figure, one computation). Today a figure on a Dossier or puls.html comes from the JSON while the release's figure comes from the store, so the two can drift. It also lets the dataset be released on its own schedule, and makes a second site (if one ever happens) a second renderer over the same release.

**Context:** Do it in slices, one page type at a time, behind a comparison test (old output vs. new output). The votes archive is the easiest first slice, because the `votes`, `vote_fractions` and `vote_members` tables already exist. Overlaps with `protocol_acquisition` (Daten), which moves acquisition states into the store.

**Update 2026-10-03 (architecture review):** the Daten export is one slice of this split. It is about 1,600 lines inside `build_dip_pulse_site.py`: export machinery, recipe SQL, and the Daten page HTML and styles. `_run_export` takes 16 keyword arguments, and `export_distribution_data` takes `mp_lookup` and `readiness` from page building. Move it into its own module, `export(store, out_dir) -> manifest`, after "One module that counts Reden and Beiträge" and "One Persons module over the person registry" land. Recipes should call those modules, and nothing in the export should read a render artifact. Moving it earlier would only relocate the code.

**Effort:** L
**Priority:** P2
**Depends on:** None; best started before the Analysen pages, so new pages are store-first from the start

### Vote-member occurrence bindings: cost and use

**What:** `persist_vote` binds every roll-call vote member to a durable occurrence (`vote-member` key), about 154k `person_bindings` rows on top of the 35k speech bindings, each through the full `registry.bind` path. Measure and reduce repeat-bind cost while preserving every occurrence binding: B.2 now uses those keys to link dossier member rows to their Personenseite. Page eligibility still comes from MdB status or speaking contributions.

**Why:** Roughly 5x the bind work of speeches on a full replay, and the rows are exported in a public table.

**Context:** Deferred from the A.2 review (2026-10-01). The third A.2 ship round already made a repeat bind cheaper (one statement for the touched mark, no rewrite of an unchanged record) and computes the facts once per rebuild.

**Effort:** M
**Priority:** P3
**Depends on:** None

### A.2 test follow-ups

**What:** Tests the A.2 reviews proposed and nobody wrote: the online `main()` roster wiring with `mp-roster` not selected; `rebuild_database_from_entries` forwarding the `built` set to the facts engine; page eligibility of persons with no current mps row (a former MdB whose roster row vanished, a vote-only historical record); arrival-order independence of `p-NNNNNN` allocation and of `_content_digests`; table-driven occurrence-id cases for vote members, sampled people and the preserved roster; `_inputs_hash` and `_zusammenfuehrung` numbers.

**Why:** Each of these can be disabled today with the suite still green (checked by mutation in the A.2 review).

**Context:** Deferred from the A.2 review (2026-10-01); the generation allowance of /ship was spent. The roster wiring on a selected `mp-roster` and its outage abort, the catalog hand-offs and the unreleased-draft registry were covered in the second A.2 ship round.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Reviewed reassignment of a source record

**What:** Redesign the two corrections that place a source record on another person, occurrence `assignments` and `splits`, which `person_corrections.json` refuses since 2026-10-02. A placed record should be keyed by occurrence and owner (not by the printed speaker's identity, so a roster occurrence seen as `dip:` and as `aw:` lands on one record), contribute only its speeches and votes to the owner's page (never name, party, biography, `is_mdb` or profile), and leave the owner's partition and name guesses untouched (a partition record plus a reviewed record on one person is one owner, not two partitions). A split must refuse a `new_person_id` that is already issued to another person.

**Why:** Seven consecutive review passes of the first design reproduced criticals here: a placed record heading or filling the owner's page, an assignment on the Föhr person splitting its roster record into a second page, a `mps.dip_person_id` UNIQUE abort, a split silently absorbing records into an unrelated person. No shipped correction used either feature, so they were cut instead of patched again.

**Context:** Cut in the third A.2 ship round (decision 2026-10-02). The removed code and its tests are in commit history before the cut (`person_registry.bind`/`reconcile`, `ASSIGNMENT_PREFIX`, `_block_profile`, tests `test_an_owner_page_is_headed_by_its_own_record_not_the_assigned_one` and the split/assignment cases). Start with the invariants: a randomized check that adds assignments and splits must keep incremental == fresh, a fixed point, and owner pages built only from the owner's own records.

**Effort:** L
**Priority:** P2
**Depends on:** A real correction that needs it (none today)

### A.2 third ship round: deferred findings

**What:** Findings of the third A.2 ship round (2026-10-02) the user chose not to fix before release, none affecting today's data: (1) removing a partition from `person_corrections.json` leaves bound occurrences on the old partition records (documented as durable), while the evidence drops `partition`/`profile_blocked` and both records then carry the shared profile; decide re-key vs keep and pin it; (2) `corrected_speaker` compares the raw `xml_redner_id`, so a merged double id like `11005304 999990074` skips the reviewed occurrence override (use `derive.first_redner_id`); (3) `--offline` over a store path that cannot be opened (a directory, an unreadable file) still ends in a traceback, because `open_readonly` sits outside the `try`; (4) DIP roster rows without an id still collapse into one record through the `name-party:Unbekannt` identity (none in the cache); `roster_occurrence_id` hashes `7` and `"7"` differently; (5) `reconcile(full_build=False)`, the `vacated` evidence flag and the `bound` set in `_load_rows` now serve only tests, and the refusal stub in `persist_dip_pulse_store.py` could go; (6) `_first_touch` treats any `OperationalError` on its first insert as a missing temp table; `facts_report` is an out-parameter whose empty dict means "compute again"; (7) the export reads `person_by_mp_id` and backs up the store on separate connections, so a concurrent rebuild between them mixes two snapshots; (8) a corrected vote-member profile URL makes an incremental build issue a second record that a fresh build does not; (9) a name-guess group with one contradicting pair drops every merge in that group; a later occurrence can inherit an earlier one's `aw_match`; reviewed merges that name the same person as survivor resolve by file order; (10) a document id includes its URL, so a DIP URL rewrite changes vote-document ids and fact receipts; (11) the debut tie-break sorts document numbers as text; agenda indexes are `int()`-ed in persist but not in render/bills; the staged copy and writer lock live in the published data directory; (12) tests missing for the rebuild's `full_build=True` call, the offline facts hand-off, `compare_store_values._zusammenfuehrung` rows, the `mps` foreign-key arm, the end-of-rebuild foreign-key check and `today` forwarding.

**Why:** (1), (2), (7) and (8) can make an incremental build differ from a fresh one or show the wrong name; the rest are robustness, cost or test gaps.

**Context:** Deferred by decision in the third A.2 ship round after three review rounds converged and the 285-report reference replay stayed unchanged (grouping sha `6f877bf3d1e92af0`). Each item was reproduced or read by a reviewer; see the ship run record for the evidence.

**Effort:** M
**Priority:** P2
**Depends on:** None

### A.2 registry follow-ups from the third review pass

**What:** Findings of the third A.2 ship review that need a design decision and were not patched (2026-10-02): (1) done 2026-10-02: a stale roster record joins a live speaker as a partner only (`person_registry._stale_roster_partners`); (2) done 2026-10-04: evidence is folded order-independently (`person_registry._fold`): the set of (name, party) pairs and of Redner-IDs per record, a separate deterministic representative for the biography; a record in two qualifying name+party buckets joins neither (see docs/stable-ids.md); (3) the coverage gaps left after the third ship round's generated tests, each an extension of an existing test: `_guess_merges` partitions from live rows only; the offline CLI with all four registry tables dropped; the `-journal`/`-wal`/`-shm` sidecar sweep and `glob.escape`; the `--repersist` DatabaseRebuildError branch (exit 1, hint); `compare_store_values._zusammenfuehrung` totals; the manifest `stable_keys` exact value; (4) the vacated flag can go if `occurrence` becomes required in `bind`/`upsert_mp` (liveness is then "bound", plus the build's touched set). (5) the durable home person of a new record is allocated from its first persisted occurrence's own Redner-ID (`bind`, `allocate(conn, preferred)`), so a record holding several Redner-IDs gets a home that depends on persist order; found 2026-10-04 by the ship Red Team: build 1 persists the aw:5 record's occurrences a (Redner-ID 1) and b (Redner-ID 2) as [a,b] or [b,a]; build 2 moves b to Redner-ID 9 and adds an unrelated record with Redner-ID 2, which is pooled into the aw:5 person only for [b,a]. Reference cache: 0 records with more than one Redner-ID, so unreached there. Fix options: key the home on the record's identity (`stable_key('person','record',identity)`), or defer the xml/dip-preferred choice to `reconcile`, where `min(xml_redner_ids)` is known; either changes issued person keys and needs its own continuity decision and a two-build test. (6) findings of the ship review of 2026-10-04..09 that were accepted as follow-ups (none is a persist-order bug): the pass-1 durable union on a shared Redner-ID ignores abgeordnetenwatch conflicts (`match_rows`, pass 1; it is the same at the base for single ids and only newly reachable for records holding several Redner-IDs); pass 3 ignores a conflicting name-found aw profile because it blanks the anchor's profile bucket; contradicting trusted aw ids on one record, and a second `dip_person_id`, are resolved by string order (`_aw_choice`, `_fold`); "Unbekannt" is a name key and can win the shown party over a lowercase party such as "fraktionslos"; `reconcile(full_build=True)` silently matches nothing when the touched table is missing; `_touched` treats every `sqlite3.OperationalError` as "untouched"; a preserved roster row counts as roster authority for biography values that once came from a cached dossier; a stale roster record with two normalised name+party keys never rejoins its speaker; removing a partition correction is never honored (handoff prompt 02); roll-call members keyed `name-party:{name}|{party}` collapse two same-name members of one Fraktion in a vote; a wrong multi-Redner-ID merge never heals because `_hard_id_conflict` ignores aw ids; `bind` is about 60 µs slower per call (fold, one more `_touched` lookup), roughly 12 s per full rebuild, which a short-circuit for evidence already contained in the record would remove; tests: no case for two roster occurrences with different biography values (the `roster_bio` smallest-value rule), no seeded property test for `_fold`, the nine biography field names are spelled in three places, `tests/test_registry_evidence.py` takes about 15 s.

**Why:** (1) and (2) change which pages exist or how records group in rare, specific situations; (3) and (4) are hygiene and guards that no test pins.

**Context:** Deferred from the third A.2 ship round by the three-fix-cycle cap; the coverage gate was resolved as "list the gaps" (generation allowance spent).

**Effort:** M
**Priority:** P2
**Depends on:** None

### A.2 second-round review leftovers

**What:** Findings of the second A.2 ship round that were deferred by decision (2026-10-01): (1) the r1/r3 Daten recipes choose each person's representative record with a correlated subquery (`JOIN mps m ON m.id = (SELECT m2.id ... ORDER BY m2.is_mdb DESC, m2.id LIMIT 1)`), about 15x slower than a plain join (r3 1.61 s against 0.11 s on the reference store), run at every export and again in `compare_store_values`; precompute a representative column in `mp_canonical` and join on it (the `m2.id` tie-break is now a hash, so choose by a content key); (2) `_content_digests` orders every table by its text primary key, about 3 s more per store and 6-7 s per rebuild than rowid order; fold per-row hashes with a commutative sum instead; (3) advisory simplifications: drop `AbgeordneteComponent.after_persist` and call `collect_abgeordnete` directly, build the `collect_abgeordnete` lookup in one pass, replace the `ensure_canonical` temp copy by a view over `mps(id, person_id)`, drop the `mp_canonical` table if it is not a published contract, one `has_page` predicate instead of three, one `valid_person_key` helper for the three key checks; (4) `write_abgeordnete_pages` trusts its caller to have validated keys and follows an existing symlink at the target; re-check keys there and unlink before writing; (5) a person whose only occurrence moved to another identity loses its page without a redirect (decided: accepted, see docs/stable-ids.md).

**Why:** None changes a published figure; (1) and (2) cost seconds per build, (3) to (5) are readability and defence in depth.

**Context:** The user deferred these to keep the final review on code with mutation-checked tests.

**Effort:** M
**Priority:** P3
**Depends on:** None

### A.2 review leftovers

**What:** Small cleanups the A.2 review found and nobody asked for yet: `person_registry.mp_keys` and `_mp_external_ids` repeat the same three-way id extraction; `_load_corrections` uses an `lru_cache` for one file; `rebuild_database_from_entries` forwards every argument to `_rebuild_database_from_entries` only to take the lock and translate errors; the `built = {"votes"} if ... else set()` expression exists in three places; the offline path reaches `collect_abgeordnete` through the mp-pages component's `after_persist` while the online path calls it directly; `tests/test_facts.py` goldens that depend on sha256-ordered ids (derive them from the data); `person_registry.merge` and `reconcile` write into the `mps` table whose schema lives in `persist_dip_pulse_store`.

**Why:** Less to read, fewer places to drift.

**Context:** Deferred from the A.2 review (2026-10-01); none changes behaviour.

**Effort:** S
**Priority:** P4
**Depends on:** None

### One module that counts Reden and Beiträge

**What:** Give the counting of Reden one module. It should own which XML records count as a Rede and which are Beiträge (ADR 0001, ADR 0002), with attribution to Zusammenschluss, Sprechrolle and Person. It returns counted rows or aggregates per period and grouping. Today `derive.py` owns attribution but nobody owns counting. Five places count on their own:
- `render_dip_pulse_html.item_stats` and `week_stats` use the parser's `xml_speech_count` (falling back to `len(speakers)`).
- `build_dip_pulse_site` counts in three spots: the bills tally in `collect_bill_pages`, `speech_count` in `collect_abgeordnete`, and Daten recipes r1, r2 and r5.
- `facts.py` has six speech queries.
- `compare_store_values.py`.

The "corrected speaker, `rede_id`, `occurrence_id` of a Rede" recipe is copied in render, build and `persist_report`. Done when every page, Kennzahl and recipe reads Reden through this module, and no other module decides what a Rede is.

**Why:** Puls counts from the report JSON (`xml_speech_count`) and Fakten count the rows `persist_report` inserted from `xml_speakers`, so a published Puls figure and a Fakt can disagree. The next change to what counts as a Rede (Zwischenfrage credit, Zu Protokoll gegebene Reden, roadmap A1) has to be made in five places.

**Context:** Found by the architecture review of 2026-10-03 (origin/main 2801f1c). This is the read path that "Split the dataset from the site: the site builds from a release alone" needs: once renderers read the store, they should read Reden through this module rather than writing new SQL. Recipe r2 hard-codes the Sprechrolle labels and the Zusammenschluss COALESCE instead of using `derive.SPRECHROLLE_LABELS` and `ZUSAMMENSCHLUSS_SQL`, and `compare_store_values._redeanteil_group_sql` is a third copy. Tests can then seed store rows and assert counts through one interface, instead of building a report, a store and a page.

**Effort:** L
**Priority:** P2
**Depends on:** Best done with or right after the A1 PRs still open, so the counting rule moves once

### Typed completeness gaps instead of reason strings

**What:** Make a Sitzung's acquisition gaps a typed value with an enum reason and structured detail (scan pages used, date), owned by `publication_state.py`. Today the reasons pass through these steps:
- `validate_dip_protocol` creates them as `failure_reasons` and `roll_call_scan_end`.
- `build_dip_pulse_site.annotate_report_acquisition` rewrites them.
- `facts.completeness_from_reports` flattens them into display text ("votes partial (source_stale)", "scan_budget_exhausted after N pages").
- `build_dip_pulse_site._structural_vote_gap` parses that text back with `text.index("(")` and `_BUDGET_PAGES_RE` to decide whether `--backfill-incomplete` rescans a Sitzung.
- `build_publication_manifest` and `features/votes.py` read the raw dicts again.

Done when the backfill decision, the Completeness basis and the manifest consume the typed gap, and text is produced only for display.

**Why:** Rewording a reason in `facts.py` silently changes which Sitzungen the backfill takes. `publication_state.AcquisitionState` is already typed, but these paths bypass it. The default vote scan budget (`30`) is repeated in `main()` and in the backfill path.

**Context:** Found by the architecture review of 2026-10-03. Overlaps "Persist per-sitting acquisition state in the store (`protocol_acquisition`)". The typed gap is the vocabulary that table would store, so do this first. Several items in "Harden the vote acquisition and catalog completeness paths" ((1), (11), (15)) touch the same code.

**Effort:** M
**Priority:** P2
**Depends on:** None

### One Persons module over the person registry

**What:** Put `person_registry.py` behind one interface that the rest of the code uses for Namensabgleich, Zusammenführung, Personenseite eligibility, page links and the mp-to-Person map. Registry tables become private to it. Today this logic is spread out:
- **Personenkennung keys** (`aw:`, `xml:`, `dip:`) and the trusted-aw rule are built in `persist_dip_pulse_store.mp_identity`, `person_registry.mp_keys`/`_mp_external_ids`, `render_dip_pulse_html.mp_page_href` and `build_dip_pulse_site.speaker_identity`.
- **The mp-to-Person map** is built three times: `facts.ensure_canonical` (a TEMP table), `_run_export`'s `mp_canonical`, and `collect_abgeordnete`.
- **`collect_abgeordnete`** (about 225 lines in the build file) queries `person_records`, `person_bindings` and `person_aliases` directly and parses `evidence_json`.
- **The `mp_lookup` dict** mixes four key namespaces and is threaded through about 50 build call sites.

**Why:** The data export's `mp_canonical.has_page` comes from `mp_lookup`, an HTML link map, so the dataset depends on what the renderer produced. Identity bugs (see the Abgeordnete merge-gap history) have to be fixed in every copy.

**Context:** Found by the architecture review of 2026-10-03. It subsumes the identity items already deferred: "A.2 review leftovers" (`mp_keys`/`_mp_external_ids` duplication, `merge`/`reconcile` writing into `mps`) and "A.2 second-round review leftovers" (3) (one `has_page` predicate instead of three, the `ensure_canonical` temp copy, dropping `mp_canonical` unless it is a published contract). Close those parts there when this lands.

**Effort:** M
**Priority:** P2
**Depends on:** None

### The store owns its schema and its rebuild

**What:** Make `persist_dip_pulse_store.py` the one module that owns the SQLite store, with a small interface: open, rebuild from entries, persist a report. Today:
- **Table definitions live in four modules:** `persist.initialize` and its migrations, `person_registry.initialize`, `facts.py`, and the export tables in `build_dip_pulse_site._run_export`.
- **The rebuild lifecycle lives in the build file:** `rebuild_database_from_entries` stages the store, copies the registry, restores the roster through about 25 keyword arguments to `upsert_mp`, reconciles, computes facts, validates and swaps. `repersist_cached_reports` and `ingest_mdb_roster` are there too.
- **The facts engine runs from three call sites:** the rebuild, `run_facts_engine`, and the fallback in `run_data_pipeline`.
- **Test fixtures are a third writer:** `tests/_facts_fixture.seed_weeks` and `tests/_daten_fixture.seed_store` write rows through `upsert_*` and have to follow every schema change.

**Why:** A schema change touches four files plus the fixtures. Store tests sit in `test_build_dip_pulse_site.py` only because the rebuild lives there.

**Context:** Found by the architecture review of 2026-10-03. Candidates for the same pass: the "`persist_votes` is dead" note in "Stale derived data after `--offline --repersist`", and `rebuild_database_from_entries` forwarding to `_rebuild_database_from_entries` ("A.2 review leftovers"). This is the foundation for the Reden and Persons modules above, and for "Split the dataset from the site". Fixtures should then build stores through `persist(report)`, the path production uses.

**Effort:** L
**Priority:** P3
**Depends on:** None

### Delete the feature-selection axis

**What:** `features.publication_selection()` always returns every component, and `render_site`, `write_report_and_page` and `render_html` overwrite their `features` argument with it. Even so, `features: Selection` is threaded through about 28 build signatures and 2 render signatures, and `if "bills" in features` guards are always true. Remove all of it:
- the Selection parameter;
- `features/loader.py`;
- the pass-through adapters `features/bills.py`, `features/facts.py` and `features/abgeordnete.py`, which call back into build functions through an untyped `ctx` dict;
- the deprecated `--features`, `--enable`, `--disable` and `--list-features` flags with `resolve_from_args` and `warn_deprecated_feature_configuration`.

`render_site` calls its page builders directly. `votes`, `summaries` and `aw_profiles` do real work and stay as plain modules without `ctx`.

**Why:** It is a seam with only one adapter: nothing varies across it, and every signature pays for it. CLAUDE.md's pre-release rule says to drop compatibility shims rather than carry them.

**Context:** Found by the architecture review of 2026-10-03. This makes "Global header nav links to a page a build didn't write when its feature is off" (Publication) moot: there will be no feature to switch off. Close it when this lands. Also check the `AbgeordneteComponent.after_persist` path that "A.2 second-round review leftovers" (3) proposes to drop.

**Effort:** S
**Priority:** P3
**Depends on:** None

### A build pipeline module behind `main()`

**What:** Replace the 480-line `main()` in `build_dip_pulse_site.py` with `build(config, source, clock) -> BuildResult` (pages written, manifest, gaps). DIP access goes behind a source seam with two adapters: HTTP for online builds, and cached reports for `--offline` and tests. Today:
- The offline and online branches repeat the same tail: `run_data_pipeline` returns a 5-tuple that is unpacked into `render_site`'s roughly 20 keyword arguments, in both branches.
- `write_report_and_page` takes 21 parameters, builds a fake `argparse.Namespace` for `dip.build_report`, and returns XML through an out-parameter dict.
- `getattr(args, ...)` appears about 40 times.
- `resolve_today` is called five times while other clocks bypass it, including some in `facts.py`.

**Why:** Orchestration can only be tested by patching module globals: `test_build_dip_pulse_site.py` has about 123 `patch()` calls and 16 full `main()` runs. "Some date checks use the wall clock, not `--today`" (item (11) of "Harden the vote acquisition…") is a symptom.

**Context:** Found by the architecture review of 2026-10-03. Easier after "The store owns its schema and its rebuild" and "Delete the feature-selection axis", which remove most of the parameters threaded through `main()`. `validate_dip_protocol.py` (2.6k lines, imported as `dip`: HTTP client, XML parser, roll-call scraping, three LLM providers, report assembly) is the natural home for the source adapter. `enrich_with_llm_summaries` taking the CLI namespace and the `global _namenslisten_entries` cache should go in the same pass.

**Effort:** L
**Priority:** P3
**Depends on:** Best after the store and feature-axis items above

## Completed

### Credit a Zwischenfrage to the MdB who asked it, and keep Gastansprachen out of speech counts

**Implemented on `a1-followups` (2026-10-05):** Nested source segments are stored and linked as separate Beiträge. Guest coverage is qualified: the inspected 2016/2021 memorial addresses precede the plenary sitting and are absent from its XML; no general guest detector or exhaustive ingestion is claimed. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### A1 classifier precision: measure and tighten the Kurzintervention and Fragestunde rules

**Implemented on `a1-followups` (2026-10-05):** Occurrence-role recovery, historical headings/classes, explicit D4 rejection, grant precision, party/name extraction and unique sitting-source asker matching are implemented. The old pronoun example at 21/81 was not reproduced; a pronoun regression is covered without claiming that source finding. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### Stale derived data after `--offline --repersist`

**Implemented on `a1-followups` (2026-10-05):** Persisted input rule version 2 guards facts/export/store-consuming rendering; SHA pairing and proven TOP mappings protect replay. Vote receipts select one coherent source row and dead adapters are removed. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### Regenerate the architecture diagram for the Rede/Beitrag split

**Implemented on `a1-followups` (2026-10-05):** Architecture JSON/HTML regenerated with speech kinds, contributions, replay and persisted-rule refusal; archify validation and Chrome light/dark inspection recorded. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### Zu Protokoll gegebene Reden: decide what they are, then store them

**Implemented on `a1-followups` (2026-10-05):** Approved separate kind `zu_protokoll` is ingested/displayed with nullable TOP/page, including sitting-level submissions. Correction to the original examples: 19/239 (29) and 18/200 (11) are §31 declarations, excluded; 18/100 has 35 explicitly typed written submissions. [Validation and remaining final A2 gate](docs/plans/a1-validation.md). Final merged A1/A2 readiness for A3 is pending.

**Completed:** v0.15.0.0 (2026-10-05)

### Roll-call member rows link to external profiles, never to our own MP pages

**Completed:** v0.14.0.0 (2026-10-04), B.2. Dossier member rows resolve the shared, normalized vote-member occurrence key through `mp_lookup`, then fall back to the external profile or a plain name. TOP and sitting votes use the same member renderer. The T0 gate required widening scope: surname-first vote names are normalized for matching, roster/speaker pairs settle first, then vote records join one unambiguous person. Conflicting ids, ambiguous namesakes and distinct records present in one roll call stay split. MP pages prefer roster/speaker biography and correctly label a Bundestag profile fallback.

**Measured:** 285-report scratch replay: internal lookup coverage **0 → 147,971 / 154,015 stored member rows (96.08%)**; split-bucket misses **147,971 → 0**; vote-only misses remain **6,044 rows**. All 154,078 vote-member occurrence keys stay byte-identical. Current person groups **3,386 → 1,294** because duplicate vote-source records now join their roster/speaker person. D3 collisions: **0** (no namesake-key TODO needed). Rendered member links: **0 → 166,656 internal**, **173,407 → 6,751 Bundestag** (965 persons); every internal href exists. Browser click-through reaches the matching vote on the Personenseite. Full unittest suite passes.


### Detect Kurzinterventionen and Erwiderungen, and stop counting them as Reden → #68; Stop counting the Fragen and Antworten of the Befragung and Fragestunde as Reden → #70

**Completed:** v0.13.0.0 (2026-10-03), PR 1 of the A1 roadmap item, branch `a1-what-counts-as-rede`. `speeches` holds Reden only; every other unit is a Beitrag in the new `contributions` table, typed by `kind` (`scripts/speech_kinds.py`). The Fragestunde, which has no `<rede>` elements (75 of 76 Fragestunden stored no row), is parsed from its flat `<p klasse="redner">` turns. Every online update now keeps the sitting's XML in `data/xml/`, and `--offline --repersist` re-reads Reden and Beiträge from it.

Reference store (285 Sitzungen), the same cached reports parsed by the code before and after, so only this change moves:
- Reden 34,775 -> 25,800 (-8,975, -26 %); DIP's own `Rede` count for the same sittings is 26,396 (our count is 2.3 % lower). The first measurement of this branch said 26,002; the /ship review found and fixed two classifier defects (below), which moved it by 202.
- Beiträge 14,363: 636 Kurzinterventionen, 581 Erwiderungen, 3,890 Fragen and 3,868 Antworten of the Befragung, 2,701 Fragen and 2,687 Antworten of the Fragestunde.
- `speeches.char_count` sum 114,848,500 -> 107,813,062 (-6.1 %).
- Redeanteil: Bundesregierung 14.6 % -> 4.6 %, CDU/CSU 22.2 -> 24.8, SPD 17.7 -> 21.2, AfD 14.6 -> 15.2, Grüne 13.5 -> 14.5, FDP 7.4 -> 8.5, Linke 6.9 -> 7.4.
- Kurzinterventionen 636 against DIP's 682 (93.3 %), Erwiderungen 581 against 646 (89.9 %); 59 of 285 sittings differ from DIP in one of the two kinds, and in 6 sitting-kinds the XML holds more than DIP. The detector reads the Sitzungsleitung's wording and prefers precision: it misses announcements that only refer back ("das Wort zu einer solchen"), that call it "Intervention" or that contain a negation ("der eine Kurzintervention bekommt, weil er keine Zwischenfrage stellen durfte"). DIP's `Frage`/`Antwort` counts are not comparable (DIP 6,884 + 633 Fragen and 4,198 Antworten against 6,451 and 6,416) and are not checked.
- Fixed in review, measured on the same 285 XMLs (17 sittings moved, nothing else): (1) three items whose heading sits in a `T_ZP_NaS` paragraph (20/143 TOP 2, 20/159 TOP 3 and 4) were not recognised as Befragung or Fragestunde, so 212 Befragung turns counted as Reden and 67 Fragestunde turns were stored nowhere; (2) the Erwiderung wording rule ("Möchten Sie antworten? - Nein") turned real Reden into Erwiderungen (15 Reden back, including Edis's maiden speech in 21/14, which the `erste-reden` Fakt needs); 5 announced Kurzinterventionen that had been read as Erwiderungen or Reden are now typed correctly. Sittings that differ from DIP: 68 -> 59; sitting-kinds where the XML holds more than DIP: 15 -> 6. The Erwiderung total moved away from DIP's 646 (596 -> 581) because the removed ones were false positives.
- Not measured: the Fakt der Woche winners that changed. The reference tree has no cached DIP catalog, so the facts engine posts nothing offline; run an online update, then compare. The five speech metrics are at version 2.

### render_html mutates the report it renders

**Completed:** v0.12.0.0 (2026-10-02). `render_html` corrects copies of the speeches; the cached dossier JSON keeps the printed speaker (pinned by a test that writes a dossier twice).

**What:** `render_dip_pulse_html.render_html` replaces each `speech["speaker"]` with the corrected speaker and adds `speaker["occurrence_id"]` in place. The online path then writes that report to the cached JSON in `write_report_files`, so the cache holds the correction instead of the raw XML evidence.

**Why:** Raw evidence should stay raw. Today the mutation is idempotent, but removing a correction cannot restore the original names, and online and offline builds see slightly different inputs.

**Context:** Deferred from the A.2 review (2026-10-01). Fix with a side map keyed by (item index, sequence) or a copy of the speakers, applied only at render and persist time.

**Effort:** M
**Priority:** P3
**Depends on:** None

### Match roll-call votes to a TOP when Drucksache numbers fail

**Completed:** v0.10.0.0 (2026-09-30). Uniquely matching titles can attach a candidate to a TOP; otherwise fetched candidates remain in `sitting_votes` and persist through `votes.protocol_id`. They appear under “TOP nicht zugeordnet”; acquisition completeness now tracks missing scans and failed fetches separately from missing TOP attribution.

**What:** `enrich_with_api` (`scripts/validate_dip_protocol.py`) attaches a roll-call vote to a TOP only when their Drucksache numbers overlap. A candidate that matches none is logged, counted (`validation_summary.unmatched_roll_call_vote_count`) and, since fix-votes-completeness, makes the sitting's votes `partial` (`unmatched_candidate`). Match by title or vote date where numbers fail, or store the vote against the Sitzung without a TOP.

**Why:** After the 2026-09-29 backfill of the reference copy, 23 candidates in 15 sittings (e.g. 21/83 vote 1008, 21/40 votes 977 and 978) matched no TOP, so those votes are in no dossier and not in the store, and those sittings, with the weeks and months holding them, stay incomplete until this is fixed.

**Effort:** M
**Priority:** P2
**Depends on:** None

### Inverted-vote reading for Beschlussempfehlungen ("Ja = Antrag ablehnen")

**Completed:** v0.10.0.0 (2026-09-30). Confirmed proposition-specific evidence is stored with its source and excerpt; raw vote totals and proposition result stay intact, while dossier and archive views derive the Antrag outcome and Fraktionsposition.

**What:** When the voted document is a committee recommendation to reject a motion, the panel states the reversal in one procedural sentence, prints the legend `Ja = Antrag ablehnen · Nein = Antrag annehmen`, and derives each fraction's position ("für den Antrag" / "gegen den Antrag" / "geteilt") from its `leading_vote`; raw counts stay untouched. Done when the Übergewinnsteuer-style case (plenarwatch post `ablehnung-eines-antrags-zur-uebergewinnsteuer-2026-04-24`) renders the derived positions and a test pins the inversion.

**Why:** Without the inversion the outcome badge from the previous item reads "Angenommen" on a vote whose political meaning is "Antrag abgelehnt", the single most misleading state a vote panel can be in. "Beschlussempfehlung" appears in our code only as glossary prose (`scripts/render_dip_pulse_html.py:59-188`).

**Context:** Detection signal: the DIP `vorgang`/Drucksache title of the voted document starts with "Beschlussempfehlung" and the recommendation text contains "abzulehnen"; DIP's `/drucksache` endpoint carries the title, so no PDF parsing. Store as a boolean on `votes`; render in `render_vote_summary`.

**Effort:** M
**Priority:** P1
**Depends on:** Vote outcome badge

### Majority rule for derived vote outcomes (Art. 79(2), 67, 68 GG)

**Completed:** v0.10.0.0 (2026-09-30). Official attributed results take precedence; without one, recognized special-majority procedures stay unknown. Ordinary votes retain the Ja/Nein rule.

**What:** `validate_dip_protocol.vote_result` derives "Angenommen"/"Abgelehnt" from a plain yes>no majority of votes cast. A Grundgesetz amendment needs two thirds of the members (Art. 79(2) GG); Kanzlerwahl, konstruktives Misstrauensvotum and Vertrauensfrage need an absolute majority of the members (Art. 63, 67, 68 GG). Thread the applicable threshold (from the Vorgang/Drucksache type) into `vote_result`, or return unknown for those vote types when no official result was scraped. Validated with fixtures for each special-majority procedure: without an attributable official result the outcome is unknown, including Ja > Nein; no membership total is inferred.

**Why:** Found by the /ship red-team review of the badge (2026-09-26). Latent: every Grundgesetz vote in the real store is labelled correctly today, but a high-absence sitting would mislabel one silently.

**Context:** The official-result scrape already wins when bundestag.de states the outcome; the gap is only in the derived fallback.

**Effort:** S
**Priority:** P2
**Depends on:** Vote outcome badge

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
