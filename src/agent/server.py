"""
HTTP Server for the AI SRE Agent.

Provides REST API endpoints for:
- Incident summarization
- Ticket triage
- Root cause analysis
- Webhook handlers for Jira, PagerDuty, etc.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agent import SREAgentSimple
from .rag import RAGEngine


# =============================================================================
# Models
# =============================================================================

class TaskType(str, Enum):
    """Supported task types."""
    SUMMARIZE = "summarize"
    TRIAGE = "triage"
    RCA = "rca"
    CHAT = "chat"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IncidentData(BaseModel):
    """Incident data for summarization."""
    key: str = Field(..., description="Incident key (e.g., INC-123)")
    summary: str = Field(..., description="Incident summary/title")
    description: Optional[str] = Field(None, description="Detailed description")
    status: Optional[str] = Field(None, description="Current status")
    priority: Optional[str] = Field(None, description="Priority level")
    assignee: Optional[Dict[str, Any]] = Field(None, description="Assignee info")
    reporter: Optional[Dict[str, Any]] = Field(None, description="Reporter info")
    created: Optional[str] = Field(None, description="Creation timestamp")
    updated: Optional[str] = Field(None, description="Last update timestamp")
    labels: Optional[List[str]] = Field(default_factory=list, description="Labels")
    components: Optional[List[str]] = Field(default_factory=list, description="Components")
    comments: Optional[Dict[str, Any]] = Field(None, description="Comments data")
    linked_issues: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class TicketData(BaseModel):
    """Support ticket data for triage."""
    key: str = Field(..., description="Ticket key")
    summary: str = Field(..., description="Ticket summary")
    description: Optional[str] = Field(None, description="Ticket description")
    reporter: Optional[Dict[str, Any]] = Field(None, description="Reporter info")
    created: Optional[str] = Field(None, description="Creation timestamp")
    labels: Optional[List[str]] = Field(default_factory=list)
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Free-form chat request."""
    message: str = Field(..., description="User message")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for history")


class SummarizeRequest(BaseModel):
    """Request to summarize an incident."""
    incident: IncidentData
    include_recommendations: bool = Field(True, description="Include prevention recommendations")
    format: str = Field("markdown", description="Output format: markdown, json, or plain")


class TriageRequest(BaseModel):
    """Request to triage a ticket."""
    ticket: TicketData
    auto_respond: bool = Field(False, description="Generate auto-response suggestion")
    auto_assign: bool = Field(False, description="Suggest team assignment")


class RCARequest(BaseModel):
    """Request for root cause analysis."""
    incident: IncidentData
    code_changes: Optional[List[Dict[str, Any]]] = Field(None, description="Related code changes")
    related_incidents: Optional[List[Dict[str, Any]]] = Field(None, description="Similar past incidents")


class TaskResponse(BaseModel):
    """Response for async task submission."""
    task_id: str
    status: TaskStatus
    message: str


class TaskResult(BaseModel):
    """Result of a completed task."""
    task_id: str
    status: TaskStatus
    task_type: TaskType
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SummarizeResponse(BaseModel):
    """Response from summarization."""
    incident_key: str
    summary: str
    timeline: Optional[List[Dict[str, str]]] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    recommendations: Optional[List[str]] = None
    processed_at: str


class TriageResponse(BaseModel):
    """Response from triage."""
    ticket_key: str
    category: str
    priority: str
    suggested_team: Optional[str] = None
    suggested_response: Optional[str] = None
    needs_escalation: bool
    confidence: float
    reasoning: str
    processed_at: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    tasks_pending: int
    tasks_completed: int


# =============================================================================
# Task Store (in-memory, replace with Redis/DB in production)
# =============================================================================

class TaskStore:
    """Simple in-memory task store."""
    
    def __init__(self):
        self.tasks: Dict[str, TaskResult] = {}
        self._counter = 0
        self._lock = asyncio.Lock()
    
    async def create_task(self, task_type: TaskType) -> str:
        async with self._lock:
            self._counter += 1
            task_id = f"{task_type.value}-{self._counter}-{int(datetime.utcnow().timestamp())}"
            self.tasks[task_id] = TaskResult(
                task_id=task_id,
                status=TaskStatus.PENDING,
                task_type=task_type,
                created_at=datetime.utcnow().isoformat(),
            )
            return task_id
    
    async def update_task(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            self.tasks[task_id].result = result
            self.tasks[task_id].error = error
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                self.tasks[task_id].completed_at = datetime.utcnow().isoformat()
    
    def get_task(self, task_id: str) -> Optional[TaskResult]:
        return self.tasks.get(task_id)
    
    def get_stats(self) -> Dict[str, int]:
        pending = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING)
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        return {"pending": pending, "completed": completed}


