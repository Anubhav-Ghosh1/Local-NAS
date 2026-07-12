#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Home NAS — startup script
#
#  First run: copy .env.example → .env and edit SECRET_KEY
#
#  External access (Cloudflare Tunnel — free, no port forwarding):
#    brew install cloudflare/cloudflare/cloudflared
#    Then in a second terminal run:
#      cloudflared tunnel --url http://localhost:8080
#    You'll get a random *.trycloudflare.com URL instantly.
#    For a permanent custom domain, see:
#      https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
# ─────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  .env created. Edit it to set a real SECRET_KEY before exposing externally."
  echo ""
fi

if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "Installing Python dependencies…"
  pip3 install -r requirements.txt
fi

# Load env vars for HOST/PORT display
export $(grep -v '^#' .env | xargs) 2>/dev/null || true
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

echo ""
echo "🗄️  Home NAS → http://${HOST}:${PORT}"
echo "    Local:    http://localhost:${PORT}"
echo "    Network:  http://$(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}'):${PORT}"
echo ""
echo "    Default login: admin / admin123  (change it after first login!)"
echo ""

python3 -m uvicorn main:app --host "$HOST" --port "$PORT" --reload
