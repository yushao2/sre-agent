"""CLI entry point for the AI SRE Agent."""

import argparse
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
Commands:
  serve                Start the HTTP API server
  worker               Start a Celery worker
  beat                 Start the Celery beat scheduler
  demo                 Run demo with sample data

Examples:
  sre-agent serve --port 8000
  sre-agent worker --concurrency 4
  sre-agent demo
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start HTTP API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve_parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    
    # Worker command
    worker_parser = subparsers.add_parser("worker", help="Start Celery worker")
    worker_parser.add_argument("--concurrency", type=int, default=4, help="Worker concurrency")
    worker_parser.add_argument("--queues", default="llm", help="Queues to consume")
    worker_parser.add_argument("--loglevel", default="info", help="Log level")
    
    # Beat command
    beat_parser = subparsers.add_parser("beat", help="Start Celery beat scheduler")
    beat_parser.add_argument("--loglevel", default="info", help="Log level")
    
    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run with demo data")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "serve":
        run_server(args)
    elif args.command == "worker":
        run_worker(args)
    elif args.command == "beat":
        run_beat(args)
    elif args.command == "demo":
        run_demo()


def run_server(args):
    """Start the FastAPI server."""
    import uvicorn
    
    print(f"Starting server on {args.host}:{args.port}")
    print(f"API docs: http://{args.host}:{args.port}/docs")
    
    uvicorn.run(
        "agent.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=1 if args.reload else args.workers,
    )


def run_worker(args):
    """Start a Celery worker."""
    from .tasks import celery
    
    print(f"Starting Celery worker (concurrency={args.concurrency})")
    
    celery.worker_main([
        "worker",
        f"--concurrency={args.concurrency}",
        f"--queues={args.queues}",
        f"--loglevel={args.loglevel}",
    ])


def run_beat(args):
    """Start Celery beat scheduler."""
    from .tasks import celery
    
    print("Starting Celery beat scheduler")
    
    celery.start([
        "beat",
        f"--loglevel={args.loglevel}",
    ])


def run_demo():
    """Run demo with sample data."""
    import asyncio
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    
    from .agent import SREAgentSimple
    
    demo_incident = {
        "key": "INC-123",
        "summary": "Production database connection pool exhausted",
        "description": """
## Impact
Users experiencing timeouts accessing the dashboard.

## Timeline
- 10:30 UTC - Alerts fired
- 10:35 UTC - Oncall paged
- 10:45 UTC - Root cause identified
- 11:00 UTC - Resolved
        """,
        "status": "Resolved",
        "priority": "Critical",
        "comments": {
            "comments": [
                {
                    "author": "oncall@example.com",
                    "body": "Long-running query from reporting service holding connections.",
                    "created": "2024-01-15T10:50:00Z",
                },
                {
                    "author": "dba@example.com",
                    "body": "Query killed. Pool recovering.",
                    "created": "2024-01-15T11:00:00Z",
                },
            ],
            "total": 2,
        },
    }
    
    async def _run():
        print("=" * 60)
        print("AI SRE Agent Demo")
        print("=" * 60)
        print(f"\nIncident: {demo_incident['key']}")
        print(f"Summary: {demo_incident['summary']}")
        print("\nGenerating analysis...\n")
        
        agent = SREAgentSimple(anthropic_api_key=api_key)
        result = await agent.summarize_incident_simple(demo_incident)
        
        print("-" * 60)
        print(result)
        print("-" * 60)
    
    asyncio.run(_run())


if __name__ == "__main__":
    main()
