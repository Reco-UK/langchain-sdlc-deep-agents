"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Ensure each test observes a fresh Settings() built from its own env vars.

    `get_settings()` is `lru_cache`d for production efficiency, which would
    otherwise leak env-var overrides from one test into the next.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
