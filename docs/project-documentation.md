# Bundestag Pulse Project Documentation

This repository builds a static, local preview of "Bundestag Pulse": a primary-source view of German Bundestag activity. The pipeline fetches official DIP Plenarprotokoll data, extracts agenda items, speeches, linked Drucksachen, roll-call votes, and MP/profile data, then renders a static HTML site and an optional SQLite graph store.

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
    `-- abgeordnetenwatch.py
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
scripts/preview_dip_pulse_site.sh update --limit 2 --detail-limit 2 --no-roster
scripts/preview_dip_pulse_site.sh refresh --document-number 21/87 --no-roster
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
|-- database.html
|-- data/
|-- protocols/
|-- bills/
`-- abgeordnete/
```

Important generated files:

| Path | Purpose |
|---|---|
| `index.html` | Landing page for the local static site |
| `puls.html` | Main Pulse/front-page view |
| `overview.html` | Protocol/catalog overview |
| `api-sitzungen.html` | API/session catalog page |
| `sources.html` | Sources/method page |
| `database.html` | Human-readable SQLite table snapshot when persistence is enabled |
| `data/plenarprotokoll-catalog.json` | Cached protocol catalog |
| `data/plenarprotokoll-<slug>.json` | Cached enriched report for one protocol |
| `protocols/plenarprotokoll-<slug>.html` | Dossier page for one protocol |
| `abgeordnete/index.html` and `abgeordnete/<id>.html` | MP index/detail pages with roster data, speeches, and roll-call vote participation |
| `data/bundestag-pulse.sqlite` | SQLite graph store, unless `--no-persist` is used |
| `data/abgeordnetenwatch-cache.json` | Speaker/profile resolution cache |

`build_dip_pulse_site.py` can run directly, but the preview shell script is usually more convenient because it also serves the files:

```bash
python3 scripts/build_dip_pulse_site.py --offline
python3 scripts/build_dip_pulse_site.py --document-number 21/87 --no-roster
```

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
scripts/preview_dip_pulse_site.sh update --limit 2 --detail-limit 2 --no-roster
```

Build one specific protocol:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-roster
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
| `--api-key KEY` | `DIP_API_KEY` | DIP API key for online fetches |
| `--limit N` | `0` | Number of recent Bundestag protocols in the catalog; `0` means all available |
| `--detail-limit N` | `5` | Number of fetched protocols to enrich into detail pages; `0` means all, `-1` means none |
| `--document-number NUM` | none | Restrict catalog/detail generation to one protocol; can be repeated |
| `--dossier-document-number NUM` | none | Generate/regenerate an extra dossier without restricting the catalog; can be repeated |
| `--output-dir PATH` | `.context/dip-pulse-site` | Static site output directory |
| `--offline` | off | Render only from cached files; makes no DIP/XML/vote/profile/LLM requests |
| `--database-path PATH` | `OUTPUT_DIR/data/bundestag-pulse.sqlite` | SQLite output path |
| `--no-persist` | off | Skip SQLite graph-store generation |
| `--preserve-existing-dossiers` | off | Keep cached dossier JSON files visible in the generated catalog |
| `--person-limit N` | `0` | Number of distinct person records fetched per dossier; `0` means all seen people |
| `--vote-scan-pages N` | `30` | Bundestag roll-call vote list pages scanned per sitting |
| `--roll-call-list-id ID` | `BT_ROLL_CALL_LIST_ID` or `484422-484422` | Bundestag roll-call vote filterlist id used for list-page scraping |
| `--sleep SECONDS` | `0.0` | Delay between DIP API requests |
| `--no-abgeordnetenwatch` | off | Skip speaker and vote-member profile resolution |
| `--abgeordnetenwatch-cache PATH` | `OUTPUT_DIR/data/abgeordnetenwatch-cache.json` | Profile cache location |
| `--abgeordnetenwatch-sleep SECONDS` | `0.5` | Minimum delay between abgeordnetenwatch API requests |
| `--roster-wahlperiode N` | `21` | Legislative period used for full MdB roster pages |
| `--no-roster` | off | Skip fetching the full MdB roster; MP pages cover only seen people |

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

