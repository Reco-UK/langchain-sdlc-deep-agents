"""Headless CLI entrypoint for CI/CD pipelines (GitHub Actions, Bitbucket Pipelines).

Runs the agent graph to completion for a single task and prints the result
as JSON on stdout, matching the contract in .claude/ci-cd.md:

    {
      "status": "success" | "failure",
      "summary": "...",
      "files_changed": [...],
      "review_score": 85,
      "security_report": "..."
    }

Exit code 0 means `review_score >= 60`; exit code 1 means failure. The same
JSON is written to `output.json` for the GitHub Actions step that posts it
as a PR comment.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.graph import GraphBuilder, checkpointer_context, load_manifest
from app.config import configure_logging, get_settings

PASSING_REVIEW_SCORE = 60


async def run_task(task: str, thread_id: str = "cli") -> dict[str, Any]:
    """Build the graph, run it once for `task`, and return the CI output contract."""
    settings = get_settings()
    manifest = load_manifest(settings)
    builder = GraphBuilder(manifest, settings)

    async with checkpointer_context(settings) as checkpointer:
        await checkpointer.setup()
        graph = await builder.build(checkpointer)
        try:
            config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
            result = await graph.ainvoke({"task": task}, config=config)
        finally:
            await builder.aclose()

    review_report = result.get("review_report", {})
    score = review_report.get("score", 0)
    return {
        "status": "success" if score >= PASSING_REVIEW_SCORE else "failure",
        "summary": result.get("final_summary", ""),
        "files_changed": result.get("files_changed", []),
        "review_score": score,
        "security_report": review_report.get("security_notes", ""),
    }


def main() -> None:
    """Entry point registered as the `langchain-sldc-agent` console script."""
    configure_logging()
    settings = get_settings()

    if not settings.task:
        print(json.dumps({"status": "failure", "summary": "TASK environment variable is required"}))
        sys.exit(1)

    output = asyncio.run(run_task(settings.task))
    print(json.dumps(output, indent=2))
    Path("output.json").write_text(json.dumps(output, indent=2))

    sys.exit(0 if output["status"] == "success" else 1)


if __name__ == "__main__":
    main()
