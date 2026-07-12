"""Evaluation tests: run the full agent against golden tasks and check outcomes.

Requires a live LLM provider (Ollama running locally, or ANTHROPIC_API_KEY
set), so these are skipped by default — see .claude/coding-standards.md's
"Evaluation Tests" section. Run manually with:
    pytest tests/eval -m eval --no-skip
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.eval

GOLDEN_TASKS_PATH = Path(__file__).parent.parent / "fixtures" / "golden_tasks.json"


def _load_golden_tasks() -> list[dict[str, Any]]:
    return json.loads(GOLDEN_TASKS_PATH.read_text())


@pytest.mark.skip(reason="Requires a live LLM provider; run manually against a real environment.")
@pytest.mark.parametrize("golden_task", _load_golden_tasks())
async def test_agent_meets_golden_task_expectations(golden_task: dict[str, Any]) -> None:
    from app.agent.graph import GraphBuilder, checkpointer_context, load_manifest
    from app.config import get_settings

    settings = get_settings()
    manifest = load_manifest(settings)
    builder = GraphBuilder(manifest, settings)

    async with checkpointer_context(settings) as checkpointer:
        await checkpointer.setup()
        graph = await builder.build(checkpointer)
        try:
            result = await graph.ainvoke({"task": golden_task["task"]})
        finally:
            await builder.aclose()

    assert result["review_report"]["score"] >= golden_task["min_review_score"]
