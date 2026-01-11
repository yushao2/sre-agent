# syntax=docker/dockerfile:1.4

# -----------------------------------------------------------------------------
# Stage: uv binaries (copy into CentOS-based images)
# -----------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:latest AS uvbin

# -----------------------------------------------------------------------------
# Stage: base (your CentOS-based Python 3.10 image)
# -----------------------------------------------------------------------------
ARG PYTHON_BASE_IMAGE=your-centos-python:3.10
FROM ${PYTHON_BASE_IMAGE} AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install uv (Option A): just copy the binaries in
COPY --from=uvbin /uv /uvx /usr/local/bin/

# Optional sanity check (keeps failures obvious during build)
RUN uv --version

# -----------------------------------------------------------------------------
# Stage: builder (create venv + install deps)
# -----------------------------------------------------------------------------
FROM base AS builder

# Copy enough for packaging (README is referenced in pyproject.toml)
COPY pyproject.toml README.md ./
COPY src ./src

# Create venv and install the package + extras needed by API/worker/MCP
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install with the extras your containers actually import/use
RUN uv pip install ".[server,celery,database,mcp]"

# -----------------------------------------------------------------------------
# Stage: API Server
# -----------------------------------------------------------------------------
FROM base AS api
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src

# Create a non-root user (assumes useradd exists in your CentOS base)
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000
CMD ["python", "-m", "agent.server"]

# -----------------------------------------------------------------------------
# Stage: Celery Worker
# -----------------------------------------------------------------------------
FROM base AS worker
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src

RUN useradd --create-home --uid 10001 appuser
USER appuser

CMD ["celery", "-A", "agent.tasks", "worker", "--loglevel=info", "-Q", "llm"]

# -----------------------------------------------------------------------------
# Stage: Celery Beat
# -----------------------------------------------------------------------------
FROM base AS beat
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src

RUN useradd --create-home --uid 10001 appuser
USER appuser

CMD ["celery", "-A", "agent.tasks", "beat", "--loglevel=info"]

# -----------------------------------------------------------------------------
# Stage: MCP Servers (shared base)
# -----------------------------------------------------------------------------
FROM base AS mcp-base
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src

RUN useradd --create-home --uid 10001 appuser
USER appuser

# MCP Jira (read-only)
FROM mcp-base AS mcp-jira
CMD ["python", "-m", "mcp_servers.jira.server"]

# MCP Confluence (read-only)
FROM mcp-base AS mcp-confluence
CMD ["python", "-m", "mcp_servers.confluence.server"]

# MCP GitLab (read-only)
FROM mcp-base AS mcp-gitlab
CMD ["python", "-m", "mcp_servers.gitlab.server"]
