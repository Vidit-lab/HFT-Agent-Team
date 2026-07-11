"""Phase 4's whole spine: decide -> act -> remember, in one function.

query memory -> agent decides -> sim/engine executes -> ledger persists ->
outcome written back to memory. This is deliberately the only place that
touches agents/, sim/, and memory/ all at once -- everything upstream of
this file is a clean, independently-testable layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from agents.schemas import Action, TradeDecision
from agents.trader import decide as agent_decide
from memory.client import SupermemoryClient
from memory.schemas import Outcome as MemoryOutcome
from memory.schemas import Side as MemorySide
from memory.schemas import TradeMemory
from sim.data_loader import load_ohlcv
from sim.engine import BacktestEngine
from sim.models import AgentDecisionLog, Portfolio, Position, Side as SimSide, Signal, Trade

DEFAULT_RUN_ID = "paper-agent-v1"
DEFAULT_LOOKBACK_DAYS = 180


@dataclass
class CycleResult:
    run_id: str
    symbol: str
    decision: TradeDecision
    trade: Trade | None
    snapshot: Portfolio
    memories_considered: int
    memory_write_id: str | None
    decision_log_id: int | None


def run_cycle(
    session: Session,
    memory_client: SupermemoryClient,
    *,
    symbol: str = "AAPL",
    run_id: str = DEFAULT_RUN_ID,
    initial_cash: float = 100_000.0,
    as_of: str | None = None,
    llm_client=None,
) -> CycleResult:
    end = as_of or datetime.now(timezone.utc).date().isoformat()
    start = (datetime.fromisoformat(end) - timedelta(days=DEFAULT_LOOKBACK_DAYS)).date().isoformat()
    bars = load_ohlcv(symbol, start, end)
    if bars.empty:
        raise ValueError(f"no market data for {symbol} between {start} and {end}")

    existing_position = session.exec(
        select(Position).where(Position.run_id == run_id, Position.symbol == symbol)
    ).first()
    current_size = existing_position.size if existing_position else 0.0

    retrieved = memory_client.query_similar(f"lessons and past trades for {symbol}", limit=5)

    decision, system_prompt, user_prompt = agent_decide(
        symbol, bars, retrieved.results, current_position_size=current_size, client=llm_client
    )

    engine = BacktestEngine.resume_or_create(session, run_id=run_id, strategy="agent_v1", initial_cash=initial_cash)
    current_bar = bars.iloc[-1]

    signal = None
    if decision.action == Action.BUY and decision.size > 0:
        signal = Signal(timestamp=current_bar.timestamp, symbol=symbol, side=SimSide.BUY, size=decision.size)
    elif decision.action == Action.SELL and decision.size > 0:
        signal = Signal(timestamp=current_bar.timestamp, symbol=symbol, side=SimSide.SELL, size=decision.size)

    trade, snapshot = engine.step(current_bar.timestamp, symbol, current_bar.close, signal)
    engine.persist(session)

    log = AgentDecisionLog(
        run_id=run_id,
        timestamp=current_bar.timestamp,
        symbol=symbol,
        action=decision.action.value,
        trade_id=trade.id if trade else None,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        raw_decision_json=decision.model_dump_json(),
        retrieved_memory_ids=json.dumps([r.id for r in retrieved.results]),
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    memory_write_id = None
    if trade is not None:
        memory_outcome = MemoryOutcome.NEUTRAL
        if trade.realized_pnl is not None:
            memory_outcome = MemoryOutcome.WIN if trade.realized_pnl > 0 else MemoryOutcome.LOSS

        memory_write_id = memory_client.write_trade_memory(
            TradeMemory(
                trade_id=str(trade.id),
                timestamp=trade.timestamp,
                symbol=symbol,
                side=MemorySide.BUY if trade.side == SimSide.BUY else MemorySide.SELL,
                size=trade.size,
                price=trade.price,
                strategy="agent_v1",
                regime="unclassified",  # regime classification arrives in Phase 5's Market Analyst
                outcome=memory_outcome,
                pnl=trade.realized_pnl or 0.0,
                rationale=decision.rationale,
            )
        )

    return CycleResult(
        run_id=run_id,
        symbol=symbol,
        decision=decision,
        trade=trade,
        snapshot=snapshot,
        memories_considered=len(retrieved.results),
        memory_write_id=memory_write_id,
        decision_log_id=log.id,
    )
