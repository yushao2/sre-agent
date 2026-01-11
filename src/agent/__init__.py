"""
AI SRE Agent - Incident management and support triage powered by Claude.

This package provides:
- SREAgentSimple: Core agent class for incident analysis
- run_summarize, run_triage, run_rca, run_chat: Synchronous helper functions
- CLI tools for local development

Quick Start:
    >>> from agent import run_chat
    >>> response = run_chat("What causes connection pool exhaustion?")
    >>> print(response)

For async usage:
    >>> from agent import SREAgentSimple
    >>> agent = SREAgentSimple()
    >>> result = await agent.summarize_incident_simple({...})
"""

from .agent import SREAgentSimple, SREAgent
from .prompts import SRE_AGENT_SYSTEM_PROMPT

# Import sync helper functions (these handle their own dependencies)
try:
    from .local import run_summarize, run_triage, run_rca, run_chat
except ImportError:
    # If local.py fails to import (shouldn't happen with minimal deps)
    run_summarize = None
    run_triage = None
    run_rca = None
    run_chat = None

# CLI entry point
try:
    from .cli import main
except ImportError:
    main = None

__version__ = "0.2.0"

__all__ = [
    # Core
    "SREAgentSimple",
    "SREAgent",
    "SRE_AGENT_SYSTEM_PROMPT",
    # Sync helpers
    "run_summarize",
    "run_triage",
    "run_rca",
    "run_chat",
    # CLI
    "main",
    # Version
    "__version__",
]
