<div align="center">

# AlphaMemoir

### A trading brain that remembers why it was wrong.

**Six agents debate every trade. It diagnoses the outcome, distils the lesson, and remembers — so the next decision is made by an agent that has already learned.**

Built on [Supermemory](https://supermemory.ai) · Self-hosted · Live crypto data

</div>

---

## 1. What this is

Almost every LLM trading agent is **stateless**. It wakes up, reads a chart, produces a confident
paragraph, places a trade, and forgets everything. Run it a thousand times and it makes the same
mistake a thousand times, with the same confidence. It has no memory, so it has no edge.

**AlphaMemoir closes that loop.**

```
   DEBATE            REFLECT              CONSOLIDATE            RECALL
 six agents  ──►  diagnose the   ──►   distil many        ──►  retrieve into
 argue it out     real outcome         lessons into one       the next debate
      ▲                                                             │
      └─────────────────────────────────────────────────────────────┘
                   every loop makes the next debate smarter
```

1. **Debate** — a Market Analyst reads the regime, a Bull and a Bear argue it out, a Risk Manager
   sets the size envelope, a Trader sizes the position, a Portfolio Manager signs off.
2. **Reflect** — once the outcome is knowable, a Reflection Agent diagnoses *why the reasoning
   worked or failed* and writes a generalised lesson.
3. **Consolidate** — a Consolidation Agent merges related lessons into higher-order meta-lessons,
   so knowledge **compounds** instead of piling up as noise.
4. **Recall** — the next debate retrieves those lessons semantically, and cites them by ID.

The agents are stateless. **Supermemory is their memory.** The self-improvement loop runs
*through* it.

> **Nothing here is mocked.** Real Binance candles, real LLM calls, real memory writes, real
> retrieval — and a provenance graph you can click that traces every lesson back to the trade that
> produced it.

---

## 2. Data source & agent architecture

### Data source — live, not a snapshot

Market data comes from **Binance public spot via `ccxt`** — `BTC/USDT`, `ETH/USDT`, `SOL/USDT` on
`15m / 1h / 4h / 1d` bars. Crypto trades 24/7, so there are no weekend gaps and no "market closed"
excuse: the chart is always the live tape, and the newest candle is the one currently forming.

Two details make it robust rather than merely live:

- **A TTL cache** (20s bars / 5s ticker) sits in front of ccxt. However many browser tabs are
  polling, the exchange sees at most one call per window.
- **A last-good Parquet snapshot** is written on every successful fetch. If the network dies
  mid-demo, the chart still renders real candles and flags itself `stale`. It never shows a lie,
  and it never shows an error page. (Fallback chain: `binance → bybit → kucoin → coinbase`.)

`sim/market_data.py` routes on the symbol and always returns the same
`[timestamp, open, high, low, close, volume]` frame. Every agent reads only `bars["close"]` — which
is exactly why the data source is swappable without touching a single agent.

### Agent architecture

```
                          ┌──────────────────────┐
   live ccxt bars ───────►│   MARKET ANALYST     │  classifies the regime
                          └──────────┬───────────┘  (trending / volatile / range-bound)
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
          ┌──────────────────┐             ┌──────────────────┐
          │  RESEARCHER  🐂  │             │  RESEARCHER  🐻  │   ◄── both RETRIEVE
          │  argues the long │             │ argues the short │       past lessons from
          └────────┬─────────┘             └─────────┬────────┘       Supermemory
                   └───────────────┬─────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │    RISK MANAGER     │  approve / veto + size envelope
                        └──────────┬──────────┘  (hard-capped in CODE, not in a prompt)
                                   ▼
                        ┌─────────────────────┐
                        │       TRADER        │  sizes the position
                        └──────────┬──────────┘
                                   ▼
                        ┌─────────────────────┐
                        │  PORTFOLIO MANAGER  │  final sign-off; may only shrink
                        └──────────┬──────────┘
                                   ▼
                    ═══════════  EXECUTE  ═══════════
                    ledger (SQLite)  +  memory (Supermemory)
                                   │
        ┌──────────────────────────┴──────────────────────────┐
        ▼                                                     ▼
┌──────────────────┐                              ┌────────────────────────┐
│ REFLECTION AGENT │   outcome is computed,  ───► │  CONSOLIDATION AGENT   │
│ diagnoses WHY    │   never LLM-judged           │  many lessons → one    │
│ → writes lesson  │                              │  meta-lesson           │
└────────┬─────────┘                              └───────────┬────────────┘
         │                                                    │
         └────────────────────► SUPERMEMORY ◄─────────────────┘
                          (retrieved by the next debate)
```

**Eight agents, orchestrated with LangGraph** — six in the decision graph, two in the learning loop.

#### The guardrails live in code, not in prompts

An LLM can be argued out of a guideline. It cannot be argued out of a `min()`.

- **Position cap** — no symbol may exceed 25% of equity, enforced arithmetically
  (`agents/limits.py`) in *both* the Risk Manager and the Portfolio Manager. Asked for a size "in
  units" with no price in context, a model will cheerfully answer `10000` — plausible for a stock,
  **~$630M of Bitcoin**. The ceiling is computed from equity and price, never guessed.
- **The Portfolio Manager may only shrink a trade**, never grow it or flip its direction.
- **A veto blocks new exposure — it does not trap you.** The Trader still runs while a position is
  open, so the book can always be *reduced*, precisely when risk is loudest.
- **Win/loss is arithmetic, not opinion.** The Reflection Agent is *told* the outcome (computed
  from realised P&L with a ±0.5% noise band) and asked only to explain it. It can never mark its
  own homework.

---

## 3. How the memory is smart — and what Supermemory actually does

This is the heart of the project, so here is the honest version.

### Supermemory is the system's long-term memory, not a database bolted on the side

Every agent is a **pure function**. Nothing survives in a session, a context window, or a variable
between cycles. What persists — what makes tomorrow's agent better than today's — lives entirely in
Supermemory. Delete the ledger and you lose the accounting. Delete Supermemory and you delete
**the intelligence**.

Five memory types are stored as first-class documents: `trade`, `lesson`, `consolidated_lesson`,
`regime_snapshot`, `event`.

### What we lean on Supermemory for

| Capability | How AlphaMemoir uses it |
|---|---|
| **Local ONNX embeddings (768-dim)** | Every memory is embedded on-device by the self-hosted server. No embedding vendor, no egress. |
| **Automatic chunking + indexing** | We hand it prose; it handles chunking, embedding and indexing. We never manage a vector store. |
| **Hybrid semantic search** | Bull and Bear retrieve with `search_mode="hybrid"` — meaning, not keywords. *"when volatility spiked"* finds the right lesson without sharing a single word with it. |
| **Metadata filtering** | Retrieval is filtered by `asset` and `type`, so a BTC debate builds a **BTC** corpus. Each asset learns its own lessons. |
| **Container tags** | One tag isolates the entire system's memory, keeping it cleanly separable. |
| **Document CRUD** | Powers the Memory Explorer: browse, open, search and delete every document the agents ever wrote. |
| **Self-hosted, encrypted on disk** | The full trading memory never leaves the machine. |

### The three things that make it *smart*, not merely stored

**1. It is written by reasoning, not by logging.**
A `lesson` is not a trade record. It is the Reflection Agent's *generalised diagnosis* of why a
debate did or didn't work — deliberately abstracted away from the specific trade, so it can fire on
a situation it has never literally seen.

**2. Knowledge compounds instead of accumulating.**
A hundred raw lessons is a hundred pieces of noise. The **Consolidation Agent** groups lessons
deterministically by `(regime, outcome)` and distils each bucket into a small number of
higher-order rules. Its idempotency key is a **hash of the exact source-document set** — so a
bucket is never re-distilled by accident, but the moment one new lesson lands in it the hash
changes, the bucket reopens, and it re-distils against the fuller group. **The memory gets denser,
not just bigger.**

**3. Every claim is traceable — it's a graph you can click.**
Each lesson stores the ID of the trade that produced it. Each meta-lesson stores the IDs of its
source lessons. Each decision logs the IDs of the memories it retrieved.

```
   trade #7 ──reflected_from──► lesson ──consolidated_into──► meta-lesson
                                   │
                                   └────────cited_by────────► a later trade's debate
```

The learning loop is not asserted on a slide. **It is a queryable edge in a graph**, rendered live
in the Memory Explorer.

> **A note on honesty.** Supermemory's self-hosted *server-side* memory-agent (its own consolidation
> pass) requires an LLM tier we don't have on the free plan, so we don't depend on it. We built
> **our own Consolidation Agent** instead and write the meta-lessons back into Supermemory as
> first-class, retrievable documents. We use Supermemory for exactly what it is excellent at —
> storage, embeddings, chunking, hybrid retrieval, metadata filtering — and we own the reasoning.
> Every claim in this README was verified against the running system.

