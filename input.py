from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser


class IncidentNormalized(BaseModel):
    key: Optional[str] = Field(default=None, description="Incident ID like INC-123 if known")
    summary: Optional[str] = Field(default=None, description="Short title")
    description: str = Field(description="Best-effort cleaned description")
    status: Optional[str] = None
    priority: Optional[str] = None


class TicketNormalized(BaseModel):
    key: Optional[str] = Field(default=None, description="Ticket ID if known")
    summary: Optional[str] = None
    description: str
    reporter: Optional[str] = None
    labels: list[str] = Field(default_factory=list)


INTAKE_SYSTEM = """You convert unstructured SRE input into STRICT JSON that matches the schema.
Rules:
- Output ONLY valid JSON (no markdown, no backticks, no commentary).
- If a field is unknown, use null (or [] for lists).
- Prefer preserving important details (symptoms, errors, timestamps, impact, actions taken).
"""


async def normalize_with_llm(llm, text: str, model: type[BaseModel]) -> BaseModel:
    parser = PydanticOutputParser(pydantic_object=model)

    prompt = f"""
Normalize this unstructured input into the target schema.

SCHEMA INSTRUCTIONS:
{parser.get_format_instructions()}

UNSTRUCTURED INPUT:
{text}
""".strip()

    resp = await llm.ainvoke([
        SystemMessage(content=INTAKE_SYSTEM),
        HumanMessage(content=prompt),
    ])

    # Parser expects pure JSON text. If model sometimes returns extra text,
    # you can add a small "JSON extraction" fallback here.
    return parser.parse(str(resp.content))