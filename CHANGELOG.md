# Changelog

All notable changes to this project will be documented in this file.

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
