"""Builds LangGraph-compatible node callables from `agents.yaml` node definitions.

`NodeFactory.build(node_def)` is the "zero Python code" seam described in
.claude/config.md: adding a node to agents.yaml plus a prompt file is
enough to add a new agent stage, because every node is assembled from the
same template here rather than a bespoke function per node.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from jinja2 import Template
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.types import interrupt

from app.agent.state import AgentState, ReviewReport
from app.config import Settings
from app.exceptions import ToolExecutionError
from app.llm_factory import get_model_for_preset
from app.tools.mcp_loader import MCPToolRegistry

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5

NodeFn = Callable[[AgentState], Awaitable[dict[str, Any]]]

_SCORE_RE = re.compile(r"Score:\s*(\d+)")
_SUMMARY_RE = re.compile(r"Summary:\s*(.+)")
_SECURITY_RE = re.compile(r"Security Notes:\s*(.+)")
_ISSUE_LINE_RE = re.compile(r"^-\s*(.+)$", re.MULTILINE)


def parse_review_report(text: str) -> ReviewReport:
    """Parse the reviewer's structured text response into a `ReviewReport`.

    The reviewer prompt (prompts/reviewer/system.jinja2) asks for a fixed
    `Score: <n>` / `Summary: ...` / `Issues:` / `Security Notes: ...` format
    specifically so this regex parse is reliable without a second
    structured-output call to the LLM. `conditions.quality_threshold` reads
    the resulting `score` field to decide whether to loop back to `coder`.
    """
    score_match = _SCORE_RE.search(text)
    summary_match = _SUMMARY_RE.search(text)
    security_match = _SECURITY_RE.search(text)
    issues = [issue for issue in _ISSUE_LINE_RE.findall(text) if issue.strip().lower() != "none"]
    return {
        "score": int(score_match.group(1)) if score_match else 0,
        "summary": summary_match.group(1).strip() if summary_match else "",
        "issues": issues,
        "security_notes": security_match.group(1).strip() if security_match else "",
    }


class NodeFactory:
    """Builds async node functions from `agents.yaml` node definitions."""

    def __init__(
        self,
        model_presets: dict[str, dict[str, Any]],
        tool_registry: MCPToolRegistry,
        settings: Settings,
    ) -> None:
        self._model_presets = model_presets
        self._tool_registry = tool_registry
        self._settings = settings

    def build(self, node_def: dict[str, Any]) -> NodeFn:
        """Return the async callable LangGraph should run for this node.

        Args:
            node_def: One entry from `agents.yaml`'s `graph.nodes`.

        Returns:
            An `async def node(state: AgentState) -> dict[str, Any]` coroutine.

        Raises:
            ValueError: If `node_def["type"]` is not a recognized node type.
        """
        node_type = node_def["type"]
        if node_type == "llm_node":
            return self._build_llm_node(node_def)
        if node_type == "interrupt_node":
            return self._build_interrupt_node(node_def)
        raise ValueError(f"Unknown node type '{node_type}' for node '{node_def['id']}'")

    def _build_llm_node(self, node_def: dict[str, Any]) -> NodeFn:
        node_id = node_def["id"]
        output_key = node_def["output_key"]
        prompt_text = Path(node_def["prompt_file"]).read_text()
        tool_names = node_def.get("tools", [])
        model = get_model_for_preset(node_def["model_preset"], self._model_presets, self._settings)

        async def run_node(state: AgentState) -> dict[str, Any]:
            tools = await self._tool_registry.get_tools(tool_names)
            system_prompt = Template(prompt_text).render(**state)
            bound_model = model.bind_tools(tools) if tools else model
            messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
            final_message = await self._run_tool_loop(bound_model, messages, tools, node_id)
            content = final_message.content
            if output_key == "review_report":
                return {output_key: parse_review_report(str(content))}
            if output_key == "code":
                return {output_key: content, "iteration_count": state.get("iteration_count", 0) + 1}
            return {output_key: content}

        return run_node

    async def _run_tool_loop(
        self,
        bound_model: Runnable[Any, BaseMessage],
        messages: list[BaseMessage],
        tools: list[BaseTool],
        node_id: str,
    ) -> BaseMessage:
        """Invoke the model, executing any requested tool calls, up to a hard cap.

        A hard iteration cap prevents a misbehaving model from looping
        forever on tool calls — see the "handle edge cases explicitly" rule
        in .claude/coding-standards.md.
        """
        tools_by_name = {tool.name: tool for tool in tools}
        response: BaseMessage = AIMessage(content="")
        for _ in range(MAX_TOOL_ITERATIONS):
            response = await bound_model.ainvoke(messages)
            messages.append(response)
            if not isinstance(response, AIMessage) or not response.tool_calls:
                return response
            for call in response.tool_calls:
                messages.append(await self._invoke_tool(tools_by_name, call, node_id))
        logger.warning(
            "%s: hit MAX_TOOL_ITERATIONS (%d) without a final answer", node_id, MAX_TOOL_ITERATIONS
        )
        return response

    async def _invoke_tool(
        self, tools_by_name: dict[str, BaseTool], call: ToolCall, node_id: str
    ) -> ToolMessage:
        tool = tools_by_name.get(call["name"])
        if tool is None:
            raise ToolExecutionError(f"{node_id} requested unknown tool '{call['name']}'")
        try:
            result = await tool.ainvoke(call["args"])
        except Exception as exc:  # noqa: BLE001 - surfaced to the model as a tool result
            logger.error("Tool '%s' failed in node '%s': %s", call["name"], node_id, exc)
            result = f"Error: {exc}"
        return ToolMessage(content=str(result), tool_call_id=call["id"])

    def _build_interrupt_node(self, node_def: dict[str, Any]) -> NodeFn:
        output_key = node_def["output_key"]
        node_id = node_def["id"]

        async def run_node(state: AgentState) -> dict[str, Any]:
            decision = interrupt({"question": f"Approve node '{node_id}'?", "state": dict(state)})
            return {output_key: decision}

        return run_node
