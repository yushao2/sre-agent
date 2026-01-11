from __future__ import annotations

import os
from typing import Optional, Union

import gitlab
from mcp.server.fastmcp import FastMCP

# Read-only GitLab MCP server.
# Write operations (commenting, approving, retrying pipelines, etc.) are intentionally omitted for now.

mcp = FastMCP("gitlab", json_response=True)

_GL: Optional[gitlab.Gitlab] = None


def _env(name: str, *, default: Optional[str] = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required env var: {name}")
    return str(val)


def _truncate_bytes(b: bytes, limit: int = 50_000) -> bytes:
    return b if len(b) <= limit else b[:limit] + b"\n...<truncated>..."


def _gl() -> gitlab.Gitlab:
    """
    Set:
      - GITLAB_URL (e.g. https://gitlab.company.com)
      - GITLAB_TOKEN (PAT)
    Optional:
      - GITLAB_SSL_VERIFY=true|false (default true)
    """
    global _GL
    if _GL is not None:
        return _GL

    url = _env("GITLAB_URL", required=True)
    token = _env("GITLAB_TOKEN", required=True)
    ssl_verify = _env("GITLAB_SSL_VERIFY", default="true").lower() in {"1", "true", "yes", "y"}

    _GL = gitlab.Gitlab(url=url, private_token=token, ssl_verify=ssl_verify)
    return _GL


def _project(proj: Union[int, str]):
    return _gl().projects.get(proj)


@mcp.tool()
def gitlab_get_project(project: Union[int, str]) -> dict:
    """
    Get a GitLab project by numeric ID or full path (e.g. "group/subgroup/repo").
    """
    p = _project(project)
    return {
        "id": p.id,
        "path_with_namespace": p.path_with_namespace,
        "web_url": p.web_url,
        "default_branch": getattr(p, "default_branch", None),
        "visibility": getattr(p, "visibility", None),
        "description": getattr(p, "description", None),
    }


@mcp.tool()
def gitlab_list_merge_requests(
    project: Union[int, str],
    state: str = "opened",
    search: Optional[str] = None,
    per_page: int = 20,
) -> list[dict]:
    """
    List merge requests for a project (read-only).
    """
    per_page = min(max(per_page, 1), 50)
    p = _project(project)
    mrs = p.mergerequests.list(state=state, search=search, per_page=per_page)
    return [
        {
            "iid": mr.iid,
            "title": mr.title,
            "state": mr.state,
            "web_url": mr.web_url,
            "source_branch": getattr(mr, "source_branch", None),
            "target_branch": getattr(mr, "target_branch", None),
            "author": (getattr(mr, "author", None) or {}).get("name") if hasattr(mr, "author") else None,
        }
        for mr in mrs
    ]


@mcp.tool()
def gitlab_get_merge_request(project: Union[int, str], iid: int) -> dict:
    """
    Get a single merge request (read-only).
    """
    p = _project(project)
    mr = p.mergerequests.get(iid)
    desc = getattr(mr, "description", "") or ""
    return {
        "iid": mr.iid,
        "title": mr.title,
        "description": desc[:60_000],
        "state": mr.state,
        "web_url": mr.web_url,
        "source_branch": mr.source_branch,
        "target_branch": mr.target_branch,
        "sha": getattr(mr, "sha", None),
        "merge_status": getattr(mr, "merge_status", None),
        "pipeline": getattr(mr, "pipeline", None),
    }


@mcp.tool()
def gitlab_list_pipelines(
    project: Union[int, str],
    ref: Optional[str] = None,
    status: Optional[str] = None,
    per_page: int = 20,
) -> list[dict]:
    """
    List pipelines for a project (read-only).
    """
    per_page = min(max(per_page, 1), 50)
    p = _project(project)
    pipes = p.pipelines.list(ref=ref, status=status, per_page=per_page)
    return [{"id": pl.id, "status": pl.status, "ref": pl.ref, "web_url": pl.web_url} for pl in pipes]


@mcp.tool()
def gitlab_get_pipeline(project: Union[int, str], pipeline_id: int) -> dict:
    """
    Get pipeline details + list jobs in that pipeline (read-only).
    """
    p = _project(project)
    pipeline = p.pipelines.get(pipeline_id)
    jobs = pipeline.jobs.list()
    return {
        "id": pipeline.id,
        "status": pipeline.status,
        "ref": pipeline.ref,
        "sha": getattr(pipeline, "sha", None),
        "web_url": pipeline.web_url,
        "jobs": [{"id": j.id, "name": j.name, "status": j.status, "stage": getattr(j, "stage", None)} for j in jobs],
    }


@mcp.tool()
def gitlab_get_job_trace(project: Union[int, str], job_id: int, max_bytes: int = 50_000) -> dict:
    """
    Fetch (truncated) CI job trace/log (read-only).
    """
    max_bytes = min(max(max_bytes, 1_000), 500_000)
    p = _project(project)
    job = p.jobs.get(job_id)
    trace = job.trace()
    if isinstance(trace, str):
        b = trace.encode("utf-8", errors="replace")
    else:
        b = trace
    b = _truncate_bytes(b, limit=max_bytes)
    return {"job_id": job_id, "name": job.name, "status": job.status, "trace": b.decode("utf-8", errors="replace")}


@mcp.tool()
def gitlab_get_file_raw(project: Union[int, str], file_path: str, ref: str = "main", max_bytes: int = 200_000) -> dict:
    """
    Get raw file contents from the repository (truncated) (read-only).
    """
    max_bytes = min(max(max_bytes, 1_000), 2_000_000)
    p = _project(project)
    raw: bytes = p.files.raw(file_path=file_path, ref=ref)
    raw = _truncate_bytes(raw, limit=max_bytes)
    return {"file_path": file_path, "ref": ref, "bytes": len(raw), "content": raw.decode("utf-8", errors="replace")}


@mcp.resource("gitlab://project/{project}/mr/{iid}")
def gitlab_mr_resource(project: str, iid: str) -> str:
    """
    Resource view of an MR: title + description (truncated).
    """
    p = _project(project)
    mr = p.mergerequests.get(int(iid))
    desc = getattr(mr, "description", "") or ""
    return (
        f"# MR !{mr.iid}: {mr.title}\n"
        f"- Project: {p.path_with_namespace}\n"
        f"- URL: {mr.web_url}\n"
        f"- State: {mr.state}\n"
        f"- Source: {mr.source_branch} -> Target: {mr.target_branch}\n\n"
        f"## Description\n{desc[:80_000]}\n"
    )


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "streamable-http":
        mcp.settings.host = os.getenv("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.getenv("MCP_PORT", "8000"))
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
