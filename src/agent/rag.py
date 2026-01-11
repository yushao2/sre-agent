"""
RAG (Retrieval-Augmented Generation) implementation for the SRE Agent.

This module provides:
- IncidentKnowledgeBase: Store and retrieve past incidents for context
- RunbookStore: Store and search runbooks/documentation
- Local file-based ChromaDB for development (no server required)

Usage:
    # Local development with file-based storage
    kb = IncidentKnowledgeBase(persist_directory="./data/chroma")
    kb.add_incident({...})
    similar = kb.search("database connection timeout", k=3)

    # In-memory (testing)
    kb = IncidentKnowledgeBase()  # No persist_directory = in-memory
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

# Lazy imports to avoid requiring RAG deps for basic usage
_chromadb = None
_embeddings = None


def _get_chromadb():
    """Lazy import ChromaDB."""
    global _chromadb
    if _chromadb is None:
        try:
            import chromadb
            _chromadb = chromadb
        except ImportError:
            raise ImportError(
                "ChromaDB not installed. Install with: pip install chromadb\n"
                "Or install RAG extras: pip install -e '.[rag]'"
            )
    return _chromadb


def _get_embeddings(model_name: str = "all-MiniLM-L6-v2"):
    """
    Get or create embedding function.
    
    Uses sentence-transformers for local embeddings (no API key needed).
    Falls back to ChromaDB's default if sentence-transformers not available.
    """
    global _embeddings
    if _embeddings is None:
        try:
            from chromadb.utils import embedding_functions
            _embeddings = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=model_name
            )
        except ImportError:
            # Fall back to ChromaDB default (requires API key or uses basic embeddings)
            _embeddings = None
    return _embeddings


class IncidentKnowledgeBase:
    """
    Vector store for past incidents to enable similarity search.
    
    Use this to:
    - Store resolved incidents for future reference
    - Find similar past incidents during RCA
    - Build institutional knowledge over time
    
    Attributes:
        collection_name: ChromaDB collection name
        persist_directory: Path for local file storage (None = in-memory)
        client: ChromaDB client instance
        collection: ChromaDB collection instance
    
    Example:
        >>> # Local file storage (persists across restarts)
        >>> kb = IncidentKnowledgeBase(persist_directory="./data/incidents")
        >>> 
        >>> # Add a resolved incident
        >>> kb.add_incident({
        ...     "key": "INC-123",
        ...     "summary": "Database connection pool exhausted",
        ...     "description": "Connection leak in reporting service...",
        ...     "root_cause": "Missing connection.close() in finally block",
        ...     "resolution": "Added proper connection cleanup",
        ... })
        >>> 
        >>> # Find similar incidents
        >>> similar = kb.search("connection timeout errors", k=3)
        >>> for inc in similar:
        ...     print(f"{inc['key']}: {inc['summary']}")
    """
    
    def __init__(
        self,
        collection_name: str = "incidents",
        persist_directory: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize the incident knowledge base.
        
        Args:
            collection_name: Name of the ChromaDB collection.
            persist_directory: Path to store the database locally.
                             If None, uses in-memory storage (lost on restart).
                             For local dev, use something like "./data/chroma"
            embedding_model: Sentence transformer model for embeddings.
                           Default "all-MiniLM-L6-v2" is fast and good quality.
        """
        chromadb = _get_chromadb()
        
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # Create client
        if persist_directory:
            # Ensure directory exists
            Path(persist_directory).mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            # In-memory for testing
            self.client = chromadb.Client()
        
        # Get or create collection with embeddings
        embedding_fn = _get_embeddings(embedding_model)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata={"description": "SRE incident knowledge base"}
        )
    
    def add_incident(
        self,
        incident: Dict[str, Any],
        include_comments: bool = True,
    ) -> str:
        """
        Add an incident to the knowledge base.
        
        Args:
            incident: Incident dictionary with keys:
                - key (str): Required. Incident ID (e.g., "INC-123")
                - summary (str): Required. Brief title
                - description (str): Full description
                - root_cause (str): Identified root cause
                - resolution (str): How it was resolved
                - status (str): Current status
                - priority (str): Priority level
                - labels (list): Tags/labels
                - comments (dict/list): Timeline comments
            include_comments: Whether to include comments in searchable text.
        
        Returns:
            The incident key (ID).
        """
        key = incident.get("key")
        if not key:
            raise ValueError("Incident must have a 'key' field")
        
        # Build searchable document text
        parts = [
            f"Incident: {key}",
            f"Summary: {incident.get('summary', '')}",
            f"Description: {incident.get('description', '')}",
        ]
        
        if incident.get("root_cause"):
            parts.append(f"Root Cause: {incident['root_cause']}")
        
        if incident.get("resolution"):
            parts.append(f"Resolution: {incident['resolution']}")
        
        if incident.get("labels"):
            parts.append(f"Labels: {', '.join(incident['labels'])}")
        
        # Include comments if requested
        if include_comments:
            comments = incident.get("comments", {})
            if isinstance(comments, dict):
                comments = comments.get("comments", [])
            if isinstance(comments, list):
                for c in comments[:10]:  # Limit to 10 comments
                    if isinstance(c, dict):
                        parts.append(f"Comment: {c.get('body', '')}")
        
        document = "\n".join(parts)
        
        # Store metadata (everything except large text fields)
        metadata = {
            "key": key,
            "summary": incident.get("summary", "")[:500],
            "status": incident.get("status", ""),
            "priority": incident.get("priority", ""),
            "root_cause": incident.get("root_cause", "")[:1000],
            "resolution": incident.get("resolution", "")[:1000],
            "added_at": datetime.utcnow().isoformat(),
        }
        
        # Upsert (update if exists)
        self.collection.upsert(
            ids=[key],
            documents=[document],
            metadatas=[metadata],
        )
        
        return key
    
    def add_incidents(self, incidents: List[Dict[str, Any]]) -> List[str]:
        """
        Batch add multiple incidents.
        
        Args:
            incidents: List of incident dictionaries.
        
        Returns:
            List of added incident keys.
        """
        return [self.add_incident(inc) for inc in incidents]
    
    def search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar incidents.
        
        Args:
            query: Search query (natural language).
            k: Number of results to return.
            filter_dict: Optional metadata filters, e.g. {"status": "Resolved"}
        
        Returns:
            List of similar incidents with metadata and similarity scores.
        
        Example:
            >>> results = kb.search("database connection issues", k=3)
            >>> for r in results:
            ...     print(f"{r['key']}: {r['summary']} (score: {r['score']:.2f})")
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=k,
            where=filter_dict,
            include=["metadatas", "documents", "distances"],
        )
        
        # Format results
        incidents = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0
                
                incidents.append({
                    "key": id_,
                    "summary": metadata.get("summary", ""),
                    "status": metadata.get("status", ""),
                    "priority": metadata.get("priority", ""),
                    "root_cause": metadata.get("root_cause", ""),
                    "resolution": metadata.get("resolution", ""),
                    "score": 1 - distance,  # Convert distance to similarity
                    "document": results["documents"][0][i] if results["documents"] else "",
                })
        
        return incidents
    
    def get_incident(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific incident by key.
        
        Args:
            key: Incident key (e.g., "INC-123")
        
        Returns:
            Incident metadata or None if not found.
        """
        results = self.collection.get(ids=[key], include=["metadatas", "documents"])
        
        if results["ids"]:
            return {
                "key": results["ids"][0],
                **results["metadatas"][0],
                "document": results["documents"][0] if results["documents"] else "",
            }
        return None
    
    def delete_incident(self, key: str) -> bool:
        """
        Delete an incident from the knowledge base.
        
        Args:
            key: Incident key to delete.
        
        Returns:
            True if deleted, False if not found.
        """
        try:
            self.collection.delete(ids=[key])
            return True
        except Exception:
            return False
    
    def count(self) -> int:
        """Return the number of incidents in the knowledge base."""
        return self.collection.count()
    
    def clear(self) -> None:
        """Clear all incidents from the knowledge base."""
        # Delete and recreate collection
        self.client.delete_collection(self.collection_name)
        embedding_fn = _get_embeddings()
        self.collection = self.client.create_collection(
            name=self.collection_name,
            embedding_function=embedding_fn,
        )


class RunbookStore:
    """
    Vector store for runbooks and documentation.
    
    Use this to:
    - Store operational runbooks
    - Enable semantic search across documentation
    - Provide relevant runbooks during incident response
    
    Example:
        >>> store = RunbookStore(persist_directory="./data/runbooks")
        >>> 
        >>> # Add a runbook
        >>> store.add_runbook(
        ...     id="rb-001",
        ...     title="Database Connection Pool Troubleshooting",
        ...     content="## Symptoms\\n- 504 errors...\\n## Steps\\n1. Check pool size...",
        ...     tags=["database", "connection-pool", "troubleshooting"],
        ... )
        >>> 
        >>> # Search
        >>> results = store.search("connection timeout")
    """
    
    def __init__(
        self,
        collection_name: str = "runbooks",
        persist_directory: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize the runbook store.
        
        Args:
            collection_name: Name of the ChromaDB collection.
            persist_directory: Path for local storage (None = in-memory).
            embedding_model: Sentence transformer model for embeddings.
        """
        chromadb = _get_chromadb()
        
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        if persist_directory:
            Path(persist_directory).mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.Client()
        
        embedding_fn = _get_embeddings(embedding_model)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata={"description": "SRE runbooks and documentation"}
        )
    
    def add_runbook(
        self,
        id: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source_url: Optional[str] = None,
    ) -> str:
        """
        Add a runbook to the store.
        
        Args:
            id: Unique identifier for the runbook.
            title: Runbook title.
            content: Full content (markdown, plain text, etc.)
            tags: Optional list of tags for filtering.
            source_url: Optional URL to the original document.
        
        Returns:
            The runbook ID.
        """
        document = f"# {title}\n\n{content}"
        
        metadata = {
            "title": title[:500],
            "tags": ",".join(tags or []),
            "source_url": source_url or "",
            "added_at": datetime.utcnow().isoformat(),
            "content_length": len(content),
        }
        
        self.collection.upsert(
            ids=[id],
            documents=[document],
            metadatas=[metadata],
        )
        
        return id
    
    def search(
        self,
        query: str,
        k: int = 5,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant runbooks.
        
        Args:
            query: Search query (natural language).
            k: Number of results.
            tags: Optional tag filter (any match).
        
        Returns:
            List of matching runbooks with metadata.
        """
        # Build filter if tags provided
        where = None
        if tags:
            # ChromaDB doesn't support array contains, so we use string contains
            # This is a simple approach; for production, consider a different strategy
            where = {"$or": [{"tags": {"$contains": tag}} for tag in tags]}
        
        results = self.collection.query(
            query_texts=[query],
            n_results=k,
            where=where,
            include=["metadatas", "documents", "distances"],
        )
        
        runbooks = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0
                
                runbooks.append({
                    "id": id_,
                    "title": metadata.get("title", ""),
                    "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                    "source_url": metadata.get("source_url", ""),
                    "score": 1 - distance,
                    "content": results["documents"][0][i] if results["documents"] else "",
                })
        
        return runbooks
    
    def get_runbook(self, id: str) -> Optional[Dict[str, Any]]:
        """Get a specific runbook by ID."""
        results = self.collection.get(ids=[id], include=["metadatas", "documents"])
        
        if results["ids"]:
            metadata = results["metadatas"][0]
            return {
                "id": results["ids"][0],
                "title": metadata.get("title", ""),
                "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                "source_url": metadata.get("source_url", ""),
                "content": results["documents"][0] if results["documents"] else "",
            }
        return None
    
    def count(self) -> int:
        """Return the number of runbooks in the store."""
        return self.collection.count()


def get_default_data_dir() -> str:
    """
    Get the default data directory for local development.
    
    Uses XDG_DATA_HOME or falls back to ~/.local/share/ai-sre-agent
    Can be overridden with SRE_AGENT_DATA_DIR env var.
    """
    if data_dir := os.getenv("SRE_AGENT_DATA_DIR"):
        return data_dir
    
    xdg_data = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(xdg_data, "ai-sre-agent")