# =============================================================================
# Application
# =============================================================================

task_store = TaskStore()
agent: Optional[SREAgentSimple] = None
rag_engine: Optional[RAGEngine] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global agent, rag_engine
    
    # Startup
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
    
    model_name = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
    agent = SREAgentSimple(anthropic_api_key=api_key, model_name=model_name)
    rag_engine = RAGEngine()
    
    print(f"AI SRE Agent server started with model: {model_name}")
    
    yield
    
    # Shutdown
    print("AI SRE Agent server shutting down")


app = FastAPI(
    title="AI SRE Agent API",
    description="REST API for AI-powered incident management and support triage",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Health & Info Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    stats = task_store.get_stats()
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        tasks_pending=stats["pending"],
        tasks_completed=stats["completed"],
    )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AI SRE Agent API",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "summarize": "POST /api/v1/summarize",
            "triage": "POST /api/v1/triage",
            "rca": "POST /api/v1/rca",
            "chat": "POST /api/v1/chat",
            "webhooks": {
                "jira": "POST /webhooks/jira",
                "pagerduty": "POST /webhooks/pagerduty",
            },
        },
    }


# =============================================================================
# Synchronous API Endpoints
# =============================================================================

@app.post("/api/v1/summarize", response_model=SummarizeResponse)
async def summarize_incident(request: SummarizeRequest):
    """
    Summarize an incident synchronously.
    
    Returns a structured summary including timeline, root cause, and recommendations.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Convert to dict for agent
        incident_data = request.incident.model_dump()
        
        # Get summary from agent
        summary_text = await agent.summarize_incident_simple(incident_data)
        
        # Parse structured response (in production, use structured output)
        return SummarizeResponse(
            incident_key=request.incident.key,
            summary=summary_text,
            processed_at=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/triage", response_model=TriageResponse)
async def triage_ticket(request: TriageRequest):
    """
    Triage a support ticket synchronously.
    
    Returns category, priority, and suggested actions.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        ticket_data = request.ticket.model_dump()
        
        # For now, use summarize as base (extend with proper triage logic)
        # In production, you'd have a dedicated triage method
        incident_like = {
            "key": ticket_data["key"],
            "summary": ticket_data["summary"],
            "description": ticket_data.get("description", ""),
            "comments": {"comments": [], "total": 0},
        }
        
        result = await agent.summarize_incident_simple(incident_like)
        
        return TriageResponse(
            ticket_key=request.ticket.key,
            category="support",  # Would come from actual triage
            priority="medium",
            suggested_team="platform",
            suggested_response=result[:500] if request.auto_respond else None,
            needs_escalation=False,
            confidence=0.8,
            reasoning="Auto-triaged by AI SRE Agent",
            processed_at=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    """
    Free-form chat with the agent.
    
    Useful for ad-hoc questions about incidents, runbooks, etc.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage, SystemMessage
        from .prompts import SRE_AGENT_SYSTEM_PROMPT
        
        # Build context if provided
        context_str = ""
        if request.context:
            context_str = f"\n\nContext:\n{json.dumps(request.context, indent=2)}"
        
        llm = ChatAnthropic(
            model=os.getenv("MODEL_NAME", "claude-sonnet-4-20250514"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
        
        response = await llm.ainvoke([
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=f"{request.message}{context_str}"),
        ])
        
        return {
            "response": response.content,
            "conversation_id": request.conversation_id,
            "processed_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/rca")
async def root_cause_analysis(request: RCARequest):
    """
    Perform root cause analysis on an incident.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        incident_data = request.incident.model_dump()
        
        # Enrich with code changes if provided
        if request.code_changes:
            incident_data["code_changes"] = request.code_changes
        
        result = await agent.summarize_incident_simple(incident_data)
        
        return {
            "incident_key": request.incident.key,
            "analysis": result,
            "processed_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Async Task Endpoints
# =============================================================================

@app.post("/api/v1/tasks/summarize", response_model=TaskResponse)
async def submit_summarize_task(
    request: SummarizeRequest,
    background_tasks: BackgroundTasks,
):
    """
    Submit an incident summarization task for async processing.
    
    Returns a task ID that can be polled for results.
    """
    task_id = await task_store.create_task(TaskType.SUMMARIZE)
    background_tasks.add_task(process_summarize_task, task_id, request)
    
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Task submitted successfully",
    )


async def process_summarize_task(task_id: str, request: SummarizeRequest):
    """Background task processor for summarization."""
    await task_store.update_task(task_id, TaskStatus.PROCESSING)
    
    try:
        incident_data = request.incident.model_dump()
        summary = await agent.summarize_incident_simple(incident_data)
        
        await task_store.update_task(
            task_id,
            TaskStatus.COMPLETED,
            result={
                "incident_key": request.incident.key,
                "summary": summary,
                "processed_at": datetime.utcnow().isoformat(),
            },
        )
    except Exception as e:
        await task_store.update_task(task_id, TaskStatus.FAILED, error=str(e))


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResult)
async def get_task_status(task_id: str):
    """Get the status and result of a task."""
    task = task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# =============================================================================
