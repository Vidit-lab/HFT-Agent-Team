# AlphaMemoir — frontend

The dashboard for AlphaMemoir: a memory-native, self-improving multi-agent
trading system. Vite + React + TypeScript + Tailwind v4, talking to the FastAPI
backend over `/api` (proxied in dev). Dark by default, with a light theme.

## Pages
- **Overview** — the memory story at a glance + the self-improvement loop.
- **Market & Ledger** — AAPL candlesticks with trade markers, positions, ledger.
- **Memory Explorer** — live semantic search, the learning-provenance graph
  (React Flow), the consolidation lens, the memory feed, and system internals.
- **Live Orchestration** — run a real cycle and watch the six agents reason,
  stage by stage, to a decision.

## Run
```bash
# 1. backend (from the repo root, venv active)
uvicorn api.main:app --port 8000
# 2. this app
npm install
npm run dev        # http://localhost:5173  (proxies /api -> :8000)
```

The self-hosted Supermemory server must also be running (scripts/run_memory_server.sh).
