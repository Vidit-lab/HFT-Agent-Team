#!/usr/bin/env bash
# Production: build the SPA and serve everything from one uvicorn process.
#
# api/main.py mounts frontend/dist at "/" if it exists, so the API and the UI
# share an origin and there is exactly one thing to deploy and one port to open.
# (In development you don't want this -- run `npm run dev` instead and let Vite
# serve the frontend on :5173 with HMR, proxying /api to :8000.)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"

echo "==> building the frontend"
(cd "$REPO/frontend" && npm ci --silent && npm run build)

echo "==> serving AlphaMemoir on :$PORT"
cd "$REPO"
exec .venv/bin/uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
