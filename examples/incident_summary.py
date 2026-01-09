"""
Example: Incident Summarization

This example demonstrates how to use the AI SRE Agent to summarize
an incident thread. It uses mock data to show the flow without
requiring actual API connections.
"""

import asyncio
import json
import os
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Mock incident data (simulates what you'd get from Jira)
MOCK_INCIDENT = {
    "key": "INC-123",
    "summary": "Production database connection pool exhausted",
    "description": """
## Impact
Users experiencing timeouts when accessing the dashboard.

## Timeline
- 10:30 UTC - First alerts fired
- 10:35 UTC - Oncall paged
- 10:40 UTC - Investigation started

## Initial Observations
- Connection pool at 100% utilization
- No recent deployments
- Traffic levels normal
    """,
    "status": "Resolved",
    "priority": "Critical",
    "assignee": {"email": "oncall@example.com", "name": "On-Call Engineer"},
    "reporter": {"email": "monitoring@example.com", "name": "Monitoring System"},
    "created": "2024-01-15T10:30:00Z",
    "updated": "2024-01-15T12:00:00Z",
    "labels": ["incident", "database", "production"],
    "components": ["backend", "database"],
    "comments": {
        "comments": [
            {
                "author": "oncall@example.com",
                "body": "Starting investigation. Checking connection pool metrics.",
                "created": "2024-01-15T10:35:00Z",
            },
            {
                "author": "oncall@example.com",
                "body": "Found the issue - a long-running query from the reporting service is holding connections. Query: SELECT * FROM orders WHERE created_at > '2020-01-01' (no index on created_at)",
                "created": "2024-01-15T10:50:00Z",
            },
            {
                "author": "dba@example.com",
                "body": "Confirmed. The reporting job started at 10:25 UTC. I'm going to kill the query and we should add an index.",
                "created": "2024-01-15T11:00:00Z",
            },
            {
                "author": "dba@example.com",
                "body": "Query killed. Created ticket DB-789 for adding the index.",
                "created": "2024-01-15T11:05:00Z",
            },
            {
                "author": "oncall@example.com",
                "body": "Connection pool recovering. Dashboard access restored. Monitoring for 30 minutes before closing.",
                "created": "2024-01-15T11:10:00Z",
            },
            {
                "author": "oncall@example.com",
                "body": "All systems stable. Closing incident. Follow-ups: 1) Add index (DB-789), 2) Review reporting job schedule (TASK-456)",
                "created": "2024-01-15T12:00:00Z",
            },
        ],
        "total": 6,
    },
    "linked_issues": [
        {
            "key": "DEPLOY-456",
            "type": "is caused by",
            "summary": "Reporting job schedule change",
            "status": "Done",
        },
        {
            "key": "DB-789",
            "type": "follow-up",
            "summary": "Add index on orders.created_at",
            "status": "Open",
        },
    ],
}


async def run_simple_example():
    """
    Run incident summarization without MCP connections.
    Uses direct LLM calls with the mock data.
    """
    from agent import SREAgentSimple
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY=your-key-here")
        return
    
    print("=" * 60)
    print("AI SRE Agent - Incident Summarization Example")
    print("=" * 60)
    print(f"\nAnalyzing incident: {MOCK_INCIDENT['key']}")
    print(f"Summary: {MOCK_INCIDENT['summary']}")
    print("\nGenerating incident summary...\n")
    
    agent = SREAgentSimple(
        anthropic_api_key=api_key,
        model_name="claude-sonnet-4-20250514",
    )
    
    summary = await agent.summarize_incident_simple(MOCK_INCIDENT)
    
    print("-" * 60)
    print("INCIDENT SUMMARY")
    print("-" * 60)
    print(summary)
    print("-" * 60)


async def run_full_example():
    """
    Run incident summarization with MCP connections.
    Requires running MCP servers.
    """
    from agent import SREAgent
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        return
    
    print("=" * 60)
    print("AI SRE Agent - Full MCP Example")
    print("=" * 60)
    
    agent = SREAgent(
        anthropic_api_key=api_key,
        model_name="claude-sonnet-4-20250514",
    )
    
    # Build agent with RAG tools only (no MCP for this example)
    agent._agent_executor = await agent._build_agent(mcp_tools=[])
    
    # Run analysis
    result = await agent.run(
        f"Summarize this incident data and identify the root cause:\n\n{json.dumps(MOCK_INCIDENT, indent=2)}"
    )
    
    print(result)


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        asyncio.run(run_full_example())
    else:
        asyncio.run(run_simple_example())


if __name__ == "__main__":
    main()
