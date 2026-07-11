"""Phase 5 orchestration graph, built with LangGraph.

    START -> market_analyst -> {bull, bear} (parallel fan-out)
                                    |    |
                                    v    v
                                 risk_manager (fan-in)
                                 /              \\
                          [approved]        [vetoed]
                                /                  \\
                            trader                 hold
                                |                     |
                        portfolio_manager             |
                                \\_____________________/
                                          v
                                        END

Deliberately data-source-agnostic: every node reads `bars` as a plain OHLCV
DataFrame and never touches yfinance/ccxt/anything data-specific directly --
that lives in the orchestrator, one layer up. Memory *retrieval* happens
inside the Bull/Bear node wrappers (each researcher needs its own biased
query before it can prompt); memory *writes* stay centralized in the
orchestrator, after the graph finishes, matching Phase 4's pattern of
keeping side effects in one place.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from agents import market_analyst, portfolio_manager, researcher, risk_manager, trader
from agents.llm import DEFAULT_MODEL, get_client
from agents.schemas import Action, RiskDecision, Stance, TradeDecision
from agents.state import AgentState, NodeTrace
from memory.client import SupermemoryClient


def _trace(node: str, system_prompt: str, user_prompt: str, raw_output: str, memory_ids: list[str] | None = None) -> NodeTrace:
    return {
        "node": node,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_output": raw_output,
        "retrieved_memory_ids": memory_ids or [],
    }


def _market_analyst_node(client: OpenAI, model: str):
    def node(state: AgentState) -> dict:
        analysis, sp, up = market_analyst.classify(state["symbol"], state["bars"], client=client, model=model)
        return {
            "market_analysis": analysis,
            "reasoning_trail": [_trace("market_analyst", sp, up, analysis.model_dump_json())],
        }

    return node


def _researcher_node(stance: Stance, memory_client: SupermemoryClient, client: OpenAI, model: str):
    state_key = "bull_thesis" if stance == Stance.BULL else "bear_thesis"

    def node(state: AgentState) -> dict:
        retrieval = researcher.retrieve_memories(memory_client, state["symbol"], stance)
        thesis, sp, up = researcher.research(
            state["symbol"],
            state["bars"],
            state["market_analysis"],
            retrieval.results,
            stance,
            client=client,
            model=model,
        )
        memory_ids = [r.id for r in retrieval.results]
        return {
            state_key: thesis,
            "reasoning_trail": [_trace(f"researcher_{stance.value}", sp, up, thesis.model_dump_json(), memory_ids)],
        }

    return node


def _risk_manager_node(client: OpenAI, model: str):
    def node(state: AgentState) -> dict:
        decision, sp, up = risk_manager.assess(
            state["symbol"],
            state["market_analysis"],
            state["bull_thesis"],
            state["bear_thesis"],
            state["current_position_size"],
            state["equity"],
            client=client,
            model=model,
        )
        return {
            "risk_decision": decision,
            "reasoning_trail": [_trace("risk_manager", sp, up, decision.model_dump_json())],
        }

    return node


def _route_after_risk(state: AgentState) -> str:
    decision: RiskDecision = state["risk_decision"]
    return "trader" if decision.approved else "hold"


def _trader_node(client: OpenAI, model: str):
    def node(state: AgentState) -> dict:
        decision, sp, up = trader.decide(
            state["symbol"],
            state["bars"],
            state["market_analysis"],
            state["bull_thesis"],
            state["bear_thesis"],
            state["risk_decision"],
            current_position_size=state["current_position_size"],
            client=client,
            model=model,
        )
        return {
            "trade_decision": decision,
            "reasoning_trail": [_trace("trader", sp, up, decision.model_dump_json())],
        }

    return node


def _portfolio_manager_node(client: OpenAI, model: str):
    def node(state: AgentState) -> dict:
        final, sp, up = portfolio_manager.finalize(
            state["symbol"],
            state["trade_decision"],
            state["current_position_size"],
            state["current_price"],
            state["cash"],
            state["equity"],
            client=client,
            model=model,
        )
        return {
            "trade_decision": final,
            "reasoning_trail": [_trace("portfolio_manager", sp, up, final.model_dump_json())],
        }

    return node


def _hold_node(state: AgentState) -> dict:
    decision = state["risk_decision"]
    final = TradeDecision(
        action=Action.HOLD, size=0.0, rationale=f"Risk Manager vetoed new exposure: {decision.reasoning}", confidence=1.0
    )
    return {
        "trade_decision": final,
        "reasoning_trail": [_trace("hold", "", "", final.model_dump_json())],
    }


def build_graph(memory_client: SupermemoryClient, llm_client: OpenAI | None = None, *, model: str = DEFAULT_MODEL):
    """Compiles the Phase 5 agent graph. One LLM client is resolved once and
    shared by every node (rather than each node lazily constructing its own),
    since they all point at the same Groq account/model within a cycle."""
    client = llm_client or get_client()
    graph = StateGraph(AgentState)

    graph.add_node("market_analyst", _market_analyst_node(client, model))
    graph.add_node("bull", _researcher_node(Stance.BULL, memory_client, client, model))
    graph.add_node("bear", _researcher_node(Stance.BEAR, memory_client, client, model))
    graph.add_node("risk_manager", _risk_manager_node(client, model))
    graph.add_node("trader", _trader_node(client, model))
    graph.add_node("portfolio_manager", _portfolio_manager_node(client, model))
    graph.add_node("hold", _hold_node)

    graph.add_edge(START, "market_analyst")
    graph.add_edge("market_analyst", "bull")
    graph.add_edge("market_analyst", "bear")
    graph.add_edge("bull", "risk_manager")
    graph.add_edge("bear", "risk_manager")
    graph.add_conditional_edges("risk_manager", _route_after_risk, {"trader": "trader", "hold": "hold"})
    graph.add_edge("trader", "portfolio_manager")
    graph.add_edge("portfolio_manager", END)
    graph.add_edge("hold", END)

    return graph.compile()
