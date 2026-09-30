# Changelog

All notable changes to this project will be documented in this file.

## [0.11.0.0] - 2026-09-30

### Added

- Kurzinterventionen, Erwiderungen, and the Fragen and Antworten of the Befragung der Bundesregierung and the Fragestunde are now stored as their own Beiträge, typed by kind, in a new `contributions` table and CSV (20 CSV files now). Each dossier shows them beside its Reden, a Person's page shows them apart from their Reden, and the week radar reads “2 Reden, 59 Fragen, 55 Antworten” for a Befragung. The Fragestunde, which has no `<rede>` elements and stored nothing for 75 of 76 sittings, is read from its flat turns.
- Change what counts as a Rede without fetching anything again. Every online update now keeps the sitting's Plenarprotokoll XML in `data/xml/`, and `--offline --repersist` re-reads Reden and Beiträge from it. `--fetch-xml` downloads the XML for sittings cached before this release (public bundestag.de files, about 0.3 s each).
- Every build warns when a cached report predates this counting rule, names how many and prints the fix, so an old store cannot quietly mix with new numbers.

### Changed

- Only Reden count as Reden. On the 285 cached sittings the Reden count falls from 34,775 to 25,800 (DIP's own count is 26,396) and the characters of all Reden by 6.1 %. The Bundesregierung's Redeanteil falls from 14.6 % to 4.6 %; CDU/CSU 22.2 to 24.8, SPD 17.7 to 21.2, AfD 14.6 to 15.2, Grüne 13.5 to 14.5, FDP 7.4 to 8.5, Linke 6.9 to 7.4. The opening reports of a Befragung stay Reden. The five Fakt der Woche metrics that count Reden are at version 2.
- Kurzinterventionen are detected from the Sitzungsleitung's wording, and the parser compares them and the Erwiderungen per sitting with DIP (636 of 682 and 581 of 646 overall, 59 of 285 sittings differ). Detection prefers precision, so some Kurzinterventionen still count as Reden.
- A cached report with a Befragung or Fragestunde heading is never ranked as a week topic, also when the report was made before this release.

### Fixed

- A Befragung or Fragestunde whose heading the Bundestag XML sets in a different paragraph class (20/143, 20/159) is recognised: 212 Fragen and Antworten no longer count as Reden and 67 Fragestunde turns are stored.
- A Rede after a Kurzintervention is an Erwiderung only when the same Redner gives it. Fifteen real Reden, including a maiden speech that the “erste Reden” Fakt needs, had been filed as Erwiderungen.
- `--offline --repersist` refuses cached XML that is not the protocol of its sitting (a maintenance page, another sitting, no agenda items), names the file, and leaves the store untouched. It no longer marks such a report as current. The profiles resolved online survive the re-parse.

## [0.10.0.0] - 2026-09-30

### Added

- See every fetched roll-call vote in its sitting, even when no agenda item can be assigned. Unambiguous title matches link votes to their topic; unmatched votes appear under “TOP nicht zugeordnet” and remain in the archive, member histories, facts, and data export.
- Read the Antrag outcome and faction positions when a vote concerns a recommendation to reject it, with an explicit “Ja = Antrag ablehnen · Nein = Antrag annehmen” explanation and retained source evidence.

### Changed

- Special-majority procedures remain unknown without an attributable official result. Ordinary votes retain the Ja/Nein rule, and raw vote counts remain unchanged.
- Vote acquisition completeness now measures scans and successful detail fetches independently of topic assignment. Existing stores migrate sitting links and interpretation fields without losing votes.

### Fixed

- Conflicting or negated recommendation evidence no longer reverses the displayed outcome. Results derived from counts use the voted proposition’s scope when official text cannot establish an outcome.
- Fresh profile resolution updates vote members instead of silently keeping stale cached links.

## [0.9.0.0] - 2026-09-29

### Added

- Apply stored-value corrections to every cached sitting without network access using `--offline --repersist`. The rebuild preserves the MdB roster, leaves the previous database untouched on failure, and keeps the file when its content is unchanged.
- Compare two builds with a read-only report showing changes in speech text, vote majorities, affiliations, person pages, legislative pages, and published facts. Shared-sitting and whole-store modes keep new acquisitions distinct from corrected values.

### Fixed

- Speech lengths now include only the named speaker’s words, excluding the chair and intervening speakers. Unattributed text is measured separately.
- Parliamentary groups and factions use consistent names, including the historical Gruppe Die Linke; duplicate speaker names and merged source records are handled consistently.
- Government, Bundesrat, and other official speaking roles count separately from factions. Unknown roles stop persistence with a diagnostic naming the affected speeches.
- Vote majorities are absent on a tie or when nobody voted. Vote panels, archive filters, and dissent counts use the same rule; non-attached members are excluded from faction dissent.
- Person pages use verified identifiers and unambiguous name matches, keeping namesakes and conflicting DIP identities separate while rejoining corroborated records for people with two speaker IDs.
- Only legislative procedures receive Gesetzesvorhaben pages; other procedures on the same agenda item (Entschließungsanträge, Anträge) are listed on each Gesetzgebung’s page as such, not as its companions. Public labels and the data-correction recipes now describe these rules.

## [0.8.0.0] - 2026-09-29

### Added

- An update now fetches roll-call votes by default. Until now they were an opt-in, so every update since June recorded votes as "not requested" and the July and September 2026 votes never reached the site. `--no-votes` skips the scan for one run. Backfilled into a copy of the reference store, votes went from 217 to 232 and the newest vote from 2026-06-12 to 2026-09-25.
- Every build now says what is incomplete: the weeks and months that cannot post a Fakt yet, the sittings DIP lists that are missing or not fully acquired, why, and the exact command that fixes it. `--backfill-incomplete` acquires exactly those sittings and keeps every other cached dossier.
- A Fakt week or month that is held back names the sitting that is missing ("unvollständig erfasst: Sitzung 21/96 (2026-09-24) fehlt").
- The build logs how many roll-call list pages and vote pages each sitting needed, and the sittings of one build share the list pages.
- The repository now carries a domain glossary (`CONTEXT.md`) and decision records (`docs/adr/`) that define the terms the site uses (Sitzung, Dossier, Rede, Fakt, completeness and more), and why a Kurzintervention is not counted as a Rede.

### Changed

- A week or month is now complete only when every sitting DIP lists for it is in the store and fully acquired. Before, a sitting whose dossier failed or was never built was invisible, so a period could look complete on one of three sittings. On the reference copy this withholds the weeks and months that lack sittings (for example June 2026, which had been measured on 3 of 6 sittings), and 15 sittings whose roll-call votes match no agenda item stay incomplete until the match rule improves.
- A vote acquisition is complete only with evidence: the scan passed the sitting's date, no request failed, every listed vote found its agenda item, and the report records how the scan ended. Older reports without that record are re-acquired by the backfill.
- Every online build fetches the whole DIP catalog (checked against DIP's own count) and keeps every cached dossier. `--limit` and `--document-number` now narrow only which sittings are refreshed, never what the site and the store keep.
- A vote scan that fails for a network or server reason keeps the sitting's cached dossier instead of replacing it.
- Roll-call and XML page requests retry a transient network error; a reset while reading a DIP response no longer ends a long build.
- The README documents the backfill recipe, a scratch-directory preview, and the order in which config files, environment and flags decide which enrichments run.

### Fixed

- A Drucksache reference with a foreign URL no longer aborts the build (a cached 2022 dossier quotes a syriahr.com article).
- Cached reports and the catalog are written atomically, so an interrupted build cannot leave a truncated file.

### Removed

- `--preserve-existing-dossiers`. Every build keeps the dossiers it has cached; delete a dossier's JSON file to drop it. A systemd unit or script that passes the flag must drop it.

## [0.7.0.0] - 2026-09-28

### Added

- Every roll-call vote panel now shows whether the motion passed. The badge reads "Angenommen" or "Abgelehnt", sourced from bundestag.de's own stated result when the page states one, or otherwise computed from the vote count and marked "(berechnet)" so the difference is visible on hover.
- Every Drucksache a vote panel mentions now links to its source document instead of showing plain text, and a link to the vote's XLSX Namensliste export appears next to the detail link when bundestag.de has published one.
- A new "Abstimmungen" page lists every roll-call vote across every sitting the site has built, reverse-chronological and grouped by month, with a Fraktion filter (by that Fraktion's majority position on each vote).

## [0.6.6.0] - 2026-09-26

### Added

- The dossier sidebar now marks the TOP you are reading. The highlight follows scrolling, sidebar clicks, resizes and the end of the page, keeps the marked row in view inside the ranking list, and turns off where the sidebar sits above the text (narrow or short windows) and in print.
- Each SQL recipe on the Daten page has a "Kopieren" button. Where the browser cannot write to the clipboard, the button selects the SQL for ⌘C/Strg+C instead; a copy that fails late never overrides a newer click or your own selection. Without JavaScript the button stays hidden.
- Dossier footers link to the Daten page when the build has data to show, like the other pages' Daten links.

## [0.6.5.0] - 2026-09-25

### Changed

- When sitting counts differ, the Wochenvergleich now compares speeches, agenda items, speech text, and Fraktion speaking shares across weekdays present in both weeks. The page names those weekdays and keeps `n/a` when none overlap.

### Fixed

- The Wochenpuls sparkline now identifies its full-week trend when the figures above it use matched weekdays.

## [0.6.4.0] - 2026-09-25

### Changed

- The architecture diagram now traces Fakten, the Daten export and generation manifest through to the Daten page. A short contributor guide links the test, offline rebuild and online update commands.

### Fixed

- Command-line scripts now reject Python versions below the documented 3.11 floor with a clear English and German error.

## [0.6.3.0] - 2026-09-25

### Fixed

- Aufmerksamkeitsrang rows now begin with the agenda topic instead of procedural wording, keeping the first sub-item's topic on a bundled heading (an Antrag under a) followed by a Gesetzentwurf under b)); the complete normalized heading remains available on hover.

## [0.6.2.0] - 2026-09-25

### Fixed

- Ranking links retain matching TOP anchors when an index contains HTML-sensitive characters.
- Links share teal visited states and visible keyboard focus outlines, including pages without their own teal palette variable.

### Removed

- New stores and speech writes no longer duplicate speech text in `paragraphs_json`. Existing stores drop the column on SQLite 3.35+; older versions log a warning and retain it. Distribution downloads keep the same schema and row counts.

### Verified

- Dossiers already show the session title above the content and place the protocol developer dump after it. Regression coverage preserves both; explicit developer builds retain their existing visible raw data without a toggle, while normal builds omit it.

## [0.6.0.0] - 2026-09-24

### Added

- A new "Fakt der Woche" page series shows one standout, statistically unusual fact per sitting week (and, monthly, per calendar month): the closest vote, the most rebel votes against a Fraktion's line, the longest debate and longest single speech, the longest sitting, the most first-time speeches, the most active MP of the month and the month's most-discussed legislative matter. Every card names its comparison population and links straight back to the protocol, speech, vote or bill it cites; a Methodik page explains the rule and why some weeks post no fact at all (the numbers only qualify once they're unusual enough, not merely "the most" of a slow week). A new "Fakten" entry joins the site's main navigation.
- Each fact ships as a downloadable, shareable image card alongside its page — the longest-speech card now also names the debate's topic, not just who spoke.
- The Daten export documents the three new fact tables and the speech-time Fraktion column as derived/DIP-sourced data respectively, so a downloaded copy of the database is self-explanatory about where every column comes from.

### Changed

- The "Redeanteil nach Fraktion" export recipe now groups speeches by the Fraktion the speaker belonged to at the time of the speech, not their current party — a member who has since switched or left a Fraktion no longer retroactively changes an earlier week's speech-share numbers.
- Building the Fakt der Woche pages resolves each fact's source citation once per build instead of twice, and stops re-scanning the whole debate-topic table once per citation — the archive keeps rebuilding at the same speed as it grows week over week.

### Fixed

- Merging a duplicate party record (the historical "list-repr" party-name bug) now recomputes which side of a vote was the majority from the merged tallies, instead of leaving a stale majority that could misclassify who voted with or against their Fraktion.
- A citation whose page reference has no quadrant marker — a normal, common case in the protocol XML — now resolves correctly instead of being wrongly treated as an unrecoverable source.
- A sitting week with genuinely zero first-time speeches now counts correctly toward the "most first-time speeches" metric's history, instead of being silently dropped and skewing how surprising later weeks' counts look.
- Building the site with `--no-persist`, or before the Fakt der Woche data has ever been generated, no longer deletes a previous real build's published fact pages and cards, or overwrites the fact archive with a false "nothing published yet" message.

## [0.5.0.0] - 2026-09-19

### Added

- A deterministic, zero-credential demo now builds the official Plenarprotokoll 21/84 TOP 32 a/b acceptance case offline, validates the deployable artifact, and links all 16 speeches plus Drucksachen 21/6354 and 21/4833.
- Publications now carry a schema-v2 data-state manifest and a reader-facing Datenstand section that distinguish unavailable, partial, genuine-empty, reused, and not-requested data.
- Operators can inspect acquisition capabilities and resolved configuration without network access through `--list-capabilities` and `--explain-config`; development views are isolated from deployable output.

### Changed

- Every visitor now receives the same complete public experience—Aktueller Puls, Sitzungen, Gesetze, Abgeordnete, and Quellen—without a gear menu, feature switches, or hidden building blocks.
- AI summaries are the only content preference: valid summaries are expanded initially, clearly labelled as AI-generated and not editorially reviewed, globally collapsible, source-bound, citation-checked, and omitted cleanly when unavailable.
- `--enrich` now controls only optional acquisition of votes, abgeordnetenwatch profiles, and the full MP roster; deprecated feature inputs remain translating aliases through `0.5.x` and are scheduled for removal in `0.6.0`.

### Fixed

- Public source links now require allowlisted HTTPS hosts, generated paths are confined to the publication root, and CI rejects developer-marked or incomplete publication artifacts.
- The fixed public experience remains intact on the week-radar and Daten pages after integrating the latest `main` releases.

## [0.4.0.0] - 2026-09-19

### Added

- The "Daten" page (`database.html`) replaces the sample-row explorer with a download page: one click gets the gzipped SQLite distribution copy or any of the 16 CSV tables, each with its size and full sha256; a Datenstand band shows how many catalog protocols are covered as dossiers and which Bausteine (roll-call votes, abgeordnetenwatch profiles, MdB roster) the file contains; five SQL "Rezepte" run at every build against the very file offered for download, with their result rows shown next to the SQL and linked to the MP, protocol and bill pages; a "So geht's los" section gives three copy-paste routes (shell, Python stdlib, pandas); every table's columns, keys and foreign keys are listed in compact schema rows with a data dictionary that marks which source each column comes from.
- The distribution copy is built by `export_distribution_data()`: `speeches.paragraphs_json` (a duplicate of `speeches.text`) is dropped, `mp_canonical` maps every `mps` row to its consolidated person, and a `datenstand` table plus `PRAGMA user_version` mark the file as a distribution copy. Export needs SQLite ≥ 3.35; older builds render the page with a "Daten nicht erzeugt" notice naming the reason. Files are deterministic (gzip without timestamps), so unchanged inputs give byte-identical downloads; the export is skipped when nothing it depends on changed (store, recipes, export format, tag, licence, issues URL, coverage counts, Baustein readiness), re-run with `--force-export`, and skipped entirely when `--data-manifest` overrides it. Each export writes a fresh `data/exports/g-<hash>/` generation and removes the previous one only after `datenstand.json` points at the new one; concurrent builds are serialised by `data/exports/.lock`, and a lock left by a crashed build is cleared automatically.
- New CLI flags `--data-base-url`, `--data-manifest`, `--force-export`, `--data-license`, `--data-issues-url` with `BUNDESTAG_PULSE_DATA_*` env fallbacks (CLI beats env beats default); a `--data-manifest` URL is an explicit opt-in fetch (10 s timeout, 32 MB cap) that `--offline` refuses; an override manifest is shape-checked before rendering and the issues URL must use `https://`, `http://`, `mailto:` or a site-relative path. Documented in `docs/project-documentation.md`; the licence wording lives in `docs/data-license.md` (still pending).
- `persist_dip_pulse_store.connect()` refuses to open a distribution copy as a build store.

### Changed

- Nav label and every "Datenbank"/"Datenbank erkunden" mention across `index.html`, `overview.html`, `api-sitzungen.html` and `sources.html` renamed to "Daten"; the index page's two SQLite-download/explorer cards merge into one "Daten" card with a "Stand … · N Protokolle" line; the SQLite download link on every page now points at the distribution copy instead of the build store, and the in-page "Daten" links appear exactly when the page has content.
- `collect_abgeordnete()` returns a third value, `canonical_by_mp_id`, mapping every `mps.id` (not only page-eligible ones) to its consolidated person.
- `sources.html` gains a "Lizenz und Weiterverwendung" entry (`#lizenz`) that the Daten page links to; the wording is a placeholder until the data licence is settled.

### Fixed

- SQLite errors while building the distribution copy (locked store, full disk) surface as a named `error:` line instead of a traceback.

### Known stale docs

- `docs/bundestag-puls-architecture.html`/`.json` omitted the Daten export step and the Daten page; regenerated in 0.6.4.0.

## [0.3.0.0] - 2026-09-18

### Added

- `puls.html` is a week radar now (`docs/designs/puls-wochenradar.md`): the page header names the newest sitting week (or `--week`) with one chip per sitting and a facts sentence that says whether the week is still running, how old it is and when the build ran ("Auswertung vom"); "Themen der Woche" ranks the week's agenda items by speech count, names them by their DIP Vorgang titles (an Antrag-only group lists every title at equal weight), shows the share of all speeches with a bar, who spoke per Fraktion, a "Fortgesetzt" trace when the procedure ran in an earlier week, the KI-Zusammenfassung with receipts (`summaries`), a "namentlich abgestimmt" badge (`votes`) and a link into the protocol on every row; question formats (Befragung, Fragestunde, Regierungsbefragung) and the remaining agenda items are listed under the rows with their counts.
- The Wochenvergleich band gains a "Namentliche Abstimmungen" card aggregated over the week (`votes`), keeps its cards without a comparison week (Wochenpuls and Redeanteil of the current week, no deltas), and reads "n/a" on the Wochenpuls chips when the two weeks hold a different number of sittings.
- Build diagnostics for the page on stderr: `[puls] KW 24/2026: 3 Sitzungen, 5 Themen, 1 Frageformat, 22 weitere, today=…`, plus warnings for undated sittings, a week without extracted speeches and a build date before the sitting week (README §8).

### Changed

- `--today`, `SOURCE_DATE_EPOCH` and `--week` now shape `puls.html`; two builds of the same cache with the same pins are byte-identical.

### Removed

- The old `puls.html` hero (sitting summary, fact tiles, "Quellen" row), the Themenbewegung card, the per-sitting Abstimmungsverschiebung panel and the `#bewegung` anchor. `#wochenvergleich` and `#abstimmungen` stay.

## [0.2.3.0] - 2026-09-18

### Added

- Builds can be pinned: `--today YYYY-MM-DD` fixes the build date, `--week YYYY-WW` names the ISO sitting week for `puls.html`, and `SOURCE_DATE_EPOCH` (UTC) is honoured when `--today` is absent. Both are validated on every build now; `puls.html` starts reading them with the week radar in the next release.
- A `--week` that the build cannot hold is refused before any file is written, and the error lists the sitting weeks that are available.

### Changed

- Source links taken from DIP data (PDF sources on positions, activities, the KI-Zusammenfassung receipts and the developer details, XML/PDF links on the overview and Daten pages) are emitted only for `http(s)` URLs; anything else degrades to plain text.
- Groundwork for the `puls.html` week radar (`docs/designs/puls-wochenradar.md`): topic naming across positions and mitberaten twins, a shared occurrence index for the returning-procedures card, roll-call votes counted by id instead of by attachment, and shared receipt rendering. Nothing on the site changes yet; the page itself follows in the next release.

## [0.2.2.0] - 2026-09-14

### Fixed

- The Aufmerksamkeitsrang sidebar on protocol dossiers is now fully reachable: on desktop it stays pinned while its rows scroll inside the sidebar, with a fade showing when more agenda items are below, instead of clipping the tail until the very end of the page.
- On narrow screens the ranking opens as a short index (five agenda items, three on phones) with an "Alle N Tagesordnungspunkte anzeigen" button, so the agenda list sits right below it; expanding moves focus to the first revealed item, and every agenda item links back to the ranking.
- Dossiers without agenda items or without extracted speeches show a plain notice instead of an empty ranking, and printouts show every ranking row with no controls.

## [0.2.1.0] - 2026-09-13

### Fixed

- Protocol dossiers now show Drucksachen directly below each agenda item heading and give speaker lists the full card width instead of leaving a mostly empty second column.
- Agenda items without linked Drucksachen no longer show an empty public placeholder; the developer diagnostics continue to report the missing source data.

## [0.2.0.0] - 2026-09-06

### Added

- Website Bausteine are now true per-browser preferences: every publication contains all user-facing areas, switches apply immediately, survive reloads, and default to the core-only view.
- Settings report whether optional vote, summary, profile, and roster data is available, partial, or unavailable without triggering network requests.
- `--enrich votes|aw-profiles|mp-roster|all` explicitly selects optional update-time data acquisition; summary generation remains separately protected by `--summary-mode`.

### Changed

- Offline and reduced-enrichment builds no longer remove bill or MP pages. Missing source data produces an honest empty state instead.
- Browser dependencies are resolved locally: enabling bill following enables bills, and disabling bills disables bill following.
- The old feature-selection CLI, JSON, and environment inputs are deprecated for one release. They remain accepted with warnings but no longer control published UI.

## [0.1.1.0] - 2026-08-03

### Changed

- The README is now a full setup guide. It covers prerequisites, where to get a DIP API key, the first online build a fresh clone needs, the sub-second offline preview loop for everyday work, and what to run after new Bundestag data or after pulling code changes.
- Refreshing is documented as the three separate things it actually is: reloading the browser, fetching new parliamentary data, and rebuilding the site after a code update. Each one now has the exact command.
- The flags that decide how much of your local site survives an online build are spelled out, including why `--preserve-existing-dossiers` matters and how to rebuild a site that a narrow update shrank to a single sitting.
- Bausteine are documented end to end: per-build flags, durable defaults in `features.local.json`, why an offline build cannot fetch votes or profiles, and the difference between what a build makes available and what the gear menu shows.
- New sections cover server settings, hosting the generated site elsewhere, and a troubleshooting table keyed to the exact error messages you can hit, including the empty `DIP_API_KEY=` line that silently overrides a key you passed on the command line.

### Fixed

- The project documentation no longer suggests passing `DIP_API_KEY` as a one-command prefix without saying that a copied `.env.local` overwrites it, which made the suggested fix fail with the error it was meant to solve.

## [0.1.0.0] - 2026-08-02

### Added

- A single Baustein registry now controls build availability and browser visibility for votes, summaries, abgeordnetenwatch profiles, MP pages and roster data, bill tracking, and developer views.
- Repeatable `--enable`/`--disable` flags, `--features`, JSON configuration files, `BUNDESTAG_PULSE_FEATURES`, and `--list-features` provide one configuration vocabulary with dependency resolution.
- Every generated page now includes a settings gear, an instant local visibility panel, and a link to the full `settings.html` view. A tooling manifest is written to `data/features.json`.
- Addon modules are discovered lazily through `scripts/features/loader.py` and expose shared enrich, persist, page, section, style, and script hooks.

### Changed

- The shipped default is now strict core-only: DIP fetch, sitting catalogs, protocol dossiers, and the SQLite store/explorer. Optional network and content features must be enabled explicitly.
- Global navigation and page bootstrap/runtime scripts are centralized, so nested pages derive their links from their depth and every template receives the same feature behavior.

### Fixed

- Bill pages no longer generate the broken `bills/abgeordnete/index.html` link.
- The Datenbank navigation item no longer disappears from dossier, bill, or MP pages.
- Developer-only content is hidden before first paint, and every theme toggle on a page is now initialized.

## [0.0.2.0] - 2026-07-31

### Fixed

- "Aktueller Puls" now opens on the newest sitting you have data for. Offline previews used to pick whichever dossier file sorted first by name, so the 100th sitting of the 20th Bundestag from 27 April 2023 was presented as the current one.
- The home page snapshot, the sitting overview, and the sources page now name the same latest sitting as "Aktueller Puls" instead of disagreeing with it.
- The cached sitting catalog is written newest-first, whatever order the DIP API hands it back in.

### For contributors

- Regression coverage pins newest-first ordering across the rendered pages and the cached catalog, including dossiers whose metadata is missing or truncated.

## [0.0.1.0] - 2026-07-30

### For contributors

- Project agents now automatically select the right workflow for common planning, review, QA, and shipping tasks.
- Regression coverage now protects offline preview builds that reuse legacy SQLite caches.

### Fixed

- Offline previews now open legacy SQLite caches without crashing when newer MP biography fields are missing.
