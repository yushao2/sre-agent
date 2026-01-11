"""
Core SRE Agent implementation.

This module provides the agent that can summarize incidents,
triage tickets, and perform root cause analysis.
"""

import os
from typing import Any, Dict, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from .prompts import (
    SRE_AGENT_SYSTEM_PROMPT,
    format_incident_prompt,
    format_triage_prompt,
    format_rca_prompt,
)


class SREAgent:
    """
    Full SRE Agent with MCP server connections.
    
    Use this when you have MCP servers running for Jira, Confluence, GitLab.
    """
    
    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        model_name: str = "claude-sonnet-4-20250514",
    ):
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required")
        
        self.model_name = model_name
        self.llm = ChatAnthropic(
            model=model_name,
            anthropic_api_key=self.api_key,
        )
    
    async def summarize_incident(self, incident_key: str) -> str:
        """Summarize an incident by fetching data from Jira."""
        # Would use MCP client to fetch from Jira
        raise NotImplementedError("Use SREAgentSimple for standalone usage")
    
    async def triage_ticket(self, ticket_key: str) -> Dict[str, Any]:
        """Triage a ticket using full context."""
        raise NotImplementedError("Use SREAgentSimple for standalone usage")


class SREAgentSimple:
    """
    Simplified SRE Agent that works with provided data.
    
    Use this when you want to pass incident/ticket data directly
    without MCP server connections.
    """
    
    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        model_name: str = "claude-sonnet-4-20250514",
    ):
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required")
        
        self.model_name = model_name
        self.llm = ChatAnthropic(
            model=model_name,
            anthropic_api_key=self.api_key,
        )
    
    async def summarize_incident_simple(self, incident_data: Dict[str, Any]) -> str:
        """
        Summarize an incident from provided data.
        
        Args:
            incident_data: Dict with keys like 'key', 'summary', 'description', 'comments'
        
        Returns:
            Structured summary as markdown text
        """
        prompt = format_incident_prompt(incident_data)
        
        response = await self.llm.ainvoke([
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        
        return response.content
    
    async def triage_ticket_simple(self, ticket_data: Dict[str, Any]) -> str:
        """
        Triage a ticket from provided data.
        
        Args:
            ticket_data: Dict with ticket details
        
        Returns:
            Triage result as text
        """
        prompt = format_triage_prompt(ticket_data)
        
        response = await self.llm.ainvoke([
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        
        return response.content
    
    async def analyze_root_cause(self, incident_data: Dict[str, Any]) -> str:
        """
        Perform root cause analysis.
        
        Args:
            incident_data: Dict with incident details, optionally including
                          'code_changes' and 'related_incidents'
        
        Returns:
            RCA result as text
        """
        prompt = format_rca_prompt(incident_data)
        
        response = await self.llm.ainvoke([
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        
        return response.content
    
    async def chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Free-form chat with SRE context.
        
        Args:
            message: User message
            context: Optional context dict
        
        Returns:
            Agent response
        """
        context_str = ""
        if context:
            import json
            context_str = f"\n\nContext:\n{json.dumps(context, indent=2)}"
        
        response = await self.llm.ainvoke([
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=f"{message}{context_str}"),
        ])
        
        return response.content
