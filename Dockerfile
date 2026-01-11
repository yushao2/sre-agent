# syntax=docker/dockerfile:1.4

# =============================================================================
# Base stage
# =============================================================================
FROM python:3.10-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# =============================================================================
# Builder stage
# =============================================================================
FROM base AS builder

COPY pyproject.toml ./
COPY src ./src

RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install .

# =============================================================================
# API Server
# =============================================================================
FROM base AS api

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["python", "-m", "agent.server"]

# =============================================================================
# Celery Worker
# =============================================================================
FROM base AS worker

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src

RUN useradd --create-home appuser
USER appuser

CMD ["celery", "-A", "agent.tasks", "worker", "--loglevel=info", "-Q", "llm"]

# =============================================================================
# Celery Beat (Scheduler)
# =============================================================================
FROM base AS beat

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src

RUN useradd --create-home appuser
USER appuser

CMD ["celery", "-A", "agent.tasks", "beat", "--loglevel=info"]

# =============================================================================
# MCP Servers (shared base)
# =============================================================================
FROM base AS mcp-base

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src

RUN useradd --create-home appuser
USER appuser

# MCP Jira
FROM mcp-base AS mcp-jira
CMD ["python", "-m", "mcp_servers.jira.server"]

# MCP Confluence
FROM mcp-base AS mcp-confluence
CMD ["python", "-m", "mcp_servers.confluence.server"]

# MCP GitLab
FROM mcp-base AS mcp-gitlab
CMD ["python", "-m", "mcp_servers.gitlab.server"]
