# Bundestag-Puls

Bundestag-Puls is a dependency-free static-site pipeline for German Bundestag primary sources. Every publication contains the DIP-backed sitting catalog, protocol dossiers, SQLite explorer, and optional browser-controlled experiences for votes, summaries, profiles, MP pages, bill tracking, and developer views.

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
| `--summary-mode auto` | Regenerate summaries with an LLM. Default `reuse` keeps existing summaries without new calls. |
| `--enrich ID` | Add optional vote, profile, or full-roster acquisition to this update. Omit it for the fastest update. |

While developing a single dossier, the fastest online build is:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/90
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

## 5. Bausteine (browser features and data enrichments)

Every build now publishes all user-facing areas and optional section shells. The gear in every page header and `settings.html` let each visitor show or hide votes, summaries, profile links, MP pages, bill tracking, and the developer view. The choice is stored only in that browser and is applied immediately; a reload keeps it. First-time visitors see the core-only view.

This is separate from **data enrichment**. Browser switches never access the network, expose API keys, or create LLM costs. If data has not been acquired, enabling its feature shows an honest unavailable or partial state. List the registry without network or build work with:

```bash
python3 scripts/build_dip_pulse_site.py --list-features
```

| Browser feature | Adds |
|---|---|
| `votes` | Roll-call totals, fractions, and individual votes |
| `summaries` | LLM summaries per sitting and agenda item |
| `aw-profiles` | abgeordnetenwatch.de profile links |
| `mp-pages` | MP index and detail pages |
| `bills` | Bill index and detail pages |
| `bill-follow` | Browser-local bill following; enabling it also enables bills |
| `dev-view` | Raw API panels and dossier command tools |

On `puls.html` the Abstimmungsverschiebung panel (`votes`) is gated this way: it renders into every build and is hidden by the visitor's setting, so the page reads correctly either way. The week-radar view designed in [docs/designs/puls-wochenradar.md](docs/designs/puls-wochenradar.md) adds its own `votes`- and `summaries`-gated elements once it lands (TODOS.md).

The ordinary offline preview needs no feature arguments:

```bash
scripts/preview_dip_pulse_site.sh
```

Use `--enrich` only when an online update should acquire optional data. It is repeatable and accepts `votes`, `aw-profiles`, `mp-roster`, or `all`:

```bash
scripts/preview_dip_pulse_site.sh update --enrich votes --enrich aw-profiles
scripts/preview_dip_pulse_site.sh update --enrich all --summary-mode auto
```

Without `--summary-mode auto` the default `reuse` carries existing summaries forward and makes no LLM request. Generating summaries needs `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` and may incur provider cost. `--enrich all` deliberately does not imply summary generation.

An update that omits an enrichment reuses already cached votes, profile links, summaries, and roster rows. Only an explicitly requested enrichment refreshes that source.

For durable operator defaults, use the gitignored `features.local.json` next to `features.json`:

```json
{ "enrich": ["votes", "aw-profiles"] }
```

`BUNDESTAG_PULSE_ENRICHMENTS=votes,aw-profiles` is the environment-variable equivalent. The old `--features`, `--enable`, `--disable`, and `BUNDESTAG_PULSE_FEATURES` inputs remain accepted for one release and print a deprecation warning; they no longer remove published UI.

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

`--today`, `SOURCE_DATE_EPOCH`, and `--week` pin the build clock and the sitting week for `puls.html`. All three are validated on every build now — a bad `SOURCE_DATE_EPOCH` or a `--week` outside the archive fails the build before any file is written — but `puls.html` does not read them yet: the rendered page is unaffected until the week radar ([docs/designs/puls-wochenradar.md](docs/designs/puls-wochenradar.md)) lands in a later release. Pin them anyway so builds stay reproducible once it does:

| Input | Effect |
|---|---|
| `--today YYYY-MM-DD` | Build date, validated; not yet reflected in `puls.html`'s wording |
| `SOURCE_DATE_EPOCH` | Fallback when `--today` is absent: an integer Unix timestamp, read as UTC |
| neither | The current date at build time |
| `--week YYYY-WW` | ISO sitting week, validated against the archive; `puls.html` still shows the newest sitting regardless of which week is named. A week the build cannot hold is refused before any file is written (offline: no cached dossier; online: none of the dossiers this run builds, per `--detail-limit`/`--dossier-document-number`, or keeps with `--preserve-existing-dossiers`) and the message lists the available weeks. Online, if every dossier of that week then fails to build, the build stops after the dossiers, before `puls.html` |

```bash
python3 scripts/build_dip_pulse_site.py --offline --today 2026-09-15 --week 2026-24
```

Stop the server before changing `PORT`, `PREVIEW_BIND`, or `DIP_PULSE_OUTPUT_DIR`. The script only checks whether *a* server is alive, not which port or directory it serves, so changing these while it runs rebuilds the files, leaves the old server in place, and prints the new URL even though nothing is listening there.

## 7. Hosting the generated site elsewhere

`.context/dip-pulse-site/` is self-contained static output. Every internal link is relative (only citations to bundestag.de and abgeordnetenwatch.de are absolute), so it can be copied to any static host, including a subdirectory:

```bash
python3 scripts/build_dip_pulse_site.py --preserve-existing-dossiers
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
| Optional feature shows no data | The UI is published, but its enrichment is absent. Check the readiness panel in settings and run an online update with the relevant `--enrich` option (§5). |
| `warning:` about roll-call votes | The Bundestag list markup or filterlist id changed. Pass `--roll-call-list-id NEW-ID` or set `BT_ROLL_CALL_LIST_ID`. |
| abgeordnetenwatch 429s / timeouts | The resolver throttles and retries; the update continues without profile links. Omit `--enrich aw-profiles` for debug runs. |
| Builds feel slow | Narrow with `--document-number`, lower `--detail-limit`, and request only the enrichments you need. |
| `error: --week 2030-01 ist nicht im Archiv` | The requested week has no cached dossier; the message lists the weeks that do (§6). |

## 9. More documentation

- [docs/project-documentation.md](docs/project-documentation.md) — full command, flag, and environment reference, pipeline internals, SQLite schema.
- [docs/design/bundestag-pulse-design.md](docs/design/bundestag-pulse-design.md) — product and design rationale.
- [docs/designs/](docs/designs/) — per-feature design docs from review sessions, e.g. [puls-wochenradar.md](docs/designs/puls-wochenradar.md) for the `puls.html` week radar.
- [CHANGELOG.md](CHANGELOG.md) — release history. [TODOS.md](TODOS.md) — tracked follow-up work.
