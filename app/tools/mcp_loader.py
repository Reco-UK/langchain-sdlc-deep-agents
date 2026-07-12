"""Loads MCP servers declared in `agents.yaml` and exposes their tools to nodes.

Uses `langchain-mcp-adapters` to convert MCP tool definitions into LangChain
`BaseTool` instances, per the "MCP Standardization" principle in
.claude/config.md: nodes never talk to GitHub/JIRA/Confluence/the
filesystem directly, only through tools loaded here.
"""

from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import Settings
from app.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class MCPToolRegistry:
    """Connects to every MCP server in `agents.yaml` and filters tools per node.

    Tool filtering is name-based and server-agnostic: a node's `tools` list
    in agents.yaml is matched against the union of tools exposed by all
    connected servers, so nodes don't need to know which server implements
    which tool.
    """

    def __init__(self, server_defs: dict[str, dict[str, Any]], settings: Settings) -> None:
        self._server_defs = server_defs
        self._settings = settings
        self._exit_stack = AsyncExitStack()
        self._tools_by_name: dict[str, BaseTool] = {}
        self._connected = False

    async def connect(self) -> None:
        """Spawn every configured MCP server subprocess and index its tools.

        A server that fails to start is logged and skipped rather than
        aborting the whole registry — a node that doesn't need that
        server's tools should still be able to run.
        """
        if self._connected:
            return
        for server_name, server_def in self._server_defs.items():
            try:
                await self._connect_server(server_name, server_def)
            except Exception as exc:  # noqa: BLE001 - one bad server shouldn't block the rest
                logger.error("Failed to start MCP server '%s': %s", server_name, exc)
        self._connected = True

    async def _connect_server(self, server_name: str, server_def: dict[str, Any]) -> None:
        env = self._resolve_env(server_def.get("env_mapping", {}))
        params = StdioServerParameters(
            command=server_def["command"],
            args=server_def.get("args", []),
            env=env or None,
        )
        read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        tools = await load_mcp_tools(session)
        for tool in tools:
            self._tools_by_name[tool.name] = tool
        logger.info("MCP server '%s' loaded %d tool(s)", server_name, len(tools))

    def _resolve_env(self, env_mapping: dict[str, str]) -> dict[str, str]:
        """Expand `${VAR}` references in an env_mapping against the process environment."""
        resolved: dict[str, str] = {}
        for key, template in env_mapping.items():
            var_name = template.strip("${}")
            resolved[key] = os.environ.get(var_name, "")
        return resolved

    async def get_tools(self, tool_names: list[str]) -> list[BaseTool]:
        """Return the subset of connected tools a node explicitly requested.

        Raises:
            ConfigurationError: If a requested tool name isn't provided by
                any connected MCP server — this is a config typo in
                agents.yaml, not a runtime condition to swallow.
        """
        tools = []
        for name in tool_names:
            tool = self._tools_by_name.get(name)
            if tool is None:
                raise ConfigurationError(
                    f"Tool '{name}' requested in agents.yaml is not provided by any "
                    f"connected MCP server. Available tools: {sorted(self._tools_by_name)}"
                )
            tools.append(tool)
        return tools

    async def close(self) -> None:
        """Tear down all MCP subprocess connections."""
        await self._exit_stack.aclose()
        self._connected = False
