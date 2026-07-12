"""Integration tests that exercise the FastAPI app against real compose services.

Run with: docker compose up -d && pytest tests/integration -m integration
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(
    reason="Requires `docker compose up -d` (postgres/redis/qdrant/ollama) — "
    "run manually or in CI's integration stage."
)
def test_health_endpoint_returns_ok() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
