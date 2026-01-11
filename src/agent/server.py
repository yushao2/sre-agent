"""
Production HTTP Server for the AI SRE Agent.

This is the main API server that:
- Receives API requests and webhook events
- Submits tasks to Celery for async processing
- Provides health checks for Kubernetes
- Implements rate limiting via Redis

Architecture:
    Client -> FastAPI Server -> Redis (queue) -> Celery Workers
                                    |
                            PostgreSQL (results)
"""

import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import redis
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# =============================================================================
# Pydantic Models
# =============================================================================

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IncidentData(BaseModel):
    """Incident data for summarization or RCA."""
    key: str = Field(..., description="Incident key (e.g., INC-123)")
    summary: str = Field(..., description="Incident title")
    description: Optional[str] = Field(None, description="Full description")
    status: Optional[str] = Field(None)
    priority: Optional[str] = Field(None)
    assignee: Optional[Dict[str, Any]] = Field(None)
    created: Optional[str] = Field(None)
    labels: Optional[List[str]] = Field(default_factory=list)
    comments: Optional[Dict[str, Any]] = Field(None)
    linked_issues: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class TicketData(BaseModel):
    """Support ticket data for triage."""
    key: str
    summary: str
    description: Optional[str] = None
    reporter: Optional[Dict[str, Any]] = None
    labels: Optional[List[str]] = Field(default_factory=list)


class SummarizeRequest(BaseModel):
    incident: IncidentData
    format: str = Field("markdown")
    async_mode: bool = Field(True, description="Process via queue (recommended)")


class TriageRequest(BaseModel):
    ticket: TicketData
    async_mode: bool = Field(True)


class RCARequest(BaseModel):
    incident: IncidentData
    code_changes: Optional[List[Dict[str, Any]]] = None
    related_incidents: Optional[List[Dict[str, Any]]] = None
    async_mode: bool = Field(True)


class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None
    async_mode: bool = Field(False, description="Chat is sync by default for UX")


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str
    result_url: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    dependencies: Dict[str, str]
    queue_stats: Optional[Dict[str, Any]] = None


# =============================================================================
# Dependencies and Helpers
# =============================================================================

_redis_client: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    """Get Redis client (lazy initialization)."""
    global _redis_client
    
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            _redis_client = redis.from_url(redis_url, decode_responses=True)
            _redis_client.ping()
        except Exception:
            _redis_client = None
    
    return _redis_client


def get_celery():
    """Import and return Celery app."""
    from .tasks import celery
    return celery


class RateLimiter:
    """Simple sliding window rate limiter using Redis."""
    
    def __init__(self, redis_client: redis.Redis, rpm: int = 60):
        self.redis = redis_client
        self.rpm = rpm
    
    def check(self, client_id: str) -> tuple:
        """Check if request is allowed. Returns (allowed, remaining)."""
        if not self.redis:
            return True, self.rpm
        
        key = f"ratelimit:{client_id}:{datetime.utcnow().minute}"
        
        try:
            count = self.redis.incr(key)
            if count == 1:
                self.redis.expire(key, 60)
            
            remaining = max(0, self.rpm - count)
            return count <= self.rpm, remaining
        except Exception:
            return True, self.rpm


async def check_rate_limit(
    request: Request,
    x_api_key: Optional[str] = Header(None),
):
    """FastAPI dependency for rate limiting."""
    redis_client = get_redis()
    if not redis_client:
        return
    
    client_id = x_api_key or request.client.host
    limiter = RateLimiter(redis_client, rpm=60)
    allowed, remaining = limiter.check(client_id)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )
    
    request.state.rate_limit_remaining = remaining


