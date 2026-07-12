"""Unit tests for app.llm_factory."""

from __future__ import annotations

import pytest
from langchain_ollama import ChatOllama

from app.config import Settings
from app.exceptions import ConfigurationError
from app.llm_factory import build_chat_model, get_model_for_preset


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_build_chat_model_ollama_needs_no_api_key() -> None:
    preset = {"provider": "ollama", "model": "llama3.2", "temperature": 0.3}
    model = build_chat_model(preset, _settings())
    assert isinstance(model, ChatOllama)
    assert model.model == "llama3.2"


def test_build_chat_model_rejects_unsupported_provider() -> None:
    preset = {"provider": "bedrock", "model": "whatever"}
    with pytest.raises(ConfigurationError, match="Unsupported provider"):
        build_chat_model(preset, _settings())


def test_build_chat_model_requires_model_name() -> None:
    preset = {"provider": "ollama"}
    with pytest.raises(ConfigurationError, match="missing a 'model'"):
        build_chat_model(preset, _settings())


def test_build_chat_model_requires_anthropic_api_key() -> None:
    preset = {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"}
    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        build_chat_model(preset, _settings(anthropic_api_key=None))


def test_get_model_for_preset_falls_back_to_configured_provider() -> None:
    presets = {"coding": {"provider": "anthropic", "model": "llama3.2", "temperature": 0.2}}
    settings = _settings(anthropic_api_key=None, fallback_provider="ollama")
    model = get_model_for_preset("coding", presets, settings)
    assert isinstance(model, ChatOllama)


def test_get_model_for_preset_unknown_name_raises() -> None:
    with pytest.raises(ConfigurationError, match="Unknown model preset"):
        get_model_for_preset("nonexistent", {}, _settings())
