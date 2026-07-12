"""Centralized runtime configuration for langchain-sldc-deep-agents.

All environment differences (local Docker Compose vs. GCP Cloud Run) are
expressed as environment variables and resolved here — nothing else in the
codebase should call `os.environ` directly. See .claude/configuration.md
for the full environment variable reference table.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Environment ---
    environment: str = Field(default="local", description="local | ci | staging | production")

    # --- LLM providers ---
    default_provider: str = Field(default="ollama")
    fallback_provider: str | None = Field(default=None)
    ollama_base_url: str = Field(default="http://localhost:11434")
    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)

    # --- State backends ---
    postgres_dsn: str = Field(default="sqlite:///memory.db")
    redis_url: str | None = Field(default=None)
    vector_db_url: str | None = Field(default=None)

    # --- Contextual ingestion ---
    context_source: str = Field(default="github", description="github | jira")

    # --- GitHub ---
    github_token: str | None = Field(default=None)
    github_repo: str | None = Field(default=None)
    github_issue_number: str | None = Field(default=None)
    github_webhook_secret: str | None = Field(default=None)

    # --- JIRA ---
    jira_url: str | None = Field(default=None)
    jira_api_token: str | None = Field(default=None)
    jira_key: str | None = Field(default=None)

    # --- Confluence ---
    confluence_url: str | None = Field(default=None)
    confluence_api_token: str | None = Field(default=None)

    # --- GCP ---
    gcp_project: str | None = Field(default=None)
    gcp_location: str = Field(default="us-central1")
    task_queue: str | None = Field(default=None)
    cloud_run_url: str | None = Field(default=None)
    task_sa_email: str | None = Field(default=None)

    # --- Headless CLI task input ---
    task: str | None = Field(default=None)

    # --- Sandbox ---
    workspace_root: Path = Field(default=Path("/workspace"))

    # --- Agent manifest ---
    agents_manifest_path: Path = Field(default=Path("agents.yaml"))

    @property
    def is_ci(self) -> bool:
        """True when running inside a CI pipeline (uses in-memory SQLite state)."""
        return self.environment == "ci"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    Cached because pydantic-settings re-reads and re-validates every
    environment variable on each instantiation, which is wasted work once
    the process has started.
    """
    return Settings()


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structured, single-line logging for local dev and Cloud Logging.

    Cloud Run ships stdout to Cloud Logging automatically; a flat
    key=value format is easy to grep locally and still parses cleanly
    there, so we avoid pulling in a structured-logging dependency.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s",
    )
