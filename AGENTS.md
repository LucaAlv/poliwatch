# Agent instructions

## Testing

Use Python 3.11 or newer. Run `python3 -m unittest discover -s tests` from the repository root. Tests live in `tests/` and use Python's standard-library unittest framework with local fixtures. The suite does not require network access.

See CONTRIBUTING.md and `.github/workflows/ci.yml` for the development and CI checks.

On this macOS machine, system `python3` is 3.9; use `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`.
