"""
Simple local runner for development - no Celery required.

Usage:
    # As module
    python -m agent.local summarize --key INC-123 --summary "DB down" --description "..."
    python -m agent.local triage --key TICKET-456 --summary "Login broken"
    python -m agent.local chat "What causes connection pool exhaustion?"
    python -m agent.local demo

    # Or import directly
    from agent.local import run_summarize, run_triage, run_chat
    result = run_summarize({"key": "INC-123", "summary": "...", ...})
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

from dotenv import load_dotenv


def get_agent():
    """Get agent instance."""
    from .agent import SREAgentSimple
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        print("Run: export ANTHROPIC_API_KEY=your-key")
        sys.exit(1)
    
    model = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
    return SREAgentSimple(anthropic_api_key=api_key, model_name=model)


# =============================================================================
# Synchronous wrapper functions - use these for simple scripting
# =============================================================================

def run_summarize(incident_data: Dict[str, Any]) -> str:
    """
    Summarize an incident synchronously.
    
    Args:
        incident_data: Dict with keys: key, summary, description, status, priority, comments
    
    Returns:
        Summary text
    
    Example:
        result = run_summarize({
            "key": "INC-123",
            "summary": "Database connection pool exhausted",
            "description": "Users seeing timeouts...",
            "status": "Resolved",
            "priority": "Critical",
        })
        print(result)
    """
    agent = get_agent()
    return asyncio.run(agent.summarize_incident_simple(incident_data))


def run_triage(ticket_data: Dict[str, Any]) -> str:
    """
    Triage a ticket synchronously.
    
    Args:
        ticket_data: Dict with keys: key, summary, description
    
    Returns:
        Triage analysis text
    """
    agent = get_agent()
    return asyncio.run(agent.triage_ticket_simple(ticket_data))


def run_rca(incident_data: Dict[str, Any]) -> str:
    """
    Run root cause analysis synchronously.
    
    Args:
        incident_data: Dict with incident details
    
    Returns:
        RCA text
    """
    agent = get_agent()
    return asyncio.run(agent.analyze_root_cause(incident_data))


def run_chat(message: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Chat with the SRE agent synchronously.
    
    Args:
        message: Your question or message
        context: Optional context dict
    
    Returns:
        Agent response
    
    Example:
        response = run_chat("What are common causes of memory leaks in Python?")
        print(response)
    """
    agent = get_agent()
    return asyncio.run(agent.chat(message, context))


# =============================================================================
# Interactive mode
# =============================================================================

