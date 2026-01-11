#!/usr/bin/env python3
"""
Local testing utilities for MCP servers.

This module provides helpers to test MCP servers locally without
deploying to Kubernetes or running Docker.

Usage:
    # Test Jira MCP server
    python -m agent.mcp_test jira
    
    # Test with custom env file
    python -m agent.mcp_test jira --env-file .env.jira
    
    # Run interactive MCP client
    python -m agent.mcp_test jira --interactive

Requirements:
    - Set environment variables for the MCP server you want to test
    - Install mcp extras: pip install -e ".[mcp]"
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

from dotenv import load_dotenv


def check_env_vars(server: str) -> Dict[str, str]:
    """Check required environment variables for a server."""
    required = {
        "jira": ["JIRA_URL", "JIRA_USERNAME", ("JIRA_TOKEN", "JIRA_API_TOKEN", "JIRA_PASSWORD")],
        "confluence": ["CONFLUENCE_URL", "CONFLUENCE_USERNAME", ("CONFLUENCE_TOKEN", "CONFLUENCE_API_TOKEN", "CONFLUENCE_PASSWORD")],
        "gitlab": ["GITLAB_URL", "GITLAB_TOKEN"],
    }
    
    if server not in required:
        print(f"Unknown server: {server}")
        print(f"Available: {', '.join(required.keys())}")
        sys.exit(1)
    
    missing = []
    found = {}
    
    for var in required[server]:
        if isinstance(var, tuple):
            # Any of these will work
            value = None
            for v in var:
                if os.getenv(v):
                    value = os.getenv(v)
                    found[var[0]] = f"(from {v})"
                    break
            if not value:
                missing.append(f"One of: {', '.join(var)}")
        else:
            if not os.getenv(var):
                missing.append(var)
            else:
                found[var] = "✓"
    
    return {"missing": missing, "found": found}


def test_jira_server():
    """Test Jira MCP server functions."""
    print("\n=== Testing Jira MCP Server ===\n")
    
    from mcp_servers.jira.server import (
        jira_search_issues,
        jira_get_issue,
        _jira,
    )
    
    # Test connection
    print("1. Testing connection...")
    try:
        jira = _jira()
        print(f"   ✓ Connected to: {os.getenv('JIRA_URL')}")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return False
    
    # Test search
    print("\n2. Testing search (recent issues)...")
    try:
        result = jira_search_issues(
            jql="created >= -7d ORDER BY created DESC",
            limit=5,
        )
        print(f"   ✓ Found {result['total']} issues (showing {len(result['issues'])})")
        for issue in result["issues"][:3]:
            print(f"      - {issue['key']}: {issue['summary'][:50]}...")
    except Exception as e:
        print(f"   ✗ Search failed: {e}")
        return False
    
    # Test get issue (if we found any)
    if result["issues"]:
        print(f"\n3. Testing get issue ({result['issues'][0]['key']})...")
        try:
            issue = jira_get_issue(result["issues"][0]["key"])
            print(f"   ✓ Got issue: {issue['key']}")
            print(f"      Status: {issue['fields'].get('status', {}).get('name')}")
        except Exception as e:
            print(f"   ✗ Get issue failed: {e}")
    
    print("\n✓ Jira MCP server tests passed!")
    return True


def test_confluence_server():
    """Test Confluence MCP server functions."""
    print("\n=== Testing Confluence MCP Server ===\n")
    
    from mcp_servers.confluence.server import (
        confluence_cql_search,
        confluence_get_page_by_id,
        _confluence,
    )
    
    # Test connection
    print("1. Testing connection...")
    try:
        confluence = _confluence()
        print(f"   ✓ Connected to: {os.getenv('CONFLUENCE_URL')}")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return False
    
    # Test search
    print("\n2. Testing search (recent pages)...")
    try:
        result = confluence_cql_search(
            cql='type = "page" ORDER BY lastmodified DESC',
            limit=5,
        )
        pages = result.get("results", [])
        print(f"   ✓ Found {len(pages)} pages")
        for page in pages[:3]:
            title = page.get("content", {}).get("title", page.get("title", "Unknown"))
            print(f"      - {title[:50]}...")
    except Exception as e:
        print(f"   ✗ Search failed: {e}")
        return False
    
    print("\n✓ Confluence MCP server tests passed!")
    return True


def test_gitlab_server():
    """Test GitLab MCP server functions."""
    print("\n=== Testing GitLab MCP Server ===\n")
    
    from mcp_servers.gitlab.server import (
        gitlab_get_project,
        gitlab_list_merge_requests,
        gitlab_list_pipelines,
        _gl,
    )
    
    # Test connection
    print("1. Testing connection...")
    try:
        gl = _gl()
        print(f"   ✓ Connected to: {os.getenv('GITLAB_URL')}")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return False
    
    # List accessible projects
    print("\n2. Listing accessible projects...")
    try:
        projects = gl.projects.list(per_page=5, membership=True)
        print(f"   ✓ Found {len(projects)} projects")
        for p in projects[:3]:
            print(f"      - {p.path_with_namespace}")
        
        if projects:
            test_project = projects[0].path_with_namespace
        else:
            print("   ⚠ No accessible projects found")
            return True
    except Exception as e:
        print(f"   ✗ List projects failed: {e}")
        return False
    
    # Test get project
    print(f"\n3. Testing get project ({test_project})...")
    try:
        project = gitlab_get_project(test_project)
        print(f"   ✓ Got project: {project['path_with_namespace']}")
        print(f"      Default branch: {project.get('default_branch')}")
    except Exception as e:
        print(f"   ✗ Get project failed: {e}")
    
    # Test list MRs
    print(f"\n4. Testing list merge requests...")
    try:
        mrs = gitlab_list_merge_requests(test_project, state="all", per_page=5)
        print(f"   ✓ Found {len(mrs)} merge requests")
        for mr in mrs[:3]:
            print(f"      - !{mr['iid']}: {mr['title'][:40]}... ({mr['state']})")
    except Exception as e:
        print(f"   ✗ List MRs failed: {e}")
    
    # Test list pipelines
    print(f"\n5. Testing list pipelines...")
    try:
        pipes = gitlab_list_pipelines(test_project, per_page=5)
        print(f"   ✓ Found {len(pipes)} pipelines")
        for p in pipes[:3]:
            print(f"      - #{p['id']}: {p['status']} ({p['ref']})")
    except Exception as e:
        print(f"   ✗ List pipelines failed: {e}")
    
    print("\n✓ GitLab MCP server tests passed!")
    return True


def run_interactive(server: str):
    """Run an interactive session with an MCP server."""
    print(f"\n=== Interactive {server.title()} MCP Session ===")
    print("Type 'help' for available commands, 'quit' to exit\n")
    
    if server == "jira":
        from mcp_servers.jira.server import jira_search_issues, jira_get_issue
        
        commands = {
            "search": ("Search issues (JQL)", lambda q: jira_search_issues(q)),
            "get": ("Get issue by key", lambda k: jira_get_issue(k)),
        }
    elif server == "confluence":
        from mcp_servers.confluence.server import confluence_cql_search, confluence_get_page_by_id
        
        commands = {
            "search": ("Search pages (CQL)", lambda q: confluence_cql_search(q)),
            "get": ("Get page by ID", lambda i: confluence_get_page_by_id(i)),
        }
    elif server == "gitlab":
        from mcp_servers.gitlab.server import (
            gitlab_get_project,
            gitlab_list_merge_requests,
            gitlab_list_pipelines,
        )
        
        commands = {
            "project": ("Get project info", lambda p: gitlab_get_project(p)),
            "mrs": ("List merge requests", lambda p: gitlab_list_merge_requests(p)),
            "pipelines": ("List pipelines", lambda p: gitlab_list_pipelines(p)),
        }
    else:
        print(f"Unknown server: {server}")
        return
    
    while True:
        try:
            user_input = input(f"{server}> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        
        if user_input.lower() == "help":
            print("\nAvailable commands:")
            for cmd, (desc, _) in commands.items():
                print(f"  {cmd} <arg>  - {desc}")
            print("  help        - Show this help")
            print("  quit        - Exit")
            print()
            continue
        
        parts = user_input.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        if cmd not in commands:
            print(f"Unknown command: {cmd}. Type 'help' for available commands.")
            continue
        
        if not arg:
            print(f"Usage: {cmd} <argument>")
            continue
        
        try:
            result = commands[cmd][1](arg)
            print(json.dumps(result, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test MCP servers locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test Jira server
  python -m agent.mcp_test jira
  
  # Load env from file first
  python -m agent.mcp_test jira --env-file .env.jira
  
  # Interactive mode
  python -m agent.mcp_test gitlab --interactive
  
Environment Variables:
  Jira:       JIRA_URL, JIRA_USERNAME, JIRA_TOKEN
  Confluence: CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_TOKEN
  GitLab:     GITLAB_URL, GITLAB_TOKEN
        """,
    )
    
    parser.add_argument(
        "server",
        choices=["jira", "confluence", "gitlab"],
        help="MCP server to test",
    )
    parser.add_argument(
        "--env-file", "-e",
        help="Load environment from file (e.g., .env.jira)",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run interactive session",
    )
    parser.add_argument(
        "--check-only", "-c",
        action="store_true",
        help="Only check environment variables",
    )
    
    args = parser.parse_args()
    
    # Load environment
    load_dotenv()  # Load default .env
    if args.env_file:
        load_dotenv(args.env_file, override=True)
    
    # Check env vars
    print(f"Checking environment for {args.server}...")
    check = check_env_vars(args.server)
    
    if check["found"]:
        print("Found:")
        for var, status in check["found"].items():
            print(f"  {var}: {status}")
    
    if check["missing"]:
        print("\nMissing:")
        for var in check["missing"]:
            print(f"  ✗ {var}")
        print("\nSet the missing environment variables and try again.")
        sys.exit(1)
    
    if args.check_only:
        print("\n✓ All required environment variables are set.")
        sys.exit(0)
    
    # Run tests or interactive mode
    if args.interactive:
        run_interactive(args.server)
    else:
        test_funcs = {
            "jira": test_jira_server,
            "confluence": test_confluence_server,
            "gitlab": test_gitlab_server,
        }
        
        success = test_funcs[args.server]()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
