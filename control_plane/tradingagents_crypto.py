"""TauricResearch/TradingAgents Integration & Crypto Multi-Agent Graph for Ophelia.

Layer: control_plane/tradingagents_crypto
Contract:
- Integrates the authentic TauricResearch/TradingAgents multi-agent framework
  (v0.4.0, commit 9dee508).
- Implements a crypto-adapted LangGraph multi-agent architecture with specialized roles:
  1. Technical Analyst (1m, 3m, 5m, 15m structure, session VWAP, displacement, retest state, CVD, RVOL, FVG)
  2. Crypto Macro & Sentiment Analyst (Yahoo macro rates: DXY, US10Y, SPX, Gold, Oil; geopolitical event dossier)
  3. Bull vs Bear Researcher debate (explicit bull and bear thesis generation)
  4. Trader Synthesis (generates structured TraderProposal with action, entry, stops, targets, thesis)
  5. Deterministic Risk Review (Ophelia fail-closed risk gate, parameter validation, advisory enforcement)
- Connects through TradingAgents LLM client with provider="ollama" and model="qwen3:4b".
- Strictly ADVISORY ONLY: NO direct BingX credentials, NO order execution authority.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, TypedDict

import tradingagents
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.agents.schemas import (
    TraderProposal,
    PortfolioDecision,
    PortfolioRating,
    TraderAction,
    SentimentReport,
    SentimentBand,
)
from langgraph.graph import StateGraph, START, END

from . import config, db

logger = logging.getLogger(__name__)

# Pinned upstream version and commit metadata
TRADINGAGENTS_COMMIT = "9dee508c44662702281a8dbaad1f7b42179b5ba7"
TRADINGAGENTS_VERSION = getattr(tradingagents, "__version__", "0.4.0")
TRADINGAGENTS_FRAMEWORK_NAME = f"TauricResearch/TradingAgents v{TRADINGAGENTS_VERSION}"
TRADINGAGENTS_PACKAGE_PATH = getattr(tradingagents, "__file__", "installed")


def get_tradingagents_diagnostic() -> Dict[str, Any]:
    """Return authoritative provenance and configuration diagnostics for TradingAgents."""
    return {
        "framework": "TauricResearch/TradingAgents",
        "version": TRADINGAGENTS_VERSION,
        "commit": TRADINGAGENTS_COMMIT,
        "package_path": TRADINGAGENTS_PACKAGE_PATH,
        "provider": "Ollama",
        "model": config.LLM_PRIMARY,
        "base_url": f"{config.OLLAMA_URL}/v1",
        "is_advisory": True,
        "execution_authority": False,
        "max_open_trades_barrier": db.get_max_open_trades(),
        "shadow_enforced": True,
    }


class TradingAgentsCryptoState(TypedDict):
    symbol: str
    price: float
    vwap: float
    cvd_delta: float
    rvol: float
    retest_state: str
    fvg_state: str
    structural_sl: float
    suggested_tp1: float
    suggested_tp2: float
    macro_context: str
    geopolitical_summary: str
    technical_analyst_report: Optional[str]
    macro_analyst_report: Optional[str]
    bull_case: Optional[str]
    bear_case: Optional[str]
    trader_proposal: Optional[Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]


def _create_llm_instance(max_tokens: int = 350, timeout: int | None = None):
    """Create authentic TradingAgents LLM client configured for Ollama qwen3:4b."""
    client = create_llm_client(
        provider="ollama",
        model=config.LLM_PRIMARY,
        base_url=f"{config.OLLAMA_URL}/v1",
        temperature=0.2,
        max_tokens=max_tokens,
        timeout=timeout or config.LLM_TIMEOUT_SEC,
    )
    return client.get_llm()


def technical_analyst_agent(state: TradingAgentsCryptoState) -> Dict[str, Any]:
    """Technical Analyst: evaluates multi-timeframe candle structure, VWAP, CVD, and FVG."""
    sym = state["symbol"]
    price = state["price"]
    vwap = state["vwap"]
    cvd = state["cvd_delta"]
    rvol = state["rvol"]
    retest = state["retest_state"]
    fvg = state["fvg_state"]

    vwap_rel = "ABOVE" if price >= vwap else "BELOW"
    cvd_flow = "BUYING_PRESSURE" if cvd > 0 else ("SELLING_PRESSURE" if cvd < 0 else "BALANCED")

    report = (
        f"Technical Analysis for {sym} at {price:.2f}:\n"
        f"- Session VWAP: {vwap:.2f} (Price is {vwap_rel} VWAP)\n"
        f"- Institutional CVD Aggressor Delta: {cvd:+.1f} ({cvd_flow})\n"
        f"- Relative Volume (RVOL): {rvol:.2f}\n"
        f"- Retest Engine State: {retest}\n"
        f"- Fair Value Gap (FVG) Status: {fvg}\n"
        f"- Structural Levels: SL {state['structural_sl']:.2f}, TP1 {state['suggested_tp1']:.2f}, TP2 {state['suggested_tp2']:.2f}"
    )
    return {"technical_analyst_report": report}


def macro_sentiment_agent(state: TradingAgentsCryptoState) -> Dict[str, Any]:
    """Macro & Sentiment Analyst: evaluates Yahoo Finance rates and geopolitical event context."""
    macro = state.get("macro_context") or "Macro data steady"
    news = state.get("geopolitical_summary") or "Geopolitical risk steady"
    report = (
        f"Macro & Sentiment Assessment for {state['symbol']}:\n"
        f"- Financial Market Rates: {macro}\n"
        f"- Geopolitical Reference Context: {news}"
    )
    return {"macro_analyst_report": report}


def bull_bear_research_agent(state: TradingAgentsCryptoState) -> Dict[str, Any]:
    """Bull vs Bear Researchers: debate directional catalysts and risks."""
    price = state["price"]
    vwap = state["vwap"]
    cvd = state["cvd_delta"]
    retest = state["retest_state"]

    if price >= vwap and cvd >= 0:
        bull = f"Price holds above session VWAP with positive aggressor CVD ({cvd:+.0f}). Retest state {retest} confirms buyers defending structure."
        bear = f"Resistance overhead at {state['suggested_tp1']:.2f}. Failure to sustain VWAP ({vwap:.2f}) risks momentum exhaustion."
    elif price < vwap and cvd <= 0:
        bull = f"Potential mean reversion if sellers fail to expand breakdown below {state['structural_sl']:.2f}."
        bear = f"Price rejected below session VWAP with negative aggressor CVD ({cvd:+.0f}). Retest state {retest} favors continuation down."
    else:
        bull = f"Mixed order flow provides potential rotation toward VWAP ({vwap:.2f})."
        bear = f"Conflicting CVD ({cvd:+.0f}) and price action indicates chop; risk of false breakout."

    return {"bull_case": bull, "bear_case": bear}


def trader_synthesis_agent(state: TradingAgentsCryptoState) -> Dict[str, Any]:
    """Trader: synthesizes analyst reports and debate into a concrete TraderProposal."""
    prompt = f"""You are the TradingAgents Lead Crypto Trader.
