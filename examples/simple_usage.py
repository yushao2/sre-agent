#!/usr/bin/env python3
"""
Example: Using the AI SRE Agent locally.

No Celery, Redis, or PostgreSQL required - just your API key!

Usage:
    export ANTHROPIC_API_KEY=your-key
    python examples/simple_usage.py
"""

import os
import sys

# Add src to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent import run_summarize, run_triage, run_chat


def main():
    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Please set ANTHROPIC_API_KEY environment variable")
        print("  export ANTHROPIC_API_KEY=your-key")
        sys.exit(1)
    
    print("=" * 60)
    print("AI SRE Agent - Simple Usage Example")
    print("=" * 60)
    
    # Example 1: Quick chat
    print("\n### Example 1: Quick Chat ###\n")
    response = run_chat("What are the top 3 things to check during a database outage?")
    print(response)
    
    # Example 2: Summarize an incident
    print("\n\n### Example 2: Incident Summary ###\n")
    incident = {
        "key": "INC-456",
        "summary": "API latency spike affecting checkout",
        "description": """
Customers reporting slow checkout. p99 latency jumped from 200ms to 5s.
Traced to a slow database query in the inventory service.
Query was missing an index on the product_sku column.
Added index and latency returned to normal.
        """,
        "status": "Resolved",
        "priority": "High",
        "comments": {"comments": [], "total": 0},
    }
    summary = run_summarize(incident)
    print(summary)
    
    # Example 3: Triage a ticket
    print("\n\n### Example 3: Ticket Triage ###\n")
    ticket = {
        "key": "SUPPORT-789",
        "summary": "Cannot export reports to PDF",
        "description": """
User reports: When I click 'Export to PDF' on the dashboard, 
nothing happens. Tried Chrome and Firefox. Started happening 
after the update last week. Other users in my team have the 
same issue.
        """,
    }
    triage = run_triage(ticket)
    print(triage)
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
