"""Tests for MCP servers."""

import pytest
from unittest.mock import patch, AsyncMock


class TestJiraMCPServer:
    """Tests for the Jira MCP server."""

    @pytest.mark.asyncio
    async def test_search_issues(self):
        """Test searching Jira issues."""
        from mcp_servers.jira.server import JiraMCPServer
        
        server = JiraMCPServer()
        
        result = await server._search_issues(
            jql="project = INC",
            max_results=10,
        )
        
        assert "issues" in result
        assert "total" in result
        assert isinstance(result["issues"], list)

    @pytest.mark.asyncio
    async def test_get_issue(self):
        """Test getting a Jira issue."""
        from mcp_servers.jira.server import JiraMCPServer
        
        server = JiraMCPServer()
        
        result = await server._get_issue(
            issue_key="INC-123",
            include_comments=True,
        )
        
        assert "key" in result
        assert "summary" in result
        assert "comments" in result

    @pytest.mark.asyncio
    async def test_get_incident_thread(self):
        """Test getting full incident thread."""
        from mcp_servers.jira.server import JiraMCPServer
        
        server = JiraMCPServer()
        
        result = await server._get_incident_thread(
            issue_key="INC-123",
            include_linked_issues=True,
        )
        
        assert "key" in result
        assert "linked_issues" in result


class TestConfluenceMCPServer:
    """Tests for the Confluence MCP server."""

    @pytest.mark.asyncio
    async def test_search_pages(self):
        """Test searching Confluence pages."""
        from mcp_servers.confluence.server import ConfluenceMCPServer
        
        server = ConfluenceMCPServer()
        
        result = await server._search_pages(
            query="runbook database",
            max_results=10,
        )
        
        assert "results" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_get_page(self):
        """Test getting a Confluence page."""
        from mcp_servers.confluence.server import ConfluenceMCPServer
        
        server = ConfluenceMCPServer()
        
        result = await server._get_page(
            page_id="12345",
            include_body=True,
        )
        
        assert "id" in result
        assert "title" in result
        assert "body" in result


class TestGitLabMCPServer:
    """Tests for the GitLab MCP server."""

    @pytest.mark.asyncio
    async def test_search_code(self):
        """Test searching GitLab code."""
        from mcp_servers.gitlab.server import GitLabMCPServer
        
        server = GitLabMCPServer()
        
        result = await server._search_code(
            query="connection_pool",
            max_results=10,
        )
        
        assert "results" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_get_file(self):
        """Test getting a file from GitLab."""
        from mcp_servers.gitlab.server import GitLabMCPServer
        
        server = GitLabMCPServer()
        
        result = await server._get_file(
            project_id="backend/api-server",
            file_path="src/db/connection_pool.py",
            ref="main",
        )
        
        assert "project" in result
        assert "file_path" in result
        assert "content" in result

    @pytest.mark.asyncio
    async def test_search_merge_requests(self):
        """Test searching merge requests."""
        from mcp_servers.gitlab.server import GitLabMCPServer
        
        server = GitLabMCPServer()
        
        result = await server._search_merge_requests(
            state="merged",
            max_results=10,
        )
        
        assert "merge_requests" in result
        assert "total" in result
