# AI SRE Agent

Production-ready AI agent for incident management and support triage, powered by Claude.

## Features

- **Incident Summarization**: Generate structured summaries with timeline, root cause, and recommendations
- **Ticket Triage**: Categorize and prioritize support tickets automatically
- **Root Cause Analysis**: Deep-dive analysis with contributing factors and fixes
- **Interactive Chat**: Ask SRE-related questions and get expert guidance
- **RAG Support**: Store and retrieve similar past incidents using local ChromaDB
- **MCP Servers**: Read-only integrations with Jira, Confluence, and GitLab

## Installation

### Minimal (Local Development)

```bash
# Install with minimal dependencies (just LangChain + Anthropic)
pip install -e .

# Set your API key
export ANTHROPIC_API_KEY=your-key

# Run the demo
python -m agent.local demo
```

### Full Installation (Production)

```bash
# Install all dependencies
pip install -e ".[all]"

# Or install specific extras
pip install -e ".[server]"      # FastAPI server
pip install -e ".[celery]"      # Celery + Redis
pip install -e ".[database]"    # PostgreSQL support
pip install -e ".[mcp]"         # MCP integrations (Jira, Confluence, GitLab)
pip install -e ".[rag]"         # RAG with ChromaDB
```

## Quick Start

### Interactive Mode

```bash
python -m agent.local interactive
```

### CLI Commands

```bash
# Chat with the agent
python -m agent.local chat "What causes connection pool exhaustion?"

# Summarize an incident
python -m agent.local summarize \
  --key INC-123 \
  --summary "Database connection timeout" \
  --description "Users seeing 504 errors..."

# Triage a ticket
python -m agent.local triage \
  --key TICKET-456 \
  --summary "Cannot login" \
  --description "Getting 500 error on login page"

# Load from JSON file
python -m agent.local summarize --file examples/sample_incident.json

# Run demo with sample data
python -m agent.local demo
```

### Python Library

```python
from agent import run_summarize, run_triage, run_chat

# Chat with the agent
response = run_chat("What should I check during a memory leak?")
print(response)

# Summarize an incident
summary = run_summarize({
    "key": "INC-123",
    "summary": "API latency spike",
    "description": "p99 went from 100ms to 5s...",
    "status": "Resolved",
    "priority": "High",
})
print(summary)

# Triage a ticket
result = run_triage({
    "key": "TICKET-789",
    "summary": "Export not working",
    "description": "PDF export button does nothing...",
})
print(result)
```

### Async Usage

```python
import asyncio
from agent import SREAgentSimple

async def main():
    agent = SREAgentSimple()
    
    # Summarize with full control
    result = await agent.summarize_incident_simple({
        "key": "INC-123",
        "summary": "High memory usage",
        "description": "Service OOMKilled repeatedly",
        "comments": {
            "comments": [
                {"author": "oncall", "body": "Investigating...", "created": "2024-01-15T10:00:00Z"}
            ]
        }
    })
    print(result)

asyncio.run(main())
```

---

## RAG: Similar Incident Search

Store resolved incidents and search for similar ones during RCA.

```bash
# Install RAG dependencies
pip install -e ".[rag]"
```

```python
from agent import IncidentKnowledgeBase

# Create knowledge base with local file storage
# Data persists in ./data/incidents across restarts
kb = IncidentKnowledgeBase(persist_directory="./data/incidents")

# Add resolved incidents
kb.add_incident({
    "key": "INC-100",
    "summary": "Database connection pool exhausted",
    "description": "Connection leak in reporting service",
    "root_cause": "Missing connection.close() in finally block",
    "resolution": "Added proper connection cleanup with context manager",
    "status": "Resolved",
    "priority": "Critical",
})

kb.add_incident({
    "key": "INC-101", 
    "summary": "API timeout during peak traffic",
    "description": "Upstream service rate limiting",
    "root_cause": "No circuit breaker, cascading failures",
    "resolution": "Added circuit breaker and retry with backoff",
})

# Search for similar incidents
similar = kb.search("connection timeout errors", k=3)
for inc in similar:
    print(f"{inc['key']}: {inc['summary']} (score: {inc['score']:.2f})")
    print(f"  Root cause: {inc['root_cause']}")

# Use in-memory storage for testing (no persistence)
kb_test = IncidentKnowledgeBase()  # No persist_directory
```

### Runbook Store

```python
from agent import RunbookStore

store = RunbookStore(persist_directory="./data/runbooks")

# Add runbooks
store.add_runbook(
    id="rb-db-conn",
    title="Database Connection Pool Troubleshooting",
    content="""
## Symptoms
- 504 Gateway Timeout errors
- "Connection pool exhausted" in logs

## Investigation Steps
1. Check current pool usage: `SELECT count(*) FROM pg_stat_activity`
2. Look for long-running queries
3. Check for connection leaks in recent deployments

## Resolution
- Restart affected service pods
- Kill long-running queries if safe
- Scale up pool size temporarily
    """,
    tags=["database", "connection-pool", "troubleshooting"],
)

# Search runbooks
results = store.search("connection timeout database")
for rb in results:
    print(f"{rb['id']}: {rb['title']}")
```

---

## MCP Servers: Local Testing

Test MCP servers locally before deploying.

```bash
# Install MCP dependencies
pip install -e ".[mcp]"
```

### Test Jira MCP Server

```bash
# Set environment variables
export JIRA_URL=https://jira.company.com
export JIRA_USERNAME=your-username
export JIRA_TOKEN=your-token  # or JIRA_API_TOKEN or JIRA_PASSWORD

# Run tests
python -m agent.mcp_test jira

# Interactive mode
python -m agent.mcp_test jira --interactive

# Check env vars only
python -m agent.mcp_test jira --check-only
```

