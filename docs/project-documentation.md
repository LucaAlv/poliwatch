# Bundestag Pulse Project Documentation

This repository builds a static, local preview of "Bundestag Pulse": a primary-source view of German Bundestag activity. The pipeline fetches official DIP Plenarprotokoll data and renders one fixed public experience with a sitting catalog, protocol dossiers, votes, laws, MP/profile pages, source links, and an optional labelled AI-summary layer. Operator enrichments control acquisition work, not visitor visibility.

The codebase is intentionally small. There is no package manager or web framework; the scripts use Python standard-library modules plus public HTTP APIs.

## Prerequisites

- Python 3.11 or newer.
- No third-party Python packages are required at runtime.
- `DIP_API_KEY` is required for online fetch/update commands.

## Project Map

```text
.
|-- README.md
|-- .env.example
|-- docs/
|   |-- design/bundestag-pulse-design.md
|   `-- project-documentation.md
|-- tests/
|   |-- fixtures/
|   `-- test_*.py
`-- scripts/
    |-- preview_dip_pulse_site.sh
    |-- build_dip_pulse_site.py
    |-- validate_dip_protocol.py
    |-- render_dip_pulse_html.py
    |-- persist_dip_pulse_store.py
    |-- abgeordnetenwatch.py
    `-- features/
        |-- __init__.py
        |-- loader.py
        `-- <addon>.py
```

Generated preview data lives under `.context/dip-pulse-site/` by default. `.context/` is gitignored and should be treated as local build output/cache, not source.

## How The Pipeline Works

```text
scripts/preview_dip_pulse_site.sh
  |
  | calls
  v
scripts/build_dip_pulse_site.py
  |
  | fetches catalog/detail data with
  v
scripts/validate_dip_protocol.py
  |
  | optionally enriches speakers through
  v
scripts/abgeordnetenwatch.py
  |
  | writes JSON + HTML detail pages through
  v
scripts/render_dip_pulse_html.py
  |
  | optionally rebuilds graph store through
  v
