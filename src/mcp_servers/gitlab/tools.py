"""GitLab MCP Server Tool Definitions."""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Tool Input Schemas
# ============================================================================

class SearchCodeInput(BaseModel):
    """Input for searching code across repositories."""
    query: str = Field(description="Code search query")
    project_id: Optional[str] = Field(default=None, description="Limit to specific project")
    file_extension: Optional[str] = Field(default=None, description="Filter by file extension (e.g., 'py', 'js')")
    max_results: int = Field(default=10, description="Maximum number of results")


class GetFileInput(BaseModel):
    """Input for getting a file from a repository."""
    project_id: str = Field(description="GitLab project ID or path")
    file_path: str = Field(description="Path to file in repository")
    ref: str = Field(default="main", description="Branch, tag, or commit SHA")


class SearchMergeRequestsInput(BaseModel):
    """Input for searching merge requests."""
    project_id: Optional[str] = Field(default=None, description="Project ID or path")
    state: str = Field(default="merged", description="MR state: opened, closed, merged, all")
    search: Optional[str] = Field(default=None, description="Search in title and description")
    max_results: int = Field(default=10, description="Maximum number of results")


class GetMergeRequestInput(BaseModel):
    """Input for getting a specific merge request."""
    project_id: str = Field(description="Project ID or path")
    mr_iid: int = Field(description="Merge request IID (internal ID)")
    include_changes: bool = Field(default=False, description="Include file changes")


class GetCommitsInput(BaseModel):
    """Input for getting recent commits."""
    project_id: str = Field(description="Project ID or path")
    ref: str = Field(default="main", description="Branch or tag")
    since: Optional[str] = Field(default=None, description="ISO datetime to filter from")
    path: Optional[str] = Field(default=None, description="Filter to specific file path")
    max_results: int = Field(default=20, description="Maximum number of commits")


class GetPipelineStatusInput(BaseModel):
    """Input for getting pipeline status."""
    project_id: str = Field(description="Project ID or path")
    ref: Optional[str] = Field(default=None, description="Branch or tag")
    pipeline_id: Optional[int] = Field(default=None, description="Specific pipeline ID")


# ============================================================================
# Tool Definitions (for MCP registration)
# ============================================================================

GITLAB_TOOLS = [
    {
        "name": "gitlab_search_code",
        "description": "Search for code across GitLab repositories. Use this to find implementations, configurations, or error sources.",
        "input_schema": SearchCodeInput.model_json_schema(),
    },
    {
        "name": "gitlab_get_file",
        "description": "Get the contents of a specific file from a GitLab repository.",
        "input_schema": GetFileInput.model_json_schema(),
    },
    {
        "name": "gitlab_search_merge_requests",
        "description": "Search for merge requests. Useful for finding recent changes that might have caused issues.",
        "input_schema": SearchMergeRequestsInput.model_json_schema(),
    },
    {
        "name": "gitlab_get_merge_request",
        "description": "Get details of a specific merge request including description and optionally file changes.",
        "input_schema": GetMergeRequestInput.model_json_schema(),
    },
    {
        "name": "gitlab_get_commits",
        "description": "Get recent commits for a project. Use to identify recent changes that might relate to an incident.",
        "input_schema": GetCommitsInput.model_json_schema(),
    },
    {
        "name": "gitlab_get_pipeline",
        "description": "Get pipeline/CI status for a project. Check if recent deployments succeeded or failed.",
        "input_schema": GetPipelineStatusInput.model_json_schema(),
    },
]
