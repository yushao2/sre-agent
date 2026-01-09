"""Tests for RAG engine."""

import pytest
from unittest.mock import patch, MagicMock


class TestRAGEngine:
    """Tests for the RAG engine."""

    @pytest.mark.asyncio
    async def test_add_documents(self, mock_incident_data):
        """Test adding documents to the knowledge base."""
        # Import here to avoid issues before mocking
        with patch("chromadb.Client"):
            from agent.rag import RAGEngine, RAGConfig
            
            config = RAGConfig(persist_directory="/tmp/test_chroma")
            engine = RAGEngine(config)
            
            # Mock the vectorstore
            engine._vectorstore = MagicMock()
            engine._vectorstore.add_documents = MagicMock()
            
            documents = [
                {"content": "Test document content", "metadata": {"source": "test"}}
            ]
            
            count = await engine.add_documents(documents, source_type="test")
            assert count > 0

    @pytest.mark.asyncio
    async def test_search(self):
        """Test searching the knowledge base."""
        with patch("chromadb.Client"):
            from agent.rag import RAGEngine, RAGConfig
            from langchain_core.documents import Document
            
            config = RAGConfig(persist_directory="/tmp/test_chroma")
            engine = RAGEngine(config)
            
            # Mock search results
            mock_docs = [
                Document(page_content="Test content", metadata={"source": "test"})
            ]
            engine._vectorstore = MagicMock()
            engine._vectorstore.similarity_search = MagicMock(return_value=mock_docs)
            
            results = await engine.search("test query", k=5)
            
            assert len(results) == 1
            assert results[0].page_content == "Test content"

    @pytest.mark.asyncio
    async def test_add_incident_context(self, mock_incident_data):
        """Test adding incident context."""
        with patch("chromadb.Client"):
            from agent.rag import RAGEngine, RAGConfig
            
            config = RAGConfig(persist_directory="/tmp/test_chroma")
            engine = RAGEngine(config)
            
            engine._vectorstore = MagicMock()
            engine._vectorstore.add_documents = MagicMock()
            
            count = await engine.add_incident_context(
                incident_key="INC-123",
                incident_data=mock_incident_data,
            )
            
            assert count > 0
