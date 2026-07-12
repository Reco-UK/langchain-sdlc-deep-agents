"""Unit tests for app.agent.graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from langgraph.graph import StateGraph

from app.agent.graph import AgentStateGraph, GraphBuilder, load_manifest
from app.agent.state import AgentState
from app.config import Settings
from app.exceptions import GraphCompilationError


def test_load_manifest_raises_for_missing_file() -> None:
    settings = Settings(_env_file=None, agents_manifest_path=Path("does_not_exist.yaml"))
    with pytest.raises(GraphCompilationError, match="not found"):
        load_manifest(settings)


def test_load_manifest_reads_agents_yaml() -> None:
    manifest = load_manifest(Settings(_env_file=None))
    assert "mcp_servers" in manifest
    assert manifest["graph"]["nodes"][0]["id"] == "context_loader"


def test_conditional_edges_reject_unknown_condition() -> None:
    manifest: dict[str, Any] = {"mcp_servers": {}, "graph": {"model_presets": {}}}
    builder = GraphBuilder(manifest, Settings(_env_file=None))
    graph: AgentStateGraph = StateGraph(AgentState)
    graph.add_node("reviewer", lambda state: state)
    graph.add_node("summarizer", lambda state: state)
    conditional_edges = [
        {
            "from": "reviewer",
            "condition": "not_a_real_condition",
            "branches": {"approved": "summarizer"},
        }
    ]
    with pytest.raises(GraphCompilationError, match="unknown condition"):
        builder._add_conditional_edges(graph, conditional_edges)
