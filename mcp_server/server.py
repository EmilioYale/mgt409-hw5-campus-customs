"""Campus Customs MCP server (FastMCP).

Every agent on the Campus Customs team gets its shop facts from these tools.
The tools only return rows that exist in the working database; nothing is made up.
Agents can *prepare* payments here, but no tool moves cash. Only a human approving
on the board does that (FastAPI -> shop_db.approve_request).

Run over stdio:  python mcp_server/server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shop_db  # noqa: E402

mcp = FastMCP(
    "campus-customs",
    instructions=(
        "Shop tools for Campus Customs. All values come from data/campus_customs_new.db. "
        "desk.date_today is 'today'. Payments are only prepared here; a human approves them."
    ),
)

# ── Reads ────────────────────────────────────────────────────────────────────


@mcp.tool
def get_desk_today() -> dict:
    """The shop's 'today' (desk.date_today). Use it for every overdue / due-soon decision."""
    return shop_db.get_desk_today()


@mcp.tool
def list_tickets(status: str | None = None) -> dict:
    """All tickets on the board (tickets table), optionally filtered by status."""
    return shop_db.list_tickets(status)


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """One ticket (tickets table) with its linked ids, plus any updates the team has logged."""
    return shop_db.get_ticket(ticket_id)


@mcp.tool
def get_ticket_work(ticket_id: int) -> dict:
    """Everything prepared on a ticket so far: quotes, purchase orders, reservations, drafts, approvals."""
    return shop_db.get_ticket_work(ticket_id)


@mcp.tool
def check_stock(sku: str, size: str | None = None) -> dict:
    """Units on hand for a SKU (optionally one size) from the inventory table."""
    return shop_db.check_stock(sku, size)


@mcp.tool
def get_pricing(sku: str) -> dict:
    """Unit cost and list price for a SKU from the pricing table, plus the per-unit margin at list."""
    return shop_db.get_pricing(sku)


@mcp.tool
def list_vendors() -> dict:
    """All vendors (vendors table) with specialty, lead_days, and whether an open invoice blocks shipping."""
    return shop_db.list_vendors()


@mcp.tool
def get_vendor_invoices(vendor_id: int) -> dict:
    """A vendor's invoices (invoices table) with days overdue vs desk.date_today and whether it can ship."""
    return shop_db.get_vendor_invoices(vendor_id)


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """One invoice (invoices + vendors tables) with days overdue vs desk.date_today."""
    return shop_db.get_invoice(invoice_id)


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """One lease from the leases table: space, landlord, monthly rent, next due date, days until due."""
    return shop_db.get_lease(lease_id)


@mcp.tool
def get_cash_balance() -> dict:
    """Checking balance (cash_accounts) and how much is already waiting on human approval."""
    return shop_db.get_cash_balance()


@mcp.tool
def list_payments() -> dict:
    """Payments already made (payments table). Every row was approved by a human."""
    return shop_db.list_payments()


@mcp.tool
def list_approvals(ticket_id: int | None = None, status: str | None = None) -> dict:
    """Payment requests waiting on / decided by a human (approvals table)."""
    return shop_db.list_approvals(ticket_id, status)


@mcp.tool
def quote_bulk_discount(sku: str, qty: int, discount_pct: float) -> dict:
    """What-if pricing (pricing table): unit price, margin and totals at a given % discount. Saves nothing."""
    return shop_db.quote_bulk_discount(sku, qty, discount_pct)


# ── Prepare-only writes (no cash moves) ──────────────────────────────────────


@mcp.tool
def record_quote(ticket_id: int, sku: str, qty: int, discount_pct: float, created_by: str) -> dict:
    """Save a discount quote for a ticket (quotes table). Refuses a price below unit cost."""
    return shop_db.record_quote(ticket_id, sku, qty, discount_pct, created_by)


@mcp.tool
def reserve_stock(ticket_id: int, sku: str, size: str, qty: int, created_by: str) -> dict:
    """Hold units on the shelf for a ticket (inventory -> reservations). Refuses more than on hand."""
    return shop_db.reserve_stock(ticket_id, sku, size, qty, created_by)


@mcp.tool
def request_payment(ticket_id: int, kind: str, ref_id: int, reason: str, requested_by: str) -> dict:
    """Prepare an invoice or rent payment for HUMAN approval (approvals table).

    kind: 'invoice' (ref_id = invoices.id) or 'rent' (ref_id = leases.id).
    The amount is read from the database. Refuses if checking can't cover it after pending approvals.
    """
    return shop_db.request_payment(ticket_id, kind, ref_id, reason, requested_by)


@mcp.tool
def create_purchase_order(ticket_id: int, vendor_id: int, sku: str, size: str, qty: int, created_by: str) -> dict:
    """Draft a restock purchase order at pricing.unit_cost and queue its payment for HUMAN approval.

    Refuses if the vendor has an open invoice that isn't already queued for payment,
    or if checking can't cover the total after pending approvals.
    """
    return shop_db.create_purchase_order(ticket_id, vendor_id, sku, size, qty, created_by)


@mcp.tool
def draft_customer_message(ticket_id: int, to_name: str, subject: str, body: str, created_by: str) -> dict:
    """Save a message draft on the board (drafts table). It is never sent."""
    return shop_db.draft_customer_message(ticket_id, to_name, subject, body, created_by)


@mcp.tool
def log_ticket_update(ticket_id: int, agent: str, summary: str) -> dict:
    """Write a short progress note on a ticket (ticket_updates table)."""
    return shop_db.log_ticket_update(ticket_id, agent, summary)


@mcp.tool
def resolve_ticket(ticket_id: int, outcome: str, agent: str = "boss") -> dict:
    """Boss only: close a ticket (tickets.status). Waits as awaiting_approval if payments are pending."""
    return shop_db.resolve_ticket(ticket_id, outcome, agent)


if __name__ == "__main__":
    mcp.run(show_banner=False)
