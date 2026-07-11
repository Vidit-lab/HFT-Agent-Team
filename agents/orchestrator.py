"""Phase 5's spine: retrieve -> multi-agent graph -> execute -> persist ->
remember. Replaces Phase 4's single-agent `agent_decide` call with the
LangGraph-based agent graph (agents/graph.py): Market Analyst -> parallel
Bull/Bear -> Risk Manager (approve/veto) -> Trader -> Portfolio Manager.

This remains the only place that touches agents/, sim/, and memory/ all at
once -- every node upstream of this file is a clean, independently
testable function, and every write to Supermemory (regime snapshot, trade
outcome) happens here, after the graph has produced a final decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from agents.graph import build_graph
from agents.schemas import Action, MarketAnalysis, TradeDecision
from memory.client import SupermemoryClient
from memory.schemas import Outcome as MemoryOutcome
from memory.schemas import RegimeSnapshotMemory
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
    market_analysis: MarketAnalysis
    trade: Trade | None
    snapshot: Portfolio
    memories_considered: int
    memory_write_id: str | None
    decision_log_id: int | None
    reasoning_trail: list[dict]


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

    latest_snapshot = session.exec(
        select(Portfolio).where(Portfolio.run_id == run_id).order_by(Portfolio.timestamp.desc()).limit(1)
    ).first()
    cash = latest_snapshot.cash if latest_snapshot else initial_cash
    equity = latest_snapshot.equity if latest_snapshot else initial_cash

    current_bar = bars.iloc[-1]

    graph = build_graph(memory_client, llm_client)
    final_state = graph.invoke(
        {
            "symbol": symbol,
            "bars": bars,
            "current_position_size": current_size,
            "current_price": current_bar.close,
            "cash": cash,
            "equity": equity,
            "reasoning_trail": [],
        }
    )

    decision: TradeDecision = final_state["trade_decision"]
    market_analysis: MarketAnalysis = final_state["market_analysis"]
    reasoning_trail: list[dict] = final_state["reasoning_trail"]

    engine = BacktestEngine.resume_or_create(session, run_id=run_id, strategy="agent_graph_v1", initial_cash=initial_cash)

    signal = None
    if decision.action == Action.BUY and decision.size > 0:
        signal = Signal(timestamp=current_bar.timestamp, symbol=symbol, side=SimSide.BUY, size=decision.size)
    elif decision.action == Action.SELL and decision.size > 0:
        signal = Signal(timestamp=current_bar.timestamp, symbol=symbol, side=SimSide.SELL, size=decision.size)

    trade, snapshot = engine.step(current_bar.timestamp, symbol, current_bar.close, signal)
    if trade is not None:
        trade.regime_at_entry = market_analysis.regime.value
        trade.rationale_summary = decision.rationale
    engine.persist(session)

    memory_ids = sorted({mid for entry in reasoning_trail for mid in entry["retrieved_memory_ids"]})
    log = AgentDecisionLog(
        run_id=run_id,
        timestamp=current_bar.timestamp,
        symbol=symbol,
        action=decision.action.value,
        regime=market_analysis.regime.value,
        trade_id=trade.id if trade else None,
        raw_decision_json=decision.model_dump_json(),
        reasoning_trail_json=json.dumps(reasoning_trail),
        retrieved_memory_ids=json.dumps(memory_ids),
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    memory_client.write_regime_snapshot(
        RegimeSnapshotMemory(
            timestamp=current_bar.timestamp,
            regime=market_analysis.regime.value,
            asset=symbol,
            summary=market_analysis.summary,
        )
    )

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
                strategy="agent_graph_v1",
                regime=market_analysis.regime.value,
                outcome=memory_outcome,
                pnl=trade.realized_pnl or 0.0,
                rationale=decision.rationale,
            )
        )

    return CycleResult(
        run_id=run_id,
        symbol=symbol,
        decision=decision,
        market_analysis=market_analysis,
        trade=trade,
        snapshot=snapshot,
        memories_considered=len(memory_ids),
        memory_write_id=memory_write_id,
        decision_log_id=log.id,
        reasoning_trail=reasoning_trail,
    )
