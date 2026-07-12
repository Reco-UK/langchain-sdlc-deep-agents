"""Maps `agents.yaml` model presets to concrete LangChain chat models.

Only three LLM wrapper packages are permitted in this project (see
.claude/config.md, "No New LLM Wrappers"): langchain-ollama,
langchain-anthropic, and langchain-openai. Supporting a fourth provider
means adding a branch here, not adding a dependency.
"""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.config import Settings
from app.exceptions import ConfigurationError

_SUPPORTED_PROVIDERS = frozenset({"ollama", "anthropic", "openai"})


def build_chat_model(preset: dict[str, Any], settings: Settings) -> BaseChatModel:
    """Instantiate the chat model described by one `model_presets` entry.

    Args:
        preset: One entry from `agents.yaml`'s `graph.model_presets`, e.g.
            `{"provider": "anthropic", "model": "claude-3-5-sonnet-20241022", "temperature": 0.2}`.
        settings: Resolved application settings (API keys, base URLs).

    Returns:
        A configured LangChain chat model ready for `.ainvoke()` / `.bind_tools()`.

    Raises:
        ConfigurationError: If the preset names an unsupported provider, or
            the required API key for that provider is missing.
    """
    provider = preset.get("provider")
    model = preset.get("model")
    temperature = preset.get("temperature", 0.3)

    if not model:
        raise ConfigurationError(f"Model preset is missing a 'model' name: {preset}")

    if provider not in _SUPPORTED_PROVIDERS:
        raise ConfigurationError(
            f"Unsupported provider '{provider}'. Must be one of {sorted(_SUPPORTED_PROVIDERS)}."
        )

    if provider == "ollama":
        return ChatOllama(model=model, base_url=settings.ollama_base_url, temperature=temperature)

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY is required for provider 'anthropic'.")
        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            timeout=60,
        )

    # provider == "openai"
    if not settings.openai_api_key:
        raise ConfigurationError("OPENAI_API_KEY is required for provider 'openai'.")
    return ChatOpenAI(model=model, api_key=settings.openai_api_key, temperature=temperature)


def get_model_for_preset(
    preset_name: str,
    model_presets: dict[str, dict[str, Any]],
    settings: Settings,
) -> BaseChatModel:
    """Resolve a named preset from `agents.yaml` into a chat model.

    Args:
        preset_name: Key into `graph.model_presets`, e.g. `"coding"`.
        model_presets: The full `graph.model_presets` mapping from agents.yaml.
        settings: Resolved application settings.

    Returns:
        A configured chat model. If the preset's primary provider is
        missing its API key and `settings.fallback_provider` is set, we
        retry with the fallback provider using the *same* model name — this
        only works if that model name is valid for the fallback provider
        too, so cross-provider fallback presets should be tested explicitly.

    Raises:
        ConfigurationError: If `preset_name` is not defined in agents.yaml,
            or no working provider (primary or fallback) is configured.
    """
    if preset_name not in model_presets:
        raise ConfigurationError(f"Unknown model preset '{preset_name}' referenced in agents.yaml.")

    preset = model_presets[preset_name]
    try:
        return build_chat_model(preset, settings)
    except ConfigurationError:
        if not settings.fallback_provider or settings.fallback_provider == preset.get("provider"):
            raise
        fallback_preset = {**preset, "provider": settings.fallback_provider}
        return build_chat_model(fallback_preset, settings)
