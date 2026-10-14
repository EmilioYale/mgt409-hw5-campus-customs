"""Data types shared by the agent team and the FastAPI routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

AGENT_LABELS: dict[str, str] = {
    "boss": "Boss",
    "inventory": "Inventory",
    "accounting": "Accounting",
    "facilities": "Facilities",
    "customer_service": "Customer Service",
}


class AgentEvent(BaseModel):
    """One step of an agent loop (or a delegation / run marker) shown on the board and audited."""

    seq: int
    ts: str
    run_id: str
    ticket_id: int
    agent: str
    kind: Literal[
        "run_started", "user_prompt", "model_request", "model_response", "tool_call", "tool_result",
        "delegation", "delegation_done", "agent_done", "run_done", "error",
    ]
    depth: int = 0
    called_by: str | None = None
    text: str = ""
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: str | None = None
    usage: dict[str, Any] | None = None


class AgentSummary(BaseModel):
    agent: str
    runs: int = 0
    tools_used: list[str] = Field(default_factory=list)
    delegated_to: list[str] = Field(default_factory=list)
    called_by: list[str] = Field(default_factory=list)
    summary: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class TicketRun(BaseModel):
    run_id: str
    ticket_id: int
    status: Literal["running", "finished", "error"] = "running"
    started_at: str
    finished_at: str | None = None
    final: str = ""
    error: str | None = None
    agents: dict[str, AgentSummary] = Field(default_factory=dict)
    delegations: list[dict[str, Any]] = Field(default_factory=list)
    total_tokens: int = 0


class RunRequest(BaseModel):
    ticket_id: int


class ApproveRequest(BaseModel):
    approved_by: str = Field(default="Emilio Gonzalez", min_length=1, max_length=80)


class Ticket(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str
    is_resolved: bool = False
