from __future__ import annotations

import os
from typing import Optional

from atlassian import Jira
from mcp.server.fastmcp import FastMCP

# Read-only Jira (Data Center) MCP server.
# Write operations (create/update/transition/comment) are intentionally omitted for now.

mcp = FastMCP("jira", json_response=True)

_JIRA: Optional[Jira] = None


def _env(name: str, *, default: Optional[str] = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required env var: {name}")
    return str(val)


def _truncate(s: str, limit: int = 30_000) -> str:
    if s is None:
        return ""
    return s if len(s) <= limit else s[: limit - 20] + "\n...<truncated>..."


def _jira() -> Jira:
    """
    Jira Data Center auth typically uses username + password or username + PAT.
    Set:
      - JIRA_URL (e.g. https://jira.company.com)
      - JIRA_USERNAME
      - JIRA_TOKEN (password or PAT)
    Optional:
      - JIRA_VERIFY_SSL=true|false  (default true)
    """
    global _JIRA
    if _JIRA is not None:
        return _JIRA

    url = _env("JIRA_URL", required=True)
    username = _env("JIRA_USERNAME", required=True)
    token = os.getenv("JIRA_TOKEN") or os.getenv("JIRA_API_TOKEN") or os.getenv("JIRA_PASSWORD")
    if not token:
        raise RuntimeError("Missing required env var: JIRA_TOKEN (or JIRA_API_TOKEN/JIRA_PASSWORD)")
    token = str(token)

    verify_ssl = _env("JIRA_VERIFY_SSL", default="true").lower() in {"1", "true", "yes", "y"}

    # Data Center: cloud=False
    try:
        _JIRA = Jira(url=url, username=username, password=token, cloud=False, verify_ssl=verify_ssl)  # type: ignore[arg-type]
    except TypeError:
        _JIRA = Jira(url=url, username=username, password=token, cloud=False)  # type: ignore[arg-type]
    return _JIRA


def _issue_url(key: str) -> str:
    base = _env("JIRA_URL", required=True).rstrip("/")
    return f"{base}/browse/{key}"


def _summarize_issue(issue: dict) -> dict:
    fields = issue.get("fields") or {}
    status = (fields.get("status") or {}).get("name")
    priority = (fields.get("priority") or {}).get("name")

    assignee = fields.get("assignee") or {}
    reporter = fields.get("reporter") or {}

    return {
        "key": issue.get("key"),
        "url": _issue_url(str(issue.get("key", ""))),
        "summary": fields.get("summary"),
        "status": status,
        "priority": priority,
        "assignee": assignee.get("displayName") or assignee.get("name"),
        "reporter": reporter.get("displayName") or reporter.get("name"),
        "labels": fields.get("labels") or [],
        "updated": fields.get("updated"),
        "created": fields.get("created"),
    }


@mcp.tool()
def jira_search_issues(
    jql: str,
    start: int = 0,
    limit: int = 20,
    fields: str = "summary,status,assignee,reporter,priority,labels,updated,created",
) -> dict:
    """
    Search Jira issues using JQL (read-only).

    Args:
      jql: JQL query string
      start: pagination start index
      limit: max results (capped at 50)
      fields: comma-separated Jira fields to return (use "*all" for everything)

    Returns:
      { total, startAt, maxResults, issues: [ {key, url, summary, status, ...} ] }
    """
    limit = min(max(limit, 1), 50)
    res = _jira().jql(jql=jql, fields=fields, start=start, limit=limit)
    issues = [_summarize_issue(i) for i in (res.get("issues") or [])]
    return {
        "total": res.get("total"),
        "startAt": res.get("startAt"),
        "maxResults": res.get("maxResults"),
        "issues": issues,
    }


@mcp.tool()
def jira_get_issue(issue_key: str, fields: str = "summary,status,description,assignee,reporter,priority,labels,updated,created") -> dict:
    """
    Get a Jira issue by key (read-only).

    Returns a trimmed payload plus a convenience URL.
    """
    issue = _jira().issue(key=issue_key, fields=fields)
    issue["url"] = _issue_url(issue_key)

    # Best-effort truncation of description (often huge).
    try:
        desc = (((issue.get("fields") or {}).get("description")) or "")
        if isinstance(desc, str):
            (issue["fields"])["description"] = _truncate(desc, 60_000)
    except Exception:
        pass

    return issue


@mcp.tool()
def jira_get_issue_transitions(issue_key: str) -> dict:
    """
    List available transitions for an issue (read-only).
    """
    return _jira().get_issue_transitions(issue_key=issue_key)


@mcp.resource("jira://issue/{issue_key}")
def jira_issue_resource(issue_key: str) -> str:
    """
    Resource form of an issue, optimized for LLM context (short summary + truncated description).
    """
    issue = _jira().issue(
        key=issue_key,
        fields="summary,status,description,assignee,reporter,priority,labels,updated,created",
    )
    s = _summarize_issue(issue)
    desc = (((issue.get("fields") or {}).get("description")) or "")
    if not isinstance(desc, str):
        desc = str(desc)

    labels = ", ".join(s.get("labels") or [])
    return (
        f"# {s.get('key')}: {s.get('summary')}\n"
        f"- URL: {s.get('url')}\n"
        f"- Status: {s.get('status')}\n"
        f"- Priority: {s.get('priority')}\n"
        f"- Assignee: {s.get('assignee')}\n"
        f"- Reporter: {s.get('reporter')}\n"
        f"- Labels: {labels}\n"
        f"- Updated: {s.get('updated')}\n"
        f"- Created: {s.get('created')}\n\n"
        f"## Description\n{_truncate(desc, 60_000)}\n"
    )


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "streamable-http":
        mcp.settings.host = os.getenv("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.getenv("MCP_PORT", "8000"))
        # default path for this transport is /mcp
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
