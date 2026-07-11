"""Integration tests for the Phase 5 LangGraph wiring itself -- fan-out to
Bull/Bear, fan-in at Risk Manager, and the conditional veto branch. Uses
DispatchFakeClient (routes by system-prompt substring, not call order)
because LangGraph's parallel superstep doesn't guarantee Bull runs before
Bear or vice versa -- a plain response queue would be flaky here.
"""

from __future__ import annotations

from agents.graph import build_graph
from agents.schemas import Action

from .conftest import FakeMemoryClient, make_bars, make_memory

_MARKET_ANALYST = "market regime classification analyst"
_BULL = "Bull Researcher"
_BEAR = "Bear Researcher"
_RISK_MANAGER = "Risk Manager for a paper-trading"
_TRADER = "Trader for a paper-trading"
_PORTFOLIO_MANAGER = "Portfolio Manager for a paper-trading"


def _initial_state() -> dict:
    return {
        "symbol": "AAPL",
        "bars": make_bars(n=30),
        "current_position_size": 0.0,
        "current_price": 100.0,
        "cash": 100_000.0,
        "equity": 100_000.0,
        "reasoning_trail": [],
    }


def test_graph_approved_path_runs_all_six_nodes(dispatch_fake_client):
    client = (
        dispatch_fake_client()
        .when(_MARKET_ANALYST, '{"regime": "trending_up", "summary": "steady climb", "confidence": 0.8}')
        .when(_BULL, '{"stance": "bull", "thesis": "momentum favors longs", "confidence": 0.7}')
        .when(_BEAR, '{"stance": "bear", "thesis": "stretched valuation", "confidence": 0.3}')
        .when(_RISK_MANAGER, '{"approved": true, "max_position_size": 10.0, "reasoning": "clear edge"}')
        .when(_TRADER, '{"action": "buy", "size": 5.0, "rationale": "bull case wins", "confidence": 0.6}')
        .when(_PORTFOLIO_MANAGER, '{"action": "buy", "size": 3.0, "rationale": "shrunk for prudence", "confidence": 0.6}')
    )
    memory_client = FakeMemoryClient(results_by_call=[[make_memory("win", type="trade")], [make_memory("loss", type="trade")]])

    graph = build_graph(memory_client, client)
    final_state = graph.invoke(_initial_state())

    assert final_state["market_analysis"].regime.value == "trending_up"
    assert final_state["bull_thesis"].stance.value == "bull"
    assert final_state["bear_thesis"].stance.value == "bear"
    assert final_state["risk_decision"].approved is True
    assert final_state["trade_decision"].action == Action.BUY
    assert final_state["trade_decision"].size == 3.0  # Portfolio Manager's final say, not the Trader's

    node_names = {entry["node"] for entry in final_state["reasoning_trail"]}
    assert node_names == {"market_analyst", "researcher_bull", "researcher_bear", "risk_manager", "trader", "portfolio_manager"}
    assert len(client.calls) == 6


def test_graph_veto_path_short_circuits_to_hold(dispatch_fake_client):
    """No `.when(_TRADER, ...)` or `.when(_PORTFOLIO_MANAGER, ...)` rule is
    registered -- if either were ever invoked, DispatchFakeClient would raise,
    so a passing test is itself proof the veto skipped them."""
    client = (
        dispatch_fake_client()
        .when(_MARKET_ANALYST, '{"regime": "high_volatility", "summary": "chaotic tape", "confidence": 0.6}')
        .when(_BULL, '{"stance": "bull", "thesis": "weak case", "confidence": 0.2}')
        .when(_BEAR, '{"stance": "bear", "thesis": "weak case", "confidence": 0.2}')
        .when(_RISK_MANAGER, '{"approved": false, "max_position_size": 0.0, "reasoning": "no clear edge"}')
    )
    memory_client = FakeMemoryClient(results_by_call=[[], []])

    graph = build_graph(memory_client, client)
    final_state = graph.invoke(_initial_state())

    assert final_state["trade_decision"].action == Action.HOLD
    assert final_state["trade_decision"].size == 0.0
    assert "no clear edge" in final_state["trade_decision"].rationale

    node_names = {entry["node"] for entry in final_state["reasoning_trail"]}
    assert node_names == {"market_analyst", "researcher_bull", "researcher_bear", "risk_manager", "hold"}
    assert len(client.calls) == 4  # market_analyst, bull, bear, risk_manager -- never trader/portfolio_manager


def test_graph_pass_through_hold_when_trader_holds(dispatch_fake_client):
    """Risk Manager approves, but the Trader itself decides to hold --
    Portfolio Manager should pass it through without its own LLM call."""
    client = (
        dispatch_fake_client()
        .when(_MARKET_ANALYST, '{"regime": "range_bound", "summary": "chop", "confidence": 0.5}')
        .when(_BULL, '{"stance": "bull", "thesis": "mixed signals", "confidence": 0.4}')
        .when(_BEAR, '{"stance": "bear", "thesis": "mixed signals", "confidence": 0.4}')
        .when(_RISK_MANAGER, '{"approved": true, "max_position_size": 10.0, "reasoning": "modest allowance"}')
        .when(_TRADER, '{"action": "hold", "size": 0, "rationale": "no edge either way", "confidence": 0.5}')
    )
    memory_client = FakeMemoryClient(results_by_call=[[], []])

    graph = build_graph(memory_client, client)
    final_state = graph.invoke(_initial_state())

    assert final_state["trade_decision"].action == Action.HOLD
    assert len(client.calls) == 5  # portfolio_manager never called for a hold pass-through