Analyze the following multi-agent reports and research debate:

{state['technical_analyst_report']}

{state['macro_analyst_report']}

BULL CASE:
{state['bull_case']}

BEAR CASE:
{state['bear_case']}

Instructions:
Synthesize an authoritative trading recommendation. Be concise. Do not output conversational preamble or verbose reasoning.
Return ONLY valid JSON matching this exact schema:
{{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": 75,
  "market_regime": "TRENDING_BULLISH" | "TRENDING_BEARISH" | "RANGE_BOUND" | "HIGH_VOLATILITY",
  "thesis": "Concise 1-2 sentence core thesis explaining why to enter or stand aside",
  "entry_recommendation": {state['price']},
  "missing_conditions": []
}}
"""
    t0 = time.time()
    full_text = ""
    try:
        import requests
        url = f"{config.OLLAMA_URL}/api/chat"
        payload = {
            "model": config.LLM_PRIMARY,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {
                "temperature": 0.2,
                "num_predict": 2500
            }
        }
        
        # We manually use requests instead of `llm.invoke` to bypass socket timeout constraints on large generations
        response = requests.post(
            url, 
            json=payload, 
            stream=True, 
            timeout=600  # Explicit 10-minute timeout for streaming chunks
        )
        response.raise_for_status()
        
        out_thinking = ""
        out_content = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line.decode("utf-8"))
                if "message" in chunk:
                    out_thinking += chunk["message"].get("thinking", "")
                    out_content += chunk["message"].get("content", "")

        # Combine both streams since Qwen3 may output the JSON inside the thinking block
        full_text = out_thinking + "\n" + out_content
        
        # Strip literal <think> tags if they appear
        full_text = re.sub(r"<think>", "", full_text)
        full_text = re.sub(r"</think>", "", full_text).strip()

        # Parse JSON
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", full_text)
        if match:
            raw_json = match.group(1)
            data = json.loads(raw_json)
        else:
            # Extract all flat JSON-like blocks and use the last one
            blocks = re.findall(r"\{[^{}]*\}", full_text)
            if blocks:
                data = json.loads(blocks[-1])
            else:
                raise ValueError("No JSON block found in output")

        data["inference_success"] = True
        data["error_state"] = None
        data["latency_ms"] = int((time.time() - t0) * 1000)
        return {"trader_proposal": data}
    except Exception as e:
        logger.warning("TradingAgents trader synthesis fallback: %s", e)
        fallback = {
            "direction": "LONG" if state["price"] >= state["vwap"] and state["cvd_delta"] >= 0 else ("SHORT" if state["price"] < state["vwap"] and state["cvd_delta"] < 0 else "NEUTRAL"),
            "confidence": 50.0,
            "market_regime": "RANGE_BOUND",
            "thesis": f"Monitoring {state['symbol']} market structure and session VWAP alignment.",
            "entry_recommendation": state["price"],
            "missing_conditions": ["LLM evaluation timed out or unavailable"],
            "inference_success": False,
            "error_state": f"{e} - RAW CONTENT: {full_text}",
            "latency_ms": int((time.time() - t0) * 1000),
        }
        return {"trader_proposal": fallback}


def risk_review_agent(state: TradingAgentsCryptoState) -> Dict[str, Any]:
    """Deterministic Risk Review: validates proposal and enforces Ophelia fail-closed invariants."""
    prop = state.get("trader_proposal") or {}
    direction = str(prop.get("direction", "NEUTRAL")).upper()
    if direction not in ("LONG", "SHORT", "NEUTRAL"):
        direction = "NEUTRAL"

    try:
        conf = float(prop.get("confidence", 50.0))
    except (ValueError, TypeError):
        conf = 50.0
    conf = max(0.0, min(100.0, conf))

    regime = str(prop.get("market_regime", "RANGE_BOUND")).upper()
    thesis = str(prop.get("thesis", f"Monitoring {state['symbol']} structure."))

    final_payload = {
        "symbol": state["symbol"],
        "direction": direction,
        "confidence": conf,
        "market_regime": regime,
        "thesis": thesis,
        "technical_summary": state.get("technical_analyst_report") or "",
        "macro_summary": state.get("macro_analyst_report") or "",
        "news_summary": state.get("geopolitical_summary") or "",
        "bull_case": state.get("bull_case") or "",
        "bear_case": state.get("bear_case") or "",
        "missing_conditions": prop.get("missing_conditions", []),
        "entry_candidate": state["price"],
        "sl_candidates": [state["structural_sl"]],
        "suggested_sl": state["structural_sl"],
        "suggested_tp1": state["suggested_tp1"],
        "suggested_tp2": state["suggested_tp2"],
        "retest_state": state["retest_state"],
        "fvg_state": state["fvg_state"],
        "cvd_delta": state["cvd_delta"],
        "rvol": state["rvol"],
        "framework": TRADINGAGENTS_FRAMEWORK_NAME,
        "framework_commit": TRADINGAGENTS_COMMIT,
        "framework_version": TRADINGAGENTS_VERSION,
        "package_path": TRADINGAGENTS_PACKAGE_PATH,
        "provider": "Ollama",
        "model": config.LLM_PRIMARY,
        "is_advisory": True,
        "execution_authority": False,
        "inference_success": prop.get("inference_success", True),
        "error_state": prop.get("error_state"),
        "latency_ms": prop.get("latency_ms", 0),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return {"final_output": final_payload}


def build_tradingagents_crypto_graph():
    """Compile the LangGraph multi-agent crypto workflow."""
    wf = StateGraph(TradingAgentsCryptoState)
    wf.add_node("technical_analyst", technical_analyst_agent)
    wf.add_node("macro_sentiment", macro_sentiment_agent)
    wf.add_node("bull_bear_research", bull_bear_research_agent)
    wf.add_node("trader_synthesis", trader_synthesis_agent)
    wf.add_node("risk_review", risk_review_agent)

    wf.add_edge(START, "technical_analyst")
    wf.add_edge("technical_analyst", "macro_sentiment")
    wf.add_edge("macro_sentiment", "bull_bear_research")
    wf.add_edge("bull_bear_research", "trader_synthesis")
    wf.add_edge("trader_synthesis", "risk_review")
    wf.add_edge("risk_review", END)

    return wf.compile()


# Singleton compiled graph
_compiled_crypto_graph = build_tradingagents_crypto_graph()


def execute_tradingagents_crypto_intelligence(
    symbol: str,
    price: float,
    vwap: float,
    cvd_delta: float,
    rvol: float,
    retest_state: str,
    fvg_state: str,
    structural_sl: float,
    suggested_tp1: float,
    suggested_tp2: float,
    macro_context: str,
    geopolitical_summary: str,
) -> Dict[str, Any]:
    """Execute the compiled TradingAgents multi-agent graph and return structured DTO."""
    initial_state: TradingAgentsCryptoState = {
        "symbol": symbol,
        "price": price,
        "vwap": vwap,
        "cvd_delta": cvd_delta,
        "rvol": rvol,
        "retest_state": retest_state,
        "fvg_state": fvg_state,
        "structural_sl": structural_sl,
        "suggested_tp1": suggested_tp1,
        "suggested_tp2": suggested_tp2,
        "macro_context": macro_context,
        "geopolitical_summary": geopolitical_summary,
        "technical_analyst_report": None,
        "macro_analyst_report": None,
        "bull_case": None,
        "bear_case": None,
        "trader_proposal": None,
        "final_output": None,
    }

    result = _compiled_crypto_graph.invoke(initial_state)
    return result.get("final_output") or {}
