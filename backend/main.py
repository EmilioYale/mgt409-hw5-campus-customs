"""Campus Customs FastAPI backend.

Start from backend/:  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import events
import team
from config import MCP_SERVER, MODEL_NAME
from models import AGENT_LABELS, ApproveRequest, Ticket

# Human-only shop actions (approve / reject / reset) are not MCP tools, so they're imported directly.
sys.path.insert(0, str(MCP_SERVER.parent))
import shop_db  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One MCP connection for the whole app; every agent uses a filtered view of it.
    async with team.MCP:
        yield


app = FastAPI(title="Campus Customs Multi-Agent Ops", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "model": MODEL_NAME, "agents": AGENT_LABELS, "db": shop_db.DB_PATH.name}


@app.get("/api/tickets")
def list_tickets() -> dict:
    """The three tickets and whether each is open or resolved."""
    pending = shop_db.list_approvals(status="pending")["approvals"]
    out = []
    for row in shop_db.list_tickets()["tickets"]:
        t = Ticket(**row, is_resolved=row["status"] == "resolved").model_dump()
        t["running"] = team.is_running(row["id"])
        t["pending_approvals"] = sum(1 for a in pending if a["ticket_id"] == row["id"])
        out.append(t)
    return {"tickets": out}


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> dict:
    """Start the agent team on one ticket (runs in the background; poll /api/events)."""
    found = shop_db.get_ticket(ticket_id)
    if not found["found"]:
        raise HTTPException(404, f"No ticket {ticket_id}.")
    if team.is_running(ticket_id):
        raise HTTPException(409, f"Ticket {ticket_id} is already running.")
    team.start_ticket(ticket_id)
    return {"ok": True, "ticket_id": ticket_id, "message": "Team started."}


@app.get("/api/events")
def get_events(since: int = 0, ticket_id: int | None = None, limit: int = 500) -> dict:
    """Recent agent events: what each agent said and which tools it called."""
    items = events.since(since, ticket_id, limit)
    return {"events": [e.model_dump() for e in items], "last_seq": items[-1].seq if items else since}


@app.get("/api/tickets/{ticket_id}/summary")
def ticket_summary(ticket_id: int) -> dict:
    """Per-agent summary of the latest run, plus everything the team prepared on the ticket."""
    found = shop_db.get_ticket(ticket_id)
    if not found["found"]:
        raise HTTPException(404, f"No ticket {ticket_id}.")
    run = team.RUNS.get(ticket_id)
    return {
        "ticket": found["ticket"],
        "updates": found["updates"],
        "run": run.model_dump() if run else None,
        "running": team.is_running(ticket_id),
        "work": shop_db.get_ticket_work(ticket_id),
    }


@app.get("/api/approvals")
def list_approvals(status: str | None = None, ticket_id: int | None = None) -> dict:
    return shop_db.list_approvals(ticket_id, status)


@app.post("/api/approvals/{approval_id}/approve")
def approve(approval_id: int, body: ApproveRequest) -> dict:
    """A human clicked Approve. This is the only route that moves cash."""
    result = shop_db.approve_request(approval_id, body.approved_by)
    if not result.get("ok"):
        raise HTTPException(409, result.get("message", "Refused."))
    return result


@app.post("/api/approvals/{approval_id}/reject")
def reject(approval_id: int, body: ApproveRequest) -> dict:
    result = shop_db.reject_request(approval_id, body.approved_by)
    if not result.get("ok"):
        raise HTTPException(409, result.get("message", "Refused."))
    return result


@app.get("/api/cash")
def cash() -> dict:
    """Current checking balance from cash_accounts (plus what's pending approval)."""
    return {**shop_db.get_cash_balance(), "payments": shop_db.list_payments()["payments"]}


@app.post("/api/reset")
def reset() -> dict:
    """Copy the original DB over the working copy for a fresh run. The audit trail is kept."""
    if any(team.is_running(t["id"]) for t in shop_db.list_tickets()["tickets"]):
        raise HTTPException(409, "A ticket is running. Wait for it to finish before resetting.")
    result = shop_db.reset_database()
    team.RUNS.clear()
    events.clear_memory()
    return result
