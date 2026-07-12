"""Shared state schema threaded through every node in the agent graph.

Node functions (see app/agent/nodes.py) return a partial dict of only the
keys they update, and LangGraph merges it into the running `AgentState`.
This mirrors the `output_key` each node declares in `agents.yaml`.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class ReviewReport(TypedDict, total=False):
    """Structured output the `reviewer` node is expected to produce."""

    score: int
    summary: str
    issues: list[str]
    security_notes: str


class AgentState(TypedDict, total=False):
    """Full state passed between nodes.

    Every key is optional (`total=False`) because each node only populates
    the fields relevant to its own stage of the pipeline — `context_loader`
    hasn't written `code` yet, for example.
    """

    task: str
    thread_id: str
    external_context: str
    plan: str
    code: str
    review_report: ReviewReport
    human_decision: str
    final_summary: str
    files_changed: list[str]
    iteration_count: int
    # `add_messages` is LangGraph's reducer for message history: new messages
    # are appended rather than overwriting the list on each node update.
    messages: Annotated[list[Any], add_messages]
