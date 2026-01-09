"""Jira MCP Server Implementation."""

import asyncio
import json
from typing import Any, Dict, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# For real implementation, uncomment:
# from atlassian import Jira

from .tools import JIRA_TOOLS


class JiraMCPServer:
    """MCP Server for Jira integration."""
    
    def __init__(
        self,
        jira_url: str = "",
        username: str = "",
        api_token: str = "",
    ):
        self.jira_url = jira_url
        self.username = username
        self.api_token = api_token
        self.server = Server("jira-mcp-server")
        self._jira_client: Optional[Any] = None
        
        self._setup_handlers()
    
    @property
    def jira(self):
        """Lazy initialization of Jira client."""
        if self._jira_client is None and self.jira_url:
            # Uncomment for real implementation:
            # self._jira_client = Jira(
            #     url=self.jira_url,
            #     username=self.username,
            #     password=self.api_token,
            # )
            pass
        return self._jira_client
    
    def _setup_handlers(self):
        """Set up MCP protocol handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """Return available Jira tools."""
            return [
                Tool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["input_schema"],
                )
                for tool in JIRA_TOOLS
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Execute a Jira tool."""
            try:
                result = await self._execute_tool(name, arguments)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _execute_tool(self, name: str, arguments: dict) -> Dict[str, Any]:
        """Route tool calls to appropriate handlers."""
        handlers = {
            "jira_search_issues": self._search_issues,
            "jira_get_issue": self._get_issue,
            "jira_get_comments": self._get_comments,
            "jira_add_comment": self._add_comment,
            "jira_transition_issue": self._transition_issue,
            "jira_get_incident_thread": self._get_incident_thread,
        }
        
        handler = handlers.get(name)
        if not handler:
            raise ValueError(f"Unknown tool: {name}")
        
        return await handler(**arguments)
    
    # ========================================================================
    # Tool Implementations
    # ========================================================================
    
    async def _search_issues(
        self, 
        jql: str, 
        max_results: int = 10,
        fields: list = None,
    ) -> Dict[str, Any]:
        """Search for issues using JQL."""
        # Mock implementation for demo
        # Replace with real Jira API call:
        # results = self.jira.jql(jql, limit=max_results, fields=fields)
        
        return {
            "issues": [
                {
                    "key": "INC-123",
                    "summary": "Production database connection pool exhausted",
                    "status": "In Progress",
                    "assignee": "oncall@example.com",
                    "created": "2024-01-15T10:30:00Z",
                    "priority": "Critical",
                },
                {
                    "key": "INC-124",
                    "summary": "API latency spike in payment service",
                    "status": "Open",
                    "assignee": None,
                    "created": "2024-01-15T11:00:00Z",
                    "priority": "High",
                },
            ],
            "total": 2,
            "jql": jql,
        }
    
    async def _get_issue(
        self,
        issue_key: str,
        include_comments: bool = True,
        include_changelog: bool = False,
    ) -> Dict[str, Any]:
        """Get detailed issue information."""
        # Mock implementation
        issue = {
            "key": issue_key,
            "summary": "Production database connection pool exhausted",
            "description": """
## Impact
Users experiencing timeouts when accessing the dashboard.

## Timeline
- 10:30 UTC - First alerts fired
- 10:35 UTC - Oncall paged
- 10:40 UTC - Investigation started

## Initial Observations
- Connection pool at 100% utilization
- No recent deployments
- Traffic levels normal
            """,
            "status": "In Progress",
            "priority": "Critical",
            "assignee": {"email": "oncall@example.com", "name": "On-Call Engineer"},
            "reporter": {"email": "monitoring@example.com", "name": "Monitoring System"},
            "created": "2024-01-15T10:30:00Z",
            "updated": "2024-01-15T11:15:00Z",
            "labels": ["incident", "database", "production"],
            "components": ["backend", "database"],
        }
        
        if include_comments:
            issue["comments"] = await self._get_comments(issue_key)
        
        if include_changelog:
            issue["changelog"] = [
                {"field": "status", "from": "Open", "to": "In Progress", "timestamp": "2024-01-15T10:35:00Z"},
            ]
        
        return issue
    
    async def _get_comments(
        self,
        issue_key: str,
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """Get comments for an issue."""
        return {
            "comments": [
                {
                    "author": "oncall@example.com",
                    "body": "Starting investigation. Checking connection pool metrics.",
                    "created": "2024-01-15T10:35:00Z",
                },
                {
                    "author": "oncall@example.com", 
                    "body": "Found the issue - a long-running query from the reporting service is holding connections. Query: SELECT * FROM orders WHERE created_at > '2020-01-01' (no index on created_at)",
                    "created": "2024-01-15T10:50:00Z",
                },
                {
                    "author": "dba@example.com",
                    "body": "Confirmed. The reporting job started at 10:25 UTC. I'm going to kill the query and we should add an index.",
                    "created": "2024-01-15T11:00:00Z",
                },
                {
                    "author": "oncall@example.com",
                    "body": "Query killed. Connection pool recovering. Dashboard access restored.",
                    "created": "2024-01-15T11:10:00Z",
                },
            ],
            "total": 4,
        }
    
    async def _add_comment(
        self,
        issue_key: str,
        body: str,
    ) -> Dict[str, Any]:
        """Add a comment to an issue."""
        # Mock implementation
        return {
            "success": True,
            "comment_id": "12345",
            "issue_key": issue_key,
            "body": body,
        }
    
    async def _transition_issue(
        self,
        issue_key: str,
        transition_name: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transition an issue to a new status."""
        # Mock implementation
        return {
            "success": True,
            "issue_key": issue_key,
            "new_status": transition_name,
            "comment_added": comment is not None,
        }
    
    async def _get_incident_thread(
        self,
        issue_key: str,
        include_linked_issues: bool = True,
    ) -> Dict[str, Any]:
        """Get complete incident thread for summarization."""
        issue = await self._get_issue(issue_key, include_comments=True, include_changelog=True)
        
        if include_linked_issues:
            issue["linked_issues"] = [
                {
                    "key": "DEPLOY-456",
                    "type": "is caused by",
                    "summary": "Reporting job schedule change",
                    "status": "Done",
                },
            ]
        
        return issue
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def main():
    """Entry point for the Jira MCP server."""
    import os
    
    server = JiraMCPServer(
        jira_url=os.getenv("JIRA_URL", ""),
        username=os.getenv("JIRA_USERNAME", ""),
        api_token=os.getenv("JIRA_API_TOKEN", ""),
    )
    
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