---

## 4. Tech stack, system analysis & applications

### Stack

| Layer | Choice | Why |
|---|---|---|
| **Memory** | Supermemory (self-hosted) | Local ONNX embeddings, hybrid search, encrypted on-device |
| **Orchestration** | LangGraph | An explicit graph with conditional routing and a real veto edge |
| **Reasoning** | Groq · `llama-3.1-8b-instant` | A full six-agent cycle completes in **~3 seconds** |
| **Market data** | ccxt → Binance | Live 24/7 candles + ticker |
| **Ledger** | SQLModel + SQLite | Exact accounting: trades, positions, equity, provenance edges |
| **API** | FastAPI | Typed contracts, ~20 endpoints |
| **Frontend** | React 19 · TypeScript · Vite · Tailwind v4 | Dark/light, fully responsive |
| **Charts / graph** | lightweight-charts · React Flow | Real candlesticks; an interactive provenance graph |
| **Tests** | pytest — **145 tests** | Agents, engine, memory and API all covered |

### System analysis

- **Two stores, two jobs, on purpose.** SQLite answers *exactly* ("what is my P&L?"). Supermemory
  answers *approximately* ("what have I learned about volatile markets?"). Neither can do the
  other's job. A single column — `lesson_memory_id` — bridges them and makes the whole provenance
  graph joinable.
