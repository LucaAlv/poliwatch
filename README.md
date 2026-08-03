# Bundestag-Puls

Bundestag-Puls is a dependency-free static-site pipeline for German Bundestag primary sources. Its strict default build contains the DIP-backed sitting catalog, protocol dossiers, and SQLite explorer; optional Bausteine add votes, summaries, profiles, MP pages, bill tracking, and developer views.

There is no package manager, no framework, and no build toolchain. Two things happen:

1. `scripts/build_dip_pulse_site.py` fetches DIP data (or reads the local cache) and writes plain HTML/JSON/SQLite into `.context/dip-pulse-site/`.
2. `scripts/preview_dip_pulse_site.sh` runs that build and serves the output with `python3 -m http.server` on localhost.

`.context/` is gitignored: it is build output and cache, never source.

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | `python3 --version`. No third-party packages are needed. |
| bash + git | The preview script is bash. On Windows use WSL, or call `build_dip_pulse_site.py` directly. |
| `DIP_API_KEY` | Required for every online fetch. Not needed for offline rebuilds. |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | Only for generating LLM summaries (`summaries` Baustein). |

Getting a DIP API key: the Bundestag publishes a shared public key on the [DIP API help page](https://dip.bundestag.de/%C3%BCber-dip/hilfe/api) (no registration), or you can request a personal, permanently valid key by e-mail to `parlamentsdokumentation@bundestag.de`.

## 2. First-time setup

```bash
git clone https://github.com/LucaAlv/poliwatch.git
cd poliwatch
cp .env.example .env.local
```

Edit `.env.local` and fill in the keys you have — at minimum `DIP_API_KEY`:

```bash
DIP_API_KEY=your-key-here
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

`.env.local` is gitignored. The preview script loads it, as do `build_dip_pulse_site.py` and `validate_dip_protocol.py` (the two scripts that make API calls); `persist_dip_pulse_store.py` and `render_dip_pulse_html.py` never read it. Precedence differs by entry point: the preview script sources the file, so `.env.local` overrides an already-exported variable; the Python scripts skip keys that are already exported, so there the environment wins.

That asymmetry has one sharp edge worth knowing before it bites you. `.env.example` ships `DIP_API_KEY=` with an empty value, so a copied-but-unedited `.env.local` will wipe a key you passed on the command line, and the preview script then aborts with `DIP_API_KEY is not set`. Either fill the key in `.env.local` or delete the empty line before passing one from the environment.

A fresh clone has no cached data, so the first build **must** be an online one:

```bash
scripts/preview_dip_pulse_site.sh update --limit 5 --detail-limit 2
```

This fetches the 5 newest Bundestag protocols into the catalog, enriches the 2 newest into full dossiers, writes the SQLite store, and starts a background server on `http://localhost:8000/` (or `$CONDUCTOR_PORT` when that is set). On macOS it also opens the browser; elsewhere open the printed URL yourself. Budget roughly half a minute per enriched sitting for a core-only build; enabling votes, profiles, or the MdB roster makes it substantially slower.

Verify the install without touching the network at all:

```bash
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests
```

The tests run from committed fixtures under `tests/fixtures/` and need no network, no `.context/`, and no API keys. CI runs the same two checks on Python 3.11, 3.12, and 3.13.

Run every command from the repository root. The preview script `cd`s there itself; the Python scripts resolve `.context/dip-pulse-site` relative to the current directory.

## 3. Everyday loop

```bash
scripts/preview_dip_pulse_site.sh        # offline rebuild from cache + serve
```

The default mode is offline: it re-renders all HTML from cached JSON/SQLite and makes zero API calls. It finishes in well under a second, which is what makes it the right command for UI and rendering work.

```bash
scripts/preview_dip_pulse_site.sh stop   # stop the background server
```

The server keeps running between rebuilds. `http.server` reads from disk on every request, so a rebuild never needs a restart — just reload the page.

## 4. Refreshing

Three different things get called "refresh". They need different commands.

### 4a. After a rebuild — refresh the browser

Reload the page (Cmd-R / Ctrl-R). Re-running the preview script while the server is up prints `Vorschau aktualisiert` and leaves the same PID serving the new files. If a page still looks stale, hard-reload; if the server itself is wedged:

```bash
scripts/preview_dip_pulse_site.sh stop
scripts/preview_dip_pulse_site.sh
```

### 4b. After new Bundestag data — refresh the data

`update`, `refresh`, and `fetch` are the same alias for "online build". Everything after that word goes to `build_dip_pulse_site.py`.

Pull the current catalog and re-enrich the newest sittings, keeping everything already built:

```bash
scripts/preview_dip_pulse_site.sh update --preserve-existing-dossiers
```

With the default `--limit 0`, the catalog covers every Bundestag plenary protocol back to 1949 — 4,667 entries in an August 2026 run, fetched in roughly 15 seconds. Only the newest `--detail-limit` sittings become dossiers; the rest stay catalog rows. Pass `--limit 20` if you want a short catalog instead.

Enrich exactly one sitting, leaving every other dossier untouched:

```bash
scripts/preview_dip_pulse_site.sh update \
  --limit 20 \
  --detail-limit -1 \
  --dossier-document-number 21/90 \
  --preserve-existing-dossiers
```

Only the dossier work is narrowed here. The catalog is still fetched (`--limit 20` keeps that cheap); drop `--limit` if you want the full catalog again.

**The `--preserve-existing-dossiers` flag matters.** Each online build rewrites the catalog and rebuilds the SQLite store from the dossiers that build knows about. Without the flag, that set is only the dossiers generated in *this* run, so a narrow update silently shrinks the site to those sittings. The cached JSON stays on disk, so recover by re-running a build that is not restricted to one document, with the flag: `scripts/preview_dip_pulse_site.sh update --limit 20 --detail-limit -1 --preserve-existing-dossiers`. Note that `--preserve-existing-dossiers` cannot rescue a `--document-number` build — preserved dossiers are filtered to the catalog, and that flag restricts the catalog to the one protocol.

Related knobs, in the order you will reach for them:

| Flag | Effect |
|---|---|
| `--limit N` | Protocols in the catalog. Default `0` = every available BT protocol. |
| `--detail-limit N` | Protocols enriched into dossiers. Default `5`; `0` = all fetched, `-1` = none. |
| `--document-number 21/90` | Restrict catalog *and* dossiers to this protocol. Repeatable. Narrowing tool. |
| `--dossier-document-number 21/90` | Add one dossier without restricting the catalog. Repeatable. Additive tool. |
| `--summary-mode off` | Never call an LLM. Default `reuse` keeps existing summaries without new calls. |
| `--no-roster`, `--no-abgeordnetenwatch` | Legacy aliases for `--disable mp-roster` / `--disable aw-profiles`. Big speed levers. |

While developing a single dossier, the fastest online build is:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/90 --no-roster --summary-mode off
```

`--document-number` restricts the catalog *and* the store to that one protocol, so use it when you want a one-sitting site to iterate on, not as a refresh of a full local site. Rebuild the wider site with the recovery command above, raising `--limit` (or dropping it, for the full catalog) to the breadth you want back.

### 4c. After pulling code changes — refresh the site

```bash
git pull
python3 -m unittest discover -s tests
scripts/preview_dip_pulse_site.sh
```

The offline rebuild regenerates every page from the existing cache, so template, renderer, navigation, and Baustein changes land without re-fetching. It also opens and migrates the SQLite store, so a cache written by an older version keeps working after a schema change.

An offline rebuild does *not* re-derive the rows in that store — it only re-renders. Two cases therefore need more than step 4c:

- **The update changed what gets persisted** (new columns filled during persist, new derived rows). Either run an online build, or re-persist the cached reports without any network access. Build a fresh database and swap it in, the way the online build does — persisting into the existing file would leave rows behind for protocols that are no longer cached:

  ```bash
  DB=.context/dip-pulse-site/data/bundestag-pulse.sqlite
  rm -f "$DB.new"
  for report in .context/dip-pulse-site/data/plenarprotokoll-*.json; do
    case "$report" in *catalog.json) continue;; esac
    python3 scripts/persist_dip_pulse_store.py "$report" --database "$DB.new"
  done
  mv "$DB.new" "$DB"
  scripts/preview_dip_pulse_site.sh
  ```

- **The update changed fetching or extraction** (`validate_dip_protocol.py`, roll-call scraping, profile resolution). The cached reports predate the fix, so re-fetch with 4b.

Otherwise the offline rebuild is enough.

Hard reset, when the cache itself is suspect:

```bash
scripts/preview_dip_pulse_site.sh stop
rm -rf .context/dip-pulse-site
scripts/preview_dip_pulse_site.sh update --limit 5 --detail-limit 2
```

## 5. Bausteine (optional features)

The shipped default is strict: only `dip-fetch`, `sitting-catalog`, `dossiers`, and `store` are built. List the registry and exit, without any network access or build work:

```bash
python3 scripts/build_dip_pulse_site.py --list-features
```

| ID | Adds | Requires |
|---|---|---|
| `votes` | Roll-call totals, fractions, individual votes | `dip-fetch` |
| `summaries` | LLM summaries per sitting and agenda item | `dip-fetch` |
| `aw-profiles` | abgeordnetenwatch.de profile links | `dip-fetch` |
| `mp-pages` | MP index and detail pages | `store` |
| `mp-roster` | Full DIP MdB roster on those pages | `mp-pages` |
| `bills` | Bill index and detail pages | `dip-fetch` |
| `bill-follow` | Browser-local bill following | `bills` |
| `dev-view` | Raw API panels and dossier command tools | `dossiers` |

Per build:

```bash
scripts/preview_dip_pulse_site.sh --features all              # everything, from cache
scripts/preview_dip_pulse_site.sh --enable bills --enable mp-pages
BUNDESTAG_PULSE_FEATURES=+dev-view,-votes scripts/preview_dip_pulse_site.sh
```

Those are offline builds: they render every enabled Baustein from what is already cached. Votes, profiles, and the MdB roster only arrive through an online build, and summaries are only generated when you ask for them:

```bash
scripts/preview_dip_pulse_site.sh update --features all --summary-mode auto
```

Without `--summary-mode auto` the default `reuse` keeps existing summaries and generates none, so the `summaries` Baustein stays empty on a fresh cache. Generating summaries needs `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`.

Requirements are pulled in automatically; an explicit disable cascades to dependents; core Bausteine cannot be disabled.

Selection is per build, not sticky: a later build without the flags deletes the optional pages it no longer owns. For a durable personal default, create a gitignored `features.local.json` next to `features.json`:

```json
{ "enable": ["bills", "mp-pages"] }
```

Use `{"features": ["all"]}` to replace the base selection instead of adding to it. Precedence: registry defaults → `features.json` → `features.local.json` → `BUNDESTAG_PULSE_FEATURES` → `--features` → legacy flags → `--enable` → `--disable`.

The gear in every page header and `settings.html` change only what the current browser *shows*; they never rebuild. A Baustein that was not built is listed there with the exact command needed to build it.

## 6. Server settings

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `$CONDUCTOR_PORT` or `8000` | HTTP port |
| `PREVIEW_BIND` | `127.0.0.1` | Bind host; set `0.0.0.0` to expose on the LAN deliberately |
| `OPEN_BROWSER` | `1` | Set `0` to not open a browser on start |
| `DIP_PULSE_OUTPUT_DIR` | `.context/dip-pulse-site` | Static output directory |
| `DIP_PULSE_PID_FILE` | `.context/dip-pulse-server.pid` | Background server PID |
| `DIP_PULSE_LOG_FILE` | `.context/dip-pulse-server.log` | Server log |

```bash
PORT=9000 OPEN_BROWSER=0 scripts/preview_dip_pulse_site.sh
```

Stop the server before changing `PORT`, `PREVIEW_BIND`, or `DIP_PULSE_OUTPUT_DIR`. The script only checks whether *a* server is alive, not which port or directory it serves, so changing these while it runs rebuilds the files, leaves the old server in place, and prints the new URL even though nothing is listening there.

## 7. Hosting the generated site elsewhere

`.context/dip-pulse-site/` is self-contained static output. Every internal link is relative (only citations to bundestag.de and abgeordnetenwatch.de are absolute), so it can be copied to any static host, including a subdirectory:

```bash
python3 scripts/build_dip_pulse_site.py --features all --preserve-existing-dossiers
rsync -a .context/dip-pulse-site/ user@host:/var/www/bundestag-puls/
```

Calling the builder directly instead of the preview script keeps the deploy build from starting a local server.

Note that `data/` ships alongside the pages and contains the cached DIP JSON and the SQLite store — that is intentional (the database explorer and dev views read them), but it means the whole cache becomes public.

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `error: DIP_API_KEY is not set.` | Online mode without a key. Put it in `.env.local`. A `DIP_API_KEY=... scripts/preview_dip_pulse_site.sh update ...` prefix only works when `.env.local` does not define the key at all — an empty `DIP_API_KEY=` line overwrites it (§2). |
| `error: No cached protocols found in .context/dip-pulse-site/data.` | Offline build on an empty cache. Run one online update first (§2). |
| Site suddenly shows only one sitting | A narrow online update rewrote the catalog. Re-run with `--preserve-existing-dossiers`. |
| Port already in use | `PORT=9000 scripts/preview_dip_pulse_site.sh` |
| Optional pages disappeared | A later build ran without the Baustein flags. Re-pass them or persist them in `features.local.json` (§5). |
| `warning:` about roll-call votes | The Bundestag list markup or filterlist id changed. Pass `--roll-call-list-id NEW-ID` or set `BT_ROLL_CALL_LIST_ID`. |
| abgeordnetenwatch 429s / timeouts | The resolver throttles and retries; the build continues without profile links. Add `--no-abgeordnetenwatch` for debug runs. |
| Builds feel slow | Narrow with `--document-number`, lower `--detail-limit`, and leave `mp-roster`, `aw-profiles`, `votes`, and `summaries` off. |

## 9. More documentation

- [docs/project-documentation.md](docs/project-documentation.md) — full command, flag, and environment reference, pipeline internals, SQLite schema.
- [docs/design/bundestag-pulse-design.md](docs/design/bundestag-pulse-design.md) — product and design rationale.
- [CHANGELOG.md](CHANGELOG.md) — release history. [TODOS.md](TODOS.md) — tracked follow-up work.
