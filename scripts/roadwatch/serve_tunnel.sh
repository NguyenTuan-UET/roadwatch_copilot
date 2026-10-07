#!/usr/bin/env bash
# Demo laptop -> public HTTPS URL through a Cloudflare quick tunnel (no account; the URL changes each start).
#   RW_PASSWORD=... scripts/roadwatch/serve_tunnel.sh        (no RW_PASSWORD: a random one is generated and printed)
# Stops both processes on Ctrl+C. Needs cloudflared in PATH: docs/roadwatch-operations.md, section 7.
set -euo pipefail
cd "$(dirname "$0")/../.."

export RW_HOST=127.0.0.1 RW_PORT="${RW_PORT:-8765}"
export RW_USER="${RW_USER:-roadwatch}" RW_PASSWORD="${RW_PASSWORD:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')}"
export RW_MAX_UPLOAD_MB="${RW_MAX_UPLOAD_MB:-100}"   # Cloudflare free plan rejects request bodies above 100 MB
export RW_KEEP_RUNS="${RW_KEEP_RUNS:-5}"            # uploaded dashcam video of other people: keep little
PY="${PY:-.venv/bin/python}"

"$PY" -m src.roadwatch.web &
SERVER=$!
trap 'kill $SERVER $TUNNEL 2>/dev/null' EXIT INT TERM
for _ in $(seq 30); do curl -sf "http://127.0.0.1:$RW_PORT/health" >/dev/null && break; sleep 1; done

LOG=$(mktemp)
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$RW_PORT" >"$LOG" 2>&1 &
TUNNEL=$!
for _ in $(seq 60); do URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1) && [ -n "$URL" ] && break; sleep 1; done
echo "RoadWatch public URL: ${URL:-not ready, see $LOG}"
echo "Login: $RW_USER / $RW_PASSWORD"
wait $SERVER
