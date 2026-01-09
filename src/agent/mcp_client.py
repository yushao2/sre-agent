"""MCP Client wrapper for connecting to multiple MCP servers."""

import asyncio
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)


class MCPClientManager:
    """Manages connections to multiple MCP servers."""
    
    def __init__(self):
        self.servers: Dict[str, MCPServerConfig] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.tools_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    def register_server(self, config: MCPServerConfig):
        """Register an MCP server configuration."""
        self.servers[config.name] = config
    
    def register_servers(self, configs: List[MCPServerConfig]):
        """Register multiple MCP server configurations."""
        for config in configs:
            self.register_server(config)
    
    @asynccontextmanager
    async def connect(self, server_name: str):
        """Connect to a specific MCP server."""
        if server_name not in self.servers:
            raise ValueError(f"Unknown server: {server_name}")
        
        config = self.servers[server_name]
        
        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env,
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.sessions[server_name] = session
                try:
                    yield session
                finally:
                    del self.sessions[server_name]
    
    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get tools from all connected servers."""
        all_tools = []
        
        for server_name, session in self.sessions.items():
            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                # Prefix tool name with server name for routing
                all_tools.append({
                    "server": server_name,
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                })
        
        return all_tools
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """Call a tool on a specific MCP server."""
        if server_name not in self.sessions:
            raise ValueError(f"Not connected to server: {server_name}")
        
        session = self.sessions[server_name]
        result = await session.call_tool(tool_name, arguments)
        
        # Parse the text content from the result
        if result.content:
            for content in result.content:
                if hasattr(content, 'text'):
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return content.text
        
        return result


class MCPToolAdapter:
    """Adapts MCP tools for use with LangChain."""
    
    def __init__(self, client_manager: MCPClientManager):
        self.client = client_manager
        self._tool_map: Dict[str, tuple] = {}  # tool_name -> (server_name, original_name)
    
    async def build_tool_map(self):
        """Build a mapping of tool names to their servers."""
        all_tools = await self.client.get_all_tools()
        
        for tool in all_tools:
            # Use server-prefixed name to avoid conflicts
            full_name = f"{tool['server']}_{tool['name']}"
            self._tool_map[full_name] = (tool['server'], tool['name'])
        
        return all_tools
    
    def get_langchain_tools(self, tools: List[Dict[str, Any]]):
        """Convert MCP tools to LangChain tool format."""
        from langchain_core.tools import StructuredTool
        
        langchain_tools = []
        
        for tool in tools:
            full_name = f"{tool['server']}_{tool['name']}"
            
            # Create an async wrapper for the tool
            async def tool_func(
                _full_name=full_name,
                **kwargs
            ) -> str:
                server_name, tool_name = self._tool_map[_full_name]
                result = await self.client.call_tool(server_name, tool_name, kwargs)
                return json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
            
            langchain_tools.append(
                StructuredTool.from_function(
                    coroutine=tool_func,
                    name=full_name,
                    description=tool['description'],
                    args_schema=None,  # Will use input_schema directly
                )
            )
        
        return langchain_tools


def get_default_server_configs() -> List[MCPServerConfig]:
    """Get default MCP server configurations."""
    import os
    
    return [
        MCPServerConfig(
            name="jira",
            command="python",
            args=["-m", "mcp_servers.jira.server"],
            env={
                "JIRA_URL": os.getenv("JIRA_URL", ""),
                "JIRA_USERNAME": os.getenv("JIRA_USERNAME", ""),
                "JIRA_API_TOKEN": os.getenv("JIRA_API_TOKEN", ""),
            },
        ),
        MCPServerConfig(
            name="confluence",
            command="python",
            args=["-m", "mcp_servers.confluence.server"],
            env={
                "CONFLUENCE_URL": os.getenv("CONFLUENCE_URL", ""),
                "CONFLUENCE_USERNAME": os.getenv("CONFLUENCE_USERNAME", ""),
                "CONFLUENCE_API_TOKEN": os.getenv("CONFLUENCE_API_TOKEN", ""),
            },
        ),
        MCPServerConfig(
            name="gitlab",
            command="python",
            args=["-m", "mcp_servers.gitlab.server"],
            env={
                "GITLAB_URL": os.getenv("GITLAB_URL", "https://gitlab.com"),
                "GITLAB_TOKEN": os.getenv("GITLAB_TOKEN", ""),
            },
        ),
    ]
