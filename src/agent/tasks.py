"""
Celery task definitions for async processing.

This module defines the Celery app and all background tasks
that can be queued for processing by workers.

Architecture:
    API Server -> Redis (broker) -> Celery Workers -> PostgreSQL (results)
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import Celery, Task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


# =============================================================================
# Celery App Configuration
# =============================================================================

def make_celery() -> Celery:
    """Create and configure the Celery application."""
    
    # Broker (Redis)
    broker_url = os.getenv(
        "CELERY_BROKER_URL",
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    
    # Result backend (Redis or PostgreSQL)
    result_backend = os.getenv(
        "CELERY_RESULT_BACKEND",
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    
    app = Celery(
        "ai_sre_agent",
        broker=broker_url,
        backend=result_backend,
    )
    
    app.conf.update(
        # Serialization
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        
        # Time limits (LLM calls can take a while)
        task_time_limit=300,  # 5 min hard limit
        task_soft_time_limit=240,  # 4 min soft limit
        
        # Reliability
        task_acks_late=True,  # Ack after task completes
        task_reject_on_worker_lost=True,  # Requeue if worker dies
        
        # Concurrency (limit due to LLM API costs/rate limits)
        worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "4")),
        worker_prefetch_multiplier=1,  # One task at a time per worker
        
        # Task routing
        task_routes={
            "agent.tasks.summarize_incident": {"queue": "llm"},
            "agent.tasks.triage_ticket": {"queue": "llm"},
            "agent.tasks.analyze_root_cause": {"queue": "llm"},
            "agent.tasks.chat_completion": {"queue": "llm"},
        },
        
        # Results
        result_expires=86400,  # 24 hours
        result_extended=True,  # Store task args in result
        
        # Retry
        task_default_retry_delay=30,
        task_max_retries=3,
    )
    
    return app


# Create the Celery app
celery = make_celery()


# =============================================================================
# Base Task Class with Retry Logic
# =============================================================================

class LLMTask(Task):
    """
    Base task class for LLM operations.
    
    Features:
    - Automatic retry with exponential backoff
    - Lazy agent initialization (one per worker)
    - Structured error handling
    """
    
    # Retry configuration
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 120
    retry_jitter = True
    
    # Lazy-loaded agent instance
    _agent = None
    
    @property
    def agent(self):
        """Get or create the agent instance (lazy initialization)."""
        if self._agent is None:
            from .agent import SREAgentSimple
            
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
            
            model = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
            self._agent = SREAgentSimple(anthropic_api_key=api_key, model_name=model)
            logger.info(f"Initialized SREAgent with model: {model}")
        
        return self._agent
    
    def run_async(self, coro):
        """Run an async coroutine in sync context."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# =============================================================================
# Task Definitions
# =============================================================================