scripts/persist_dip_pulse_store.py
```

The build has two modes:

- Offline render: rebuilds HTML from cached JSON/database files and makes no external API calls.
- Online update: fetches or refreshes DIP data, roll-call vote data, abgeordnetenwatch profiles, optional LLM summaries, and the optional MdB roster.

## Important Files

### `scripts/preview_dip_pulse_site.sh`

Primary developer entry point for local previewing. It loads `.env.local`, chooses a port and output paths, calls `build_dip_pulse_site.py`, then starts a background `python3 -m http.server` for the generated static site.

Default behavior is intentionally offline:

```bash
scripts/preview_dip_pulse_site.sh
```

This renders from cached files in `.context/dip-pulse-site/data` and does not call the DIP API. To fetch or refresh data, run one of the online modes:

```bash
scripts/preview_dip_pulse_site.sh update --limit 2 --detail-limit 2
scripts/preview_dip_pulse_site.sh refresh --document-number 21/87
scripts/preview_dip_pulse_site.sh fetch --document-number 21/87 --summary-mode off
```

The aliases `update`, `refresh`, and `fetch` all mean "online build." Everything after that word is forwarded to `build_dip_pulse_site.py`.

The script also manages the preview server:

```bash
scripts/preview_dip_pulse_site.sh stop
```

The preview server binds to localhost only by default. Set `PREVIEW_BIND=0.0.0.0` when you intentionally want to expose the generated site on the LAN.

Key defaults:

| Setting | Default | Purpose |
|---|---:|---|
| `PORT` | `${CONDUCTOR_PORT}` or `8000` | Local HTTP server port |
| `PREVIEW_BIND` | `127.0.0.1` | HTTP server bind host |
| `DIP_PULSE_OUTPUT_DIR` | `.context/dip-pulse-site` | Static site output directory |
| `DIP_PULSE_PID_FILE` | `.context/dip-pulse-server.pid` | Background server PID |
| `DIP_PULSE_LOG_FILE` | `.context/dip-pulse-server.log` | Server stdout/stderr |
| `OPEN_BROWSER` | `1` | Opens the preview URL on server start; set `0` to disable |

When the server is already running, the script only rebuilds files and prints a refresh message. The server does not need to restart because `http.server` reads files from disk on each request.

### `scripts/build_dip_pulse_site.py`

Main static-site builder. It coordinates fetching protocols, generating dossier JSON/HTML, rebuilding the SQLite graph store, writing index pages, and collecting bill/MP pages.

It creates these directories under the output directory:

```text
.context/dip-pulse-site/
|-- index.html
|-- puls.html
|-- overview.html
|-- api-sitzungen.html
|-- sources.html
|-- settings.html
|-- database.html
|-- data/
|   `-- exports/            # distribution SQLite + CSVs + datenstand.json, unless --no-persist
|-- protocols/
|-- bills/                  # always published; honest empty state without matching data
`-- abgeordnete/            # always published; observed MPs remain available without a full roster
```

Important generated files:

| Path | Purpose |
|---|---|
| `index.html` | Landing page for the local static site |
| `puls.html` | Front page, the week radar (docs/designs/puls-wochenradar.md): the newest dated sitting week (or `--week`) with one chip per sitting, "Themen der Woche" ranked by speech count and named by DIP Vorgang titles with a receipt on every row, and the Wochenvergleich band incl. the week's roll-call votes |
| `overview.html` | Protocol/catalog overview |
| `api-sitzungen.html` | API/session catalog page |
| `sources.html` | Sources/method page |
| `settings.html` | Temporary `0.5.x` compatibility page explaining the fixed presentation |
| `database.html` | "Daten" page: download panel, Datenstand, five executed SQL recipes, schema and foreign-key reference, or a clear `--no-persist`/SQLite-too-old explanation |
| `data/features.json` | Schema-v2 publication manifest with fixed presentation and acquisition states |
| `data/plenarprotokoll-catalog.json` | Cached protocol catalog |
| `data/plenarprotokoll-<slug>.json` | Cached enriched report for one protocol |
| `protocols/plenarprotokoll-<slug>.html` | Dossier page for one protocol |
| `abgeordnete/index.html` and `abgeordnete/<id>.html` | MP index/detail pages with roster data, speeches, and roll-call vote participation |
| `data/bundestag-pulse.sqlite` | SQLite graph store, unless `--no-persist` is used |
| `data/exports/datenstand.json` | Manifest the Daten page renders from: file sizes/checksums, Datenstand, coverage, schema data dictionary, executed recipe rows |
| `data/exports/g-<hash>/` | One export generation's files (distribution `.sqlite.gz` + 16 `.csv.gz`); the previous generation is deleted only after `datenstand.json` switches to point at the new one |
| `data/abgeordnetenwatch-cache.json` | Speaker/profile resolution cache |

`build_dip_pulse_site.py` can run directly, but the preview shell script is usually more convenient because it also serves the files:

```bash
python3 scripts/build_dip_pulse_site.py --offline
python3 scripts/build_dip_pulse_site.py --document-number 21/87
```

### `scripts/build_demo_site.py` and `scripts/extract_demo_fixture.py`

`build_demo_site.py` turns the committed Plenarprotokoll 21/84 TOP 32 a/b fixture into a complete static site without credentials or network access. It is the implementation behind `scripts/preview_dip_pulse_site.sh demo`, validates ordinary public output, and prints the exact dossier path plus the next online-update command.

`extract_demo_fixture.py` reproducibly rebuilds that fixture from a local copy of the official XML transcript. It deliberately performs no download itself: an operator must explicitly supply the local XML path, and the script refuses an unexpected document set or speech count rather than silently changing the acceptance case.

```bash
python3 scripts/extract_demo_fixture.py \
  --xml /path/to/21084.xml \
  --output tests/fixtures/demo-report-21-84.json
```

### `scripts/publication_state.py`

Shared schema-v2 trust boundary for acquisition facts, presentation-state derivation, allowed source URLs, confined generated paths, and public-artifact validation. Producers and renderers use this module instead of independently guessing whether absent data means “not requested,” “failed,” or a genuine empty result.

## Fixed public presentation and enrichments

Every ordinary static publication has six stable public destinations: Aktueller Puls, Sitzungen, Gesetze, Abgeordnete, Daten, and Quellen. Public components load unconditionally; no gear, `data-feature-*` CSS gate, or general browser preference decides whether they exist. The compatibility `settings.html` page contains no switches.

Votes, profile links, and the full roster have explicit acquisition states: `not_requested`, `complete`, `partial`, or `failed`. Renderers derive contextual public copy from those facts. A successful lookup with zero matching votes is therefore different from a build that never requested vote data. `data/features.json` aggregates those facts and `sources.html#datenstand` explains them.

