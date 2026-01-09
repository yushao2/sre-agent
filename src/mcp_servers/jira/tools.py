"""Jira MCP Server Tool Definitions."""

from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# Tool Input Schemas
# ============================================================================

class SearchIssuesInput(BaseModel):
    """Input for searching Jira issues."""
    jql: str = Field(description="JQL query to search issues")
    max_results: int = Field(default=10, description="Maximum number of results")
    fields: List[str] = Field(
        default=["summary", "status", "assignee", "created", "updated", "description"],
        description="Fields to return"
    )


class GetIssueInput(BaseModel):
    """Input for getting a specific issue."""
    issue_key: str = Field(description="Jira issue key (e.g., PROJ-123)")
    include_comments: bool = Field(default=True, description="Include issue comments")
    include_changelog: bool = Field(default=False, description="Include change history")


class GetIssueCommentsInput(BaseModel):
    """Input for getting issue comments."""
    issue_key: str = Field(description="Jira issue key")
    max_results: int = Field(default=50, description="Maximum comments to return")


class AddCommentInput(BaseModel):
    """Input for adding a comment to an issue."""
    issue_key: str = Field(description="Jira issue key")
    body: str = Field(description="Comment body (supports Jira markup)")


class TransitionIssueInput(BaseModel):
    """Input for transitioning an issue."""
    issue_key: str = Field(description="Jira issue key")
    transition_name: str = Field(description="Name of the transition (e.g., 'In Progress', 'Done')")
    comment: Optional[str] = Field(default=None, description="Optional comment to add")


class GetIncidentThreadInput(BaseModel):
    """Input for getting a full incident thread."""
    issue_key: str = Field(description="Incident issue key")
    include_linked_issues: bool = Field(default=True, description="Include linked issues")


# ============================================================================
# Tool Definitions (for MCP registration)
# ============================================================================

JIRA_TOOLS = [
    {
        "name": "jira_search_issues",
        "description": "Search for Jira issues using JQL. Use this to find incidents, bugs, or support tickets.",
        "input_schema": SearchIssuesInput.model_json_schema(),
    },
    {
        "name": "jira_get_issue",
        "description": "Get detailed information about a specific Jira issue including description, status, and optionally comments.",
        "input_schema": GetIssueInput.model_json_schema(),
    },
    {
        "name": "jira_get_comments",
        "description": "Get all comments on a Jira issue. Useful for understanding the discussion and troubleshooting steps.",
        "input_schema": GetIssueCommentsInput.model_json_schema(),
    },
    {
        "name": "jira_add_comment",
        "description": "Add a comment to a Jira issue. Use this to document findings or suggestions.",
        "input_schema": AddCommentInput.model_json_schema(),
    },
    {
        "name": "jira_transition_issue",
        "description": "Change the status of a Jira issue (e.g., move to 'In Progress' or 'Resolved').",
        "input_schema": TransitionIssueInput.model_json_schema(),
    },
    {
        "name": "jira_get_incident_thread",
        "description": "Get a complete incident thread including the main issue, all comments, and linked issues. Best for incident summarization.",
        "input_schema": GetIncidentThreadInput.model_json_schema(),
    },
]
