"""Unit tests for app.config.Settings."""

from __future__ import annotations

import pytest

from app.config import Settings, get_settings


def test_defaults_match_local_docker_compose(monkeypatch: pytest.MonkeyPatch) -> None:
    # `Settings` reads process env vars regardless of `_env_file`, and CI sets
    # ENVIRONMENT=ci at the job level — isolate from that explicitly rather
    # than relying on the ambient environment being empty.
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    settings = Settings(_env_file=None)
    assert settings.environment == "local"
    assert settings.default_provider == "ollama"
    assert settings.is_ci is False


def test_is_ci_true_when_environment_is_ci() -> None:
    settings = Settings(_env_file=None, environment="ci")
    assert settings.is_ci is True


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
