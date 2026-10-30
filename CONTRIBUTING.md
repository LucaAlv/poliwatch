# Contributing

Before your first fetch, check `.env.local`: the empty `DIP_API_KEY=` copied from `.env.example` overrides an exported key and makes the preview stop. Fill it in or remove the empty line. See [First-time setup (§2)](README.md#2-first-time-setup).

Run these from the repository root:

```bash
python3 -m unittest discover -s tests
```

Runs the fixture-based test suite without network access. See [First-time setup (§2)](README.md#2-first-time-setup).

The browser checks require Node 22 or newer and Chrome or Chromium; CI uses
Node 24. They generate local fixtures and run in a temporary headless browser
profile, checking repeated speech-link keyboard activation, recipe copy,
responsive week-comparison layouts, and bill-search matching and URL/history:

```bash
node tests/run_bills_browser_check.mjs python3.13
```

Set `CHROME_BIN` if the browser is installed outside the standard locations.
CI runs these checks once, alongside the Python 3.13 lane.

The gstack pre-gate uses `python3.13 tests/run_pregate.py {files}`. It runs the
complete unit suite and browser checks for every selected lane, because automatic
lane discovery misses Python imports from `scripts/`. On this Mac, `python3.13`
resolves to `/opt/miniconda3/bin/python3.13`.

While introducing or changing `.gstack/pregate.json`, validate the branch's
configuration explicitly:

```bash
$HOME/.codex/skills/gstack/bin/gstack-pregate validate
$HOME/.codex/skills/gstack/bin/gstack-pregate --policy-from head --allow-repo-commands
```

Adjust the path if gstack is installed elsewhere. The default pre-gate reads
the configuration committed on `origin/main`.

```bash
scripts/preview_dip_pulse_site.sh
```

Rebuilds the site from cached data and serves it locally. See [Everyday loop (§3)](README.md#3-everyday-loop) and [Server settings (§6)](README.md#6-server-settings).

```bash
scripts/preview_dip_pulse_site.sh update --limit 5 --detail-limit 2
```

Fetches recent Bundestag data and builds dossiers; requires a `DIP_API_KEY`. See [Refreshing (§4)](README.md#4-refreshing) and [First-time setup (§2)](README.md#2-first-time-setup).