# =============================================================================
# Application Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    print("=" * 60)
    print("Starting AI SRE Agent API Server")
    print("=" * 60)
    
    # Check Anthropic API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  WARNING: ANTHROPIC_API_KEY not set")
    else:
        print("✓ Anthropic API key configured")
    
    # Check Redis
    redis_client = get_redis()
    if redis_client:
        print("✓ Redis connected")
    else:
        print("⚠️  WARNING: Redis not available")
    
    # Check Database
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            from .database import init_database
            if init_database(database_url):
                print("✓ PostgreSQL connected")
            else:
                print("⚠️  WARNING: PostgreSQL connection failed")
        except Exception as e:
            print(f"⚠️  WARNING: Database init error: {e}")
    else:
        print("ℹ️  PostgreSQL not configured (optional)")
    
    # Check Celery broker
    try:
        celery = get_celery()
        print(f"✓ Celery broker: {celery.conf.broker_url}")
    except Exception as e:
        print(f"⚠️  WARNING: Celery error: {e}")
    
    print("=" * 60)
    print("Server ready!")
    print("=" * 60)
    
    yield
    
    print("Shutting down...")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="AI SRE Agent API",
    description="Production API for AI-powered incident management",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_headers(request: Request, call_next):
    """Add rate limit headers to responses."""
    response = await call_next(request)
    if hasattr(request.state, "rate_limit_remaining"):
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
    return response


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/", include_in_schema=False)
async def root():
    return {"name": "AI SRE Agent", "version": "0.2.0", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse)
async def health():
    """Comprehensive health check."""
    deps = {}
    queue_stats = None
    
    # Redis
    try:
        r = get_redis()
        deps["redis"] = "healthy" if r and r.ping() else "unavailable"
    except Exception as e:
        deps["redis"] = f"error: {e}"
    
    # PostgreSQL
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            from sqlalchemy import text
            from .database import get_db_session
            with get_db_session() as db:
                db.execute(text("SELECT 1"))
            deps["postgresql"] = "healthy"
        except Exception as e:
            deps["postgresql"] = f"error: {e}"
    else:
        deps["postgresql"] = "not configured"
    
    # Celery workers
    try:
        celery = get_celery()
        inspect = celery.control.inspect(timeout=2)
        active = inspect.active()
        if active:
            deps["celery"] = "healthy"
            queue_stats = {
                "workers": len(active),
                "active_tasks": sum(len(t) for t in active.values()),
            }
        else:
            deps["celery"] = "no workers"
    except Exception as e:
        deps["celery"] = f"error: {e}"
    
    status = "healthy" if all("error" not in v for v in deps.values()) else "degraded"
    
    return HealthResponse(
        status=status,
        version="0.2.0",
        dependencies=deps,
        queue_stats=queue_stats,
    )


@app.get("/health/live")
async def liveness():
    """Kubernetes liveness probe - is the process alive?"""
    return {"status": "alive"}