# Fetch two recent protocols, generate two detailed dossiers, skip full roster.
python3 scripts/build_dip_pulse_site.py --limit 2 --detail-limit 2 --no-roster

# Generate one specific protocol and no LLM summaries.
python3 scripts/build_dip_pulse_site.py --document-number 21/87 --summary-mode off --no-roster

# Refresh cached summaries with Gemini.
python3 scripts/build_dip_pulse_site.py --document-number 21/87 \
  --refresh-summaries \
  --summary-provider gemini \
  --no-roster

# Rebuild the site without the SQLite graph store.
python3 scripts/build_dip_pulse_site.py --document-number 21/87 --no-persist --no-roster
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
| `PORT` | preview script | No | HTTP server port |
| `PREVIEW_BIND` | preview script | No | HTTP server bind host; defaults to localhost-only |
| `CONDUCTOR_PORT` | preview script | No | Port fallback inside Conductor |
| `DIP_PULSE_OUTPUT_DIR` | preview script | No | Static output directory |
| `DIP_PULSE_PID_FILE` | preview script | No | Preview server PID file |
| `DIP_PULSE_LOG_FILE` | preview script | No | Preview server log file |
| `OPEN_BROWSER` | preview script | No | Set `0` to avoid opening browser |

## Offline vs Online Behavior

Offline commands are safe for quick UI iteration. They never call external APIs, but they require cached data:

```bash
scripts/preview_dip_pulse_site.sh
python3 scripts/build_dip_pulse_site.py --offline
```

If no cached protocols exist, offline mode fails with:

```text
error: No cached protocols found in .context/dip-pulse-site/data. Run an online update first.
```

Online commands require `DIP_API_KEY` and can call several external services:

- DIP API for Plenarprotokolle, Vorgangspositionen, Aktivitaeten, Personen, and Drucksachen links.
- Bundestag web pages for roll-call vote list/detail pages.
- abgeordnetenwatch.de API unless `--no-abgeordnetenwatch` is passed.
- Anthropic or Gemini APIs only when summaries are generated/refreshed.

For fast development, prefer:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-roster --summary-mode off
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

Or export it for one command:

```bash
DIP_API_KEY=... scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-roster
```

### Offline mode has no cached protocols

Run one online update first:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-roster --summary-mode off
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
scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-roster --summary-mode off
```

Useful speed levers:

- `--document-number` instead of a broad catalog fetch.
- `--detail-limit 1` or `--detail-limit 2`.
- `--no-roster` to skip the full MdB roster.
- `--no-abgeordnetenwatch` to skip speaker and vote-member profile enrichment.
- `--summary-mode off` or default `reuse` to avoid LLM calls.
- Offline mode after a first successful update.

### abgeordnetenwatch rate limits or outages

The resolver throttles requests and retries HTTP 429s. If profile links are not needed for a debug run, skip them:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-abgeordnetenwatch --no-roster
```

### Summary generation fails

Use `--summary-mode off` or the default build behavior (`reuse`) while debugging. Use `required` only when a failed summary should fail the whole command.

### Roll-call vote scraping warnings

Roll-call votes are scraped from Bundestag HTML list/detail pages. If the list page returns HTML but no parseable vote entries, the build prints a `warning:` line and adds a German warning to the validation report. This usually means the Bundestag page markup changed or the filterlist id rotated.

Try the current Bundestag filterlist id with either the CLI flag or environment variable:

```bash
python3 scripts/build_dip_pulse_site.py --document-number 21/87 \
  --roll-call-list-id NEW-ID \
  --no-roster

BT_ROLL_CALL_LIST_ID=NEW-ID python3 scripts/validate_dip_protocol.py --document-number 21/87
```

## Recommended Development Workflow

1. Put secrets in `.env.local`.

   ```bash
   cp .env.example .env.local
   ```

2. Fetch one protocol without expensive enrichment.

   ```bash
   scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-roster --summary-mode off
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
