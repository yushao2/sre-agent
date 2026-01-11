from __future__ import annotations

import os
from typing import Optional

from atlassian import Confluence
from mcp.server.fastmcp import FastMCP

# Read-only Confluence (Data Center) MCP server.
# Write operations (create/update) are intentionally omitted for now.

mcp = FastMCP("confluence", json_response=True)

_CONFLUENCE: Optional[Confluence] = None


def _env(name: str, *, default: Optional[str] = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required env var: {name}")
    return str(val)


def _truncate(s: str, limit: int = 60_000) -> str:
    if s is None:
        return ""
    return s if len(s) <= limit else s[: limit - 20] + "\n...<truncated>..."


def _confluence() -> Confluence:
    """
    Confluence Data Center auth typically uses username + password or username + PAT.
    Set:
      - CONFLUENCE_URL (e.g. https://confluence.company.com)
      - CONFLUENCE_USERNAME
      - CONFLUENCE_TOKEN (password or PAT)
    Optional:
      - CONFLUENCE_VERIFY_SSL=true|false  (default true)
    """
    global _CONFLUENCE
    if _CONFLUENCE is not None:
        return _CONFLUENCE

    url = _env("CONFLUENCE_URL", required=True)
    username = _env("CONFLUENCE_USERNAME", required=True)
    token = os.getenv("CONFLUENCE_TOKEN") or os.getenv("CONFLUENCE_API_TOKEN") or os.getenv("CONFLUENCE_PASSWORD")
    if not token:
        raise RuntimeError("Missing required env var: CONFLUENCE_TOKEN (or CONFLUENCE_API_TOKEN/CONFLUENCE_PASSWORD)")
    token = str(token)
    verify_ssl = _env("CONFLUENCE_VERIFY_SSL", default="true").lower() in {"1", "true", "yes", "y"}

    # atlassian-python-api supports Confluence Server/DC. If `verify_ssl` isn't accepted
    # in your version, remove it.
    try:
        _CONFLUENCE = Confluence(url=url, username=username, password=token, verify_ssl=verify_ssl)  # type: ignore[arg-type]
    except TypeError:
        _CONFLUENCE = Confluence(url=url, username=username, password=token)  # type: ignore[arg-type]
    return _CONFLUENCE


def _page_url(page_id: str) -> str:
    base = _env("CONFLUENCE_URL", required=True).rstrip("/")
    return f"{base}/pages/viewpage.action?pageId={page_id}"


@mcp.tool()
def confluence_cql_search(
    cql: str,
    limit: int = 10,
    expand: str = "content.body.view",
) -> dict:
    """
    Search Confluence using CQL (read-only).

    Args:
      cql: e.g. 'space = "DOCS" AND title ~ "runbook" AND type = "page"'
      limit: max results (capped at 25)
      expand: expand fields (e.g. "content.body.view")

    Returns:
      raw Confluence CQL search payload
    """
    limit = min(max(limit, 1), 25)
    return _confluence().cql(cql=cql, limit=limit, expand=expand)


@mcp.tool()
def confluence_get_page_by_id(
    page_id: str,
    expand: str = "body.view,version,space",
) -> dict:
    """
    Fetch a Confluence page by page ID (read-only).

    Returns a trimmed payload plus a convenience URL.
    """
    page = _confluence().get_page_by_id(page_id=page_id, expand=expand)
    if isinstance(page, dict):
        page["url"] = _page_url(page_id)

        # Avoid huge HTML bodies.
        try:
            view = (((page.get("body") or {}).get("view") or {}).get("value")) or ""
            if isinstance(view, str) and "body" in page and "view" in (page["body"] or {}):
                page["body"]["view"]["value"] = _truncate(view, 80_000)  # type: ignore[index]
        except Exception:
            pass

    return page


@mcp.tool()
def confluence_get_page_by_title(
    space: str,
    title: str,
    expand: str = "body.view,version,space",
) -> dict:
    """
    Fetch a page by (space, title) (read-only).
    """
    page = _confluence().get_page_by_title(space=space, title=title, expand=expand)
    if isinstance(page, dict) and "id" in page:
        page["url"] = _page_url(str(page["id"]))
    return page


@mcp.resource("confluence://page/{page_id}")
def confluence_page_resource(page_id: str) -> str:
    """
    Resource view of a page: title + view body (truncated), ideal for LLM context.
    """
    page = _confluence().get_page_by_id(page_id=page_id, expand="body.view,version,space")
    title = page.get("title")
    space = (page.get("space") or {}).get("key")
    body = (((page.get("body") or {}).get("view") or {}).get("value")) or ""
    if not isinstance(body, str):
        body = str(body)
    return (
        f"# {title}\n"
        f"- Page ID: {page_id}\n"
        f"- Space: {space}\n"
        f"- URL: {_page_url(page_id)}\n\n"
        f"{_truncate(body, 80_000)}\n"
    )


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "streamable-http":
        mcp.settings.host = os.getenv("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.getenv("MCP_PORT", "8000"))
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
