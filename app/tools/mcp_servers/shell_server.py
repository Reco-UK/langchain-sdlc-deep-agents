"""Minimal first-party MCP server exposing sandboxed shell and lint tools.

No public MCP server exposes generic shell execution (for good reason —
see .claude/architecture.md's Security Architecture table: "Shell commands
run in restricted directory /workspace. Path traversal prevented."). This
server fills that one gap for the `coder`/`reviewer` nodes while keeping
the same process-isolation and tool-discovery model as every other MCP
server declared in agents.yaml.

Run standalone for local testing:
    python -m app.tools.mcp_servers.shell_server
"""

from __future__ import annotations

import asyncio
import os
import shlex
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("shell")

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace")).resolve()


def _resolve_within_workspace(relative_path: str) -> Path:
    """Resolve a path against WORKSPACE_ROOT, rejecting any traversal outside it."""
    candidate = (WORKSPACE_ROOT / relative_path).resolve()
    if not candidate.is_relative_to(WORKSPACE_ROOT):
        raise ValueError(f"Path '{relative_path}' escapes the workspace sandbox")
    return candidate


async def _run(command: list[str], cwd: Path) -> str:
    """Run a command with no shell interpolation, capturing combined output."""
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    output = stdout.decode(errors="replace")
    if process.returncode != 0:
        return f"[exit code {process.returncode}]\n{output}"
    return output


@mcp.tool()
async def run_shell_command(command: str, working_directory: str = ".") -> str:
    """Run a shell command inside the sandboxed workspace.

    Args:
        command: The command to execute, e.g. "pytest tests/unit". Parsed
            with `shlex.split` and run without a shell, so pipes/redirects
            are not supported — this is intentional, not a bug.
        working_directory: Path relative to WORKSPACE_ROOT to run the command in.

    Returns:
        Combined stdout/stderr, prefixed with the exit code on failure.
    """
    cwd = _resolve_within_workspace(working_directory)
    return await _run(shlex.split(command), cwd)


@mcp.tool()
async def run_linter(target: str = ".") -> str:
    """Run `ruff check` against a path inside the sandboxed workspace.

    Args:
        target: Path relative to WORKSPACE_ROOT to lint.

    Returns:
        Ruff's output, prefixed with the exit code on failure.
    """
    cwd = _resolve_within_workspace(target)
    return await _run(["ruff", "check", "."], cwd)


if __name__ == "__main__":
    mcp.run(transport="stdio")
