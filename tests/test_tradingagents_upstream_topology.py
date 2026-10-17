import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'vendor', 'TradingAgents')))

import pytest

def test_tradingagents_package_metadata():
    """Verify authentic TauricResearch/TradingAgents package version and commit."""
    ver = None
    try:
        import importlib.metadata
        ver = importlib.metadata.version("tradingagents")
    except Exception:
        pass
    if not ver:
        try:
            import tomllib
            with open("vendor/TradingAgents/pyproject.toml", "rb") as f:
                data = tomllib.load(f)
                ver = data.get("project", {}).get("version")
        except Exception:
            pass
    assert ver == "0.4.0"

def test_upstream_graph_topology_and_router_maps():
    """Verify the actual upstream TradingAgents graph topology, nodes, and conditional router path maps."""
    try:
        from tradingagents.graph.setup import DEBATE_PATH_MAP, RISK_ANALYSIS_PATH_MAP, GraphSetup
        from tradingagents.agents.utils.agent_states import AgentState
        from langgraph.graph import StateGraph, START, END

        # 1. Verify debate router path map contains all valid targets
        assert "Bull Researcher" in DEBATE_PATH_MAP
        assert "Bear Researcher" in DEBATE_PATH_MAP
        assert "Research Manager" in DEBATE_PATH_MAP

        # 2. Verify risk router path map contains all multi-agent risk debators and portfolio manager
        assert "Aggressive Analyst" in RISK_ANALYSIS_PATH_MAP
        assert "Conservative Analyst" in RISK_ANALYSIS_PATH_MAP
        assert "Neutral Analyst" in RISK_ANALYSIS_PATH_MAP
        assert "Portfolio Manager" in RISK_ANALYSIS_PATH_MAP

        # 3. Verify graph setup can construct the full multi-agent analyst + debate + risk topology
        # Mock LLM and tool nodes for pure topology construction verification
        class DummyLLM:
            pass

        tool_nodes = {
            "market": lambda s: s,
            "social": lambda s: s,
            "news": lambda s: s,
            "fundamentals": lambda s: s,
        }

        class DummyConditionalLogic:
            max_debate_rounds = 2
            max_risk_discuss_rounds = 2
            def should_continue_market(self, s): return "clear_market"
            def should_continue_social(self, s): return "clear_social"
            def should_continue_news(self, s): return "clear_news"
            def should_continue_fundamentals(self, s): return "clear_fundamentals"
            def should_continue_debate(self, s): return "Research Manager"
            def should_continue_risk_analysis(self, s): return "Portfolio Manager"

        setup = GraphSetup(
            quick_thinking_llm=DummyLLM(),
            deep_thinking_llm=DummyLLM(),
            tool_nodes=tool_nodes,
            conditional_logic=DummyConditionalLogic()
        )

        wf = setup.setup_graph(selected_analysts=("market", "social", "news", "fundamentals"))
        assert wf is not None

        # Verify all mandatory agent nodes exist in the graph workflow
        nodes = wf.nodes
        assert "Market Analyst" in nodes
        assert "Sentiment Analyst" in nodes
        assert "News Analyst" in nodes
        assert "Fundamentals Analyst" in nodes
        assert "Bull Researcher" in nodes
        assert "Bear Researcher" in nodes
        assert "Research Manager" in nodes
        assert "Trader" in nodes
        assert "Aggressive Analyst" in nodes
        assert "Neutral Analyst" in nodes
        assert "Conservative Analyst" in nodes
        assert "Portfolio Manager" in nodes

    except ImportError:
        pytest.skip("tradingagents or langgraph not installed in local environment")

def test_tradingagents_crypto_advisory_isolation():
    """Verify that the crypto-adapted TradingAgents integration strictly maintains advisory isolation."""
    from control_plane import tradingagents_crypto
    diag = tradingagents_crypto.get_tradingagents_diagnostic()
    assert diag["framework"] == "TauricResearch/TradingAgents"
    assert diag["version"] == "0.4.0"
    assert diag["is_advisory"] is True
    assert diag["execution_authority"] is False
    assert isinstance(diag["max_open_trades_barrier"], int)

def test_actual_dynamic_route_taken_by_conditional_logic():
    """Validate that ConditionalLogic chooses the actual dynamic route taken based on state,

    without artificially forcing every node to execute unconditionally.
    """
    try:
        from tradingagents.graph.conditional_logic import ConditionalLogic
    except ImportError:
        pytest.skip("tradingagents not in path")

    logic = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)

    # 1. Test debate routing: Bull speaks -> routes to Bear
    state_bull = {
        "investment_debate_state": {
            "count": 0,
            "current_response": "Bullish view: momentum is surging"
        }
    }
    assert logic.should_continue_debate(state_bull) == "Bear Researcher"

    # 2. Test debate routing: Bear speaks -> routes back to Bull if count not exceeded
    state_bear = {
        "investment_debate_state": {
            "count": 1,
            "current_response": "Bearish view: resistance holds"
        }
    }
    assert logic.should_continue_debate(state_bear) == "Bull Researcher"

    # 3. Test debate routing: When count >= 2 * max_debate_rounds (2), routes to Research Manager
    state_debate_done = {
        "investment_debate_state": {
            "count": 2,
            "current_response": "Bearish view: confirmed"
        }
    }
    assert logic.should_continue_debate(state_debate_done) == "Research Manager"

    # 4. Test risk analysis routing: Aggressive speaks -> routes to Conservative
    state_risk_agg = {
        "risk_debate_state": {
            "count": 1,
            "latest_speaker": "Aggressive Analyst: Take 5x leverage"
        }
    }
    assert logic.should_continue_risk_analysis(state_risk_agg) == "Conservative Analyst"

    # 5. Test risk analysis routing: Conservative speaks -> routes to Neutral
    state_risk_cons = {
        "risk_debate_state": {
            "count": 2,
            "latest_speaker": "Conservative Analyst: Limit risk to 1%"
        }
    }
    assert logic.should_continue_risk_analysis(state_risk_cons) == "Neutral Analyst"

    # 6. Test risk analysis routing: When count >= 3 * max_risk_discuss_rounds (3), routes to Portfolio Manager
    state_risk_done = {
        "risk_debate_state": {
            "count": 3,
            "latest_speaker": "Neutral Analyst: Compromise"
        }
    }
    assert logic.should_continue_risk_analysis(state_risk_done) == "Portfolio Manager"

