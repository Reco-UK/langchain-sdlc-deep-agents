"""Custom exception hierarchy for langchain-sldc-deep-agents.

Catching a narrow exception (ConnectionError, ValueError, ...) at the point
of failure and re-raising as `AgentError` lets callers at the graph/CLI
boundary handle all agent failures uniformly without needing to know which
node or tool produced the original error.
"""


class AgentError(Exception):
    """Base exception for all agent-related failures."""


class ConfigurationError(AgentError):
    """Raised when agents.yaml or environment configuration is invalid."""


class ToolExecutionError(AgentError):
    """Raised when an MCP tool call fails, times out, or is denied by the sandbox."""


class GraphCompilationError(AgentError):
    """Raised when the LangGraph graph cannot be built from agents.yaml."""
