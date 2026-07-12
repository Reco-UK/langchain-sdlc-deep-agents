"""Condition functions referenced by name from `agents.yaml`'s conditional_edges.

Each function takes the current `AgentState` and returns a branch key that
must match one of the branches declared for that edge in agents.yaml — see
`CONDITION_REGISTRY` at the bottom of this file and how it's consumed in
app/agent/graph.py's `GraphBuilder._add_conditional_edges`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.agent.state import AgentState

logger = logging.getLogger(__name__)

QUALITY_THRESHOLD = 60
MAX_REVIEW_ITERATIONS = 3

ConditionFn = Callable[[AgentState], str]


def quality_threshold(state: AgentState) -> str:
    """Route based on the reviewer's score, capping coder<->reviewer loops.

    Returns:
        "approved" if the review score meets QUALITY_THRESHOLD.
        "reject" once MAX_REVIEW_ITERATIONS is exceeded, escalating to a
            human instead of letting coder/reviewer loop forever.
        "needs_work" otherwise, sending control back to `coder`.
    """
    review_report = state.get("review_report", {})
    score = review_report.get("score", 0)
    iteration_count = state.get("iteration_count", 0)

    if score >= QUALITY_THRESHOLD:
        return "approved"

    if iteration_count >= MAX_REVIEW_ITERATIONS:
        logger.warning(
            "quality_threshold: max iterations (%d) reached, escalating to human",
            MAX_REVIEW_ITERATIONS,
        )
        return "reject"

    return "needs_work"


def check_approval(state: AgentState) -> str:
    """Route based on the human reviewer's decision from the `human_approval` node.

    Returns:
        "approved" if `human_decision` is exactly "approved" (case-insensitive).
        "rejected" otherwise, including when no decision was recorded.
    """
    decision = state.get("human_decision", "")
    return "approved" if decision.strip().lower() == "approved" else "rejected"


CONDITION_REGISTRY: dict[str, ConditionFn] = {
    "quality_threshold": quality_threshold,
    "check_approval": check_approval,
}
