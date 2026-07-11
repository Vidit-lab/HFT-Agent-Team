# Trading Brain — Memory-Centric Self-Improving Multi-Agent Trading System

A live paper-trading dashboard driven by a multi-agent LLM system, where all learning,
reflection, and cross-cycle memory is built on top of **Supermemory** as the semantic
memory layer, and a deterministic simulation engine + SQL ledger as the source of truth
for money. The system follows a decide → act → observe → reflect → remember → retrieve
loop ("autoresearch" style self-improvement), and every phase is designed to produce a
runnable, demoable artifact before the next phase begins.

**Non-goals for v1**: no real broker execution, no real money, no multi-user auth,
no production infra. These are explicitly deferred to Phase 9.

---

## 0. Grounding decisions (read this before writing any code)

These correct a few assumptions that are easy to get wrong and are expensive to unwind
later, since the whole project pivots on the memory layer.

1. **Supermemory is not a flat tag store.** Each `containerTag` passed to
   `/v3/documents` is hashed into its own isolated vector namespace. Writing many
   tags per memory (e.g. `trade`, `lesson`, `regime_bull`, `asset_BTC` all as
   container tags) fragments retrieval and adds latency — it does **not** behave like
   a multi-label filter.
   **Correct pattern**: `containerTag` = isolation scope (e.g. `trading_system`, or
   later `user_<id>`). Everything else (`type`, `strategy`, `regime`, `asset`, `pnl`,
   `outcome`) goes into the `metadata` JSON object, which supports AND/OR filtering
   at query time via `/v4/search`.

2. **Supermemory ≠ your ledger.** It extracts facts, resolves contradictions, and can
   let information expire — great for lessons, profiles, and "what happened in
   similar regimes," terrible for exact P&L and position state (you never want a
   trade "contradiction-resolved" away). **Correct pattern**: SQLite (→ Postgres
   later) is the source of truth for exact numbers. Supermemory is the semantic
   learning/insight layer only.

3. **Two search endpoints, different purposes**: `/v4/search` searches a user's
   consolidated memories/preferences/history (what we mostly want). `/v3/search`
   searches raw document chunks; hybrid mode falls back to chunks when no
   consolidated memory is found. Default to `/v4/search` for lesson/trade retrieval.

4. **`/v4/profile`** returns a condensed static + dynamic view of a user/scope — ideal
   for injecting risk tolerance / goals / standing constraints into agent prompts
   without re-querying every time.

5. **Build order principle**: de-risk the deterministic core (memory schema +
   simulation engine) *before* adding the non-deterministic parts (agents, LLMs). If
   the ledger and backtester are provably correct and reproducible, any weirdness
   once agents are wired in is attributable to the agents — not the plumbing.

---

## 1. Resource & technology stack

| Layer | Choice | Notes |
|---|---|---|
| Memory | Supermemory local binary, `http://localhost:6767` | Install: `curl -fsSL https://supermemory.ai/install \| bash` or `npx supermemory local`. Data in `./.supermemory`. Prints an API key on first boot — capture it into `.env`. |
| Memory SDK | `supermemory` (Python) | Official Python + TS SDKs. Wrappers exist for LangGraph/LangChain/OpenAI Agents SDK, but we write our own thin wrapper (Phase 1) so the whole codebase touches Supermemory through one module. |
| Source-of-truth DB | SQLite (dev) → Postgres (later) | Exact ledger: trades, positions, portfolio snapshots. Accessed via SQLModel/SQLAlchemy. |
| Backend | FastAPI + Uvicorn, Python 3.11+ | Async; Pydantic models double as frontend data contracts. |
| Agent framework | LangGraph | Stateful, cyclic graph; fits a multi-node deliberation + reflection loop better than a linear chain. CrewAI/AutoGen are acceptable alternatives if a role-based abstraction is preferred later. |
| LLM | Pluggable: hosted (Groq/Anthropic/OpenAI) or local (Ollama, e.g. `gpt-oss:20b`) | Start hosted for quality; keep an Ollama path so the whole stack can run fully offline (Supermemory itself supports pointing at Ollama). |
| Backtesting | Custom event-driven loop (own code) | Agents make sequential, memory-conditioned decisions — awkward to express in vectorized backtesting frameworks. `vectorbt` may be used later purely for independent metric validation, not as the primary engine. |
| Market data | `yfinance` (equities), `ccxt` (crypto) | Cache to local Parquet so backtests are deterministic and fully offline-repeatable. |
| Frontend | React + TypeScript + Vite, Tailwind, `lightweight-charts` (TradingView OSS) for candlesticks, Recharts for simpler stat charts | |
| Live updates | REST polling first; WebSocket only if/when live tick replay is needed (Phase 7+) | Don't build sockets before there's something worth streaming. |
| Containerization | Docker Compose (Supermemory binary, API, frontend) | Introduced once Phase 3 backend exists; not needed for Phase 0-1. |

