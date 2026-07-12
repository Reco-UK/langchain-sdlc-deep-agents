"""FastAPI application: webhook, scheduler, and synchronous invoke entrypoints.

This is the "Cloud Run (Stateless)" component from .claude/architecture.md —
it accepts HTTP requests, GitHub webhooks, and Cloud Scheduler calls, then
runs the compiled LangGraph agent. Short-lived work runs in-process here;
.claude/architecture.md's "Long-Running Task" flow (Cloud Tasks + interrupt)
is the natural next step once this ships to Cloud Run.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from app.agent.graph import GraphBuilder, checkpointer_context, load_manifest
from app.config import configure_logging, get_settings

logger = logging.getLogger(__name__)


class InvokeRequest(BaseModel):
    """Body for POST /invoke."""

    task: str
    thread_id: str = "default"


class InvokeResponse(BaseModel):
    """Response for POST /invoke."""

    thread_id: str
    final_summary: str | None = None
    review_report: dict[str, Any] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the compiled graph once at startup and tear it down at shutdown."""
    configure_logging()
    settings = get_settings()
    manifest = load_manifest(settings)
    builder = GraphBuilder(manifest, settings)

    async with checkpointer_context(settings) as checkpointer:
        await checkpointer.setup()
        app.state.graph = await builder.build(checkpointer)
        yield
        await builder.aclose()


app = FastAPI(title="langchain-sldc-deep-agents", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness/readiness probe for Cloud Run."""
    return {"status": "ok"}


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(request: InvokeRequest) -> InvokeResponse:
    """Synchronously run the agent graph to completion for a given task."""
    config = {"configurable": {"thread_id": request.thread_id}}
    result = await app.state.graph.ainvoke({"task": request.task}, config=config)
    return InvokeResponse(
        thread_id=request.thread_id,
        final_summary=result.get("final_summary"),
        review_report=result.get("review_report"),
    )


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    """Accept a GitHub issue/PR webhook and run the agent in the background.

    Returns 200 immediately (per .claude/architecture.md's happy-path flow)
    while the graph runs as a FastAPI background task. On Cloud Run this
    should be swapped for a Cloud Tasks enqueue so work survives instance
    scale-down; that's a deployment concern, not a graph-logic one, so it's
    left as the natural next step here.
    """
    settings = get_settings()
    payload = await request.body()
    _verify_github_signature(payload, x_hub_signature_256, settings.github_webhook_secret)

    body: dict[str, Any] = await request.json()
    task = _extract_task(body)
    thread_id = str((body.get("issue") or body.get("pull_request") or {}).get("number", "webhook"))

    background_tasks.add_task(_run_graph_background, task, thread_id)
    return {"status": "accepted", "thread_id": thread_id}


@app.post("/schedule/nightly-review")
async def nightly_review(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Entry point for the Cloud Scheduler nightly tech-debt scan."""
    background_tasks.add_task(_run_graph_background, "Nightly tech debt review", "nightly")
    return {"status": "accepted"}


def _extract_task(webhook_body: dict[str, Any]) -> str:
    """Pull a human-readable task description out of a GitHub webhook payload."""
    issue = webhook_body.get("issue") or webhook_body.get("pull_request")
    if issue:
        return str(issue.get("title", "Untitled"))
    comment = webhook_body.get("comment")
    if comment:
        return str(comment.get("body", ""))
    return "Unknown GitHub event"


def _verify_github_signature(payload: bytes, signature: str | None, secret: str | None) -> None:
    """Reject webhook requests that don't carry a valid HMAC signature.

    Skipped entirely when no secret is configured, which is the case for
    local development against the docker-compose mocks.

    Raises:
        HTTPException: 401 if the signature is missing or doesn't match.
    """
    if not secret:
        return
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing or malformed webhook signature")
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


async def _run_graph_background(task: str, thread_id: str) -> None:
    """Run the compiled graph for a background webhook/scheduler trigger.

    Exceptions are caught and logged rather than propagated — there is no
    HTTP request left to return an error to by the time this runs.
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        result = await app.state.graph.ainvoke({"task": task}, config=config)
        logger.info("Background run '%s' finished: %s", thread_id, result.get("final_summary"))
    except Exception:
        logger.exception("Background run '%s' failed", thread_id)
