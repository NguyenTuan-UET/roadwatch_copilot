#!/usr/bin/env bash
# Demo laptop -> public HTTPS URL. Stops the server and the tunnel on Ctrl+C.
#   RW_NGROK_DOMAIN=xxx.ngrok-free.app RW_PASSWORD=... scripts/roadwatch/serve_tunnel.sh   # fixed ngrok URL
#   RW_PASSWORD=... scripts/roadwatch/serve_tunnel.sh                                      # Cloudflare quick tunnel,
#                                                                                          # new URL each start
# No RW_PASSWORD: a random one is generated and printed. Needs ngrok (or cloudflared) in PATH.
set -euo pipefail
cd "$(dirname "$0")/../.."

export RW_HOST=127.0.0.1 RW_PORT="${RW_PORT:-8765}"
export RW_USER="${RW_USER:-roadwatch}" RW_PASSWORD="${RW_PASSWORD:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')}"
export RW_KEEP_RUNS="${RW_KEEP_RUNS:-5}"            # uploaded dashcam video of other people: keep little
PY="${PY:-.venv/bin/python}"
LOG=$(mktemp)

if [ -n "${RW_NGROK_DOMAIN:-}" ]; then
  export RW_MAX_UPLOAD_MB="${RW_MAX_UPLOAD_MB:-500}"
else
  export RW_MAX_UPLOAD_MB="${RW_MAX_UPLOAD_MB:-100}"   # Cloudflare free plan rejects request bodies above 100 MB
fi

"$PY" -m src.roadwatch.web &
SERVER=$!
TUNNEL=
trap 'kill $SERVER $TUNNEL 2>/dev/null' EXIT INT TERM
for _ in $(seq 30); do curl -sf "http://127.0.0.1:$RW_PORT/health" >/dev/null && break; sleep 1; done

if [ -n "${RW_NGROK_DOMAIN:-}" ]; then
  ngrok http "http://127.0.0.1:$RW_PORT" --url "https://$RW_NGROK_DOMAIN" --log stdout >"$LOG" 2>&1 &
  TUNNEL=$!
  for _ in $(seq 30); do grep -q 'started tunnel' "$LOG" && URL="https://$RW_NGROK_DOMAIN" && break; sleep 1; done
else
  cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$RW_PORT" >"$LOG" 2>&1 &
  TUNNEL=$!
  for _ in $(seq 60); do URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1) && [ -n "$URL" ] && break; sleep 1; done
fi
echo "RoadWatch public URL: ${URL:-not ready, see $LOG}"
echo "Login: $RW_USER / $RW_PASSWORD"
# Exit when either the server or the tunnel dies, so a supervisor (systemd Restart=always) restarts both.
wait -n $SERVER $TUNNEL