@app.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe - can we handle requests?"""
    try:
        celery = get_celery()
        celery.connection().ensure_connection(max_retries=1)
        return {"status": "ready"}
    except Exception:
        raise HTTPException(503, "Broker unavailable")


# =============================================================================
# API Endpoints
# =============================================================================

@app.post("/api/v1/summarize", response_model=TaskResponse)
async def summarize_incident(
    request: SummarizeRequest,
    _: None = Depends(check_rate_limit),
):
    """
    Summarize an incident.
    
    By default, the task is processed asynchronously via Celery.
    Poll `/api/v1/tasks/{task_id}` for results.
    """
    from .tasks import summarize_incident as task_fn
    
    data = request.incident.model_dump()
    options = {"format": request.format}
    
    if request.async_mode:
        task = task_fn.delay(data, options)
        return TaskResponse(
            task_id=task.id,
            status=TaskStatus.PENDING,
            message="Task queued",
            result_url=f"/api/v1/tasks/{task.id}",
        )
    else:
        # Synchronous (blocking) - use for testing only
        result = task_fn.apply(args=[data, options]).get(timeout=120)
        return TaskResponse(
            task_id=result.get("task_id", "sync"),
            status=TaskStatus.COMPLETED,
            message="Completed",
        )


@app.post("/api/v1/triage", response_model=TaskResponse)
async def triage_ticket(
    request: TriageRequest,
    _: None = Depends(check_rate_limit),
):
    """Triage a support ticket."""
    from .tasks import triage_ticket as task_fn
    
    data = request.ticket.model_dump()
    
    if request.async_mode:
        task = task_fn.delay(data, {})
        return TaskResponse(
            task_id=task.id,
            status=TaskStatus.PENDING,
            message="Task queued",
            result_url=f"/api/v1/tasks/{task.id}",
        )
    else:
        result = task_fn.apply(args=[data, {}]).get(timeout=120)
        return TaskResponse(
            task_id=result.get("task_id", "sync"),
            status=TaskStatus.COMPLETED,
            message="Completed",
        )


@app.post("/api/v1/rca", response_model=TaskResponse)
async def root_cause_analysis(
    request: RCARequest,
    _: None = Depends(check_rate_limit),
):
    """Perform root cause analysis on an incident."""
    from .tasks import analyze_root_cause as task_fn
    
    data = request.incident.model_dump()
    
    if request.async_mode:
        task = task_fn.delay(data, request.code_changes, request.related_incidents)
        return TaskResponse(
            task_id=task.id,
            status=TaskStatus.PENDING,
            message="Task queued",
            result_url=f"/api/v1/tasks/{task.id}",
        )
    else:
        result = task_fn.apply(
            args=[data, request.code_changes, request.related_incidents]
        ).get(timeout=180)
        return TaskResponse(
            task_id=result.get("task_id", "sync"),
            status=TaskStatus.COMPLETED,
            message="Completed",
        )


@app.post("/api/v1/chat")
async def chat(
    request: ChatRequest,
    _: None = Depends(check_rate_limit),
):
    """Free-form chat with the SRE agent."""
    from .tasks import chat_completion as task_fn
    
    if request.async_mode:
        task = task_fn.delay(request.message, request.context, request.conversation_id)
        return TaskResponse(
            task_id=task.id,
            status=TaskStatus.PENDING,
            message="Task queued",
            result_url=f"/api/v1/tasks/{task.id}",
        )
    else:
        result = task_fn.apply(
            args=[request.message, request.context, request.conversation_id]
        ).get(timeout=60)
        return {
            "response": result.get("response"),
            "conversation_id": request.conversation_id,
        }


# =============================================================================
# Task Status Endpoint
# =============================================================================

@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status and result of an async task.
    
    Poll this endpoint until status is 'completed' or 'failed'.
    """
    from .tasks import celery
    
    result = celery.AsyncResult(task_id)
    
    if result.ready():
        if result.successful():
            return {
                "task_id": task_id,
                "status": "completed",
                "result": result.result,
            }
        else:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(result.result),
            }
    elif result.status == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    else:
        return {"task_id": task_id, "status": "processing"}


