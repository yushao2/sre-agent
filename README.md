# AI SRE Agent

An extensible AI agent for incident management and support triage, built with LangChain and MCP (Model Context Protocol).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Runtime                          │
│  ┌───────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │   LangChain   │  │     RAG     │  │  Incident Tools  │  │
│  │  Orchestrator │  │   Engine    │  │   & Prompts      │  │
│  └───────┬───────┘  └──────┬──────┘  └────────┬─────────┘  │
│          │                 │                   │            │
│          └─────────────────┼───────────────────┘            │
│                            │                                │
│                    ┌───────▼───────┐                        │
│                    │  MCP Client   │                        │
│                    └───────┬───────┘                        │
└────────────────────────────┼────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  MCP Server   │   │  MCP Server   │   │  MCP Server   │
│     Jira      │   │  Confluence   │   │    GitLab     │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Quick Start with uv

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/yourorg/ai-sre-agent.git
cd ai-sre-agent

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run the demo
sre-agent demo
```

## Alternative: pip install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Project Structure

```
ai-sre-agent/
├── src/
│   ├── agent/                  # Agent runtime
│   │   ├── __init__.py
│   │   ├── agent.py           # Main LangChain agent
│   │   ├── cli.py             # CLI entry point
│   │   ├── mcp_client.py      # MCP client wrapper
│   │   ├── prompts.py         # System prompts
│   │   └── rag.py             # RAG engine
│   │
│   ├── mcp_servers/           # MCP server implementations
│   │   ├── jira/
│   │   ├── confluence/
│   │   └── gitlab/
│   │
│   └── config/
│       └── settings.py        # Configuration
│
├── tests/                     # Test suite
├── examples/                  # Example scripts
├── pyproject.toml            # Project configuration
└── README.md
```

## Usage

### CLI Commands

```bash
# Run demo with sample data
sre-agent demo

# Summarize an incident
sre-agent summarize INC-123

# Summarize with local data file
sre-agent summarize INC-123 --json-file incident.json

# Interactive chat
sre-agent chat

# Triage a ticket
sre-agent triage SUPPORT-456

# Root cause analysis
sre-agent rca INC-123
```

### As a Library

```python
import asyncio
from agent import SREAgentSimple

async def main():
    agent = SREAgentSimple(
        anthropic_api_key="your-key",
        model_name="claude-sonnet-4-20250514",
    )
    
    incident_data = {
        "key": "INC-123",
        "summary": "Database connection issues",
        "description": "...",
        "comments": {"comments": [...], "total": 5},
    }
    
    summary = await agent.summarize_incident_simple(incident_data)
    print(summary)

asyncio.run(main())
```

## Development

### Setup dev environment

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[all]"

# Install pre-commit hooks
pre-commit install
```

### Run tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_mcp_servers.py -v
```

### Code quality

```bash
# Format and lint (via pre-commit)
pre-commit run --all-files

# Or run individually
ruff check src tests --fix
ruff format src tests
mypy src
```

## MCP Servers

Each MCP server is independent and can be run standalone:

```bash
# Run individual servers
mcp-jira
mcp-confluence
mcp-gitlab
```

## Webhook Integration

For Jira Service Desk integration:

```bash
# Install webhook dependencies
uv pip install -e ".[webhook]"

# Run webhook server
uvicorn examples.webhook_handler:app --host 0.0.0.0 --port 8000
```

Then configure Jira webhooks to POST to `https://your-server/webhook/jira`.

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Anthropic API key | Yes |
| `JIRA_URL` | Jira instance URL | For Jira integration |
| `JIRA_USERNAME` | Jira username | For Jira integration |
| `JIRA_API_TOKEN` | Jira API token | For Jira integration |
| `CONFLUENCE_URL` | Confluence URL | For Confluence integration |
| `GITLAB_URL` | GitLab URL | For GitLab integration |
| `GITLAB_TOKEN` | GitLab token | For GitLab integration |

## Extending

### Adding a new MCP server

1. Create a new directory under `src/mcp_servers/`
2. Implement `server.py` with your tools
3. Add entry point in `pyproject.toml`
4. Register in `agent/mcp_client.py`

### Adding new capabilities

Add new prompts in `agent/prompts.py` for different use cases.

## License

MIT
