# AI SRE Agent

Production-ready AI agent for incident management and support triage, powered by Claude.

## Features

- **Incident Summarization**: Generate structured summaries with timeline, root cause, and recommendations
- **Ticket Triage**: Categorize and prioritize support tickets automatically
- **Root Cause Analysis**: Deep-dive analysis with contributing factors and fixes
- **Interactive Chat**: Ask SRE-related questions and get expert guidance

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
pip install -e ".[mcp]"         # MCP integrations
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
│   ├── server.py         # FastAPI production server
│   ├── tasks.py          # Celery task definitions
│   └── database.py       # SQLAlchemy models
├── examples/
│   ├── simple_usage.py   # Python usage examples
│   └── sample_incident.json
├── helm/ai-sre-agent/    # Kubernetes Helm chart
├── docker-compose.yml    # Local development stack
└── Dockerfile            # Multi-stage build
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
