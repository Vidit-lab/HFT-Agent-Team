"""Demo mode: seed a realistic backlog so Reflect and Consolidate are eligible
*now* instead of in five days.

The honest framing, which the UI repeats verbatim to anyone watching: the only
thing faked here is the **trade history**. Everything downstream of it is the
real system -- the real Reflection Agent making real LLM calls, real lessons
written to Supermemory, the real Consolidation Agent distilling them, and real
provenance edges. We are not replaying a recording.

Why seeded trades are instantly eligible, with no waiting and no network:

  * `_find_eligible_trades` treats `realized_pnl is not None` as "outcome known",
    so a closed trade skips the lookback wait entirely.
  * `compute_outcome` then reads that P&L directly and never calls `_latest_close`,
    so reflection needs no market data at all -- it works offline.

Everything lives under `run_id="demo"` and is removed by POST /reset, so the real
paper-trading run's ledger, equity and lessons are never touched.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from api.deps import get_memory_client, get_session
from api.schemas import DemoSeedOut, DemoStatusOut
from memory.client import SupermemoryClient
from sim.market_data import get_bars
from sim.models import AgentDecisionLog, Consolidation, Reflection, Side, Trade

router = APIRouter(prefix="/api/demo", tags=["demo"])

DEMO_RUN_ID = "demo"
DEMO_SYMBOL = "BTC/USDT"
DEMO_STRATEGY = "agent_graph_v1"

# Six trades, hand-tuned so the (regime, outcome) buckets land exactly where we
# want them after reflection:
#
#   trending_up     / win   x2  -> READY to consolidate (>= the min-2 threshold)
#   high_volatility / loss  x2  -> READY to consolidate
#   trending_up     / loss  x1  -> stays waiting
#   range_bound     / neutral x1 -> stays waiting
#
# The two that stay waiting are deliberate. They prove the threshold is a real
# gate rather than theatre -- a judge can see that not everything is always ready.
#
# `return_pct` drives the outcome via compute_outcome's +/-0.5% noise threshold;
# realized_pnl is derived from it against the real bar price at seed time.
_SEED = [
    {
        "bars_ago": 96,
        "regime": "trending_up",
        "return_pct": 3.1,
        "size": 0.42,
        "rationale": "Bull thesis carried the debate: eight consecutive higher lows and expanding volume. Risk approved full size.",
        "trail": [
            ("market_analyst", "Sustained higher highs and higher lows across the window with volume confirmation. Regime: trending_up (confidence 0.78)."),
            ("researcher_bull", "Momentum is intact and pullbacks are being bought within the hour. This is a continuation setup, not exhaustion."),
            ("researcher_bear", "The move is extended and RSI is elevated; a mean-reversion snap is possible. But I concede the trend structure is unbroken."),
            ("risk_manager", "Volatility is moderate and the position sits inside the concentration cap. APPROVED, max size 0.50."),
            ("trader", "BUY 0.42 -- trend continuation with risk-approved sizing."),
            ("portfolio_manager", "Confirmed. Size is within 25% of equity; no adjustment needed."),
        ],
    },
    {
        "bars_ago": 78,
        "regime": "trending_up",
        "return_pct": 2.2,
        "size": 0.38,
        "rationale": "Trend still intact after a shallow pullback; added on the retest of the prior breakout level.",
        "trail": [
            ("market_analyst", "Pullback held above the breakout level and the uptrend resumed. Regime: trending_up (confidence 0.71)."),
            ("researcher_bull", "The retest held. Buying the first pullback in an established trend is the highest-quality entry available."),
            ("researcher_bear", "Volume is thinner on this leg than the last. Not a reason to be short, but a reason to size down."),
            ("risk_manager", "Bear's volume concern is fair; trimming max size to 0.40. APPROVED."),
            ("trader", "BUY 0.38 -- pullback entry, trimmed for the volume divergence."),
            ("portfolio_manager", "Confirmed at 0.38."),
        ],
    },
    {
        "bars_ago": 60,
        "regime": "high_volatility",
        "return_pct": -2.8,
        "size": 0.30,
        "rationale": "Bought a sharp dip expecting a bounce; volatility kept expanding and the position went against us.",
        "trail": [
            ("market_analyst", "Realized volatility has doubled versus the prior window with no clear direction. Regime: high_volatility (confidence 0.83)."),
            ("researcher_bull", "This is capitulation. Sharp flushes in a structurally intact market are where the best entries are made."),
            ("researcher_bear", "Volatility expansion without direction is not an entry signal, it is a warning. Standing aside is a position."),
            ("risk_manager", "High volatility regime -- halving the envelope. APPROVED, max size 0.30."),
            ("trader", "BUY 0.30 -- dip-buy at the reduced envelope."),
            ("portfolio_manager", "Confirmed, though I note the Bear was not answered on the direction question."),
        ],
    },
    {
        "bars_ago": 44,
        "regime": "high_volatility",
        "return_pct": -1.9,
        "size": 0.25,
        "rationale": "Second dip-buy into an unresolved volatility regime; the range kept widening.",
        "trail": [
            ("market_analyst", "Volatility remains elevated and price is whipsawing without trend. Regime: high_volatility (confidence 0.80)."),
            ("researcher_bull", "The prior flush found buyers. A second test on lower volume is a higher-probability long."),
            ("researcher_bear", "We are catching a falling knife twice. Nothing has changed structurally since the last loss."),
            ("risk_manager", "Consecutive drawdown in this regime -- cutting the envelope again. APPROVED, max size 0.25."),
            ("trader", "BUY 0.25 -- reduced size on the second test."),
            ("portfolio_manager", "Confirmed at 0.25."),
        ],
    },
    {
        "bars_ago": 30,
        "regime": "trending_up",
        "return_pct": -1.4,
        "size": 0.20,
        "rationale": "Chased a late-stage breakout; entered near the top of the move and it faded.",
        "trail": [
            ("market_analyst", "Trend is still up but decelerating -- the last three bars have narrowing ranges. Regime: trending_up (confidence 0.62)."),
            ("researcher_bull", "Breakouts are meant to be bought. New highs beget new highs."),
            ("researcher_bear", "Decelerating momentum into a new high is distribution, not continuation. This is a late entry."),
            ("risk_manager", "Confidence is only 0.62 -- reducing the envelope accordingly. APPROVED, max size 0.20."),
            ("trader", "BUY 0.20 -- breakout continuation at reduced size."),
            ("portfolio_manager", "Confirmed at 0.20, with reservations about the entry location."),
        ],
    },
    {
        "bars_ago": 14,
        "regime": "range_bound",
        "return_pct": 0.2,
        "size": 0.15,
        "rationale": "Small probe inside an established range; price went nowhere and the trade was flat.",
        "trail": [
            ("market_analyst", "Price is oscillating between well-defined bounds with no directional bias. Regime: range_bound (confidence 0.74)."),
            ("researcher_bull", "We are near the lower bound of the range -- a mean-reversion long back toward the midpoint."),
            ("researcher_bear", "Ranges are where edges go to die. Fees and slippage will eat any small move."),
            ("risk_manager", "Low conviction on both sides -- minimum envelope only. APPROVED, max size 0.15."),
            ("trader", "BUY 0.15 -- small mean-reversion probe."),
            ("portfolio_manager", "Confirmed at 0.15."),
        ],
    },
]


def _demo_trade_ids(session: Session) -> list[int]:
    return [t.id for t in session.exec(select(Trade).where(Trade.run_id == DEMO_RUN_ID)).all()]


@router.get("/status", response_model=DemoStatusOut)
def demo_status(session: Session = Depends(get_session)):
    trade_ids = _demo_trade_ids(session)
    reflections = session.exec(select(Reflection).where(Reflection.run_id == DEMO_RUN_ID)).all()
    metas = _demo_consolidations(session, {r.lesson_memory_id for r in reflections})
    return DemoStatusOut(
        seeded=bool(trade_ids),
        run_id=DEMO_RUN_ID,
        symbol=DEMO_SYMBOL,
        trades=len(trade_ids),
        reflections=len(reflections),
        consolidations=len(metas),
    )


@router.post("/seed", response_model=DemoSeedOut)
def seed_demo(session: Session = Depends(get_session)):
    """Idempotent: re-seeding an already-seeded demo is a no-op."""
    if _demo_trade_ids(session):
        status = demo_status(session)
        return DemoSeedOut(seeded=0, already_seeded=True, run_id=DEMO_RUN_ID, symbol=DEMO_SYMBOL, trades=status.trades)

    # Price the fills off real candles so the markers land on the actual chart
    # and the P&L is plausible rather than invented.
    bars = get_bars(DEMO_SYMBOL, timeframe="1h", limit=200)

    count = 0
    for spec in _SEED:
        bar = bars.iloc[-int(spec["bars_ago"])]
        price = float(bar.close)
        size = float(spec["size"])
        notional = price * size
        # compute_outcome derives return_pct back out of exactly this.
        realized_pnl = notional * float(spec["return_pct"]) / 100.0

        trade = Trade(
            run_id=DEMO_RUN_ID,
            timestamp=bar.timestamp.to_pydatetime(),
            symbol=DEMO_SYMBOL,
            side=Side.BUY,
            size=size,
            price=price,
            fee=notional * 10.0 / 10_000,
            slippage_cost=notional * 5.0 / 10_000,
            strategy=DEMO_STRATEGY,
            realized_pnl=realized_pnl,
            regime_at_entry=spec["regime"],
            rationale_summary=spec["rationale"],
        )
        session.add(trade)
        session.commit()
        session.refresh(trade)

        # Without a reasoning trail the reflection prompt degrades to "No
        # reasoning trail available" and the agent can only diagnose the number,
        # not the argument that produced it. The trail IS the thing being learned from.
        session.add(
            AgentDecisionLog(
                run_id=DEMO_RUN_ID,
                timestamp=bar.timestamp.to_pydatetime(),
                symbol=DEMO_SYMBOL,
                action="buy",
                regime=spec["regime"],
                trade_id=trade.id,
                raw_decision_json=json.dumps(
                    {"action": "buy", "size": size, "rationale": spec["rationale"], "confidence": 0.7}
                ),
                reasoning_trail_json=json.dumps(
                    [{"node": node, "raw_output": out, "retrieved_memory_ids": []} for node, out in spec["trail"]]
                ),
                retrieved_memory_ids=json.dumps([]),
            )
        )
        session.commit()
        count += 1

    return DemoSeedOut(seeded=count, already_seeded=False, run_id=DEMO_RUN_ID, symbol=DEMO_SYMBOL, trades=count)


def _sources(consolidation: Consolidation) -> set[str]:
    try:
        return set(json.loads(consolidation.source_memory_ids))
    except Exception:
        return set()


def _demo_consolidations(session: Session, lesson_ids: set[str]) -> list[Consolidation]:
    """Every meta-lesson produced from a bucket that contained a demo lesson.

    Matching row-by-row on `source_memory_ids` is not enough. One consolidation
    run distils a whole (regime, outcome) bucket into *several* meta-lessons, and
    a bucket can mix demo lessons with legacy ones -- so a meta-lesson can be
    drawn purely from the legacy sources and still be an artefact of the demo run.
    Deleting only the rows that cite a demo lesson would strand its siblings.

    All the meta-lessons from one bucket share a `group_signature` (it hashes the
    bucket's full membership, not the per-meta subset), so contamination is
    decided per *signature*: if any row under it cites a demo lesson, the whole
    bucket was a demo artefact and every row under it goes.

    Matching on the `scope` label instead would be unreliable -- the frontend
    Consolidate button sets its own scope.
    """
    rows = session.exec(select(Consolidation)).all()
    tainted = {c.group_signature for c in rows if _sources(c) & lesson_ids}
    return [c for c in rows if c.group_signature in tainted]


@router.post("/reset", response_model=DemoStatusOut)
def reset_demo(
    session: Session = Depends(get_session),
    memory_client: SupermemoryClient = Depends(get_memory_client),
):
    """Remove everything the demo created, in both stores.

    Order matters: the Supermemory document ids live *only* in the SQLite rows,
    so deleting SQL first would orphan the documents with no way to find them
    again. Docs first, rows second.
    """
    reflections = session.exec(select(Reflection).where(Reflection.run_id == DEMO_RUN_ID)).all()
    lesson_ids = {r.lesson_memory_id for r in reflections if r.lesson_memory_id}
    metas = _demo_consolidations(session, lesson_ids)

    for doc_id in lesson_ids | {c.consolidated_memory_id for c in metas if c.consolidated_memory_id}:
        memory_client.delete_document(doc_id)

    for consolidation in metas:
        session.delete(consolidation)
    for reflection in reflections:
        session.delete(reflection)
    for log in session.exec(select(AgentDecisionLog).where(AgentDecisionLog.run_id == DEMO_RUN_ID)).all():
        session.delete(log)
    for trade in session.exec(select(Trade).where(Trade.run_id == DEMO_RUN_ID)).all():
        session.delete(trade)
    session.commit()

    return DemoStatusOut(
        seeded=False, run_id=DEMO_RUN_ID, symbol=DEMO_SYMBOL, trades=0, reflections=0, consolidations=0
    )
