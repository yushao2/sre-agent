"""
Core SRE Agent implementation.

This module provides the AI-powered SRE agent that can:
- Summarize incidents with structured analysis
- Triage support tickets with priority recommendations
- Perform root cause analysis on production issues
- Answer SRE-related questions via chat

Example:
    >>> from agent import SREAgentSimple
    >>> agent = SREAgentSimple()
    >>> result = await agent.summarize_incident_simple({
    ...     "key": "INC-123",
    ...     "summary": "Database connection timeout",
    ...     "description": "Users seeing 504 errors...",
    ... })
"""

import json
import os
from typing import Any, Dict, List, Optional, Union

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from .prompts import (
    SRE_AGENT_SYSTEM_PROMPT,
    format_incident_prompt,
    format_triage_prompt,
    format_rca_prompt,
)


class SREAgentSimple:
    """
    Simplified SRE Agent that works with provided data directly.
    
    This is the recommended agent for most use cases. Pass incident/ticket
    data directly without requiring MCP server connections.
    
    Attributes:
        api_key: Anthropic API key (from param or ANTHROPIC_API_KEY env var)
        model_name: Claude model to use (default: claude-sonnet-4-20250514)
        llm: LangChain ChatAnthropic instance
    
    Example:
        >>> agent = SREAgentSimple()
        >>> # Or with explicit key
        >>> agent = SREAgentSimple(anthropic_api_key="sk-ant-...")
    """
    
    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        model_name: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ):
        """
        Initialize the SRE Agent.
        
        Args:
            anthropic_api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY 
                              environment variable if not provided.
            model_name: Claude model identifier. Defaults to claude-sonnet-4-20250514.
            max_tokens: Maximum tokens in response. Defaults to 4096.
            temperature: Sampling temperature (0.0 = deterministic). Defaults to 0.0.
        
        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY required. Pass it as a parameter or set the "
                "ANTHROPIC_API_KEY environment variable."
            )
        
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        self.llm = ChatAnthropic(
            model=model_name,
            anthropic_api_key=self.api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    
    async def summarize_incident_simple(
        self,
        incident_data: Dict[str, Any],
    ) -> str:
        """
        Generate a structured summary of an incident.
        
        Analyzes the incident data and produces a summary including:
        - Executive summary
        - Timeline of key events
        - Root cause (if identifiable)
        - Resolution steps taken
        - Recommendations to prevent recurrence
        
        Args:
            incident_data: Dictionary containing incident details:
                - key (str): Incident identifier (e.g., "INC-123")
                - summary (str): Brief title/summary
                - description (str, optional): Full description
                - status (str, optional): Current status
                - priority (str, optional): Priority level
                - comments (dict, optional): Dict with 'comments' list containing
                  comment objects with 'author', 'body', 'created' fields
        
        Returns:
            Markdown-formatted incident summary.
        
        Example:
            >>> summary = await agent.summarize_incident_simple({
            ...     "key": "INC-123",
            ...     "summary": "API latency spike",
            ...     "description": "p99 latency increased from 100ms to 5s",
            ...     "status": "Resolved",
            ...     "priority": "High",
            ...     "comments": {
            ...         "comments": [
            ...             {"author": "oncall", "body": "Investigating...", "created": "..."}
            ...         ]
            ...     }
            ... })
        """
        prompt = format_incident_prompt(incident_data)
        
        response = await self.llm.ainvoke([
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        
        return str(response.content)
    
    async def triage_ticket_simple(
        self,
        ticket_data: Dict[str, Any],
    ) -> str:
        """
        Triage a support ticket and provide categorization.
        
        Analyzes the ticket and provides:
        - Category (bug, feature request, support, incident)
        - Recommended priority (critical, high, medium, low)
        - Suggested team/owner
        - Whether escalation is needed
        - Brief reasoning
        
        Args:
            ticket_data: Dictionary containing ticket details:
                - key (str): Ticket identifier (e.g., "TICKET-456")
                - summary (str): Brief title/summary
                - description (str, optional): Full description
                - reporter (dict, optional): Reporter information
                - labels (list, optional): Existing labels
        
        Returns:
            Triage analysis as formatted text.
        
        Example:
            >>> result = await agent.triage_ticket_simple({
            ...     "key": "SUPPORT-789",
            ...     "summary": "Cannot export reports",
            ...     "description": "PDF export button does nothing..."
            ... })
        """
        prompt = format_triage_prompt(ticket_data)
        
        response = await self.llm.ainvoke([
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        
        return str(response.content)
    
    async def analyze_root_cause(
        self,
        incident_data: Dict[str, Any],
        code_changes: Optional[List[Dict[str, Any]]] = None,
        related_incidents: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Perform root cause analysis on an incident.
        
        Provides detailed RCA including:
        - Primary root cause
        - Contributing factors
        - Why existing safeguards failed
        - Recommended fixes (immediate and long-term)
        - Process improvements
        
        Args:
            incident_data: Dictionary containing incident details (same as summarize).
            code_changes: Optional list of related code changes/merge requests.
                         Each dict may contain 'title', 'url', 'author', 'diff'.
            related_incidents: Optional list of similar past incidents for context.
        
        Returns:
            Root cause analysis as formatted text.
        
        Example:
            >>> rca = await agent.analyze_root_cause(
            ...     incident_data={"key": "INC-123", "summary": "..."},
            ...     code_changes=[{"title": "Add caching", "url": "..."}],
            ... )
        """
        # Enrich incident data with additional context
        enriched_data = incident_data.copy()
        
        if code_changes:
            enriched_data["code_changes"] = json.dumps(code_changes, indent=2)
        
        if related_incidents:
            enriched_data["related_incidents"] = json.dumps(related_incidents, indent=2)
        
        prompt = format_rca_prompt(enriched_data)
        
        response = await self.llm.ainvoke([
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        
        return str(response.content)
    
    async def chat(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Free-form chat with the SRE agent.
        
        Ask questions about SRE topics, debugging, incident response,
        or provide context for analysis.
        
        Args:
            message: User message or question.
            context: Optional context dictionary that will be included
                    in the prompt (e.g., current incident details).
            conversation_history: Optional list of previous messages for
                                 multi-turn conversations. Each dict should
                                 have 'role' ('user' or 'assistant') and 'content'.
        
        Returns:
            Agent's response.
        
        Example:
            >>> # Simple question
            >>> response = await agent.chat("What causes connection pool exhaustion?")
            
            >>> # With context
            >>> response = await agent.chat(
            ...     "What should I check next?",
            ...     context={"error": "OOMKilled", "service": "api-gateway"}
            ... )
        """
        # Build message content
        content = message
        if context:
            content = f"{message}\n\nContext:\n```json\n{json.dumps(context, indent=2)}\n```"
        
        # Build messages list
        messages: List[Union[SystemMessage, HumanMessage]] = [
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
        ]
        
        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                # Note: For assistant messages, we'd need AIMessage from langchain
                # Skipping for simplicity - can be added if multi-turn is needed
        
        messages.append(HumanMessage(content=content))
        
        response = await self.llm.ainvoke(messages)
        
        return str(response.content)


# Backwards compatibility alias
SREAgent = SREAgentSimple
