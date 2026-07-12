"""Compiles a LangGraph `StateGraph` from `agents.yaml`.

This is the "Dynamic Graph Compilation" layer described in
.claude/architecture.md: nodes, edges, and conditional branches are all
data from agents.yaml rather than Python control flow, so extending the
workflow never requires touching this file.
"""

from __future__ import annotations

import logging
from contextlib import AbstractAsyncContextManager
from typing import Any, cast

import yaml
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.conditions import CONDITION_REGISTRY
from app.agent.nodes import NodeFactory
from app.agent.state import AgentState
from app.config import Settings
from app.exceptions import GraphCompilationError
from app.tools.mcp_loader import MCPToolRegistry

logger = logging.getLogger(__name__)

# AgentState is used as state, input, and output schema — the graph never
# narrows its input/output shape, so all three of StateGraph's type params
# are the same TypedDict.
AgentStateGraph = StateGraph[AgentState, AgentState, AgentState]
AgentCompiledGraph = CompiledStateGraph[AgentState, AgentState, AgentState]

CheckpointSaver = AsyncPostgresSaver | AsyncSqliteSaver


def checkpointer_context(settings: Settings) -> AbstractAsyncContextManager[CheckpointSaver]:
    """Return an async context manager yielding the configured checkpoint saver.

    Postgres backs staging/production state; CI and local test runs use an
    in-memory or file-backed SQLite checkpointer instead (see
    .claude/architecture.md, "State Management"). Selection is driven
    entirely by the `POSTGRES_DSN` scheme, so no code change is needed to
    switch environments.
    """
    if settings.postgres_dsn.startswith("postgresql"):
        return AsyncPostgresSaver.from_conn_string(settings.postgres_dsn)
    sqlite_path = settings.postgres_dsn.removeprefix("sqlite:///")
    return AsyncSqliteSaver.from_conn_string(sqlite_path)


def load_manifest(settings: Settings) -> dict[str, Any]:
    """Parse `agents.yaml` into a plain dict.

    Raises:
        GraphCompilationError: If the manifest file is missing.
    """
    manifest_path = settings.agents_manifest_path
    if not manifest_path.exists():
        raise GraphCompilationError(f"agents.yaml not found at '{manifest_path}'")
    return cast(dict[str, Any], yaml.safe_load(manifest_path.read_text()))


class GraphBuilder:
    """Builds and compiles the agent's StateGraph from a parsed agents.yaml manifest."""

    def __init__(self, manifest: dict[str, Any], settings: Settings) -> None:
        self._manifest = manifest
        self._settings = settings
        self._tool_registry = MCPToolRegistry(manifest.get("mcp_servers", {}), settings)

    async def build(self, checkpointer: BaseCheckpointSaver[Any]) -> AgentCompiledGraph:
        """Assemble nodes, edges, and conditional branches into a compiled graph.

        Args:
            checkpointer: The LangGraph checkpoint saver (Postgres in
                production, SQLite in CI/local tests).

        Returns:
            A compiled LangGraph graph, ready for `.ainvoke()`.

        Raises:
            GraphCompilationError: If agents.yaml references an unknown
                condition function.
        """
        graph_def = self._manifest["graph"]
        await self._tool_registry.connect()
        factory = NodeFactory(graph_def["model_presets"], self._tool_registry, self._settings)

        builder: AgentStateGraph = StateGraph(AgentState)
        for node_def in graph_def["nodes"]:
            node_id = str(node_def["id"])
            # cast: our node callables are plain `async def (state) -> dict`
            # functions, which are structurally compatible with LangGraph's
            # node Protocol union at runtime but mypy can't unify a bare
            # Callable against that many Protocol overloads.
            builder.add_node(node_id, cast(Any, factory.build(node_def)))
        builder.set_entry_point(str(graph_def["nodes"][0]["id"]))

        self._add_edges(builder, graph_def.get("edges", []))
        self._add_conditional_edges(builder, graph_def.get("conditional_edges", []))

        return builder.compile(checkpointer=checkpointer)

    def _add_edges(self, builder: AgentStateGraph, edges: list[dict[str, str]]) -> None:
        for edge in edges:
            target = END if edge["to"] == "END" else edge["to"]
            builder.add_edge(edge["from"], target)

    def _add_conditional_edges(
        self, builder: AgentStateGraph, conditional_edges: list[dict[str, Any]]
    ) -> None:
        for edge in conditional_edges:
            condition_name = edge["condition"]
            condition_fn = CONDITION_REGISTRY.get(condition_name)
            if condition_fn is None:
                raise GraphCompilationError(
                    f"agents.yaml references unknown condition '{condition_name}'. "
                    f"Known conditions: {sorted(CONDITION_REGISTRY)}"
                )
            branches = {
                key: (END if target == "END" else target)
                for key, target in edge["branches"].items()
            }
            builder.add_conditional_edges(edge["from"], condition_fn, branches)

    async def aclose(self) -> None:
        """Release MCP subprocess connections opened by `build()`."""
        await self._tool_registry.close()