---

## 2. Repository layout

```
trading-brain/
├── memory/                # Supermemory integration layer (Phase 1) — the ONLY module that talks to Supermemory
│   ├── client.py           # SupermemoryClient wrapper
│   ├── schemas.py          # Pydantic models for memory payloads (Trade, Lesson, RegimeSnapshot, Event)
│   └── tests/
├── sim/                    # Deterministic simulation + ledger (Phase 2)
│   ├── models.py            # Trade, Position, Portfolio, BacktestResult (Pydantic/SQLModel)
│   ├── data_loader.py        # yfinance/ccxt -> parquet cache
│   ├── engine.py             # event-driven backtest loop: fees, slippage, fills
│   ├── metrics.py            # PnL, Sharpe, max drawdown, win rate
│   ├── ledger.db              # SQLite (gitignored)
│   └── tests/
├── agents/                 # Agent definitions + orchestrator (Phase 4-6)
│   ├── state.py              # shared LangGraph state schema
│   ├── nodes/
│   │   ├── market_analyst.py
│   │   ├── researcher_bull.py
│   │   ├── researcher_bear.py
│   │   ├── risk_manager.py
│   │   ├── trader.py
│   │   ├── portfolio_manager.py
│   │   └── reflection.py       # Phase 6: the self-improvement node
│   ├── orchestrator.py        # LangGraph graph definition + run_cycle()
│   ├── prompts/               # prompt templates per node
│   └── tests/
├── api/                     # FastAPI app (Phase 3)
│   ├── main.py
│   ├── routers/ (portfolio.py, trades.py, regime.py, lessons.py, cycle.py, backtest.py)
│   └── deps.py
├── data/                    # cached OHLCV parquet + .supermemory/ (gitignored)
├── frontend/                # React app (Phase 7)
│   └── src/components/ (PortfolioCard, TradeList, TradeDetailPanel, MarketChart, RegimeIndicator, InsightsPanel, LessonCard)
├── eval/                    # Self-improvement A/B harness (Phase 8)
│   └── memory_on_off.py
├── docker-compose.yml
├── .env.example
└── plan.md                  # this file
```

---

## 3. Data & memory schema (locked before Phase 1 code)

### Structured ledger (SQLite/Postgres — source of truth)
- `trades`: id, timestamp, symbol, side, size, price, fee, slippage, strategy, regime_at_entry, rationale_summary, pnl (nullable until closed), status
- `positions`: symbol, size, avg_entry_price, unrealized_pnl
- `portfolio_snapshots`: timestamp, cash, equity, total_pnl, drawdown
- `backtest_runs`: id, params, start/end date, metrics json

### Supermemory (semantic layer)
- `containerTag`: `trading_system` (single scope for v1; revisit per-user/per-strategy isolation only if genuinely needed)
- `metadata` fields used for filtering: `type` (`trade` | `lesson` | `regime_snapshot` | `event`), `strategy`, `regime`, `asset`, `outcome` (`win`/`loss`/`neutral`), `pnl`
- Memory content is always a natural-language narrative (not raw JSON) so the extraction/embedding step has something meaningful to work with, e.g.:
  > "Entered long BTC on momentum breakout during high-volatility bull regime; exited +3.2% after RSI divergence signal. Lesson: momentum entries after 3+ consecutive green candles in high-vol regimes had strong follow-through this cycle."
- `/v3/settings.filterPrompt` configured early to constrain what the engine bothers extracting (avoid noise memories).

