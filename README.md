# Bundestag-Puls

Bundestag-Puls is a dependency-free static-site pipeline for German Bundestag primary sources. Its strict default build contains the DIP-backed sitting catalog, protocol dossiers, and SQLite explorer; optional Bausteine add votes, summaries, profiles, MP pages, bill tracking, and developer views.

## Prerequisites

- Python 3.11 or newer
- No third-party Python packages
- `DIP_API_KEY` for online updates

## Common Commands

Offline preview from cached data:

```bash
scripts/preview_dip_pulse_site.sh
```

Enable every optional Baustein for a full local preview:

```bash
scripts/preview_dip_pulse_site.sh --features all
```

Update one protocol online, then serve the preview:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-roster
```

Stop the background preview server:

```bash
scripts/preview_dip_pulse_site.sh stop
```

See [docs/project-documentation.md](docs/project-documentation.md) for the full command and flag reference. Release history is in [CHANGELOG.md](CHANGELOG.md), and tracked follow-up work is in [TODOS.md](TODOS.md).