### Test Confluence MCP Server

```bash
export CONFLUENCE_URL=https://confluence.company.com
export CONFLUENCE_USERNAME=your-username
export CONFLUENCE_TOKEN=your-token

python -m agent.mcp_test confluence
```

### Test GitLab MCP Server

```bash
export GITLAB_URL=https://gitlab.company.com
export GITLAB_TOKEN=your-pat

python -m agent.mcp_test gitlab
python -m agent.mcp_test gitlab --interactive
```

### Using Env Files

```bash
# Create .env.jira with your credentials
echo "JIRA_URL=https://jira.company.com" > .env.jira
echo "JIRA_USERNAME=me@company.com" >> .env.jira
echo "JIRA_TOKEN=secret" >> .env.jira

# Load and test
python -m agent.mcp_test jira --env-file .env.jira
```

### Run MCP Server Locally (stdio mode)

```bash
# Jira server
python -m mcp_servers.jira.server

# Confluence server  
python -m mcp_servers.confluence.server

# GitLab server
python -m mcp_servers.gitlab.server
```

### Run MCP Server (HTTP mode)

```bash
export MCP_TRANSPORT=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8080

python -m mcp_servers.jira.server
# Server available at http://localhost:8080/mcp
```

---

## Production Deployment

For production with async processing, webhooks, and horizontal scaling:

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Kubernetes                                  │
│                                                                         │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐   │
│  │   Ingress   │────▶│  API Server │────▶│      Redis (Broker)     │   │
│  └─────────────┘     │  (FastAPI)  │     └───────────┬─────────────┘   │
│                      └─────────────┘                 │                  │
│                                                      ▼                  │
│                      ┌───────────────────────────────────────────┐     │
│                      │           Celery Workers (N)              │     │
│                      │  ┌─────────┐ ┌─────────┐ ┌─────────┐     │     │
│                      │  │Worker 1 │ │Worker 2 │ │Worker N │     │     │
│                      │  └────┬────┘ └────┬────┘ └────┬────┘     │     │
│                      └───────┼───────────┼───────────┼───────────┘     │
│                              │           │           │                  │
│                              ▼           ▼           ▼                  │
│                      ┌─────────────────────────────────────┐           │
│                      │         Anthropic Claude API        │           │
│                      └─────────────────────────────────────┘           │
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │   PostgreSQL    │  (Task results, webhook logs)                     │
│  └─────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Docker Compose

```bash
export ANTHROPIC_API_KEY=your-key
docker-compose up -d
```

### Kubernetes (Helm)

```bash
# Add Bitnami repo
helm repo add bitnami https://charts.bitnami.com/bitnami

# Update dependencies
cd helm/ai-sre-agent && helm dependency update

# Create secret
kubectl create secret generic ai-sre-agent-secrets \
  --from-literal=ANTHROPIC_API_KEY=your-key

# Install
helm install ai-sre-agent ./helm/ai-sre-agent \
  --set secrets.existingSecret=ai-sre-agent-secrets
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/summarize` | POST | Summarize an incident |
| `/api/v1/triage` | POST | Triage a ticket |
| `/api/v1/rca` | POST | Root cause analysis |
| `/api/v1/chat` | POST | Chat with agent |
| `/api/v1/tasks/{id}` | GET | Get task status/result |
| `/webhooks/jira` | POST | Jira webhook handler |
| `/webhooks/pagerduty` | POST | PagerDuty webhook handler |
| `/health` | GET | Health check |

### Example: Submit Incident

```bash
curl -X POST http://localhost:8000/api/v1/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {
      "key": "INC-123",
      "summary": "Database connection pool exhausted",
      "description": "Users experiencing timeouts",
      "priority": "critical"
    }
  }'

# Response: {"task_id": "abc-123", "status": "pending", "result_url": "/api/v1/tasks/abc-123"}
```

### Example: Poll for Result

```bash
curl http://localhost:8000/api/v1/tasks/abc-123

# Response: {"task_id": "abc-123", "status": "completed", "result": {"summary": "..."}}
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key |
| `MODEL_NAME` | No | `claude-sonnet-4-20250514` | Claude model |
| `REDIS_URL` | No* | `redis://localhost:6379/0` | Redis URL (*required for server) |
| `DATABASE_URL` | No | - | PostgreSQL URL |
| `CELERY_CONCURRENCY` | No | `4` | Worker concurrency |

## Project Structure

```
ai-sre-agent/
├── src/agent/
│   ├── agent.py          # Core SREAgentSimple class
│   ├── prompts.py        # System prompts and formatters
│   ├── local.py          # CLI and sync wrappers
│   ├── rag.py            # RAG with ChromaDB (IncidentKnowledgeBase, RunbookStore)
│   ├── mcp_test.py       # MCP server testing utilities
│   ├── server.py         # FastAPI production server
│   ├── tasks.py          # Celery task definitions
│   └── database.py       # SQLAlchemy models
├── src/mcp_servers/
│   ├── jira/server.py    # Jira Data Center MCP (read-only)
│   ├── confluence/server.py  # Confluence Data Center MCP (read-only)
│   └── gitlab/server.py  # GitLab MCP (read-only)
├── examples/
│   ├── simple_usage.py   # Python usage examples
│   └── sample_incident.json
├── helm/ai-sre-agent/    # Kubernetes Helm chart
├── docker-compose.yml    # Local development stack
└── Dockerfile            # Multi-stage build (CentOS-based)
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src

# Type check  
mypy src
```

## License

MIT
