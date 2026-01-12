# src/agent/intake.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser


SourceType = Literal["jira_ticket", "incident_chat", "support_channel", "email", "unknown"]


class EvidenceItem(BaseModel):
    kind: Literal["log", "metric", "trace", "command_output", "link", "message", "other"] = "other"
    content: str
    timestamp: Optional[str] = None
    author: Optional[str] = None


class TriageContext(BaseModel):
    # Where did this come from?
    source_type: SourceType = "unknown"
    external_id: Optional[str] = Field(default=None, description="INC-123 / JIRA-456 / thread link / etc.")
    title: Optional[str] = None

    # Core triage facts (best-effort)
    problem_statement: str = Field(description="What is happening? Cleaned, best-effort.")
    impact: Optional[str] = None
    scope: Optional[str] = None
    severity: Optional[str] = None  # Sev0/1/2 or High/Med/Low, etc.
    urgency: Optional[str] = None

    # Operational state
    what_changed: Optional[str] = None
    actions_taken: List[str] = Field(default_factory=list)
    current_status: Optional[str] = None

    # Signals
    suspected_services: List[str] = Field(default_factory=list)
    suspected_causes: List[str] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)

    # Coordination
    stakeholders: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)


INTAKE_SYSTEM = """You convert unstructured SRE/support/incident input into STRICT JSON that matches the schema.

Rules:
- Output ONLY valid JSON. No markdown. No backticks. No commentary.
- If unknown, use null (or [] for lists).
- Do not invent specifics (e.g. exact services/metrics) unless clearly present in the input.
- Prefer preserving key details: symptoms, errors, timestamps, impact, actions taken, hypotheses, questions.
"""


async def normalize_to_triage_context(llm, text: str, source_hint: SourceType = "unknown") -> TriageContext:
    """
    Turn arbitrary unstructured text (chat paste, ticket paste, logs) into TriageContext.
    """
    parser = PydanticOutputParser(pydantic_object=TriageContext)

    prompt = f"""
Normalize the input into the schema.

SCHEMA INSTRUCTIONS:
{parser.get_format_instructions()}

SOURCE HINT:
{source_hint}

UNSTRUCTURED INPUT:
{text}
""".strip()

    resp = await llm.ainvoke(
        [
            SystemMessage(content=INTAKE_SYSTEM),
            HumanMessage(content=prompt),
        ]
    )
    return parser.parse(str(resp.content))


def jira_issue_to_triage_context(
    issue: Dict[str, Any],
    comments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Map the MCP Jira get_issue() output (and optional get_issue_comments()) into a TriageContext-like dict.

    Expected issue shape (from mcp_servers/jira/server.py):
      key, summary, description, status, priority, assignee, reporter, labels, components, issue_type, project, created, updated
    Expected comments element shape:
      id, author, body, created, updated
    """
    key = issue.get("key")
    summary = issue.get("summary") or None
    description = issue.get("description") or ""
    status = issue.get("status") or None
    priority = issue.get("priority") or None

    components = issue.get("components") or []
    labels = issue.get("labels") or []

    stakeholders: List[str] = []
    if issue.get("assignee"):
        stakeholders.append(str(issue["assignee"]))
    if issue.get("reporter"):
        stakeholders.append(str(issue["reporter"]))

    evidence: List[Dict[str, Any]] = []

    # Treat description as "message-like" evidence if it contains content
    if description.strip():
        evidence.append(
            {
                "kind": "message",
                "content": description,
                "timestamp": issue.get("created"),
                "author": issue.get("reporter"),
            }
        )

    if comments:
        for c in comments:
            body = (c.get("body") or "").strip()
            if not body:
                continue
            evidence.append(
                {
                    "kind": "message",
                    "content": body,
                    "timestamp": c.get("created"),
                    "author": c.get("author"),
                }
            )

    ctx: Dict[str, Any] = {
        "source_type": "jira_ticket",
        "external_id": key,
        "title": summary,
        # problem_statement should always be non-empty:
        "problem_statement": (summary or "").strip() or (description.strip()[:200] if description.strip() else "No problem statement provided"),
        "current_status": status,
        # map Jira "priority" to severity loosely; keep raw string
        "severity": priority,
        "suspected_services": [*components],
        # labels often hint routing/service; keep as signals
        "suspected_causes": [],
        "evidence": evidence,
        "stakeholders": stakeholders,
        "open_questions": [],
        "actions_taken": [],
        "impact": None,
        "scope": None,
        "urgency": None,
        "what_changed": None,
    }

    # Heuristic: labels/components often include service names
    # (Leave to LLM triage to interpret; we just preserve them.)
    if labels:
        ctx["suspected_services"] = list(dict.fromkeys([*ctx["suspected_services"], *labels]))

    return ctx