# Webhook Endpoints
# =============================================================================

@app.post("/webhooks/jira")
async def jira_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Jira webhooks.
    
    Configure in Jira: System > Webhooks > Create
    Events: Issue Created, Issue Updated
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event_type = payload.get("webhookEvent", "unknown")
    issue = payload.get("issue", {})
    issue_key = issue.get("key", "UNKNOWN")
    
    # Filter events
    if event_type not in ["jira:issue_created", "jira:issue_updated"]:
        return {"status": "ignored", "event": event_type}
    
    # Check if it's an incident (customize based on your Jira setup)
    issue_type = issue.get("fields", {}).get("issuetype", {}).get("name", "")
    labels = issue.get("fields", {}).get("labels", [])
    
    is_incident = (
        issue_type.lower() == "incident" or
        "incident" in labels or
        issue_key.startswith("INC-")
    )
    
    if is_incident:
        # Auto-summarize incidents
        incident_data = IncidentData(
            key=issue_key,
            summary=issue.get("fields", {}).get("summary", ""),
            description=issue.get("fields", {}).get("description", ""),
            status=issue.get("fields", {}).get("status", {}).get("name"),
            priority=issue.get("fields", {}).get("priority", {}).get("name"),
            labels=labels,
        )
        
        task_id = await task_store.create_task(TaskType.SUMMARIZE)
        background_tasks.add_task(
            process_summarize_task,
            task_id,
            SummarizeRequest(incident=incident_data),
        )
        
        return {
            "status": "processing",
            "task_id": task_id,
            "issue_key": issue_key,
            "action": "summarize",
        }
    else:
        # Triage other tickets
        ticket_data = TicketData(
            key=issue_key,
            summary=issue.get("fields", {}).get("summary", ""),
            description=issue.get("fields", {}).get("description", ""),
            labels=labels,
        )
        
        task_id = await task_store.create_task(TaskType.TRIAGE)
        # Would add triage background task here
        
        return {
            "status": "processing",
            "task_id": task_id,
            "issue_key": issue_key,
            "action": "triage",
        }


@app.post("/webhooks/pagerduty")
async def pagerduty_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle PagerDuty webhooks.
    
    Configure in PagerDuty: Integrations > Generic Webhooks (v3)
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event = payload.get("event", {})
    event_type = event.get("event_type", "unknown")
    
    # Handle incident triggers
    if event_type == "incident.triggered":
        incident_data = event.get("data", {})
        
        incident = IncidentData(
            key=incident_data.get("id", "PD-UNKNOWN"),
            summary=incident_data.get("title", ""),
            description=incident_data.get("description", ""),
            status="triggered",
            priority=incident_data.get("urgency", "high"),
        )
        
        task_id = await task_store.create_task(TaskType.SUMMARIZE)
        background_tasks.add_task(
            process_summarize_task,
            task_id,
            SummarizeRequest(incident=incident),
        )
        
        return {
            "status": "processing",
            "task_id": task_id,
            "incident_id": incident.key,
        }
    
    return {"status": "ignored", "event_type": event_type}


@app.post("/webhooks/generic")
async def generic_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Generic webhook handler for custom integrations.
    
    Expects a JSON body with:
    - action: "summarize" | "triage" | "rca" | "chat"
    - data: The relevant data for the action
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    action = payload.get("action", "chat")
    data = payload.get("data", {})
    
    if action == "summarize":
        incident = IncidentData(**data)
        task_id = await task_store.create_task(TaskType.SUMMARIZE)
        background_tasks.add_task(
            process_summarize_task,
            task_id,
            SummarizeRequest(incident=incident),
        )
        return {"status": "processing", "task_id": task_id}
    
    elif action == "chat":
        message = data.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="Message required for chat")
        
        # Sync chat for generic webhook
        result = await chat(ChatRequest(message=message, context=data.get("context")))
        return result
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


# =============================================================================
# Entry point
# =============================================================================

def create_app() -> FastAPI:
    """Create the FastAPI application."""
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "agent.server:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