def interactive_mode():
    """Run an interactive chat session."""
    print("=" * 60)
    print("AI SRE Agent - Interactive Mode")
    print("=" * 60)
    print("Type your questions. Type 'quit' or 'exit' to stop.")
    print("Type 'help' for example questions.")
    print("-" * 60)
    
    agent = get_agent()
    
    while True:
        try:
            user_input = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        
        if user_input.lower() == "help":
            print("""
Example questions:
  - What causes database connection pool exhaustion?
  - How do I debug a memory leak in Python?
  - What should I check when API latency spikes?
  - Explain the difference between P1 and P2 incidents
  - What are best practices for incident postmortems?
            """)
            continue
        
        print("\nThinking...\n")
        try:
            response = asyncio.run(agent.chat(user_input))
            print(response)
        except Exception as e:
            print(f"Error: {e}")


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point."""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="AI SRE Agent - Local Development Runner (no Celery required)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive chat
  python -m agent.local interactive
  
  # Summarize an incident
  python -m agent.local summarize --key INC-123 --summary "DB connection pool exhausted"
  
  # Triage a ticket  
  python -m agent.local triage --key TICKET-456 --summary "Can't login" --description "Getting 500 error"
  
  # Quick chat
  python -m agent.local chat "What causes high CPU usage?"
  
  # Run demo
  python -m agent.local demo
  
  # Load from JSON file
  python -m agent.local summarize --file incident.json
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Interactive
    subparsers.add_parser("interactive", aliases=["i", "repl"], help="Interactive chat mode")
    
    # Chat
    chat_parser = subparsers.add_parser("chat", aliases=["c"], help="Quick chat")
    chat_parser.add_argument("message", nargs="+", help="Message to send")
    
    # Summarize
    sum_parser = subparsers.add_parser("summarize", aliases=["sum", "s"], help="Summarize incident")
    sum_parser.add_argument("--key", "-k", required=False, help="Incident key (e.g., INC-123)")
    sum_parser.add_argument("--summary", "-s", required=False, help="Incident summary/title")
    sum_parser.add_argument("--description", "-d", default="", help="Full description")
    sum_parser.add_argument("--status", default="Open", help="Status")
    sum_parser.add_argument("--priority", "-p", default="High", help="Priority")
    sum_parser.add_argument("--file", "-f", help="Load incident from JSON file")
    
    # Triage
    tri_parser = subparsers.add_parser("triage", aliases=["tri", "t"], help="Triage ticket")
    tri_parser.add_argument("--key", "-k", required=False, help="Ticket key")
    tri_parser.add_argument("--summary", "-s", required=False, help="Ticket summary")
    tri_parser.add_argument("--description", "-d", default="", help="Description")
    tri_parser.add_argument("--file", "-f", help="Load ticket from JSON file")
    
    # RCA
    rca_parser = subparsers.add_parser("rca", help="Root cause analysis")
    rca_parser.add_argument("--key", "-k", required=False, help="Incident key")
    rca_parser.add_argument("--summary", "-s", required=False, help="Incident summary")
    rca_parser.add_argument("--description", "-d", default="", help="Description")
    rca_parser.add_argument("--file", "-f", help="Load from JSON file")
    
    # Demo
    subparsers.add_parser("demo", help="Run with sample incident data")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Interactive mode
    if args.command in ("interactive", "i", "repl"):
        interactive_mode()
        return
    
    # Chat
    if args.command in ("chat", "c"):
        message = " ".join(args.message)
        print(f"You: {message}\n")
        result = run_chat(message)
        print(f"Agent:\n{result}")
        return
    
    # Summarize
    if args.command in ("summarize", "sum", "s"):
        if args.file:
            with open(args.file) as f:
                data = json.load(f)
        else:
            if not args.key or not args.summary:
                print("Error: --key and --summary required (or use --file)")
                sys.exit(1)
            data = {
                "key": args.key,
                "summary": args.summary,
                "description": args.description,
                "status": args.status,
                "priority": args.priority,
                "comments": {"comments": [], "total": 0},
            }
        
        print(f"Summarizing incident: {data.get('key')}\n")
        result = run_summarize(data)
        print(result)
        return
    
    # Triage
    if args.command in ("triage", "tri", "t"):
        if args.file:
            with open(args.file) as f:
                data = json.load(f)
        else:
            if not args.key or not args.summary:
                print("Error: --key and --summary required (or use --file)")
                sys.exit(1)
            data = {
                "key": args.key,
                "summary": args.summary,
                "description": args.description,
            }
        
        print(f"Triaging ticket: {data.get('key')}\n")
        result = run_triage(data)
        print(result)
        return
    
    # RCA
    if args.command == "rca":
        if args.file:
            with open(args.file) as f:
                data = json.load(f)
        else:
            if not args.key or not args.summary:
                print("Error: --key and --summary required (or use --file)")
                sys.exit(1)
            data = {
                "key": args.key,
                "summary": args.summary,
                "description": args.description,
            }
        
        print(f"Running RCA for: {data.get('key')}\n")
        result = run_rca(data)
        print(result)
        return
    
    # Demo
    if args.command == "demo":
        run_demo()
        return


def run_demo():
    """Run demo with sample data."""
    demo_incident = {
        "key": "INC-123",
        "summary": "Production database connection pool exhausted",
        "description": """
## Impact
Users experiencing timeouts accessing the dashboard. Approximately 30% of requests failing.

## Timeline
- 10:30 UTC - Monitoring alerts fired for increased 5xx errors
- 10:35 UTC - On-call engineer paged
- 10:40 UTC - Initial investigation started
- 10:45 UTC - Root cause identified: connection leak in reporting service
- 10:50 UTC - Reporting service restarted
- 11:00 UTC - Connection pool recovered, errors cleared

## Technical Details
The reporting service was not properly closing database connections after generating 
large reports. This caused connections to accumulate until the pool was exhausted.
        """,
        "status": "Resolved",
        "priority": "Critical",
        "comments": {
            "comments": [
                {
                    "author": "oncall@example.com",
                    "body": "Seeing connection pool at 100% capacity. Investigating source of leak.",
                    "created": "2024-01-15T10:42:00Z",
                },
                {
                    "author": "oncall@example.com",
                    "body": "Found it - reporting service not closing connections. Restarting service.",
                    "created": "2024-01-15T10:48:00Z",
                },
                {
                    "author": "dba@example.com",
                    "body": "Pool recovering. Down to 45% utilization.",
                    "created": "2024-01-15T10:55:00Z",
                },
            ],
            "total": 3,
        },
    }
    
    print("=" * 60)
    print("AI SRE Agent - Demo")
    print("=" * 60)
    print(f"\nIncident: {demo_incident['key']}")
    print(f"Summary: {demo_incident['summary']}")
    print(f"Priority: {demo_incident['priority']}")
    print("\n" + "-" * 60)
    print("Generating analysis...")
    print("-" * 60 + "\n")
    
    result = run_summarize(demo_incident)
    print(result)
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
