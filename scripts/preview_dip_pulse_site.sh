#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -f ".env.local" ]; then
  set -a
  . "./.env.local"
  set +a
fi

PORT="${PORT:-${CONDUCTOR_PORT:-8000}}"
OUTPUT_DIR="${DIP_PULSE_OUTPUT_DIR:-.context/dip-pulse-site}"
PID_FILE="${DIP_PULSE_PID_FILE:-.context/dip-pulse-server.pid}"
LOG_FILE="${DIP_PULSE_LOG_FILE:-.context/dip-pulse-server.log}"
URL="http://localhost:${PORT}/"

usage() {
  cat <<'EOF'
Usage:
  scripts/preview_dip_pulse_site.sh [render options]
  scripts/preview_dip_pulse_site.sh update [fetch/build options]
  scripts/preview_dip_pulse_site.sh stop

Default mode renders the site from cached files in .context/dip-pulse-site/data
and never calls the DIP API. Use "update" when you explicitly want to fetch or
refresh DIP data before serving the preview.

Examples:
  scripts/preview_dip_pulse_site.sh
  scripts/preview_dip_pulse_site.sh update --limit 2 --detail-limit 2 --no-roster
  scripts/preview_dip_pulse_site.sh update --document-number 21/87 --no-roster
EOF
}

server_running() {
  [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

stop_server() {
  if server_running; then
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    echo "Vorschau-Server gestoppt (Port ${PORT})."
  else
    echo "Kein laufender Vorschau-Server gefunden."
  fi
  rm -f "$PID_FILE"
}

# `stop` tears down the background server when you are done for the day.
if [ "${1:-}" = "stop" ]; then
  stop_server
  exit 0
fi

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

BUILD_ARGS=(--output-dir "$OUTPUT_DIR")
if [ "${1:-}" = "update" ] || [ "${1:-}" = "refresh" ] || [ "${1:-}" = "fetch" ]; then
  shift
  if [ "${1:-}" != "-h" ] && [ "${1:-}" != "--help" ] && [ -z "${DIP_API_KEY:-}" ]; then
    echo "error: DIP_API_KEY is not set. Add it to .env.local or export it before running update." >&2
    exit 1
  fi
  BUILD_ARGS+=("$@")
else
  BUILD_ARGS+=(--offline "$@")
fi

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  python3 scripts/build_dip_pulse_site.py "${BUILD_ARGS[@]}"
  exit 0
fi

# 1. Rebuild the static site in place. The build overwrites files individually
#    and never wipes the directory, so a running server keeps serving safely.
python3 scripts/build_dip_pulse_site.py "${BUILD_ARGS[@]}"

# 2. Ensure the static file server is up. http.server reads from disk on every
#    request, so it only ever needs to start once — never restart it to refresh.
if server_running; then
  echo "Vorschau aktualisiert: ${URL} — Seite im Browser neu laden (Cmd-R)."
else
  mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LOG_FILE")"
  nohup python3 -m http.server "$PORT" --directory "$OUTPUT_DIR" >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  disown 2>/dev/null || true
  echo "Bundestag-Puls-Vorschau läuft auf ${URL}"
  echo "Stoppen mit: scripts/preview_dip_pulse_site.sh stop"
  if command -v open >/dev/null 2>&1 && [ "${OPEN_BROWSER:-1}" != "0" ]; then
    open "$URL" || true
  fi
fi
