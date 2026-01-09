"""Main AI SRE Agent implementation using LangChain."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent

from .prompts import SRE_AGENT_SYSTEM_PROMPT, format_incident_prompt
from .rag import RAGEngine, RAGConfig
from .mcp_client import MCPClientManager, MCPServerConfig, get_default_server_configs


class SREAgent:
    """
    AI SRE Agent that orchestrates MCP tools and RAG for incident management.
    
    This agent can:
    - Summarize incident threads
    - Search documentation and runbooks
    - Analyze code changes
    - Provide root cause analysis
    - Triage support tickets
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        model_name: str = "claude-sonnet-4-20250514",
        rag_config: Optional[RAGConfig] = None,
        mcp_configs: Optional[List[MCPServerConfig]] = None,
    ):
        self.model_name = model_name
        self.anthropic_api_key = anthropic_api_key
        
        # Initialize LLM
        self.llm = ChatAnthropic(
            model=model_name,
            anthropic_api_key=anthropic_api_key,
            max_tokens=4096,
        )
        
        # Initialize RAG
        self.rag = RAGEngine(rag_config)
        
        # Initialize MCP client manager
        self.mcp_manager = MCPClientManager()
        mcp_configs = mcp_configs or get_default_server_configs()
        self.mcp_manager.register_servers(mcp_configs)
        
        # Agent executor (initialized when connecting to MCP servers)
        self._agent_executor: Optional[AgentExecutor] = None
    
    def _create_tools(self) -> List:
        """Create LangChain tools for the agent."""
        
        @tool
        async def search_knowledge_base(query: str, k: int = 5) -> str:
            """
            Search the knowledge base for relevant documentation, runbooks, and past incidents.
            
            Args:
                query: Search query describing what you're looking for
                k: Number of results to return (default 5)
            
            Returns:
                Relevant context from the knowledge base
            """
            results = await self.rag.search(query, k=k)
            
            if not results:
                return "No relevant documents found in the knowledge base."
            
            formatted = []
            for doc in results:
                source = doc.metadata.get("source", "unknown")
                doc_type = doc.metadata.get("type", "document")
                formatted.append(f"[{doc_type}] {source}:\n{doc.page_content}\n")
            
            return "\n---\n".join(formatted)
        
        @tool
        async def get_incident_context(incident_key: str, summary: str = "") -> str:
            """
            Get all relevant context for a specific incident from the knowledge base.
            
            Args:
                incident_key: The incident key (e.g., INC-123)
                summary: Optional incident summary to help find related content
            
            Returns:
                All relevant context including incident details and related documentation
            """
            results = await self.rag.get_incident_context(
                incident_key=incident_key,
                additional_query=summary,
                k=10,
            )
            
            if not results:
                return f"No indexed context found for incident {incident_key}."
            
            formatted = []
            for doc in results:
                source = doc.metadata.get("source", "unknown")
                formatted.append(f"[{source}]:\n{doc.page_content}\n")
            
            return "\n---\n".join(formatted)
        
        return [search_knowledge_base, get_incident_context]
    
    async def _build_agent(self, mcp_tools: List = None) -> AgentExecutor:
        """Build the LangChain agent with all tools."""
        
        # Get RAG tools
        rag_tools = self._create_tools()
        
        # Combine with MCP tools if provided
        all_tools = rag_tools + (mcp_tools or [])
        
        # Create the prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", SRE_AGENT_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create the agent
        agent = create_tool_calling_agent(self.llm, all_tools, prompt)
        
        # Create executor
        return AgentExecutor(
            agent=agent,
            tools=all_tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True,
        )
    
    async def summarize_incident(
        self,
        incident_key: str,
        incident_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Summarize an incident thread.
        
        Args:
            incident_key: The incident key (e.g., INC-123)
            incident_data: Pre-fetched incident data (optional, will fetch if not provided)
        
        Returns:
            A structured incident summary
        """
        # If incident data provided, index it for RAG
        if incident_data:
            await self.rag.add_incident_context(incident_key, incident_data)
        
        # Build the analysis request
        input_text = f"""Please analyze and summarize incident {incident_key}.

Steps to follow:
1. Use the jira_get_incident_thread tool to get the full incident details
2. Search the knowledge base for relevant runbooks and documentation
3. If needed, search GitLab for related code changes
4. Provide a comprehensive incident summary

Start by fetching the incident details."""
        
        # Run the agent
        result = await self._agent_executor.ainvoke({
            "input": input_text,
            "chat_history": [],
        })
        
        return result.get("output", "Unable to generate summary.")
    
    async def triage_ticket(
        self,
        ticket_key: str,
        ticket_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Triage a support ticket.
        
        Args:
            ticket_key: The ticket key
            ticket_data: Pre-fetched ticket data
        
        Returns:
            Triage result including category, priority, and recommendations
        """
        input_text = f"""Please triage support ticket {ticket_key}.

Steps to follow:
1. Use the jira_get_issue tool to get the ticket details
2. Search the knowledge base for related issues and documentation
3. Determine the appropriate category, priority, and owner
4. Suggest initial response or resolution steps

Provide your triage analysis in a structured JSON format with keys:
- category: The issue category
- priority: Suggested priority (Critical, High, Medium, Low)
- team: Appropriate team to handle
- initial_response: Suggested response
- needs_escalation: Boolean
- reasoning: Brief explanation"""
        
        result = await self._agent_executor.ainvoke({
            "input": input_text,
            "chat_history": [],
        })
        
        # Try to parse JSON from result
        output = result.get("output", "{}")
        try:
            # Find JSON in the output
            import re
            json_match = re.search(r'\{[^{}]*\}', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        
        return {"raw_response": output}
    
    async def analyze_root_cause(
        self,
        incident_key: str,
    ) -> str:
        """
        Perform root cause analysis for an incident.
        
        Args:
            incident_key: The incident key
        
        Returns:
            Detailed root cause analysis
        """
        input_text = f"""Perform a detailed root cause analysis for incident {incident_key}.

Steps to follow:
1. Get the full incident thread with comments
2. Search for recent merge requests and code changes in related services
3. Review relevant documentation and runbooks
4. Apply the "5 Whys" technique to identify the root cause
5. Provide recommendations to prevent recurrence

Be thorough and cite specific evidence for your conclusions."""
        
        result = await self._agent_executor.ainvoke({
            "input": input_text,
            "chat_history": [],
        })
        
        return result.get("output", "Unable to complete root cause analysis.")
    
    async def run(self, query: str, chat_history: List = None) -> str:
        """
        Run the agent with a free-form query.
        
        Args:
            query: The user's question or request
            chat_history: Optional conversation history
        
        Returns:
            Agent's response
        """
        result = await self._agent_executor.ainvoke({
            "input": query,
            "chat_history": chat_history or [],
        })
        
        return result.get("output", "No response generated.")


class SREAgentSimple:
    """
    Simplified SRE Agent that works without MCP connections.
    
    Uses mock data for demonstration purposes.
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        model_name: str = "claude-sonnet-4-20250514",
    ):
        self.llm = ChatAnthropic(
            model=model_name,
            anthropic_api_key=anthropic_api_key,
            max_tokens=4096,
        )
        self.rag = RAGEngine()
    
    async def summarize_incident_simple(
        self,
        incident_data: Dict[str, Any],
    ) -> str:
        """
        Summarize an incident using provided data (no MCP needed).
        
        Args:
            incident_data: Complete incident data including comments
        
        Returns:
            Incident summary
        """
        # Index the incident
        incident_key = incident_data.get("key", "UNKNOWN")
        await self.rag.add_incident_context(incident_key, incident_data)
        
        # Get relevant context
        summary = incident_data.get("summary", "")
        context_docs = await self.rag.search(summary, k=5)
        context = "\n\n".join([doc.page_content for doc in context_docs])
        
        # Format prompt
        prompt = format_incident_prompt(
            incident_data=json.dumps(incident_data, indent=2),
            rag_context=context or "No additional context available.",
        )
        
        # Get response
        messages = [
            SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        
        response = await self.llm.ainvoke(messages)
        return response.content
