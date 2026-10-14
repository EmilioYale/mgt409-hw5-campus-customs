"""The Campus Customs agent team (PydanticAI).

Five agents: boss, inventory, accounting, facilities, customer_service.
- Full connectivity: every agent has a `delegate` tool that can hand work to any
  other agent, and that agent can delegate again (up to MAX_DELEGATION_DEPTH).
- Every shop fact comes from the campus-customs MCP server. Each agent sees only
  the MCP tools its role needs (a filtered view of one shared MCP connection).
- Every agent-loop step is emitted as an event (board feed + audit trail).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import TextPart, ToolCallPart, ToolReturnPart, RetryPromptPart, UserPromptPart

import events
from config import (
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_TICKET,
    MAX_REQUESTS_PER_AGENT_RUN,
    MAX_TOKENS_PER_AGENT_RUN,
    MAX_TOKENS_PER_TICKET,
    MCP_SERVER,
    PROMPTS,
    ROOT,
    build_model,
)
from models import AGENT_LABELS, AgentName, AgentSummary, TicketRun

AGENT_NAMES: tuple[str, ...] = tuple(AGENT_LABELS)

# Which MCP tools each role may call. Everyone shares the basics.
_COMMON = {"get_desk_today", "get_ticket", "get_ticket_work", "log_ticket_update"}
ROLE_TOOLS: dict[str, set[str]] = {
    "boss": _COMMON | {"list_tickets", "get_cash_balance", "list_approvals", "resolve_ticket"},
    "inventory": _COMMON | {"check_stock", "get_pricing", "list_vendors", "get_vendor_invoices", "reserve_stock"},
    "accounting": _COMMON | {
        "get_cash_balance", "get_invoice", "get_vendor_invoices", "get_pricing", "quote_bulk_discount",
        "record_quote", "request_payment", "create_purchase_order", "list_payments", "list_approvals",
    },
    "facilities": _COMMON | {"get_lease", "get_cash_balance"},
    "customer_service": _COMMON | {"check_stock", "get_pricing", "draft_customer_message"},
}

# Tool args that name "who did this". The real agent is stamped in, whatever the model typed.
_IDENTITY_ARGS = ("created_by", "requested_by", "agent")


@dataclass
class Budget:
    delegations: int = 0
    tokens: int = 0


@dataclass
class TeamDeps:
    run: TicketRun
    agent: str
    depth: int
    budget: Budget
    called_by: str | None = None
    tools_used: list[str] = field(default_factory=list)


async def _stamp_agent(ctx: RunContext[TeamDeps], call_tool: Any, name: str, tool_args: dict[str, Any]) -> Any:
    for key in _IDENTITY_ARGS:
        if key in tool_args:
            tool_args[key] = ctx.deps.agent
    if name == "resolve_ticket":
        tool_args["agent"] = ctx.deps.agent
    return await call_tool(name, tool_args)


def _make_mcp() -> MCPToolset:
    env = {"PATH": os.environ.get("PATH", "")}
    if os.getenv("CAMPUS_CUSTOMS_DB"):
        env["CAMPUS_CUSTOMS_DB"] = os.environ["CAMPUS_CUSTOMS_DB"]
    transport = StdioTransport(command=sys.executable, args=[str(MCP_SERVER)], env=env, cwd=str(ROOT), keep_alive=True)
    return MCPToolset(Client(transport), process_tool_call=_stamp_agent, max_retries=2, id="campus-customs")


MCP = _make_mcp()


async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> str:
    """Hand a task to another agent on the Campus Customs team and get their report back.

    Args:
        to_agent: one of boss, inventory, accounting, facilities, customer_service.
        task: a specific, self-contained request: include the ticket id, SKU/size/qty,
            invoice/lease ids and any numbers you already confirmed, so they don't redo your work.
    """
    d = ctx.deps
    if to_agent == d.agent:
        return "Refused: you cannot delegate to yourself. Do the task with your own tools."
    if to_agent not in AGENT_NAMES:
        return f"Refused: unknown agent '{to_agent}'."
    if d.depth >= MAX_DELEGATION_DEPTH:
        return "Refused: delegation chain is already at the depth limit. Finish with what you have."
    if d.budget.delegations >= MAX_DELEGATIONS_PER_TICKET:
        return "Refused: this ticket used its delegation budget. Report back with what you have."
    if d.budget.tokens >= MAX_TOKENS_PER_TICKET:
        return "Refused: this ticket used its token budget. Report back with what you have."

    d.budget.delegations += 1
    record = {"from": d.agent, "to": to_agent, "task": task, "depth": d.depth + 1, "status": "running"}
    d.run.delegations.append(record)
    d.run.agents[d.agent].delegated_to.append(to_agent)
    events.emit(
        run_id=d.run.run_id, ticket_id=d.run.ticket_id, agent=d.agent, kind="delegation",
        depth=d.depth, called_by=d.called_by, text=task, tool=to_agent,
    )
    try:
        reply = await run_agent(to_agent, task, run=d.run, budget=d.budget, depth=d.depth + 1, called_by=d.agent)
        record["status"] = "done"
    except Exception as exc:  # report the failure back to the caller instead of crashing the whole ticket
        reply = f"{AGENT_LABELS[to_agent]} could not finish: {type(exc).__name__}: {events.clip(str(exc), 300)}"
        record["status"] = "error"
    record["reply"] = events.clip(reply, 600)
    events.emit(
        run_id=d.run.run_id, ticket_id=d.run.ticket_id, agent=d.agent, kind="delegation_done",
        depth=d.depth, called_by=d.called_by, tool=to_agent, result=events.clip(reply, 800),
    )
    return reply


def _build_agent(name: str) -> Agent[TeamDeps, str]:
    prompt = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    allowed = ROLE_TOOLS[name]
    return Agent(
        build_model(),
        name=name,
        deps_type=TeamDeps,
        output_type=str,
        instructions=prompt,
        toolsets=[MCP.filtered(lambda ctx, tool_def: tool_def.name in allowed)],
        tools=[delegate],
        retries=2,
    )


_agents: dict[str, Agent[TeamDeps, str]] = {}


def get_agent(name: str) -> Agent[TeamDeps, str]:
    if name not in _agents:
        _agents[name] = _build_agent(name)
    return _agents[name]


def _emit_node(node: Any, deps: TeamDeps) -> None:
    base = dict(run_id=deps.run.run_id, ticket_id=deps.run.ticket_id, agent=deps.agent, depth=deps.depth, called_by=deps.called_by)
    summary = deps.run.agents[deps.agent]

    if Agent.is_model_request_node(node):
        for part in node.request.parts:
            if isinstance(part, UserPromptPart):
                events.emit(**base, kind="user_prompt", text=events.clip(part.content, 2000))
            elif isinstance(part, ToolReturnPart):
                events.emit(**base, kind="tool_result", tool=part.tool_name, result=events.clip(part.model_response_str(), 1500))
            elif isinstance(part, RetryPromptPart):
                events.emit(**base, kind="tool_result", tool=part.tool_name, result="retry: " + events.clip(part.model_response(), 600))
        return

    if Agent.is_call_tools_node(node):
        resp = node.model_response
        usage = resp.usage
        tokens_in, tokens_out = usage.input_tokens or 0, usage.output_tokens or 0
        deps.budget.tokens += tokens_in + tokens_out
        deps.run.total_tokens = deps.budget.tokens
        summary.input_tokens += tokens_in
        summary.output_tokens += tokens_out
        text = "".join(p.content for p in resp.parts if isinstance(p, TextPart)).strip()
        events.emit(
            **base, kind="model_response", text=events.clip(text, 2000),
            usage={"input_tokens": tokens_in, "output_tokens": tokens_out, "model": resp.model_name},
        )
        for part in resp.parts:
            if isinstance(part, ToolCallPart):
                deps.tools_used.append(part.tool_name)
                if part.tool_name not in summary.tools_used:
                    summary.tools_used.append(part.tool_name)
                events.emit(**base, kind="tool_call", tool=part.tool_name, args=part.args_as_dict())
        return

    if Agent.is_end_node(node):
        events.emit(**base, kind="agent_done", text=events.clip(str(node.data.output), 2000))


async def run_agent(name: str, task: str, *, run: TicketRun, budget: Budget, depth: int, called_by: str | None) -> str:
    deps = TeamDeps(run=run, agent=name, depth=depth, budget=budget, called_by=called_by)
    summary = run.agents.setdefault(name, AgentSummary(agent=name))
    summary.runs += 1
    if called_by and called_by not in summary.called_by:
        summary.called_by.append(called_by)

    header = (
        f"Ticket #{run.ticket_id}. You are the {AGENT_LABELS[name]} agent."
        + (f" The {AGENT_LABELS[called_by]} agent delegated this to you." if called_by else "")
    )
    prompt = f"{header}\n\n{task}"
    limits = UsageLimits(request_limit=MAX_REQUESTS_PER_AGENT_RUN, total_tokens_limit=MAX_TOKENS_PER_AGENT_RUN)

    async with get_agent(name).iter(prompt, deps=deps, usage_limits=limits) as agent_run:
        async for node in agent_run:
            _emit_node(node, deps)
        output = str(agent_run.result.output).strip()

    summary.summary = output if not summary.summary else f"{summary.summary}\n\n{output}"
    return output


# ── Ticket runs ──────────────────────────────────────────────────────────────

RUNS: dict[int, TicketRun] = {}
_running: set[int] = set()


def is_running(ticket_id: int) -> bool:
    return ticket_id in _running


async def run_ticket(ticket_id: int) -> TicketRun:
    if ticket_id in _running:
        raise RuntimeError(f"Ticket {ticket_id} is already running.")
    _running.add(ticket_id)
    run = TicketRun(run_id=uuid.uuid4().hex[:10], ticket_id=ticket_id, started_at=datetime.now().isoformat(timespec="seconds"))
    RUNS[ticket_id] = run
    events.emit(run_id=run.run_id, ticket_id=ticket_id, agent="boss", kind="run_started", text=f"Team started on ticket {ticket_id}.")
    task = (
        f"Work ticket {ticket_id} from the board until it is resolved. Read it first with get_ticket, "
        "bring in only the specialists this ticket actually needs, and call resolve_ticket at the end "
        "with a clear outcome."
    )
    try:
        run.final = await run_agent("boss", task, run=run, budget=Budget(), depth=0, called_by=None)
        run.status = "finished"
    except Exception as exc:
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"
        events.emit(run_id=run.run_id, ticket_id=ticket_id, agent="boss", kind="error", text=events.clip(run.error, 1000))
    finally:
        run.finished_at = datetime.now().isoformat(timespec="seconds")
        _running.discard(ticket_id)
        events.emit(
            run_id=run.run_id, ticket_id=ticket_id, agent="boss", kind="run_done",
            text=events.clip(run.final or run.error or "", 2000), usage={"total_tokens": run.total_tokens},
        )
    return run


def start_ticket(ticket_id: int) -> asyncio.Task:
    return asyncio.create_task(run_ticket(ticket_id))
