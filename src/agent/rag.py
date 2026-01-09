"""RAG Engine for the AI SRE Agent.

This module handles document embedding, storage, and retrieval
for providing relevant context to the agent.
"""

import hashlib
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


@dataclass
class RAGConfig:
    """Configuration for the RAG engine."""
    persist_directory: str = "./data/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    collection_name: str = "sre_knowledge"


class RAGEngine:
    """Retrieval-Augmented Generation engine for SRE context."""
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self._embeddings: Optional[HuggingFaceEmbeddings] = None
        self._vectorstore: Optional[Chroma] = None
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
        )
    
    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """Lazy initialization of embeddings model."""
        if self._embeddings is None:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.config.embedding_model,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self._embeddings
    
    @property
    def vectorstore(self) -> Chroma:
        """Lazy initialization of vector store."""
        if self._vectorstore is None:
            persist_path = Path(self.config.persist_directory)
            persist_path.mkdir(parents=True, exist_ok=True)
            
            self._vectorstore = Chroma(
                collection_name=self.config.collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(persist_path),
            )
        return self._vectorstore
    
    def _generate_doc_id(self, content: str, metadata: Dict[str, Any]) -> str:
        """Generate a unique ID for a document."""
        id_string = f"{metadata.get('source', '')}{content[:100]}"
        return hashlib.sha256(id_string.encode()).hexdigest()[:16]
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        source_type: str = "unknown",
    ) -> int:
        """
        Add documents to the knowledge base.
        
        Args:
            documents: List of dicts with 'content' and optional 'metadata'
            source_type: Type of source (e.g., 'confluence', 'runbook', 'incident')
        
        Returns:
            Number of chunks added
        """
        all_chunks = []
        
        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            metadata["source_type"] = source_type
            
            # Split into chunks
            chunks = self._text_splitter.split_text(content)
            
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
                all_chunks.append(
                    Document(page_content=chunk, metadata=chunk_metadata)
                )
        
        if all_chunks:
            self.vectorstore.add_documents(all_chunks)
        
        return len(all_chunks)
    
    async def add_incident_context(
        self,
        incident_key: str,
        incident_data: Dict[str, Any],
    ) -> int:
        """
        Add incident-specific context to the knowledge base.
        
        This indexes the incident details, comments, and any linked issues
        for later retrieval.
        """
        documents = []
        
        # Main incident description
        if incident_data.get("description"):
            documents.append({
                "content": f"Incident {incident_key}: {incident_data.get('summary', '')}\n\n{incident_data['description']}",
                "metadata": {
                    "source": f"incident:{incident_key}",
                    "type": "incident_description",
                    "incident_key": incident_key,
                },
            })
        
        # Comments
        comments = incident_data.get("comments", {}).get("comments", [])
        if comments:
            comment_text = "\n\n".join([
                f"[{c.get('author', 'unknown')}]: {c.get('body', '')}"
                for c in comments
            ])
            documents.append({
                "content": f"Incident {incident_key} - Discussion:\n\n{comment_text}",
                "metadata": {
                    "source": f"incident:{incident_key}:comments",
                    "type": "incident_comments",
                    "incident_key": incident_key,
                },
            })
        
        # Linked issues
        for linked in incident_data.get("linked_issues", []):
            documents.append({
                "content": f"Linked issue: {linked.get('key')} ({linked.get('type')}): {linked.get('summary')}",
                "metadata": {
                    "source": f"incident:{incident_key}:linked:{linked.get('key')}",
                    "type": "linked_issue",
                    "incident_key": incident_key,
                },
            })
        
        return await self.add_documents(documents, source_type="incident")
    
    async def add_runbook(
        self,
        runbook_id: str,
        title: str,
        content: str,
        service: Optional[str] = None,
    ) -> int:
        """Add a runbook to the knowledge base."""
        documents = [{
            "content": f"# {title}\n\n{content}",
            "metadata": {
                "source": f"confluence:{runbook_id}",
                "type": "runbook",
                "title": title,
                "service": service or "unknown",
            },
        }]
        
        return await self.add_documents(documents, source_type="runbook")
    
    async def add_code_context(
        self,
        project: str,
        file_path: str,
        content: str,
        ref: str = "main",
    ) -> int:
        """Add code context to the knowledge base."""
        documents = [{
            "content": f"File: {project}/{file_path}\n\n```\n{content}\n```",
            "metadata": {
                "source": f"gitlab:{project}:{file_path}",
                "type": "code",
                "project": project,
                "file_path": file_path,
                "ref": ref,
            },
        }]
        
        return await self.add_documents(documents, source_type="code")
    
    async def search(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Search for relevant context.
        
        Args:
            query: Search query
            k: Number of results to return
            filter_dict: Optional metadata filters
        
        Returns:
            List of relevant documents
        """
        if filter_dict:
            results = self.vectorstore.similarity_search(
                query,
                k=k,
                filter=filter_dict,
            )
        else:
            results = self.vectorstore.similarity_search(query, k=k)
        
        return results
    
    async def search_with_scores(
        self,
        query: str,
        k: int = 5,
        score_threshold: float = 0.5,
    ) -> List[tuple]:
        """Search with relevance scores."""
        results = self.vectorstore.similarity_search_with_relevance_scores(
            query,
            k=k,
            score_threshold=score_threshold,
        )
        return results
    
    async def get_incident_context(
        self,
        incident_key: str,
        additional_query: Optional[str] = None,
        k: int = 10,
    ) -> List[Document]:
        """
        Get context relevant to a specific incident.
        
        Combines incident-specific context with general knowledge base search.
        """
        results = []
        
        # Get incident-specific context
        incident_results = await self.search(
            query=incident_key,
            k=k // 2,
            filter_dict={"incident_key": incident_key},
        )
        results.extend(incident_results)
        
        # If there's an additional query (e.g., the incident summary), search general KB
        if additional_query:
            general_results = await self.search(
                query=additional_query,
                k=k // 2,
            )
            # Deduplicate
            seen_sources = {doc.metadata.get("source") for doc in results}
            for doc in general_results:
                if doc.metadata.get("source") not in seen_sources:
                    results.append(doc)
        
        return results
    
    def get_retriever(self, k: int = 5):
        """Get a LangChain retriever for the vectorstore."""
        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k},
        )
    
    async def clear(self):
        """Clear all documents from the knowledge base."""
        self.vectorstore.delete_collection()
        self._vectorstore = None
