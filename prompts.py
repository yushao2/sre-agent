# src/agent/prompts.py

from typing import Any, Dict, List, Optional

# (keep existing SRE_AGENT_SYSTEM_PROMPT, incident + rca formatters, etc.)

def format_ops_triage_prompt(ctx: Dict[str, Any]) -> str:
    """
    Format source-agnostic operational triage input.

    Works for:
    - Jira tickets
    - Incident chats / war rooms
    - Support channel threads
    - Arbitrary pasted text (after normalization)
    """
    source_type = ctx.get("source_type", "unknown")
    external_id = ctx.get("external_id")
    title = ctx.get("title")

    problem_statement = ctx.get("problem_statement", "No problem statement provided")
    impact = ctx.get("impact")
    scope = ctx.get("scope")
    severity = ctx.get("severity")
    urgency = ctx.get("urgency")

    what_changed = ctx.get("what_changed")
    actions_taken = ctx.get("actions_taken", []) or []
    current_status = ctx.get("current_status")

    suspected_services = ctx.get("suspected_services", []) or []
    suspected_causes = ctx.get("suspected_causes", []) or []

    evidence = ctx.get("evidence", []) or []
    open_questions = ctx.get("open_questions", []) or []
    stakeholders = ctx.get("stakeholders", []) or []

    def fmt_list(items: List[str]) -> str:
        return "\n".join(f"- {x}" for x in items) if items else "- (none provided)"

    def fmt_evidence(items: List[Dict[str, Any]]) -> str:
        if not items:
            return "- (none provided)"
        out = []
        for e in items:
            kind = e.get("kind", "other")
            author = e.get("author")
            ts = e.get("timestamp")
            header = f"[{kind}]"
            meta = " ".join(x for x in [author, ts] if x)
            if meta:
                header = f"{header} {meta}"
            out.append(f"- {header}\n  {e.get('content', '')}")
        return "\n".join(out)

    prompt = f"""Please triage the following operational issue.

## Source
- **Type**: {source_type}
- **External ID**: {external_id or "N/A"}
- **Title**: {title or "N/A"}

## Problem Statement
{problem_statement}

## Impact / Scope / Severity
- **Impact**: {impact or "Unknown"}
- **Scope**: {scope or "Unknown"}
- **Severity**: {severity or "Unknown"}
- **Urgency**: {urgency or "Unknown"}

## Current Status
{current_status or "Unknown"}

## What Changed (if known)
{what_changed or "Unknown"}

## Actions Taken So Far
{fmt_list(actions_taken)}

## Suspected Services
{", ".join(suspected_services) if suspected_services else "Unknown"}

## Suspected Causes / Hypotheses (if any)
{fmt_list(suspected_causes)}

## Evidence (logs/metrics/links/messages)
{fmt_evidence(evidence)}

## Stakeholders (if known)
{", ".join(stakeholders) if stakeholders else "Unknown"}

## Open Questions
{fmt_list(open_questions)}

Now produce:
1. **Situation Summary** (2-5 bullets)
2. **Working Hypotheses (ranked)** with evidence for/against each
3. **Immediate Actions (next 15 min)**: concrete steps + what signal to check
4. **Next Actions (next 1-2 hours)**: deeper investigation / mitigation / comms
5. **What to Ask For**: the minimum questions to reduce uncertainty quickly
6. **Mitigation/Containment Options** (if incident-like) + rollback/stop criteria
7. **Who to Involve** (teams/roles; names only if provided)
"""
    return prompt


def format_triage_prompt(ticket_data: Dict[str, Any]) -> str:
    """
    Backwards-compatible wrapper: the old ticket-specific triage now routes through ops triage format.
    """
    # Preserve old behavior as much as possible:
    key = ticket_data.get("key")
    summary = ticket_data.get("summary")
    description = ticket_data.get("description", "")

    reporter = ticket_data.get("reporter")
    labels = ticket_data.get("labels") or []

    ctx = {
        "source_type": "jira_ticket",
        "external_id": key,
        "title": summary,
        "problem_statement": (summary or "").strip() or (description.strip()[:200] if description.strip() else "No problem statement provided"),
        "current_status": ticket_data.get("status"),
        "severity": ticket_data.get("priority"),
        "suspected_services": labels,
        "evidence": [{"kind": "message", "content": description, "author": reporter, "timestamp": None}] if description else [],
        "stakeholders": [reporter] if reporter else [],
        "actions_taken": [],
        "open_questions": [],
    }

    return format_ops_triage_prompt(ctx)