# Bundestag-Puls

Bundestag-Puls is a dependency-free static-site pipeline for German Bundestag primary sources. It turns DIP Plenarprotokoll XML, DIP API metadata, scraped roll-call vote pages, and abgeordnetenwatch.de profiles into a local HTML preview and an optional SQLite entity graph.

## Prerequisites

- Python 3.11 or newer
- No third-party Python packages
- `DIP_API_KEY` for online updates

## Common Commands

Offline preview from cached data:

```bash
scripts/preview_dip_pulse_site.sh
```

Update one protocol online, then serve the preview:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-roster
```

Stop the background preview server:

```bash
scripts/preview_dip_pulse_site.sh stop
```

See [docs/project-documentation.md](docs/project-documentation.md) for the full command and flag reference.