@celery.task(bind=True, base=LLMTask, name="agent.tasks.summarize_incident")
def summarize_incident(
    self,
    incident_data: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Summarize an incident asynchronously.
    
    Args:
        incident_data: Incident details dict with keys:
            - key: Incident ID (e.g., "INC-123")
            - summary: Title
            - description: Full description
            - status: Current status
            - priority: Priority level
            - comments: Dict with 'comments' list
        options: Optional settings dict:
            - format: Output format ("markdown", "json", "plain")
            - include_recommendations: Include prevention tips
    
    Returns:
        Dict with task_id, status, summary, and metadata
    """
    options = options or {}
    task_id = self.request.id
    incident_key = incident_data.get("key", "UNKNOWN")
    
    logger.info(f"[{task_id}] Starting summarization for incident: {incident_key}")
    
    try:
        # Call the agent
        summary = self.run_async(
            self.agent.summarize_incident_simple(incident_data)
        )
        
        result = {
            "task_id": task_id,
            "incident_key": incident_key,
            "status": "completed",
            "summary": summary,
            "format": options.get("format", "markdown"),
            "processed_at": datetime.utcnow().isoformat(),
        }
        
        logger.info(f"[{task_id}] Completed summarization for: {incident_key}")
        
        # Optionally store in database
        _store_result_in_db(task_id, "summarize", result)
        
        return result
        
    except Exception as e:
        logger.error(f"[{task_id}] Failed summarization for {incident_key}: {e}")
        raise


@celery.task(bind=True, base=LLMTask, name="agent.tasks.triage_ticket")
def triage_ticket(
    self,
    ticket_data: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Triage a support ticket asynchronously.
    
    Args:
        ticket_data: Ticket details dict
        options: Triage options (auto_respond, auto_assign)
    
    Returns:
        Dict with triage results
    """
    options = options or {}
    task_id = self.request.id
    ticket_key = ticket_data.get("key", "UNKNOWN")
    
    logger.info(f"[{task_id}] Starting triage for ticket: {ticket_key}")
    
    try:
        analysis = self.run_async(
            self.agent.triage_ticket_simple(ticket_data)
        )
        
        result = {
            "task_id": task_id,
            "ticket_key": ticket_key,
            "status": "completed",
            "analysis": analysis,
            "processed_at": datetime.utcnow().isoformat(),
        }
        
        logger.info(f"[{task_id}] Completed triage for: {ticket_key}")
        
        _store_result_in_db(task_id, "triage", result)
        
        return result
        
    except Exception as e:
        logger.error(f"[{task_id}] Failed triage for {ticket_key}: {e}")
        raise


@celery.task(bind=True, base=LLMTask, name="agent.tasks.analyze_root_cause")
def analyze_root_cause(
    self,
    incident_data: Dict[str, Any],
    code_changes: Optional[List[Dict[str, Any]]] = None,
    related_incidents: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Perform root cause analysis asynchronously.
    
    Args:
        incident_data: Incident details
        code_changes: Related code changes/MRs
        related_incidents: Similar past incidents
    
    Returns:
        Dict with RCA results
    """
    task_id = self.request.id
    incident_key = incident_data.get("key", "UNKNOWN")
    
    logger.info(f"[{task_id}] Starting RCA for incident: {incident_key}")
    
    try:
        # Enrich incident data with additional context
        enriched_data = incident_data.copy()
        if code_changes:
            enriched_data["code_changes"] = code_changes
        if related_incidents:
            enriched_data["related_incidents"] = related_incidents
        
        analysis = self.run_async(
            self.agent.analyze_root_cause(enriched_data)
        )
        
        result = {
            "task_id": task_id,
            "incident_key": incident_key,
            "status": "completed",
            "analysis": analysis,
            "processed_at": datetime.utcnow().isoformat(),
        }
        
        logger.info(f"[{task_id}] Completed RCA for: {incident_key}")
        
        _store_result_in_db(task_id, "rca", result)
        
        return result
        
    except Exception as e:
        logger.error(f"[{task_id}] Failed RCA for {incident_key}: {e}")
        raise


@celery.task(bind=True, base=LLMTask, name="agent.tasks.chat_completion")
def chat_completion(
    self,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process a chat message asynchronously.
    
    Args:
        message: User message
        context: Additional context
        conversation_id: For tracking conversation history
    
    Returns:
        Dict with chat response
    """
    task_id = self.request.id
    
    logger.info(f"[{task_id}] Processing chat message")
    
    try:
        response = self.run_async(
            self.agent.chat(message, context)
        )
        
        result = {
            "task_id": task_id,
            "status": "completed",
            "response": response,
            "conversation_id": conversation_id,
            "processed_at": datetime.utcnow().isoformat(),
        }
        
        logger.info(f"[{task_id}] Completed chat")
        
        return result
        
    except Exception as e:
        logger.error(f"[{task_id}] Failed chat: {e}")
        raise


# =============================================================================
# Periodic Tasks (Celery Beat)
# =============================================================================

celery.conf.beat_schedule = {
    # Clean up old task results every hour
    "cleanup-old-results": {
        "task": "agent.tasks.cleanup_old_results",
        "schedule": 3600.0,
    },
}


@celery.task(name="agent.tasks.cleanup_old_results")
def cleanup_old_results() -> Dict[str, Any]:
    """Clean up task results older than 7 days."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return {"status": "skipped", "reason": "no database configured"}
    
    try:
        from datetime import timedelta
        from .database import get_db_session, TaskResult
        
        cutoff = datetime.utcnow() - timedelta(days=7)
        
        with get_db_session() as db:
            deleted = db.query(TaskResult).filter(
                TaskResult.created_at < cutoff
            ).delete()
            db.commit()
        
        logger.info(f"Cleaned up {deleted} old task results")
        return {"status": "completed", "deleted": deleted}
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"status": "failed", "error": str(e)}


# =============================================================================
# Helper Functions
# =============================================================================

def _store_result_in_db(task_id: str, task_type: str, result: Dict[str, Any]):
    """Store task result in PostgreSQL if configured."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return
    
    try:
        from .database import get_db_session, TaskResult as TaskResultModel
        
        with get_db_session() as db:
            db_result = TaskResultModel(
                task_id=task_id,
                task_type=task_type,
                status=result.get("status", "completed"),
                result_data=json.dumps(result),
                created_at=datetime.utcnow(),
            )
            db.add(db_result)
            db.commit()
            
    except Exception as e:
        logger.warning(f"Failed to store result in database: {e}")
