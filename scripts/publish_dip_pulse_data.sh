#!/usr/bin/env bash
# Thin wrapper: the release logic and its tests live in publish_dip_pulse_data.py.
# Dry run by default; --publish needs LICENSE-DATA.md at the repository root (ADR 0003).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$HERE/publish_dip_pulse_data.py" "$@"