AI summaries are controlled separately through `reuse`, `off`, `auto`, and `required` modes. A usable summary is expanded by default, permanently labelled `KI-generiert · nicht redaktionell geprüft`, and has 3–5 distinct resolvable citations. The browser stores only the global expanded/collapsed preference under `bundestag-pulse-ai-summaries-v1`.

Online updates preserve previously cached votes, profiles, summaries, and roster rows when their enrichment is omitted. Selecting an enrichment refreshes that source instead.

```bash
# Publish every experience from the current cache.
scripts/preview_dip_pulse_site.sh

# Acquire selected optional data during an online update.
scripts/preview_dip_pulse_site.sh update --enrich votes --enrich aw-profiles

# Acquire every non-LLM enrichment and explicitly regenerate summaries.
scripts/preview_dip_pulse_site.sh update --enrich all --summary-mode auto
```

`features.json` is the committed enrichment default. Put personal enrichment defaults such as `{"enrich":["votes"]}` in gitignored `features.local.json`, not `.context/`, because `.context/` contains generated output rather than operator configuration. Legacy feature-selection inputs remain accepted with warnings through `0.5.x`, cannot remove published UI, and are scheduled for removal in `0.6.0`.

### `scripts/validate_dip_protocol.py`

Protocol extraction and enrichment engine. Given a DIP protocol id or document number, it:

- loads `.env.local` without overriding already-exported variables,
- fetches the official DIP Plenarprotokoll metadata,
- downloads the official XML transcript,
- parses agenda items, page ranges, speeches, speakers, and XML-linked Drucksachen,
- fetches related DIP `/vorgangsposition`, `/aktivitaet`, and `/person` records,
- scans Bundestag roll-call vote pages and matches votes by same-day protocol plus Drucksachennummer,
- optionally generates per-agenda-item LLM summaries.

It prints a validation report JSON to stdout:

```bash
python3 scripts/validate_dip_protocol.py --document-number 21/87 > .context/report.json
```

This is the lowest-level command to use when debugging extraction quality for a single protocol.

### `scripts/render_dip_pulse_html.py`

Standalone HTML renderer for a single validation report JSON. `build_dip_pulse_site.py` imports it for dossier pages, but it can also be used directly:

```bash
python3 scripts/render_dip_pulse_html.py .context/report.json .context/report.html
```

The renderer owns the detailed dossier page HTML, shared site header styles, party colors, vote labels, source links, speaker/profile links, and summary presentation.

The dossier's Aufmerksamkeitsrang sidebar lives here too. On desktop it is sticky and its rows scroll inside the panel; at 1120px and below it renders collapsed to `ATTENTION_PREVIEW_ROWS` rows (`ATTENTION_PREVIEW_ROWS_PHONE` at 720px and below) behind an expand button, protocols without agenda items or extracted speeches get a plain notice instead of a ranking, and print output shows every row without controls. Both row counts are module constants near the top of the file.

### `scripts/persist_dip_pulse_store.py`

SQLite persistence layer. It turns a validation report JSON into a linked entity graph with tables for parties, MPs, protocols, agenda items, proceedings, documents, speeches, votes, vote fractions, and individual vote members.

MP identity rows are consolidated from DIP roster IDs, XML speaker IDs, resolved abgeordnetenwatch IDs, and guarded name+party matches. This lets MP detail pages show speeches and roll-call vote participation even when abgeordnetenwatch resolution is disabled or unavailable, while rows with conflicting external IDs remain separate.

Direct usage:

```bash
python3 scripts/persist_dip_pulse_store.py .context/report.json \
  --database .context/dip-pulse-site/data/bundestag-pulse.sqlite
```

`build_dip_pulse_site.py` normally handles this automatically unless `--no-persist` is passed.

### `scripts/abgeordnetenwatch.py`

Profile resolver for linking Bundestag speakers and roll-call vote members to abgeordnetenwatch.de politician profiles. It first tries the exact Bundestagsverwaltung speaker id (`ext_id_bundestagsverwaltung`) when available, then falls back to name plus party disambiguation.

It uses a disk cache so repeat builds do not keep querying the API. Network failures degrade gracefully: the build continues without profile links instead of failing the whole site.

Direct usage:

```bash
python3 scripts/abgeordnetenwatch.py \
  --ext-id 11005074 \
  --first-name Max \
  --last-name Mustermann \
  --fraktion SPD \
  --cache .context/dip-pulse-site/data/abgeordnetenwatch-cache.json
```