### Operational notes: the self-hosted memory-agent (updated Phase 6)
- The self-hosted binary's memory-agent (server-side LLM fact extraction/consolidation) was broken from Phase 0 through v0.0.3 regardless of provider (native `GROQ_API_KEY`, or `OPENAI_BASE_URL` pointed at Groq's compatible endpoint) — every document sat at `status: "failed"` with no diagnosable error (closed-source binary).
- **As of v0.0.5, it works**, using the native `GROQ_API_KEY` provider path *only* — no `OPENAI_BASE_URL`/`OPENAI_MODEL` override alongside it. Mixing the native-provider env var with the generic OpenAI-compatible override is the likely cause of the earlier failures. Upgrading requires a fresh data directory (an in-place `upgrade` on old data broke API-key auth entirely; recovered by re-initializing and treating the old container as historical/unrecoverable via the API).
- Even with the memory-agent working, `query_similar()`'s metadata filters are **not exhaustive** — empirically, filters apply within a semantically-ranked candidate subset, not the full corpus (a document can match a filter's metadata perfectly and still be excluded if it doesn't rank in the initial similarity pass for that query's text). `list_documents()` is exhaustive; `query_similar()` isn't. `agents/researcher.retrieve_memories()` mitigates this by always merging a filtered query with an unfiltered semantic query rather than only falling back when the filtered result is fully empty.
- Search results are **chunk-level**: `result.id` is a chunk id in a different namespace from the document id `write_lesson()`/`write_trade_memory()` return (`get_document(result.id)` 404s). The actual parent document id is `result.documents[0].id` — use `agents.researcher.document_id()` for anything that needs to trace a retrieval back to a specific write (the reasoning trail's `retrieved_memory_ids`).

---

## 4. Phased roadmap

Each phase has a goal, concrete build tasks, and a hard Definition of Done (DoD) —
don't proceed to the next phase until DoD is met and demoed.

### Phase 0 — Foundations & "hello, memory" (~½–1 day)
**Goal**: every moving part installed and talking, proven via the smallest possible round trip.
- Scaffold the monorepo layout above.
- Install & boot Supermemory locally; capture API key into `.env`.
- 20-line script: `client.add(content=..., container_tag="trading_system")` then
  `client.search.memories(q=..., container_tag="trading_system")`, confirm round trip.
- Decide LLM path (hosted vs Ollama); confirm one completion call succeeds.
- **DoD**: memory write→read works locally; one LLM completion succeeds. Nothing else.

### Phase 1 — Memory layer & schema (~2–3 days)
**Goal**: `memory/` is the single, fully-typed gateway to Supermemory for the rest of the codebase.
- Implement `SupermemoryClient` wrapper with:
  - `write_trade_memory(trade)`, `write_lesson(lesson)`, `write_regime_snapshot(snapshot)`, `write_event(event)`
  - `get_user_profile(q)` → `/v4/profile`
  - `query_similar(q, filters)` → `/v4/search` with metadata AND/OR filters
- Lock in the containerTag/metadata schema from §3.
- Configure `filterPrompt` in `/v3/settings`.
- Write integration tests against the **live local binary** (not mocked).
- **DoD**: write 50 synthetic trades + lessons; retrieve "lessons for strategy=momentum in regime=high-vol" with correct filtering, verified by test.

### Phase 2 — Simulation & backtesting engine (~3–5 days)
**Goal**: deterministic virtual-money trading, no LLMs involved yet.
- Pydantic/SQLModel data models: `Trade`, `Position`, `Portfolio`, `BacktestResult`.
- OHLCV loader with Parquet caching (`yfinance`/`ccxt`).
- Event-driven loop: signal in (side/size/symbol) → apply fees + slippage → update positions/cash → persist to SQLite.
- Metrics module: PnL, max drawdown, Sharpe, win rate.
- Validate against a trivial mechanical strategy (moving-average crossover).
- **DoD**: running the mechanical strategy over a fixed date range produces byte-identical results on every run. This determinism is required for Phase 8 to mean anything.

### Phase 3 — Backend API skeleton (~2 days)
**Goal**: FastAPI exposing simulation + memory state, before any agents exist.
- Read-only endpoints: `GET /api/portfolio`, `GET /api/trades`, `GET /api/trades/{id}`, `GET /api/regime`, `GET /api/lessons` (proxies `memory/`).
- Stub endpoints: `POST /api/run-cycle`, `POST /api/backtest` (not yet functional).
- Pydantic response models become the frontend's data contract.
- **DoD**: every endpoint returns real data from SQLite + Supermemory via curl/HTTPie.

### Phase 4 — Single agent + orchestrator (~3–4 days)
**Goal**: one LLM agent closing the entire loop before scaling to a team — the classic mistake is building 6 agents before 1 works end-to-end.
- Minimal LangGraph with one `Trader/Analyst` node: receives market state + retrieved memories → outputs structured decision (`{side, size, rationale}` JSON).
- Orchestrator runs the decision through the Phase 2 engine and writes a trade memory via Phase 1.
- Wire `POST /api/run-cycle` to trigger a real cycle.
- **DoD**: one API call → agent decides → simulated trade executes → ledger and Supermemory both update, observably.

### Phase 5 — Multi-agent system (~4–6 days)
**Goal**: expand the single node into the full specialist graph.
- Nodes: `Market Analyst` (regime classification from data + regime memories), `Researcher Bull`/`Researcher Bear` (debate, each citing retrieved lessons), `Risk Manager` (checks proposal against user-profile constraints — position limits, drawdown caps), `Trader` (sizing/execution), `Portfolio Manager` (final arbiter/allocation).
- Every node reads/writes Supermemory **only** through `memory/`.
- Standard prompt injection per node: `{market_state}`, `{retrieved_lessons}`, `{retrieved_similar_trades}`, `{risk_constraints}`; instruct explicitly to prefer strategies that worked in similar regimes, avoid patterns from failure-tagged lessons, and cite which memory informed the decision.
- **DoD**: a cycle produces a decision with a visible cross-agent reasoning trail, and logs show which retrieved memories influenced the outcome.

### Phase 6 — Reflection loop / the "autoresearch" core (~3–4 days)
**Goal**: the actual self-improvement mechanism — what makes this more than a chatbot with a backtester.
- `Reflection/Learning Agent` runs after trade outcomes are known: compares intent vs. result, diagnoses cause (regime misread? risk ignored? good thesis/bad timing?), writes a generalizable natural-language `lesson` memory tagged with `strategy`/`regime` metadata.
- Next cycle's `query_similar()` calls surface these lessons into decision prompts — closing decide → act → observe → reflect → remember → retrieve.
- Framing note for docs/README: this is *inspired by* the self-improving-agent lineage (Reflexion's verbal self-feedback, Voyager's growing skill library) — there is no single canonical "Karpathy autoresearch paper" to cite; describe it honestly as inspired-by, not attributed.
- **DoD**: run the same market window twice; on the second pass, decisions demonstrably reference lessons written during the first pass (visible in logs/reasoning trail).
- **Done**: `agents/reflection.py` computes outcome (win/loss/neutral) deterministically from realized or forward return — never asked of the LLM — and diagnoses cause + writes the lesson. `agents/reflection_loop.py` batches eligible trades (closed, or aged past a lookback window) on demand via `POST /api/reflect`, decoupled from `run_cycle`'s hot path. Validated with a 13-cycle, 6-month AAPL stress test: 4 trades reflected on, 4 lessons written, and a follow-up cycle's Bull researcher cited 2 of them by verified document id (see §3's operational notes for the chunk-id/document-id distinction this required fixing).

### Phase 7 — Live dashboard (~5–7 days)
**Goal**: the front-facing product.
- Views: Portfolio Overview (`PortfolioCard`), Trade History & Detail (`TradeList`, `TradeDetailPanel` with agent reasoning trail), Market & Regime (`MarketChart` via `lightweight-charts`, `RegimeIndicator`), and the differentiator — Insights & Lessons (`InsightsPanel`, `LessonCard`: "lessons from similar regimes," "strategy performance over time") fed directly from Supermemory queries.
- REST polling to start; WebSocket only if live tick replay during a running simulation is wanted.
- **DoD**: watch a backtest replay in the UI with memory-driven insights updating alongside trades.

### Phase 8 — Prove it actually improves (~3–4 days)
**Goal**: turn "it feels smarter" into evidence. Frequently skipped — this is what makes the whole project credible.
- `eval/` harness: run the same held-out market period twice — once with memory retrieval disabled (agents blind to past lessons), once enabled.
- Compare PnL, Sharpe, drawdown, win rate, and qualitative decision quality; track lesson-count and lesson-reuse across successive runs.
- **DoD**: a reproducible memory-on vs memory-off A/B with a measurable delta, reported honestly even if the delta is small early on.

### Phase 9 — Future / real-execution path (explicitly deferred)
- Design `ExecutionInterface` abstraction now (in Phase 2/4) so a real broker adapter can later replace the simulation engine without touching agent code.
- Add auth, rate limiting, and a hard paper-vs-live guard before any real-money path is considered.
- No real money, no production infra, single-user — for all of Phases 0–8.

---

## 5. Cross-cutting engineering practices
- **One gateway rule**: nothing outside `memory/` calls the Supermemory API directly; nothing outside `sim/` writes to the ledger directly. This keeps Phase 8's A/B harness trustworthy (memory-off means literally routing around one module).
- **Determinism first**: fix random seeds, cache all market data locally, and keep the Phase 2 engine agent-agnostic so backtests are exactly reproducible.
- **Tests against the real local binary** for the memory layer (Phase 1) rather than mocks — Supermemory's fact-extraction/contradiction-resolution behavior is exactly what needs verifying and is not meaningfully mockable.
- **Prompt logging**: persist the full prompt + retrieved-memory set + raw LLM output for every agent decision (small JSON blob per cycle) — this is what makes Phase 5's "reasoning trail" and Phase 8's evaluation possible after the fact.

---

## 6. Immediate next step

Start Phase 0: scaffold the repo layout in §2, install and boot the Supermemory local
binary, and get the write→read→LLM-completion round trip working. Nothing in Phase 1+
should begin until that's demoed.
