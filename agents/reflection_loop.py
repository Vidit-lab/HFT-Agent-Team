"""Phase 6: the batch process that drives agents/reflection.py across
whatever trades are eligible. Deliberately separate from run_cycle -- this
is retrospective analysis of past trades, not part of any single cycle's
decision, and is meant to be triggered on its own cadence (on-demand via
POST /api/reflect for now; a scheduler takes over once one exists).

A trade is eligible once its outcome is knowable and it hasn't been
reflected on yet: closed (realized_pnl is not None), or opened at least
`lookback_days` ago so a forward return can stand in for a still-open
position. Idempotency comes for free from the Reflection table itself --
"already reflected" is just "a Reflection row exists for this trade_id."
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from agents.reflection import compute_outcome, reflect
from memory.client import SupermemoryClient
from memory.schemas import LessonMemory
from sim.data_loader import load_ohlcv
from sim.market_data import get_bars, is_crypto
from sim.models import AgentDecisionLog, Reflection, Trade

DEFAULT_MAX_TRADES = 10
# Days a still-open trade must age before its forward return is judged. On 1h
# crypto bars a position matures in hours, not days, so callers routinely pass a
# fraction (0.1667 == 4h) -- hence float, not int.
DEFAULT_LOOKBACK_DAYS = 5.0
_PRICE_LOOKUP_BUFFER_DAYS = 10


@dataclass
class ReflectionResult:
    trade_id: int
    symbol: str
    outcome: str
    return_pct: float
    diagnosis: str
    lesson_text: str
    lesson_memory_id: str
    confidence: float


def _find_eligible_trades(
    session: Session, *, run_id: str | None, max_trades: int, lookback_days: float, as_of_date: datetime
) -> list[Trade]:
    already_reflected = select(Reflection.trade_id)
    query = select(Trade).where(Trade.id.not_in(already_reflected))
    if run_id is not None:
        query = query.where(Trade.run_id == run_id)
    query = query.order_by(Trade.timestamp)

    cutoff = as_of_date - timedelta(days=lookback_days)
    eligible = [
        trade
        for trade in session.exec(query).all()
        if trade.realized_pnl is not None or trade.timestamp <= cutoff
    ]
    return eligible[:max_trades]


def _latest_close(symbol: str, as_of: str) -> float:
    """The price a still-open trade is marked against.

    The two asset classes want genuinely different things here, so they fork:

    * **Crypto** -- the latest live bar. `as_of` is meaningless on a 24/7 feed we
      always fetch right up to now, and "the price this instant" is exactly the
      forward return we want to diagnose.
    * **Equity** -- the last bar at or before `as_of`, so a backdated reflect run
      is still judged against the price as it actually stood on that date rather
      than against today's.
    """
    if is_crypto(symbol):
        bars = get_bars(symbol, limit=2)
    else:
        start = (datetime.fromisoformat(as_of) - timedelta(days=_PRICE_LOOKUP_BUFFER_DAYS)).date().isoformat()
        bars = load_ohlcv(symbol, start, as_of)

    if bars.empty:
        raise ValueError(f"no market data for {symbol} to evaluate a still-open trade as of {as_of}")
    return float(bars.iloc[-1].close)


def run_reflection_batch(
    session: Session,
    memory_client: SupermemoryClient,
    *,
    run_id: str | None = None,
    max_trades: int = DEFAULT_MAX_TRADES,
    lookback_days: float = DEFAULT_LOOKBACK_DAYS,
    as_of: str | None = None,
    llm_client=None,
) -> list[ReflectionResult]:
    as_of = as_of or datetime.now(timezone.utc).date().isoformat()
    as_of_date = datetime.fromisoformat(as_of)

    eligible = _find_eligible_trades(
        session, run_id=run_id, max_trades=max_trades, lookback_days=lookback_days, as_of_date=as_of_date
    )

    results: list[ReflectionResult] = []
    price_cache: dict[str, float] = {}

    for trade in eligible:
        current_price = None
        if trade.realized_pnl is None:
            if trade.symbol not in price_cache:
                price_cache[trade.symbol] = _latest_close(trade.symbol, as_of)
            current_price = price_cache[trade.symbol]

        outcome, return_pct = compute_outcome(trade, current_price)

        log = session.exec(select(AgentDecisionLog).where(AgentDecisionLog.trade_id == trade.id)).first()
        reasoning_trail = json.loads(log.reasoning_trail_json) if log else []

        reflection, _, _ = reflect(trade, reasoning_trail, outcome, return_pct, client=llm_client)

        lesson_memory_id = memory_client.write_lesson(
            LessonMemory(
                strategy=trade.strategy,
                regime=trade.regime_at_entry or "unclassified",
                lesson_text=reflection.lesson_text,
                asset=trade.symbol,
                outcome=outcome,
                source_trade_id=str(trade.id),
            )
        )

        session.add(
            Reflection(
                trade_id=trade.id,
                run_id=trade.run_id,
                created_at=datetime.now(timezone.utc),
                outcome=outcome.value,
                return_pct=return_pct,
                diagnosis=reflection.diagnosis,
                lesson_text=reflection.lesson_text,
                lesson_memory_id=lesson_memory_id,
                confidence=reflection.confidence,
            )
        )
        session.commit()

        results.append(
            ReflectionResult(
                trade_id=trade.id,
                symbol=trade.symbol,
                outcome=outcome.value,
                return_pct=return_pct,
                diagnosis=reflection.diagnosis,
                lesson_text=reflection.lesson_text,
                lesson_memory_id=lesson_memory_id,
                confidence=reflection.confidence,
            )
        )

    return results
