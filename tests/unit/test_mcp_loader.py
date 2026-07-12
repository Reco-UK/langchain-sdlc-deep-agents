"""Unit tests for app.tools.mcp_loader.MCPToolRegistry."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.exceptions import ConfigurationError
from app.tools.mcp_loader import MCPToolRegistry


def test_resolve_env_expands_from_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
    registry = MCPToolRegistry({}, Settings(_env_file=None))
    resolved = registry._resolve_env({"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"})
    assert resolved == {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_test123"}


def test_resolve_env_defaults_missing_var_to_empty_string() -> None:
    registry = MCPToolRegistry({}, Settings(_env_file=None))
    resolved = registry._resolve_env({"X": "${DEFINITELY_NOT_SET_XYZ}"})
    assert resolved == {"X": ""}


async def test_get_tools_raises_for_unknown_tool() -> None:
    registry = MCPToolRegistry({}, Settings(_env_file=None))
    with pytest.raises(ConfigurationError, match="not provided by any"):
        await registry.get_tools(["nonexistent_tool"])