### `docs/design/bundestag-pulse-design.md`

Product/design rationale. It explains the original thesis: a primary-source, receipt-backed civic radar for Bundestag activity. Use it for product intent and constraints, not command reference.

### `docs/designs/`

Per-feature design docs written by review sessions (`docs/design/` is the product-level design; `docs/designs/` holds one doc per feature). `puls-wochenradar.md` records the `puls.html` week radar: premises, measured evidence from the cache, the approach chosen, and the gate decisions; `puls-wochenradar-sketch.png` is its real-data wireframe.

### `.env.example` and `.env.local`

`.env.example` lists supported local secrets:

```bash
DIP_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

Copy the keys you need into `.env.local`. That file is gitignored. `DIP_API_KEY` is required for online DIP fetches. LLM keys are only needed when summaries are generated or refreshed.

## Important Commands

### Running Tests

The automated test suite uses only Python's standard-library `unittest` module. It runs from committed fixtures under `tests/fixtures/` and does not require network access, `.context/`, or `.env.local`.

```bash
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests -v
```

GitHub Actions runs the same checks on Python 3.11, 3.12, and 3.13.

### Preview Site Commands

Show help:

```bash
scripts/preview_dip_pulse_site.sh --help
```

Render cached data and serve it:

```bash
scripts/preview_dip_pulse_site.sh
```

Fetch/update online data, then serve it:

```bash
scripts/preview_dip_pulse_site.sh update --limit 2 --detail-limit 2
```

Build one specific protocol:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87
```

Regenerate only from cached files into a custom output directory:

```bash
DIP_PULSE_OUTPUT_DIR=.context/alternate-site scripts/preview_dip_pulse_site.sh
```

Run on a custom port:

```bash
PORT=9000 scripts/preview_dip_pulse_site.sh
```

Start without opening the browser:

```bash
OPEN_BROWSER=0 scripts/preview_dip_pulse_site.sh
```

Expose the preview on the LAN intentionally:

```bash
PREVIEW_BIND=0.0.0.0 scripts/preview_dip_pulse_site.sh
```

Stop the background preview server:

```bash
scripts/preview_dip_pulse_site.sh stop
```

### Build Script Options

The preview script forwards render options to:

```bash
python3 scripts/build_dip_pulse_site.py [options]
```

Common options:

| Option | Default | Effect |
|---|---:|---|
| `--enrich ID` | none | Acquire `votes`, `aw-profiles`, `mp-roster`, or `all` during an online update; repeatable |
| `--features-file PATH` | none | Read `{"enrich":[...]}` from another JSON file; legacy selection keys are deprecated |
| `--enable`, `--disable`, `--features` | deprecated | Accepted for one release; data selections map to enrichments but published UI is unaffected |
| `--list-capabilities` | off | Print operator enrichments and summary/developer controls, then exit before build work |
| `--explain-config` | off | Print effective enrichment configuration with provenance, then exit |
| `--list-features` | deprecated | Compatibility alias for `--list-capabilities` through `0.5.x` |
| `--include-dev-view` | off | Include developer markup only in a separate, explicit output directory |
| `--validate-publication PATH` | none | Validate a completed output tree's manifest and presentation surfaces |
| `--api-key KEY` | `DIP_API_KEY` | DIP API key for online fetches |
| `--limit N` | `0` | Number of recent Bundestag protocols in the catalog; `0` means all available |
| `--detail-limit N` | `5` | Number of fetched protocols to enrich into detail pages; `0` means all, `-1` means none |
| `--document-number NUM` | none | Restrict catalog/detail generation to one protocol; can be repeated |
| `--dossier-document-number NUM` | none | Generate/regenerate an extra dossier without restricting the catalog; can be repeated |
| `--output-dir PATH` | `.context/dip-pulse-site` | Static site output directory |
| `--offline` | off | Render only from cached files; makes no DIP/XML/vote/profile/LLM requests |
| `--today YYYY-MM-DD` | `SOURCE_DATE_EPOCH` (UTC) or the current date | Build date: `puls.html` decides running vs. past week from it, states the age of an older week and prints it as "Auswertung vom" |
| `--week YYYY-WW` | newest dated week | ISO sitting week, validated against the archive; refused before any file is written when it is not among the cached dossiers (offline) or the dossiers this run builds or preserves (online); online, a week whose dossiers all fail to build stops the run after the dossiers, before `puls.html`. `puls.html` renders that week |
| `--database-path PATH` | `OUTPUT_DIR/data/bundestag-pulse.sqlite` | SQLite output path |
| `--no-persist` | off | Skip SQLite graph-store generation |
| `--preserve-existing-dossiers` | off | Keep cached dossier JSON files visible in the generated catalog |
| `--person-limit N` | `0` | Number of distinct person records fetched per dossier; `0` means all seen people |
| `--vote-scan-pages N` | `0` / `30` | `0` normally; `30` with `--enrich votes`; an explicit positive value implies that enrichment |
| `--roll-call-list-id ID` | `BT_ROLL_CALL_LIST_ID` or `484422-484422` | Bundestag roll-call vote filterlist id used for list-page scraping |
| `--sleep SECONDS` | `0.0` | Delay between DIP API requests |
| `--no-abgeordnetenwatch` | deprecated | Explicitly veto profile resolution during the compatibility window |
| `--abgeordnetenwatch-cache PATH` | `OUTPUT_DIR/data/abgeordnetenwatch-cache.json` | Profile cache location |
| `--abgeordnetenwatch-sleep SECONDS` | `0.5` | Minimum delay between abgeordnetenwatch API requests |
| `--roster-wahlperiode N` | `21` | Legislative period used for full MdB roster pages |
| `--no-roster` | deprecated | Explicitly veto full-roster acquisition during the compatibility window |

