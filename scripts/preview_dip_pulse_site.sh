#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -f ".env.local" ]; then
  set -a
  . ".env.local"
  set +a
fi

if [ -z "${DIP_API_KEY:-}" ]; then
  echo "error: DIP_API_KEY is not set. Add it to .env.local or export it before running." >&2
  exit 1
fi

PORT="${PORT:-${CONDUCTOR_PORT:-8000}}"
OUTPUT_DIR="${DIP_PULSE_OUTPUT_DIR:-.context/dip-pulse-site}"

python3 scripts/build_dip_pulse_site.py --output-dir "$OUTPUT_DIR" "$@"

URL="http://localhost:${PORT}/"
echo "Bundestag-Puls-Vorschau: ${URL}"

if command -v open >/dev/null 2>&1 && [ "${OPEN_BROWSER:-1}" != "0" ]; then
  open "$URL" || true
fi

exec python3 -m http.server "$PORT" --directory "$OUTPUT_DIR"
