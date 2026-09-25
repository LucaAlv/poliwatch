# Contributing

Before your first fetch, check `.env.local`: the empty `DIP_API_KEY=` copied from `.env.example` overrides an exported key and makes the preview stop. Fill it in or remove the empty line. See [First-time setup (§2)](README.md#2-first-time-setup).

Run these from the repository root:

```bash
python3 -m unittest discover -s tests
```

Runs the fixture-based test suite without network access. See [First-time setup (§2)](README.md#2-first-time-setup).

```bash
scripts/preview_dip_pulse_site.sh
```

Rebuilds the site from cached data and serves it locally. See [Everyday loop (§3)](README.md#3-everyday-loop) and [Server settings (§6)](README.md#6-server-settings).

```bash
scripts/preview_dip_pulse_site.sh update --limit 5 --detail-limit 2
```

Fetches recent Bundestag data and builds dossiers; requires a `DIP_API_KEY`. See [Refreshing (§4)](README.md#4-refreshing) and [First-time setup (§2)](README.md#2-first-time-setup).
