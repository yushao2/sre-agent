"""Test configuration and fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    response = MagicMock()
    response.content = "This is a mock incident summary."
    return response


@pytest.fixture
def mock_incident_data():
    """Sample incident data for testing."""
    return {
        "key": "INC-123",
        "summary": "Production database connection pool exhausted",
        "description": "Users experiencing timeouts when accessing the dashboard.",
        "status": "Resolved",
        "priority": "Critical",
        "assignee": {"email": "oncall@example.com", "name": "On-Call Engineer"},
        "created": "2024-01-15T10:30:00Z",
        "comments": {
            "comments": [
                {
                    "author": "oncall@example.com",
                    "body": "Starting investigation.",
                    "created": "2024-01-15T10:35:00Z",
                },
            ],
            "total": 1,
        },
        "linked_issues": [],
    }


@pytest.fixture
def mock_jira_client():
    """Mock Jira client."""
    client = AsyncMock()
    client.search_issues = AsyncMock(return_value={"issues": [], "total": 0})
    client.get_issue = AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_confluence_client():
    """Mock Confluence client."""
    client = AsyncMock()
    client.search_pages = AsyncMock(return_value={"results": [], "total": 0})
    client.get_page = AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_gitlab_client():
    """Mock GitLab client."""
    client = AsyncMock()
    client.search_code = AsyncMock(return_value={"results": [], "total": 0})
    client.get_file = AsyncMock(return_value={})
    return client
