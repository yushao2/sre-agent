# AI SRE Agent

Production-ready AI agent for incident management and support triage.

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
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        MCP Servers                               │   │
│  │  ┌───────────┐    ┌───────────────┐    ┌─────────────┐          │   │
│  │  │   Jira    │    │  Confluence   │    │   GitLab    │          │   │
│  │  └───────────┘    └───────────────┘    └─────────────┘          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │   PostgreSQL    │  (Task results, webhook logs)                     │
│  └─────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Async Task Processing**: Celery workers handle LLM calls without blocking
- **Horizontal Scaling**: Add workers to handle more concurrent requests
- **Rate Limiting**: Redis-based rate limiting per client
- **Webhook Support**: Jira, PagerDuty, and generic webhook handlers
- **Health Checks**: Kubernetes-ready liveness and readiness probes
- **Task Persistence**: PostgreSQL storage for results and audit logs

## Quick Start

### Local Development

```bash
# Install dependencies
uv venv && source .venv/bin/activate
uv pip install -e .

# Start infrastructure
docker-compose up -d redis postgres

# Set environment
export ANTHROPIC_API_KEY=your-key
export REDIS_URL=redis://localhost:6379/0
export DATABASE_URL=postgresql://sre_agent:sre_agent@localhost:5432/sre_agent

# Start API server
sre-agent serve

# Start worker (in another terminal)
sre-agent worker --concurrency 4
```

### Docker Compose

```bash
# Set your API key
export ANTHROPIC_API_KEY=your-key

# Start everything
docker-compose up -d

# Check logs
docker-compose logs -f api worker
```

### Kubernetes (Helm)

```bash
# Add Bitnami repo for Redis/PostgreSQL
helm repo add bitnami https://charts.bitnami.com/bitnami

# Update dependencies
cd helm/ai-sre-agent
helm dependency update

# Create secret
kubectl create secret generic ai-sre-agent-secrets \
  --from-literal=ANTHROPIC_API_KEY=your-key \
  --from-literal=JIRA_URL=https://your.atlassian.net \
  --from-literal=JIRA_USERNAME=email@example.com \
  --from-literal=JIRA_API_TOKEN=your-token

# Install
helm install ai-sre-agent ./helm/ai-sre-agent \
  --set secrets.existingSecret=ai-sre-agent-secrets
```

## API Usage

### Submit an Incident for Summarization

```bash
curl -X POST http://localhost:8000/api/v1/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {
      "key": "INC-123",
      "summary": "Database connection pool exhausted",
      "description": "Users experiencing timeouts",
      "priority": "critical",
      "comments": {
        "comments": [
          {"author": "oncall", "body": "Investigating connection leak"}
        ]
      }
    }
  }'

# Response:
# {"task_id": "abc-123", "status": "pending", "result_url": "/api/v1/tasks/abc-123"}
```

### Poll for Results

```bash
curl http://localhost:8000/api/v1/tasks/abc-123

# Response (when complete):
# {"task_id": "abc-123", "status": "completed", "result": {"summary": "..."}}
```

### Synchronous Mode (Testing Only)

```bash
curl -X POST http://localhost:8000/api/v1/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {...},
    "async_mode": false
  }'
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection URL |
| `DATABASE_URL` | No | - | PostgreSQL URL for persistence |
| `CELERY_CONCURRENCY` | No | `4` | Workers per Celery process |
| `MODEL_NAME` | No | `claude-sonnet-4-20250514` | Claude model to use |

### Helm Values

```yaml
# Use external Redis instead of subchart
redis:
  enabled: false
externalRedis:
  host: my-redis.example.com
  port: 6379
  existingSecret: my-redis-secret

# Use external PostgreSQL
postgresql:
  enabled: false
externalPostgresql:
  host: my-postgres.example.com
  port: 5432
  database: sre_agent
  existingSecret: my-postgres-secret

# Scale workers
worker:
  replicaCount: 5
  concurrency: 8
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 20
```

## Scaling Guide

### API Servers
- Stateless, scale horizontally
- 2+ replicas recommended for HA
- Use HPA based on CPU

### Celery Workers
- Each worker handles 1 LLM call at a time (prefetch=1)
- Scale based on queue depth
- `concurrency=4` means 4 concurrent tasks per pod
- For 100 concurrent requests: ~25 worker pods with concurrency=4

### Redis
- Standalone mode sufficient for most cases
- Enable replication for HA
- Monitor memory usage (task results stored here)

### PostgreSQL
- Optional but recommended for production
- Stores task results and webhook logs
- Enable for audit trail and debugging

## Monitoring

### Health Endpoints

- `GET /health` - Full dependency check
- `GET /health/live` - Liveness probe (is process running?)
- `GET /health/ready` - Readiness probe (can handle requests?)

### Celery Monitoring

```bash
# Active tasks
celery -A agent.tasks inspect active

# Queue length
celery -A agent.tasks inspect reserved

# Worker stats
celery -A agent.tasks inspect stats
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src

# Type check
mypy src
```

## License

MIT