Daten export options (`data/exports/`, the Daten page's download panel, Datenstand and recipes):

| Option | Default | Effect |
|---|---:|---|
| `--data-base-url URL` | `data/exports/` or `$BUNDESTAG_PULSE_DATA_BASE_URL` | Where the page's download links point; absolute only for `https://`, `http://` or a leading `/` |
| `--data-manifest PATH\|URL` | `OUTPUT_DIR/data/exports/datenstand.json` or `$BUNDESTAG_PULSE_DATA_MANIFEST` | Which manifest the Daten page renders from; a URL is an explicit opt-in fetch (10 s timeout, 32 MB cap) and is rejected under `--offline`. The local export is skipped while an override is given (unless `--force-export`) |
| `--force-export` | off | Re-run the export even when its inputs (store, recipes, export format, tag, licence, issues URL, coverage counts) are unchanged, or when `--data-manifest` would otherwise skip it |
| `--data-license TEXT` | `""` or `$BUNDESTAG_PULSE_DATA_LICENSE` | Licence string recorded in the manifest and shown on the page (placeholder text until set) |
| `--data-issues-url URL` | none or `$BUNDESTAG_PULSE_DATA_ISSUES_URL` | Optional "Fragen und Fehler" footer link on the Daten page; must start with `https://`, `http://`, `mailto:` or `/` |

The export writes a distribution copy of the store (`speeches.paragraphs_json` dropped, `mp_canonical` and `datenstand` tables added, requires SQLite ≥ 3.35) plus 16 CSV.gz files and executes the five `RECIPES` SQL statements against it; `export_format` (currently `1`) is bumped whenever that CSV layout or transformation changes, additive columns are not a bump.

Summary options:

| Option | Default | Effect |
|---|---:|---|
| `--summary-mode reuse` | yes | Reuse existing summaries and do not call an LLM API |
| `--summary-mode off` | no | Do not use or generate LLM summaries |
| `--summary-mode auto` | no | Generate summaries when a provider key is available |
| `--summary-mode required` | no | Require summary generation and fail if it cannot complete |
| `--refresh-summaries` | no | Equivalent to `--summary-mode auto` |
| `--summary-provider auto` | yes | Prefer Anthropic when both Anthropic and Gemini keys are set |
| `--summary-provider anthropic` | no | Use Anthropic |
| `--summary-provider gemini` | no | Use Gemini |
| `--anthropic-api-key KEY` | `ANTHROPIC_API_KEY` | Anthropic key |
| `--gemini-api-key KEY` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Gemini key |
| `--summary-model IDS` | provider defaults | Comma-separated model ids to try |

Useful build examples:

```bash
# Fast local rebuild from existing cache.
python3 scripts/build_dip_pulse_site.py --offline

# Fetch two recent protocols and generate two detailed dossiers without optional enrichments.
python3 scripts/build_dip_pulse_site.py --limit 2 --detail-limit 2

# Generate one specific protocol and no LLM summaries.
python3 scripts/build_dip_pulse_site.py --document-number 21/87 --summary-mode off

# Refresh cached summaries with Gemini.
python3 scripts/build_dip_pulse_site.py --document-number 21/87 \
  --refresh-summaries \
  --summary-provider gemini

# Rebuild the site without the SQLite graph store.
python3 scripts/build_dip_pulse_site.py --document-number 21/87 --no-persist
```

### Validation/Debug Commands

The validation script accepts the same roll-call scraping controls as the site builder:

| Option | Default | Effect |
|---|---:|---|
| `--vote-scan-pages N` | `30` | Bundestag roll-call vote list pages scanned for same-day matches |
| `--roll-call-list-id ID` | `BT_ROLL_CALL_LIST_ID` or `484422-484422` | Bundestag roll-call vote filterlist id used for list-page scraping |

Fetch and inspect one protocol as JSON:

```bash
python3 scripts/validate_dip_protocol.py --document-number 21/87 > .context/report.json
```

Fetch by DIP protocol id:

```bash
python3 scripts/validate_dip_protocol.py --protocol-id 5799 > .context/report.json
```

Limit agenda items while debugging:

```bash
python3 scripts/validate_dip_protocol.py --document-number 21/87 --limit-tops 3
```

Fetch only a limited number of person records:

```bash
python3 scripts/validate_dip_protocol.py --document-number 21/87 --person-limit 10
```

Generate summaries at validation level:

```bash
python3 scripts/validate_dip_protocol.py --document-number 21/87 \
  --summary-mode auto \
  --summary-provider anthropic
```

Render a single validation JSON to HTML:

```bash
python3 scripts/render_dip_pulse_html.py .context/report.json .context/report.html
```

Persist a single validation JSON to SQLite:

```bash
python3 scripts/persist_dip_pulse_store.py .context/report.json \
  --database .context/dip-pulse-site/data/bundestag-pulse.sqlite
```

Resolve one speaker profile:

```bash
python3 scripts/abgeordnetenwatch.py \
  --first-name Max \
  --last-name Mustermann \
  --fraktion SPD \
  --cache .context/dip-pulse-site/data/abgeordnetenwatch-cache.json
```

## Environment Variables

| Variable | Used by | Required? | Purpose |
|---|---|---:|---|
| `DIP_API_KEY` | preview/build/validation | Online fetches | DIP API key |
| `ANTHROPIC_API_KEY` | build/validation | Only Anthropic summaries | Anthropic summary generation |
| `GEMINI_API_KEY` | build/validation | Only Gemini summaries | Gemini summary generation |
| `GOOGLE_API_KEY` | validation | Optional Gemini fallback | Alternative Gemini key name |
| `BT_ROLL_CALL_LIST_ID` | build/validation | No | Bundestag roll-call vote filterlist id override; `--roll-call-list-id` wins when both are set |
| `SOURCE_DATE_EPOCH` | build | No | Integer Unix timestamp read as UTC; pins the build clock for puls.html (`--today` wins when both are set) |
| `PORT` | preview script | No | HTTP server port |
| `PREVIEW_BIND` | preview script | No | HTTP server bind host; defaults to localhost-only |
| `CONDUCTOR_PORT` | preview script | No | Port fallback inside Conductor |
| `DIP_PULSE_OUTPUT_DIR` | preview script | No | Static output directory |
| `DIP_PULSE_PID_FILE` | preview script | No | Preview server PID file |
| `DIP_PULSE_LOG_FILE` | preview script | No | Preview server log file |
| `OPEN_BROWSER` | preview script | No | Set `0` to avoid opening browser |
| `BUNDESTAG_PULSE_ENRICHMENTS` | build | No | Comma-separated update enrichments such as `votes,aw-profiles` |
| `BUNDESTAG_PULSE_FEATURES` | build | Deprecated | Accepted through `0.5.x`; use `BUNDESTAG_PULSE_ENRICHMENTS` |

## Offline vs Online Behavior

Offline commands are safe for quick UI iteration. They never call external APIs, but they require cached data:

```bash
scripts/preview_dip_pulse_site.sh
python3 scripts/build_dip_pulse_site.py --offline
```

When persistence is enabled, an offline build initializes and migrates the cached SQLite schema before reading MP data. Caches created by older versions therefore remain usable when newer biography fields are added.

If no cached protocols exist, offline mode fails with:

```text
error: No cached protocols found in .context/dip-pulse-site/data. Run an online update first.
```

Online commands require `DIP_API_KEY` and can call several external services:

- DIP API for Plenarprotokolle, Vorgangspositionen, Aktivitaeten, Personen, and Drucksachen links.
- Bundestag web pages for roll-call vote list/detail pages only with `--enrich votes`.
- abgeordnetenwatch.de API only with `--enrich aw-profiles`.
- Anthropic or Gemini APIs only when summaries are generated/refreshed.

For fast development, prefer:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87
```

Then iterate offline with:

```bash
scripts/preview_dip_pulse_site.sh
```

## SQLite Store

When persistence is enabled, the build rewrites `data/bundestag-pulse.sqlite` from the current detail entries. The schema is managed in `persist_dip_pulse_store.py` and currently includes:

- `schema_migrations`
- `parties`
- `mps`
- `protocols`
- `agenda_items`
- `proceedings`
- `proceeding_positions`
- `documents`
- `agenda_item_documents`
- `speeches`
- `votes`
- `agenda_item_votes`
- `vote_documents`
- `vote_fractions`
- `vote_members`

The database is a graph-shaped local cache for connected views: protocols link to agenda items, agenda items link to speeches/documents/votes, votes link to fractions and individual MPs.

## Common Troubleshooting

### `DIP_API_KEY is not set`

Online preview mode checks `DIP_API_KEY` before calling the builder:

```bash
cp .env.example .env.local
# then edit .env.local and set DIP_API_KEY
```

Passing the key for one command only works when `.env.local` does not define `DIP_API_KEY` at all:

```bash
DIP_API_KEY=... scripts/preview_dip_pulse_site.sh update --document-number 21/87
```

The preview script sources `.env.local` after it inherits the environment, so the empty `DIP_API_KEY=` line copied from `.env.example` overwrites the value passed on the command line and the script aborts with the same error. Either fill the key in `.env.local` or delete that line.

### Offline mode has no cached protocols

Run one online update first:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87
```

After that, offline rebuilds can use the generated files in `.context/dip-pulse-site/data`.

### The browser still shows old content

The preview server does not restart on every rebuild. Reload the page in the browser. If the server seems stuck, stop and start it:

```bash
scripts/preview_dip_pulse_site.sh stop
scripts/preview_dip_pulse_site.sh
```

### The chosen port is busy

Use another port:

```bash
PORT=9000 scripts/preview_dip_pulse_site.sh
```

### Builds are slow

Use a narrower online build:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87
```

Useful speed levers:

- `--document-number` instead of a broad catalog fetch.
- `--detail-limit 1` or `--detail-limit 2`.
- Omit `--enrich` to skip full-roster, profile, and vote acquisition.
- Keep the default `--summary-mode reuse` to preserve cached summaries without making an LLM request.
- Offline mode after a first successful update.

### abgeordnetenwatch rate limits or outages

The resolver throttles requests and retries HTTP 429s. If profile links are not needed for a debug run, skip them:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87
```

### Summary generation fails

Use `--summary-mode off` or the default build behavior (`reuse`) while debugging. Use `required` only when a failed summary should fail the whole command.

### Roll-call vote scraping warnings

Roll-call votes are scraped from Bundestag HTML list/detail pages. If the list page returns HTML but no parseable vote entries, the build prints a `warning:` line and adds a German warning to the validation report. This usually means the Bundestag page markup changed or the filterlist id rotated.

Try the current Bundestag filterlist id with either the CLI flag or environment variable:

```bash
python3 scripts/build_dip_pulse_site.py --document-number 21/87 \
  --enrich votes \
  --roll-call-list-id NEW-ID

BT_ROLL_CALL_LIST_ID=NEW-ID python3 scripts/validate_dip_protocol.py --document-number 21/87
```

## Recommended Development Workflow

1. Put secrets in `.env.local`.

   ```bash
   cp .env.example .env.local
   ```

2. Fetch one protocol without expensive enrichment.

   ```bash
   scripts/preview_dip_pulse_site.sh update --document-number 21/87
   ```

3. Iterate on rendering offline.

   ```bash
   scripts/preview_dip_pulse_site.sh
   ```

4. Inspect the generated site at the printed URL, usually:

   ```text
   http://localhost:8000/
   ```

5. Stop the server when done.

   ```bash
   scripts/preview_dip_pulse_site.sh stop
   ```