@app.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a pending or running task."""
    from .tasks import celery
    celery.control.revoke(task_id, terminate=True)
    return {"task_id": task_id, "status": "cancelled"}


# =============================================================================
# Webhook Endpoints
# =============================================================================

@app.post("/webhooks/jira")
async def jira_webhook(
    request: Request,
    _: None = Depends(check_rate_limit),
):
    """
    Handle Jira webhooks.
    
    Configure in Jira: Settings → System → Webhooks
    Events: issue_created, issue_updated
    """
    from .tasks import summarize_incident, triage_ticket
    
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    
    webhook_id = str(uuid.uuid4())
    event = payload.get("webhookEvent", "")
    issue = payload.get("issue", {})
    issue_key = issue.get("key", "UNKNOWN")
    
    # Log webhook
    _log_webhook(webhook_id, "jira", payload, event)
    
    # Only process create/update
    if event not in ["jira:issue_created", "jira:issue_updated"]:
        return {"status": "ignored", "event": event}
    
    # Build incident data
    fields = issue.get("fields", {})
    data = {
        "key": issue_key,
        "summary": fields.get("summary", ""),
        "description": fields.get("description", ""),
        "status": fields.get("status", {}).get("name"),
        "priority": fields.get("priority", {}).get("name"),
        "labels": fields.get("labels", []),
        "comments": {"comments": [], "total": 0},
    }
    
    # Route to appropriate task
    is_incident = (
        fields.get("issuetype", {}).get("name", "").lower() == "incident"
        or issue_key.startswith("INC-")
        or "incident" in fields.get("labels", [])
    )
    
    if is_incident:
        task = summarize_incident.delay(data, {})
        action = "summarize"
    else:
        task = triage_ticket.delay(data, {})
        action = "triage"
    
    _update_webhook(webhook_id, task.id)
    
    return {
        "status": "queued",
        "task_id": task.id,
        "issue_key": issue_key,
        "action": action,
    }


@app.post("/webhooks/pagerduty")
async def pagerduty_webhook(
    request: Request,
    _: None = Depends(check_rate_limit),
):
    """
    Handle PagerDuty webhooks.
    
    Configure in PagerDuty: Integrations → Generic Webhooks (v3)
    """
    from .tasks import summarize_incident
    
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    
    webhook_id = str(uuid.uuid4())
    event = payload.get("event", {})
    event_type = event.get("event_type", "")
    
    _log_webhook(webhook_id, "pagerduty", payload, event_type)
    
    if event_type != "incident.triggered":
        return {"status": "ignored", "event_type": event_type}
    
    incident = event.get("data", {})
    data = {
        "key": incident.get("id", f"PD-{webhook_id[:8]}"),
        "summary": incident.get("title", ""),
        "description": incident.get("description", ""),
        "status": "triggered",
        "priority": incident.get("urgency", "high"),
        "comments": {"comments": [], "total": 0},
    }
    
    task = summarize_incident.delay(data, {})
    _update_webhook(webhook_id, task.id)
    
    return {"status": "queued", "task_id": task.id}


@app.post("/webhooks/generic")
async def generic_webhook(
    request: Request,
    _: None = Depends(check_rate_limit),
):
    """
    Generic webhook for custom integrations.
    
    Payload format:
    {
        "action": "summarize" | "triage" | "rca" | "chat",
        "data": { ... }
    }
    """
    from .tasks import summarize_incident, triage_ticket, analyze_root_cause, chat_completion
    
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    
    action = payload.get("action", "")
    data = payload.get("data", {})
    
    webhook_id = str(uuid.uuid4())
    _log_webhook(webhook_id, "generic", payload, action)
    
    task_map = {
        "summarize": lambda: summarize_incident.delay(data, {}),
        "triage": lambda: triage_ticket.delay(data, {}),
        "rca": lambda: analyze_root_cause.delay(data, None, None),
        "chat": lambda: chat_completion.delay(data.get("message", ""), data.get("context")),
    }
    
    if action not in task_map:
        raise HTTPException(400, f"Unknown action: {action}")
    
    task = task_map[action]()
    _update_webhook(webhook_id, task.id)
    
    return {"status": "queued", "task_id": task.id, "action": action}


# =============================================================================
# Webhook Helpers
# =============================================================================

def _log_webhook(webhook_id: str, source: str, payload: dict, event: str):
    """Log webhook to database."""
    if not os.getenv("DATABASE_URL"):
        return
    try:
        from .database import get_db_session, WebhookLogRepository
        with get_db_session() as db:
            WebhookLogRepository(db).create(webhook_id, source, json.dumps(payload), event)
    except Exception:
        pass


def _update_webhook(webhook_id: str, task_id: str):
    """Update webhook with task ID."""
    if not os.getenv("DATABASE_URL"):
        return
    try:
        from .database import get_db_session, WebhookLogRepository
        with get_db_session() as db:
            WebhookLogRepository(db).update_processed(webhook_id, task_id, "queued")
    except Exception:
        pass


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agent.server:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEBUG", "").lower() == "true",
    )
