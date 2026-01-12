# src/agent/agent.py

from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .prompts import SRE_AGENT_SYSTEM_PROMPT, format_ops_triage_prompt, format_triage_prompt
from .intake import normalize_to_triage_context, jira_issue_to_triage_context

# ... keep existing class and __init__ ...

class SREAgentSimple:
    # ... keep summarize_incident_simple etc ...

    async def triage_ops_simple(self, ctx: Dict[str, Any]) -> str:
        """
        Source-agnostic ops triage:
        - Jira tickets
        - Incident chats
        - Support channels
        - Anything normalized into TriageContext-like dict
        """
        prompt = format_ops_triage_prompt(ctx)

        response = await self.llm.ainvoke(
            [
                SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        return str(response.content)

    async def triage_unstructured(self, text: str, source_hint: str = "unknown") -> str:
        """
        Accept totally unstructured input (chat paste, logs, partial context),
        normalize it into TriageContext, then triage.
        """
        normalized = await normalize_to_triage_context(self.llm, text=text, source_hint=source_hint)  # type: ignore[arg-type]
        ctx = normalized.model_dump(exclude_none=True)
        return await self.triage_ops_simple(ctx)

    async def triage_jira_issue(
        self,
        issue: Dict[str, Any],
        comments: Optional[list[Dict[str, Any]]] = None,
    ) -> str:
        """
        Triage using Jira MCP output directly (no need to pre-shape into ticket fields).
        """
        ctx = jira_issue_to_triage_context(issue=issue, comments=comments)
        return await self.triage_ops_simple(ctx)

    async def triage_ticket_simple(self, ticket_data: Dict[str, Any]) -> str:
        """
        Backwards-compatible: old ticket triage now routes via ops triage formatting.
        """
        prompt = format_triage_prompt(ticket_data)

        response = await self.llm.ainvoke(
            [
                SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        return str(response.content)