# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Node is required for the npx-launched MCP servers (github/jira/confluence/filesystem).
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# uv is required for the uvx-launched git MCP server.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY pyproject.toml ./

# --- dev: full dependency set, source mounted at runtime via docker-compose ---
FROM base AS dev
RUN pip install --no-cache-dir -e ".[dev]" --no-build-isolation || pip install --no-cache-dir .[dev]
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- builder: production dependencies only ---
FROM base AS builder
RUN pip install --no-cache-dir .
COPY app ./app
COPY prompts ./prompts
COPY agents.yaml ./

# --- runtime: slim final image for Cloud Run / CI ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/app ./app
COPY --from=builder /app/prompts ./prompts
COPY --from=builder /app/agents.yaml ./

RUN useradd --create-home --uid 1000 agent \
    && mkdir -p /workspace \
    && chown -R agent:agent /workspace /app
USER agent

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
