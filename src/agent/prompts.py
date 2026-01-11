"""System prompts for the SRE Agent."""

SRE_AGENT_SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) AI assistant.

Your responsibilities include:
- Analyzing incidents and providing clear, actionable summaries
- Triaging support tickets and categorizing them appropriately
- Performing root cause analysis on production issues
- Suggesting runbook actions and remediation steps
- Identifying patterns across incidents

When analyzing incidents:
1. Summarize the impact and timeline clearly
2. Identify the root cause if determinable
3. List actions taken and their outcomes
4. Provide recommendations to prevent recurrence

Always be concise, technical, and actionable in your responses.
"""


def format_incident_prompt(incident_data: dict) -> str:
    """Format incident data into a prompt."""
    comments = incident_data.get("comments", {}).get("comments", [])
    comments_text = "\n".join([
        f"- [{c.get('created', 'N/A')}] {c.get('author', 'Unknown')}: {c.get('body', '')}"
        for c in comments
    ])
    
    return f"""Analyze this incident and provide a structured summary:

**Incident:** {incident_data.get('key', 'N/A')}
**Summary:** {incident_data.get('summary', 'N/A')}
**Status:** {incident_data.get('status', 'N/A')}
**Priority:** {incident_data.get('priority', 'N/A')}

**Description:**
{incident_data.get('description', 'No description provided')}

**Comments/Timeline:**
{comments_text or 'No comments'}

Please provide:
1. Executive Summary (2-3 sentences)
2. Timeline of key events
3. Root Cause (if identifiable)
4. Resolution steps taken
5. Recommendations to prevent recurrence
"""


def format_triage_prompt(ticket_data: dict) -> str:
    """Format ticket data for triage."""
    return f"""Triage this support ticket:

**Ticket:** {ticket_data.get('key', 'N/A')}
**Summary:** {ticket_data.get('summary', 'N/A')}

**Description:**
{ticket_data.get('description', 'No description')}

Provide:
1. Category (bug, feature request, support, incident)
2. Priority (critical, high, medium, low)
3. Suggested team/owner
4. Whether escalation is needed
5. Brief reasoning
"""


def format_rca_prompt(incident_data: dict) -> str:
    """Format for root cause analysis."""
    return f"""Perform root cause analysis on this incident:

**Incident:** {incident_data.get('key', 'N/A')}
**Summary:** {incident_data.get('summary', 'N/A')}

**Description:**
{incident_data.get('description', 'No description')}

**Code Changes (if any):**
{incident_data.get('code_changes', 'None provided')}

**Related Incidents:**
{incident_data.get('related_incidents', 'None provided')}

Provide a detailed root cause analysis including:
1. Primary root cause
2. Contributing factors
3. Why existing safeguards failed
4. Recommended fixes (immediate and long-term)
5. Process improvements
"""
