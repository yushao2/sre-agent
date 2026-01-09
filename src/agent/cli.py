"""CLI entry point for the AI SRE Agent."""

import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv


def main():
    """Main CLI entry point."""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="AI SRE Agent - Incident management and support triage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sre-agent summarize INC-123          Summarize an incident
  sre-agent triage SUPPORT-456         Triage a support ticket
  sre-agent rca INC-123                Root cause analysis
  sre-agent chat                       Interactive chat mode
        """,
    )
    
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Model to use (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Summarize command
    summarize_parser = subparsers.add_parser("summarize", help="Summarize an incident")
    summarize_parser.add_argument("incident_key", help="Incident key (e.g., INC-123)")
    summarize_parser.add_argument(
        "--json-file",
        help="Path to JSON file with incident data (optional)",
    )
    
    # Triage command
    triage_parser = subparsers.add_parser("triage", help="Triage a support ticket")
    triage_parser.add_argument("ticket_key", help="Ticket key (e.g., SUPPORT-456)")
    
    # RCA command
    rca_parser = subparsers.add_parser("rca", help="Root cause analysis")
    rca_parser.add_argument("incident_key", help="Incident key")
    
    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Interactive chat mode")
    
    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run with demo data")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY=your-key-here")
        sys.exit(1)
    
    # Run the appropriate command
    if args.command == "summarize":
        asyncio.run(cmd_summarize(args, api_key))
    elif args.command == "triage":
        asyncio.run(cmd_triage(args, api_key))
    elif args.command == "rca":
        asyncio.run(cmd_rca(args, api_key))
    elif args.command == "chat":
        asyncio.run(cmd_chat(args, api_key))
    elif args.command == "demo":
        asyncio.run(cmd_demo(args, api_key))


async def cmd_summarize(args, api_key: str):
    """Run incident summarization."""
    from agent import SREAgentSimple
    
    agent = SREAgentSimple(anthropic_api_key=api_key, model_name=args.model)
    
    # Load incident data if provided
    if args.json_file:
        with open(args.json_file) as f:
            incident_data = json.load(f)
    else:
        # Would fetch from Jira in real implementation
        incident_data = {
            "key": args.incident_key,
            "summary": f"Incident {args.incident_key}",
            "description": "No data provided. Use --json-file to provide incident data.",
            "comments": {"comments": [], "total": 0},
        }
    
    print(f"Analyzing incident: {args.incident_key}")
    print("-" * 60)
    
    summary = await agent.summarize_incident_simple(incident_data)
    print(summary)


async def cmd_triage(args, api_key: str):
    """Run ticket triage."""
    from agent import SREAgentSimple
    
    print(f"Triaging ticket: {args.ticket_key}")
    print("(Full triage requires MCP connections - showing demo output)")
    print("-" * 60)
    print("Category: Support Request")
    print("Priority: Medium")
    print("Team: Platform")
    print("Needs Escalation: No")


async def cmd_rca(args, api_key: str):
    """Run root cause analysis."""
    from agent import SREAgentSimple
    
    print(f"Running RCA for: {args.incident_key}")
    print("(Full RCA requires MCP connections - use 'demo' command for example)")


async def cmd_chat(args, api_key: str):
    """Run interactive chat mode."""
    from agent import SREAgentSimple
    
    agent = SREAgentSimple(anthropic_api_key=api_key, model_name=args.model)
    
    print("AI SRE Agent - Interactive Mode")
    print("Type 'quit' or 'exit' to stop")
    print("-" * 60)
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Simple chat without full agent
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage, SystemMessage
            from agent.prompts import SRE_AGENT_SYSTEM_PROMPT
            
            llm = ChatAnthropic(
                model=args.model,
                anthropic_api_key=api_key,
            )
            
            response = await llm.ainvoke([
                SystemMessage(content=SRE_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=user_input),
            ])
            
            print(f"\nAgent: {response.content}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


async def cmd_demo(args, api_key: str):
    """Run demo with sample data."""
    from agent import SREAgentSimple
    
    # Sample incident data
    demo_incident = {
        "key": "INC-123",
        "summary": "Production database connection pool exhausted",
        "description": """
## Impact
Users experiencing timeouts when accessing the dashboard.

## Timeline
- 10:30 UTC - First alerts fired
- 10:35 UTC - Oncall paged
- 10:40 UTC - Investigation started
        """,
        "status": "Resolved",
        "priority": "Critical",
        "comments": {
            "comments": [
                {
                    "author": "oncall@example.com",
                    "body": "Found the issue - a long-running query from the reporting service is holding connections.",
                    "created": "2024-01-15T10:50:00Z",
                },
                {
                    "author": "dba@example.com",
                    "body": "Query killed. Connection pool recovering.",
                    "created": "2024-01-15T11:05:00Z",
                },
            ],
            "total": 2,
        },
        "linked_issues": [
            {"key": "DB-789", "type": "follow-up", "summary": "Add index on orders.created_at"},
        ],
    }
    
    print("=" * 60)
    print("AI SRE Agent - Demo")
    print("=" * 60)
    print(f"\nAnalyzing demo incident: {demo_incident['key']}")
    print(f"Summary: {demo_incident['summary']}")
    print("\nGenerating analysis...\n")
    print("-" * 60)
    
    agent = SREAgentSimple(anthropic_api_key=api_key, model_name=args.model)
    summary = await agent.summarize_incident_simple(demo_incident)
    
    print(summary)
    print("-" * 60)


if __name__ == "__main__":
    main()
