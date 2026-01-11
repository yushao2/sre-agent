"""
System prompts and formatting functions for the SRE Agent.

This module contains:
- The main system prompt that defines the agent's behavior
- Formatting functions that structure user data into effective prompts

The prompts are designed to elicit structured, actionable responses
from Claude for SRE-related tasks.
"""

from typing import Any, Dict, List

# =============================================================================
# System Prompt
# =============================================================================

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

Communication style:
- Be concise and technical
- Use clear structure with headers and bullet points
- Focus on actionable insights
- Acknowledge uncertainty when root cause is unclear
- Prioritize information by importance

Always respond in a structured, professional manner suitable for
incident reviews and post-mortems.
"""


# =============================================================================
# Prompt Formatting Functions
# =============================================================================

def format_incident_prompt(incident_data: Dict[str, Any]) -> str:
    """
    Format incident data into a prompt for summarization.
    
    Args:
        incident_data: Dictionary containing incident details:
            - key: Incident identifier
            - summary: Brief title
            - description: Full description
            - status: Current status
            - priority: Priority level
            - comments: Dict with 'comments' list
    
    Returns:
        Formatted prompt string for the LLM.
    """
    # Extract and format comments/timeline
    comments_data = incident_data.get("comments", {})
    comments: List[Dict[str, Any]] = []
    
    if isinstance(comments_data, dict):
        comments = comments_data.get("comments", [])
    elif isinstance(comments_data, list):
        comments = comments_data
    
    comments_text = "\n".join([
        f"- [{c.get('created', 'N/A')}] {c.get('author', 'Unknown')}: {c.get('body', '')}"
        for c in comments
    ]) if comments else "No comments available"
    
    # Extract labels if present
    labels = incident_data.get("labels", [])
    labels_text = ", ".join(labels) if labels else "None"
    
    return f"""Analyze this incident and provide a structured summary:

**Incident:** {incident_data.get('key', 'N/A')}
**Summary:** {incident_data.get('summary', 'N/A')}
**Status:** {incident_data.get('status', 'N/A')}
**Priority:** {incident_data.get('priority', 'N/A')}
**Labels:** {labels_text}

**Description:**
{incident_data.get('description', 'No description provided')}

**Comments/Timeline:**
{comments_text}

Please provide:
1. **Executive Summary** (2-3 sentences capturing impact and resolution)
2. **Timeline** of key events
3. **Root Cause** (if identifiable from the information provided)
4. **Resolution** steps taken
5. **Recommendations** to prevent recurrence
"""


def format_triage_prompt(ticket_data: Dict[str, Any]) -> str:
    """
    Format ticket data for triage analysis.
    
    Args:
        ticket_data: Dictionary containing ticket details:
            - key: Ticket identifier
            - summary: Brief title
            - description: Full description
            - reporter: Reporter information (optional)
            - labels: Existing labels (optional)
    
    Returns:
        Formatted prompt string for the LLM.
    """
    # Format reporter info if available
    reporter = ticket_data.get("reporter", {})
    reporter_text = "Unknown"
    if isinstance(reporter, dict):
        reporter_text = reporter.get("displayName", reporter.get("name", "Unknown"))
    elif isinstance(reporter, str):
        reporter_text = reporter
    
    # Format labels
    labels = ticket_data.get("labels", [])
    labels_text = ", ".join(labels) if labels else "None"
    
    return f"""Triage this support ticket:

**Ticket:** {ticket_data.get('key', 'N/A')}
**Summary:** {ticket_data.get('summary', 'N/A')}
**Reporter:** {reporter_text}
**Labels:** {labels_text}

**Description:**
{ticket_data.get('description', 'No description provided')}

Analyze and provide:
1. **Category**: bug | feature request | support question | incident | documentation
2. **Priority**: critical | high | medium | low
3. **Suggested Team/Owner**: Which team should handle this
4. **Escalation Needed**: Yes/No and why
5. **Reasoning**: Brief explanation of your categorization
"""


def format_rca_prompt(incident_data: Dict[str, Any]) -> str:
    """
    Format incident data for root cause analysis.
    
    Args:
        incident_data: Dictionary containing incident details.
            May also include:
            - code_changes: Related code changes or merge requests
            - related_incidents: Similar past incidents
    
    Returns:
        Formatted prompt string for the LLM.
    """
    # Handle code changes - could be string or list
    code_changes = incident_data.get("code_changes")
    if code_changes is None:
        code_changes_text = "None provided"
    elif isinstance(code_changes, str):
        code_changes_text = code_changes
    elif isinstance(code_changes, list):
        code_changes_text = "\n".join([
            f"- {c.get('title', 'Untitled')}: {c.get('url', 'No URL')}"
            for c in code_changes
        ])
    else:
        code_changes_text = str(code_changes)
    
    # Handle related incidents
    related = incident_data.get("related_incidents")
    if related is None:
        related_text = "None provided"
    elif isinstance(related, str):
        related_text = related
    elif isinstance(related, list):
        related_text = "\n".join([
            f"- {r.get('key', 'Unknown')}: {r.get('summary', 'No summary')}"
            for r in related
        ])
    else:
        related_text = str(related)
    
    return f"""Perform root cause analysis on this incident:

**Incident:** {incident_data.get('key', 'N/A')}
**Summary:** {incident_data.get('summary', 'N/A')}
**Status:** {incident_data.get('status', 'N/A')}
**Priority:** {incident_data.get('priority', 'N/A')}

**Description:**
{incident_data.get('description', 'No description provided')}

**Recent Code Changes:**
{code_changes_text}

**Related Past Incidents:**
{related_text}

Provide a detailed root cause analysis:
1. **Primary Root Cause**: The main technical cause
2. **Contributing Factors**: Other factors that contributed
3. **Detection Gap**: Why wasn't this caught earlier?
4. **Immediate Fixes**: What was done to resolve it
5. **Long-term Fixes**: Recommended permanent solutions
6. **Process Improvements**: Changes to prevent recurrence
"""
