"""Jira MCP Server - placeholder for MCP integration."""

import os

def main():
    print("Jira MCP Server starting...")
    print(f"JIRA_URL: {os.getenv('JIRA_URL', 'not set')}")
    # MCP server implementation would go here
    import time
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
