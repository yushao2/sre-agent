"""
Database models and connection management.

Uses SQLAlchemy with PostgreSQL for:
- Task result persistence
- Webhook logging
- Incident history
"""

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Optional

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

Base = declarative_base()

# Global engine and session factory
_engine = None
_SessionLocal = None


def init_database(database_url: Optional[str] = None) -> bool:
    """
    Initialize database connection and create tables.
    
    Args:
        database_url: PostgreSQL connection string. Falls back to DATABASE_URL env var.
    
    Returns:
        True if successful, False otherwise.
    """
    global _engine, _SessionLocal
    
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        return False
    
    try:
        _engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_pre_ping=True,  # Test connections before use
        )
        
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        
        # Create all tables
        Base.metadata.create_all(bind=_engine)
        
        return True
        
    except Exception as e:
        print(f"Database initialization failed: {e}")
        return False


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Get a database session as a context manager.
    
    Usage:
        with get_db_session() as db:
            db.query(TaskResult).all()
    """
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized")
    
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# Models
# =============================================================================

class TaskResult(Base):
    """Stores results of completed Celery tasks."""
    
    __tablename__ = "task_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    task_type = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    result_data = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("ix_task_results_type_status", "task_type", "status"),
        Index("ix_task_results_created", "created_at"),
    )


class WebhookLog(Base):
    """Logs incoming webhooks for debugging and replay."""
    
    __tablename__ = "webhook_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    webhook_id = Column(String(64), unique=True, nullable=False, index=True)
    source = Column(String(32), nullable=False)  # jira, pagerduty, generic
    event_type = Column(String(64), nullable=True)
    payload = Column(Text, nullable=False)
    
    task_id = Column(String(64), nullable=True, index=True)
    status = Column(String(16), default="received")
    error = Column(Text, nullable=True)
    
    received_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("ix_webhook_logs_source_status", "source", "status"),
        Index("ix_webhook_logs_received", "received_at"),
    )


class IncidentHistory(Base):
    """Stores processed incidents for analytics and similarity matching."""
    
    __tablename__ = "incident_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_key = Column(String(64), nullable=False, index=True)
    source = Column(String(32), nullable=True)  # jira, pagerduty
    
    summary = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    severity = Column(String(16), nullable=True)
    
    incident_created_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("ix_incident_history_key", "incident_key"),
        Index("ix_incident_history_source", "source"),
    )


# =============================================================================
# Repository Classes
# =============================================================================

class TaskResultRepository:
    """Repository for task result operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_task_id(self, task_id: str) -> Optional[TaskResult]:
        return self.db.query(TaskResult).filter(TaskResult.task_id == task_id).first()
    
    def create(self, task_id: str, task_type: str) -> TaskResult:
        result = TaskResult(
            task_id=task_id,
            task_type=task_type,
            status="pending",
            created_at=datetime.utcnow(),
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result
    
    def update_completed(
        self,
        task_id: str,
        status: str,
        result_data: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[TaskResult]:
        result = self.get_by_task_id(task_id)
        if result:
            result.status = status
            result.result_data = result_data
            result.error = error
            result.completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(result)
        return result


class WebhookLogRepository:
    """Repository for webhook log operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(
        self,
        webhook_id: str,
        source: str,
        payload: str,
        event_type: Optional[str] = None,
    ) -> WebhookLog:
        log = WebhookLog(
            webhook_id=webhook_id,
            source=source,
            event_type=event_type,
            payload=payload,
            received_at=datetime.utcnow(),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
    
    def update_processed(
        self,
        webhook_id: str,
        task_id: str,
        status: str = "processed",
        error: Optional[str] = None,
    ) -> Optional[WebhookLog]:
        log = self.db.query(WebhookLog).filter(WebhookLog.webhook_id == webhook_id).first()
        if log:
            log.task_id = task_id
            log.status = status
            log.error = error
            log.processed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(log)
        return log
