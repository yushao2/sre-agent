"""Confluence MCP Server Tool Definitions."""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Tool Input Schemas
# ============================================================================

class SearchPagesInput(BaseModel):
    """Input for searching Confluence pages."""
    query: str = Field(description="Search query (CQL or text)")
    space_key: Optional[str] = Field(default=None, description="Limit search to a specific space")
    max_results: int = Field(default=10, description="Maximum number of results")


class GetPageInput(BaseModel):
    """Input for getting a specific page."""
    page_id: Optional[str] = Field(default=None, description="Page ID")
    title: Optional[str] = Field(default=None, description="Page title (requires space_key)")
    space_key: Optional[str] = Field(default=None, description="Space key")
    include_body: bool = Field(default=True, description="Include page content")


class SearchRunbooksInput(BaseModel):
    """Input for searching runbooks/documentation."""
    service_name: str = Field(description="Service or component name")
    issue_type: Optional[str] = Field(
        default=None, 
        description="Type of issue (e.g., 'database', 'memory', 'network')"
    )


class GetServiceDocsInput(BaseModel):
    """Input for getting service documentation."""
    service_name: str = Field(description="Service name to get docs for")
    doc_types: List[str] = Field(
        default=["runbook", "architecture", "oncall"],
        description="Types of documentation to retrieve"
    )


# ============================================================================
# Tool Definitions (for MCP registration)
# ============================================================================

CONFLUENCE_TOOLS = [
    {
        "name": "confluence_search",
        "description": "Search Confluence for pages, runbooks, and documentation. Use this to find relevant documentation for troubleshooting.",
        "input_schema": SearchPagesInput.model_json_schema(),
    },
    {
        "name": "confluence_get_page",
        "description": "Get the full content of a specific Confluence page by ID or title.",
        "input_schema": GetPageInput.model_json_schema(),
    },
    {
        "name": "confluence_search_runbooks",
        "description": "Search for runbooks and troubleshooting guides for a specific service or issue type.",
        "input_schema": SearchRunbooksInput.model_json_schema(),
    },
    {
        "name": "confluence_get_service_docs",
        "description": "Get all documentation for a service including runbooks, architecture docs, and on-call guides.",
        "input_schema": GetServiceDocsInput.model_json_schema(),
    },
]
