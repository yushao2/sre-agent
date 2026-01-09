"""
Example: Webhook Handler for Jira Service Desk

This example shows how to set up a webhook endpoint that can receive
events from Jira Service Desk and trigger the AI SRE Agent for
automatic triage and response.

Run with: uvicorn examples.webhook_handler:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="AI SRE Agent Webhook Handler",
    description="Receives webhooks from Jira Service Desk for automatic triage",
    version="1.0.0",
)


# ============================================================================
# Models
# ============================================================================

class JiraWebhookEvent(BaseModel):
    """Jira webhook event payload."""
    timestamp: int
    webhookEvent: str
    issue_event_type_name: Optional[str] = None
    issue: Optional[Dict[str, Any]] = None
    user: Optional[Dict[str, Any]] = None
    changelog: Optional[Dict[str, Any]] = None
    comment: Optional[Dict[str, Any]] = None


class TriageResult(BaseModel):
    """Result of ticket triage."""
    ticket_key: str
    category: str
    priority: str
    team: str
    initial_response: str
    needs_escalation: bool
    reasoning: str
    processed_at: str


# ============================================================================
# In-memory storage (replace with database in production)
# ============================================================================

triage_results: Dict[str, TriageResult] = {}
processing_queue: asyncio.Queue = asyncio.Queue()


# ============================================================================
# Background processing
# ============================================================================

async def process_ticket(ticket_key: str, ticket_data: Dict[str, Any]):
    """Process a ticket through the AI SRE Agent."""
    from agent import SREAgentSimple
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"Error: No API key, skipping triage for {ticket_key}")
        return
    
    print(f"[{datetime.utcnow().isoformat()}] Processing ticket: {ticket_key}")
    
    try:
        agent = SREAgentSimple(anthropic_api_key=api_key)
        
        # Get triage result
        # In production, you'd use the full agent with MCP connections
        result_text = await agent.summarize_incident_simple(ticket_data)
        
        # Store result
        triage_results[ticket_key] = TriageResult(
            ticket_key=ticket_key,
            category="support",  # Would come from actual triage
            priority=ticket_data.get("priority", {}).get("name", "Medium"),
            team="sre",
            initial_response=result_text[:500],  # Truncate for storage
            needs_escalation=False,
            reasoning="Auto-triaged by AI SRE Agent",
            processed_at=datetime.utcnow().isoformat(),
        )
        
        print(f"[{datetime.utcnow().isoformat()}] Completed triage for: {ticket_key}")
        
        # In production: Update Jira ticket with triage results
        # await update_jira_ticket(ticket_key, triage_result)
        
    except Exception as e:
        print(f"Error processing {ticket_key}: {e}")


async def background_processor():
    """Background task to process tickets from queue."""
    while True:
        try:
            ticket_key, ticket_data = await processing_queue.get()
            await process_ticket(ticket_key, ticket_data)
        except Exception as e:
            print(f"Background processor error: {e}")
        await asyncio.sleep(0.1)


# ============================================================================
# Endpoints
# ============================================================================

@app.on_event("startup")
async def startup():
    """Start background processor on startup."""
    asyncio.create_task(background_processor())


@app.post("/webhook/jira")
async def handle_jira_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Handle incoming Jira webhooks.
    
    Configure this URL in Jira:
    1. Go to System > Webhooks
    2. Create webhook with URL: https://your-server/webhook/jira
    3. Select events: Issue Created, Issue Updated
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event_type = payload.get("webhookEvent", "unknown")
    issue = payload.get("issue", {})
    issue_key = issue.get("key", "UNKNOWN")
    
    print(f"[{datetime.utcnow().isoformat()}] Received webhook: {event_type} for {issue_key}")
    
    # Filter for events we care about
    handled_events = [
        "jira:issue_created",
        "jira:issue_updated",
    ]
    
    if event_type not in handled_events:
        return {"status": "ignored", "event": event_type}
    
    # For issue updates, check if it's a status change we care about
    if event_type == "jira:issue_updated":
        changelog = payload.get("changelog", {})
        items = changelog.get("items", [])
        
        # Only process if status changed to something we handle
        status_changes = [i for i in items if i.get("field") == "status"]
        if not status_changes:
            return {"status": "ignored", "reason": "no_status_change"}
    
    # Convert to our format
    ticket_data = {
        "key": issue_key,
        "summary": issue.get("fields", {}).get("summary", ""),
        "description": issue.get("fields", {}).get("description", ""),
        "status": issue.get("fields", {}).get("status", {}).get("name", ""),
        "priority": issue.get("fields", {}).get("priority", {}),
        "assignee": issue.get("fields", {}).get("assignee", {}),
        "reporter": issue.get("fields", {}).get("reporter", {}),
        "created": issue.get("fields", {}).get("created", ""),
        "labels": issue.get("fields", {}).get("labels", []),
        "comments": {"comments": [], "total": 0},  # Would fetch separately
    }
    
    # Add to processing queue
    await processing_queue.put((issue_key, ticket_data))
    
    return {
        "status": "queued",
        "ticket_key": issue_key,
        "event": event_type,
    }


@app.get("/triage/{ticket_key}")
async def get_triage_result(ticket_key: str):
    """Get the triage result for a ticket."""
    if ticket_key not in triage_results:
        raise HTTPException(status_code=404, detail="Triage result not found")
    
    return triage_results[ticket_key]


@app.get("/triage")
async def list_triage_results():
    """List all triage results."""
    return list(triage_results.values())


@app.post("/triage/manual/{ticket_key}")
async def manual_triage(ticket_key: str, request: Request):
    """
    Manually trigger triage for a ticket.
    
    Body should contain ticket data.
    """
    try:
        ticket_data = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    ticket_data["key"] = ticket_key
    await processing_queue.put((ticket_key, ticket_data))
    
    return {
        "status": "queued",
        "ticket_key": ticket_key,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "queue_size": processing_queue.qsize(),
        "processed_count": len(triage_results),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
