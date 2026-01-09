# syntax=docker/dockerfile:1.4

# ============================================================================
# Base stage - shared dependencies
# ============================================================================
FROM python:3.10-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# ============================================================================
# Builder stage - install dependencies
# ============================================================================
FROM base as builder

# Copy project files
COPY pyproject.toml ./
COPY src ./src

# Create virtual environment and install dependencies
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install -e ".[webhook]"

# ============================================================================
# Agent runtime image
# ============================================================================
FROM base as agent

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src
COPY examples ./examples

# Create non-root user
RUN useradd --create-home --shell /bin/bash agent
USER agent

EXPOSE 8000

# Default command runs the HTTP server
CMD ["python", "-m", "agent.server"]

# ============================================================================
# MCP Server base image
# ============================================================================
FROM base as mcp-base

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src ./src

# Create non-root user
RUN useradd --create-home --shell /bin/bash mcp
USER mcp

# ============================================================================
# Jira MCP Server
# ============================================================================
FROM mcp-base as mcp-jira

ENV MCP_SERVER_NAME=jira

CMD ["python", "-m", "mcp_servers.jira.server"]

# ============================================================================
# Confluence MCP Server
# ============================================================================
FROM mcp-base as mcp-confluence

ENV MCP_SERVER_NAME=confluence

CMD ["python", "-m", "mcp_servers.confluence.server"]

# ============================================================================
# GitLab MCP Server
# ============================================================================
FROM mcp-base as mcp-gitlab

ENV MCP_SERVER_NAME=gitlab

CMD ["python", "-m", "mcp_servers.gitlab.server"]
