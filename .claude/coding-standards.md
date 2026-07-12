# Coding Standards: Karpathy Guidelines

We adhere to Andrej Karpathy's philosophy of **clean, readable, and educational code**. This is a **mandatory skill** for all contributors to `langchain-sldc-deep-agents`.

---

## Core Principles

### 1. Clarity Over Cleverness
- Code should read like prose.
- Use descriptive variable and function names.
- Avoid opaque one-liners or overly complex abstractions.

### 2. Minimal Dependencies
- Before adding a new library, ask: "Could I write this in 20 lines of Python?"
- Prefer standard library and langchain primitives over niche packages.

### 3. Type Hints Everywhere
- All function signatures must have type hints.
- Use `Protocol` and `TypedDict` for complex data structures.
- Enable `mypy --strict` in CI.

### 4. Function Purity & Small Scope
- Functions should do one thing and do it well.
- Aim for functions under 20 lines.
- Prefer pure functions (no side effects) where possible.

### 5. Self-Documenting Code
- Comments explain *why*, not *what*.
- Use docstrings for all public APIs (Google or NumPy style).
- Examples in docstrings are encouraged.

### 6. Defensive & Explicit
- Validate inputs early (`assert` or `raise`).
- Handle edge cases explicitly.
- Favor `if`/`else` over clever but fragile logic.

### 7. Educational Value
- Code should be a learning resource.
- Use consistent patterns across the codebase.
- When using advanced features (e.g., asyncio, generics), add a comment explaining them.

---

## Example: Good Code (Karpathy-Approved)

```python
from typing import Optional, List
import asyncio

async def fetch_issue_details(
    issue_key: str,
    session: Optional[ClientSession] = None,
    timeout: int = 30
) -> dict:
    """
    Fetch JIRA issue details via MCP.

    Args:
        issue_key: The JIRA ticket identifier (e.g., "PROJ-123").
        session: Optional existing MCP session to reuse.
        timeout: Request timeout in seconds.

    Returns:
        Dict containing issue fields: summary, description, acceptance criteria.

    Raises:
        ValueError: If issue_key is empty or malformed.
        ConnectionError: If JIRA server is unreachable.
    """
    if not issue_key or not issue_key.startswith("PROJ-"):
        raise ValueError(f"Invalid issue key: {issue_key}")

    async with session or create_mcp_session() as mcp_session:
        # The actual fetch logic goes here
        response = await mcp_session.call_tool("get_issue", {"key": issue_key})
        return parse_jira_response(response)
```

## Example: Bad Code (Avoid)

```python
def get_issue(k, s=None, t=30):
    # Bad: unclear variable names, no types, no docs
    if s:
        return s.call("get", k)
    return call("get", k)
```

---

## How to Enforce Karpathy Standards

### 1. Pre-commit Hooks

File: `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        args: [--strict]
```

### 2. CI Checks

GitHub Actions will fail if code violates these standards.

### 3. Review Checklist

Reviewers must check:

- [ ] Does the code pass `ruff` and `mypy`?
- [ ] Are functions under 20 lines?
- [ ] Are there sufficient docstrings?
- [ ] Would I be happy to show this code to a junior engineer?
- [ ] Are type hints present on all function signatures?
- [ ] Are edge cases handled explicitly?

---

## Quick Reference: Karpathy Checklist

| Rule | Pass/Fail |
| :--- | :--- |
| Type hints present | ☐ |
| No opaque one-liners | ☐ |
| Functions < 20 lines | ☐ |
| Descriptive variable names | ☐ |
| Docstrings for public APIs | ☐ |
| Comments explain *why* | ☐ |
| Edge cases handled | ☐ |
| Dependency justified | ☐ |

---

## Python-Specific Standards

### Imports

- Standard library first, third-party second, local last.
- Avoid `from module import *`.
- Use absolute imports over relative.

### Naming Conventions

| Type | Convention | Example |
| :--- | :--- | :--- |
| Variables | `snake_case` | `user_request` |
| Functions | `snake_case` | `fetch_issue_details` |
| Classes | `PascalCase` | `NodeFactory` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Private methods | `_leading_underscore` | `_parse_response` |

### Async Patterns

- Prefer `async`/`await` over callback-based patterns.
- Use `asyncio.gather()` for concurrent operations.
- Always `await` coroutines.

### Error Handling

```python
# Good
try:
    result = await risky_operation()
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
    raise AgentError("Unable to reach service") from e

# Bad
try:
    result = await risky_operation()
except:
    pass  # Silent failure - never do this!
```

---

## Testing Standards

### Unit Tests (pytest)

- Test files live in `tests/unit/`.
- Name test files `test_*.py`.
- Name test functions `test_*`.
- Aim for > 80% coverage.

### Integration Tests

- Test files live in `tests/integration/`.
- Use `docker compose` for external dependencies.
- Mark with `@pytest.mark.integration`.

### Evaluation Tests

- Test files live in `tests/eval/`.
- Define golden tasks in `tests/fixtures/golden_tasks.json`.
- Compare agent output against expected results.

```python
# Example: Good test
def test_fetch_issue_details_success(mock_session):
    """Test successful JIRA issue fetch."""
    result = await fetch_issue_details("PROJ-123", session=mock_session)
    assert result["summary"] == "Fix login bug"
    assert "acceptance_criteria" in result

# Example: Bad test (too broad)
def test_fetch_issue_details():
    result = await fetch_issue_details("PROJ-123")
    assert result is not None  # Too vague!
```

---

## Summary

By following the Karpathy Coding Guidelines, we ensure that `langchain-sldc-deep-agents` remains:

- **Readable**: Code is self-documenting and easy to understand.
- **Maintainable**: Clean separation of concerns and minimal dependencies.
- **Educational**: Every file serves as a learning resource.
- **Reliable**: Type hints and defensive programming catch errors early.

**Remember:** Code is read far more often than it is written. Write for the reader.