- **Idempotent by construction.** `Reflection.trade_id` is `UNIQUE`, so a trade can never be
  reflected on twice — enforced in the query *and* at the database level. Consolidation is
  idempotent via its source-set hash.
- **Degrades honestly.** No network? The chart serves its last-good snapshot and *says* it's cached.
  An LLM fails to return valid JSON after retries? A clean `502` with a readable message, not a
  stack trace. It never quietly presents a stale number as if it were live.
- **Latency:** a full six-agent cycle ≈ **3s**; reflection ≈ **1.5s per trade**.
- **Known limits, stated plainly:** long-only (no shorting); fills modelled as `close ± 5bps` with
  no order book; paper trading only.

### Applications beyond trading

The loop — *act → diagnose the real outcome → distil a transferable lesson → retrieve it into the
next decision* — is domain-agnostic. Swap the tape and the agents, keep the memory architecture: a
support agent that learns which resolutions actually stuck; an SRE agent that remembers which
mitigations really fixed the incident; a research agent that stops re-running the experiment it
already disproved. **Any agent with a measurable outcome can run this loop.**

---

## 5. Reproducibility

**Prerequisites:** Python 3.11+, Node 20+, a free [Groq](https://console.groq.com) API key, and the
Supermemory self-hosted server binary.

```bash
git clone https://github.com/Vidit-lab/HFT-Agent-Team.git && cd HFT-Agent-Team

# 1. Python
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Config — add GROQ_API_KEY and SUPERMEMORY_API_KEY
cp .env.example .env

# 3. Memory server   (terminal 1) — prints its API key on first boot
bash scripts/run_memory_server.sh

# 4. API             (terminal 2)
uvicorn api.main:app --port 8000

# 5. Frontend        (terminal 3)
cd frontend && npm install && npm run dev      # → http://localhost:5173
```

**Then, in the UI — the whole thesis in four clicks:**

1. **Live Orchestration** → pick a market → **Run new cycle**. Watch six agents reason in sequence.
2. **Memory Explorer** → **Reflect** the trade. A lesson appears, and the provenance graph grows an edge.
3. Reflect a few more until a `(regime, outcome)` bucket hits its threshold → **Consolidate** → a
   meta-lesson forms from them, and the graph grows another layer.
4. **Ask the memory** in plain English and watch semantic recall surface what matters.

```bash
pytest        # 145 tests
```

### Deploy — one process, one port

`api/main.py` mounts the built SPA at `/`, so the API and the UI share an origin and there is
exactly one service to ship:

```bash
bash scripts/serve.sh        # builds the frontend, serves everything on :8000
```

Point `SUPERMEMORY_BASE_URL` at your memory server, set `PORT`, and it runs anywhere that runs a
Python process — Fly, Railway, Render, or a bare VM.

---

## License

[MIT](LICENSE) © 2026 Vidit Shrimali

<div align="center">

**Built with ❤️ by Vidit**

*Most trading agents are goldfish. This one keeps a diary.*

</div>
