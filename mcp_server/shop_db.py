"""Shop database logic behind the Campus Customs MCP server.

server.py exposes the agent-safe functions here as MCP tools. The human-only
functions (approve_request, reject_request, reset_database) are NOT exposed over
MCP. Only the FastAPI approve/reset routes call them, so no agent can move cash.

Every value an agent sees comes from data/campus_customs_new.db. Amounts for
payments are always looked up from the database, never taken from the model.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
DB_PATH = Path(os.getenv("CAMPUS_CUSTOMS_DB") or ROOT / "data" / "campus_customs_new.db")

AGENTS = ("boss", "inventory", "accounting", "facilities", "customer_service")
PAYMENT_KINDS = ("invoice", "rent", "purchase_order")

# Workflow tables the team writes to. They live only in the working copy and are
# created on first use; the original shop tables keep their schema.
_APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    ref_id INTEGER NOT NULL,
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    reason TEXT,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    result TEXT
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    vendor_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    total REAL NOT NULL,
    eta TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL,
    discount_pct REAL NOT NULL,
    unit_price REAL NOT NULL,
    unit_cost REAL NOT NULL,
    margin_per_unit REAL NOT NULL,
    total REAL NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    to_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_updates (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    agent TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}. Copy {ORIGINAL_DB.name} to it first.")
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_APP_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _row(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def _today(conn: sqlite3.Connection) -> date:
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()[0])


def _balance(conn: sqlite3.Connection) -> float:
    return float(conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()[0])


def _pending_total(conn: sqlite3.Connection) -> float:
    return float(conn.execute("SELECT COALESCE(SUM(amount), 0) FROM approvals WHERE status = 'pending'").fetchone()[0])


def _open_invoices(conn: sqlite3.Connection, vendor_id: int) -> list[dict]:
    return _rows(conn, "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY id", (vendor_id,))


def _check_agent(agent: str) -> None:
    if agent not in AGENTS:
        raise ValueError(f"Unknown agent '{agent}'. Use one of: {', '.join(AGENTS)}.")


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(d)


# ── Reads ────────────────────────────────────────────────────────────────────


def get_desk_today() -> dict:
    with connect() as conn:
        desk = _row(conn, "SELECT date_today, notes FROM desk")
    return {"date_today": desk["date_today"], "notes": desk["notes"]}


def list_tickets(status: str | None = None) -> dict:
    with connect() as conn:
        if status:
            rows = _rows(conn, "SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,))
        else:
            rows = _rows(conn, "SELECT * FROM tickets ORDER BY id")
    return {"tickets": rows}


def get_ticket(ticket_id: int) -> dict:
    with connect() as conn:
        ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"found": False, "ticket_id": ticket_id, "message": "No ticket with that id."}
        updates = _rows(conn, "SELECT agent, status, summary, created_at FROM ticket_updates WHERE ticket_id = ? ORDER BY id", (ticket_id,))
    return {"found": True, "ticket": ticket, "updates": updates}


def check_stock(sku: str, size: str | None = None) -> dict:
    with connect() as conn:
        if size:
            rows = _rows(conn, "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?", (sku, size))
        else:
            rows = _rows(conn, "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid", (sku,))
    if not rows:
        return {"found": False, "sku": sku, "size": size, "message": "No inventory row for that SKU/size."}
    return {"found": True, "rows": rows}


def get_pricing(sku: str) -> dict:
    with connect() as conn:
        row = _row(conn, "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if row is None:
        return {"found": False, "sku": sku, "message": "No pricing row for that SKU."}
    row["margin_per_unit_at_list"] = round(row["list_price"] - row["unit_cost"], 2)
    return {"found": True, "pricing": row}


def list_vendors() -> dict:
    with connect() as conn:
        vendors = _rows(conn, "SELECT * FROM vendors ORDER BY id")
        for v in vendors:
            open_inv = _open_invoices(conn, v["id"])
            v["open_invoice_ids"] = [i["id"] for i in open_inv]
            v["can_ship_new_product"] = not open_inv
    return {"vendors": vendors}


def get_vendor_invoices(vendor_id: int) -> dict:
    with connect() as conn:
        vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if vendor is None:
            return {"found": False, "vendor_id": vendor_id, "message": "No vendor with that id."}
        today = _today(conn)
        invoices = _rows(conn, "SELECT * FROM invoices WHERE vendor_id = ? ORDER BY id", (vendor_id,))
    for inv in invoices:
        inv["days_overdue"] = max(0, (today - date.fromisoformat(inv["due_date"])).days) if inv["status"] == "open" else 0
    open_inv = [i for i in invoices if i["status"] == "open"]
    return {
        "found": True,
        "date_today": today.isoformat(),
        "vendor": vendor,
        "invoices": invoices,
        "can_ship_new_product": not open_inv,
        "blocked_by_invoice_ids": [i["id"] for i in open_inv],
    }


def get_invoice(invoice_id: int) -> dict:
    with connect() as conn:
        inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        if inv is None:
            return {"found": False, "invoice_id": invoice_id, "message": "No invoice with that id."}
        today = _today(conn)
        vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (inv["vendor_id"],))
    inv["days_overdue"] = max(0, (today - date.fromisoformat(inv["due_date"])).days) if inv["status"] == "open" else 0
    return {"found": True, "date_today": today.isoformat(), "invoice": inv, "vendor": vendor}


def get_lease(lease_id: int) -> dict:
    with connect() as conn:
        lease = _row(conn, "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?", (lease_id,))
        if lease is None:
            return {"found": False, "lease_id": lease_id, "message": "No lease with that id."}
        today = _today(conn)
    lease["days_until_due"] = (date.fromisoformat(lease["next_due"]) - today).days
    return {"found": True, "date_today": today.isoformat(), "lease": lease}


def get_cash_balance() -> dict:
    with connect() as conn:
        acct = _row(conn, "SELECT name, balance, date FROM cash_accounts WHERE name = 'checking'")
        pending = _pending_total(conn)
    return {
        "account": acct["name"],
        "balance": acct["balance"],
        "as_of": acct["date"],
        "pending_approval_total": round(pending, 2),
        "available_after_pending": round(acct["balance"] - pending, 2),
    }


def list_payments() -> dict:
    with connect() as conn:
        return {"payments": _rows(conn, "SELECT * FROM payments ORDER BY id")}


def list_approvals(ticket_id: int | None = None, status: str | None = None) -> dict:
    sql, params = "SELECT * FROM approvals WHERE 1=1", []
    if ticket_id is not None:
        sql += " AND ticket_id = ?"
        params.append(ticket_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    with connect() as conn:
        return {"approvals": _rows(conn, sql + " ORDER BY id", tuple(params))}


def get_ticket_work(ticket_id: int) -> dict:
    """Everything the team has prepared on a ticket: quotes, POs, reservations, drafts, approvals."""
    with connect() as conn:
        return {
            "quotes": _rows(conn, "SELECT * FROM quotes WHERE ticket_id = ? ORDER BY id", (ticket_id,)),
            "purchase_orders": _rows(conn, "SELECT * FROM purchase_orders WHERE ticket_id = ? ORDER BY id", (ticket_id,)),
            "reservations": _rows(conn, "SELECT * FROM reservations WHERE ticket_id = ? ORDER BY id", (ticket_id,)),
            "drafts": _rows(conn, "SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,)),
            "approvals": _rows(conn, "SELECT * FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,)),
            "updates": _rows(conn, "SELECT * FROM ticket_updates WHERE ticket_id = ? ORDER BY id", (ticket_id,)),
        }


def quote_bulk_discount(sku: str, qty: int, discount_pct: float) -> dict:
    if qty <= 0 or not 0 <= discount_pct < 100:
        return {"ok": False, "message": "qty must be > 0 and discount_pct between 0 and 100."}
    with connect() as conn:
        p = _row(conn, "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    if p is None:
        return {"ok": False, "sku": sku, "message": "No pricing row for that SKU."}
    unit_price = round(p["list_price"] * (1 - discount_pct / 100), 2)
    margin = round(unit_price - p["unit_cost"], 2)
    return {
        "ok": True,
        "sku": sku,
        "qty": qty,
        "list_price": p["list_price"],
        "unit_cost": p["unit_cost"],
        "discount_pct": discount_pct,
        "unit_price": unit_price,
        "margin_per_unit": margin,
        "margin_pct_of_price": round(100 * margin / unit_price, 1) if unit_price else None,
        "total_price": round(unit_price * qty, 2),
        "total_margin": round(margin * qty, 2),
        "below_cost": margin < 0,
    }


# ── Agent writes (prepare only; nothing here moves cash) ─────────────────────


def record_quote(ticket_id: int, sku: str, qty: int, discount_pct: float, created_by: str) -> dict:
    _check_agent(created_by)
    q = quote_bulk_discount(sku, qty, discount_pct)
    if not q.get("ok"):
        return q
    if q["below_cost"]:
        return {"ok": False, "message": f"Refused: {discount_pct}% off puts the price below unit cost.", **q}
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO quotes (ticket_id, sku, qty, discount_pct, unit_price, unit_cost, margin_per_unit, total, created_by, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (ticket_id, sku, qty, discount_pct, q["unit_price"], q["unit_cost"], q["margin_per_unit"], q["total_price"], created_by, _now()),
        )
    return {**q, "quote_id": cur.lastrowid, "ticket_id": ticket_id}


def reserve_stock(ticket_id: int, sku: str, size: str, qty: int, created_by: str) -> dict:
    _check_agent(created_by)
    if qty <= 0:
        return {"ok": False, "message": "qty must be > 0."}
    with connect() as conn:
        row = _row(conn, "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size))
        if row is None:
            return {"ok": False, "message": "No inventory row for that SKU/size."}
        if row["qty"] < qty:
            return {"ok": False, "message": f"Refused: only {row['qty']} on hand, cannot reserve {qty}.", "on_hand": row["qty"]}
        conn.execute("UPDATE inventory SET qty = qty - ? WHERE sku = ? AND size = ?", (qty, sku, size))
        cur = conn.execute(
            "INSERT INTO reservations (ticket_id, sku, size, qty, created_by, created_at) VALUES (?,?,?,?,?,?)",
            (ticket_id, sku, size, qty, created_by, _now()),
        )
    return {"ok": True, "reservation_id": cur.lastrowid, "reserved": qty, "on_hand_after": row["qty"] - qty}


def _request_approval(
    conn: sqlite3.Connection, ticket_id: int, kind: str, ref_id: int, payee: str, amount: float, reason: str, requested_by: str
) -> dict:
    dup = _row(
        conn,
        "SELECT * FROM approvals WHERE kind = ? AND ref_id = ? AND status IN ('pending', 'approved')",
        (kind, ref_id),
    )
    if dup:
        return {"ok": True, "duplicate": True, "message": f"Already {dup['status']} as approval #{dup['id']}.", "approval": dup}
    balance, pending = _balance(conn), _pending_total(conn)
    available = round(balance - pending, 2)
    if amount > available:
        return {
            "ok": False,
            "refused": True,
            "message": f"Refused: ${amount:,.2f} is more than the ${available:,.2f} checking has left after pending approvals. No negative balances.",
            "balance": balance,
            "pending_approval_total": pending,
        }
    cur = conn.execute(
        "INSERT INTO approvals (ticket_id, kind, ref_id, payee, amount, reason, requested_by, status, created_at) "
        "VALUES (?,?,?,?,?,?,?, 'pending', ?)",
        (ticket_id, kind, ref_id, payee, amount, reason, requested_by, _now()),
    )
    return {
        "ok": True,
        "approval_id": cur.lastrowid,
        "status": "pending",
        "amount": amount,
        "payee": payee,
        "message": "Prepared. A human must approve this on the board before any cash moves.",
        "available_after_this": round(available - amount, 2),
    }


def request_payment(ticket_id: int, kind: str, ref_id: int, reason: str, requested_by: str) -> dict:
    """Prepare an invoice or rent payment for human approval. The amount comes from the DB."""
    _check_agent(requested_by)
    if kind not in ("invoice", "rent"):
        return {"ok": False, "message": "kind must be 'invoice' or 'rent' (purchase orders use create_purchase_order)."}
    with connect() as conn:
        if kind == "invoice":
            inv = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ref_id,))
            if inv is None:
                return {"ok": False, "message": "No invoice with that id."}
            if inv["status"] != "open":
                return {"ok": False, "message": f"Invoice {ref_id} is already {inv['status']}."}
            vendor = _row(conn, "SELECT name FROM vendors WHERE id = ?", (inv["vendor_id"],))
            return _request_approval(conn, ticket_id, "invoice", ref_id, vendor["name"], inv["amount"], reason, requested_by)
        lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ref_id,))
        if lease is None:
            return {"ok": False, "message": "No lease with that id."}
        return _request_approval(
            conn, ticket_id, "rent", ref_id, lease["landlord"], lease["monthly_rent"],
            f"{reason} (rent due {lease['next_due']})", requested_by,
        )


def create_purchase_order(ticket_id: int, vendor_id: int, sku: str, size: str, qty: int, created_by: str) -> dict:
    """Draft a restock PO at pricing.unit_cost and queue its payment for human approval."""
    _check_agent(created_by)
    if qty <= 0:
        return {"ok": False, "message": "qty must be > 0."}
    with connect() as conn:
        vendor = _row(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if vendor is None:
            return {"ok": False, "message": "No vendor with that id."}
        if _row(conn, "SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)) is None:
            return {"ok": False, "message": "No inventory row for that SKU/size."}
        price = _row(conn, "SELECT unit_cost FROM pricing WHERE sku = ?", (sku,))
        if price is None:
            return {"ok": False, "message": "No pricing row for that SKU."}
        blockers = _open_invoices(conn, vendor_id)
        uncovered = [
            i["id"] for i in blockers
            if not _row(conn, "SELECT 1 FROM approvals WHERE kind = 'invoice' AND ref_id = ? AND status = 'pending'", (i["id"],))
        ]
        if uncovered:
            return {
                "ok": False,
                "refused": True,
                "message": f"Refused: {vendor['name']} will not ship while invoice(s) {uncovered} are unpaid. "
                "Prepare that invoice payment first.",
            }
        total = round(price["unit_cost"] * qty, 2)
        eta = (_today(conn) + timedelta(days=vendor["lead_days"])).isoformat()
        cur = conn.execute(
            "INSERT INTO purchase_orders (ticket_id, vendor_id, sku, size, qty, unit_cost, total, eta, status, created_by, created_at) "
            "VALUES (?,?,?,?,?,?,?,?, 'awaiting_approval', ?, ?)",
            (ticket_id, vendor_id, sku, size, qty, price["unit_cost"], total, eta, created_by, _now()),
        )
        po_id = cur.lastrowid
        approval = _request_approval(
            conn, ticket_id, "purchase_order", po_id, vendor["name"], total,
            f"Restock {qty} x {sku} {size} from {vendor['name']}, ETA {eta}", created_by,
        )
        if not approval.get("ok"):
            conn.execute("UPDATE purchase_orders SET status = 'cancelled' WHERE id = ?", (po_id,))
            return {**approval, "purchase_order_id": po_id, "po_status": "cancelled", "total": total}
    note = f" Ships only after invoice(s) {[i['id'] for i in blockers]} are paid." if blockers else ""
    return {
        **approval,
        "purchase_order_id": po_id,
        "vendor": vendor["name"],
        "qty": qty,
        "unit_cost": price["unit_cost"],
        "total": total,
        "eta_if_approved_today": eta,
        "message": approval["message"] + note,
    }


def draft_customer_message(ticket_id: int, to_name: str, subject: str, body: str, created_by: str) -> dict:
    _check_agent(created_by)
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, to_name, subject, body, created_by, created_at) VALUES (?,?,?,?,?,?)",
            (ticket_id, to_name, subject, body, created_by, _now()),
        )
    return {"ok": True, "draft_id": cur.lastrowid, "message": "Draft saved to the board. Nothing was sent."}


def log_ticket_update(ticket_id: int, agent: str, summary: str) -> dict:
    _check_agent(agent)
    with connect() as conn:
        conn.execute(
            "INSERT INTO ticket_updates (ticket_id, agent, status, summary, created_at) VALUES (?,?, 'note', ?, ?)",
            (ticket_id, agent, summary, _now()),
        )
    return {"ok": True}


def resolve_ticket(ticket_id: int, outcome: str, agent: str = "boss") -> dict:
    """Boss closes a ticket. If payments still need a human, it waits as awaiting_approval."""
    if agent != "boss":
        return {"ok": False, "message": "Only the Boss can resolve a ticket."}
    with connect() as conn:
        if _row(conn, "SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)) is None:
            return {"ok": False, "message": "No ticket with that id."}
        pending = _rows(conn, "SELECT id, kind, amount, payee FROM approvals WHERE ticket_id = ? AND status = 'pending'", (ticket_id,))
        status = "awaiting_approval" if pending else "resolved"
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.execute(
            "INSERT INTO ticket_updates (ticket_id, agent, status, summary, created_at) VALUES (?, 'boss', ?, ?, ?)",
            (ticket_id, status, outcome, _now()),
        )
    msg = "Resolved." if not pending else f"Waiting on human approval of {len(pending)} payment(s); resolves once approved."
    return {"ok": True, "ticket_id": ticket_id, "status": status, "pending_approvals": pending, "message": msg}


# ── Human-only (FastAPI routes; never exposed over MCP) ──────────────────────


def _maybe_close_ticket(conn: sqlite3.Connection, ticket_id: int) -> str:
    status = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()[0]
    left = conn.execute("SELECT COUNT(*) FROM approvals WHERE ticket_id = ? AND status = 'pending'", (ticket_id,)).fetchone()[0]
    if status == "awaiting_approval" and left == 0:
        conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
        conn.execute(
            "INSERT INTO ticket_updates (ticket_id, agent, status, summary, created_at) VALUES (?, 'human', 'resolved', ?, ?)",
            (ticket_id, "All payments on this ticket were decided by a human.", _now()),
        )
        return "resolved"
    return status


def approve_request(approval_id: int, approved_by: str) -> dict:
    """The only code path that moves cash. Refuses rather than go negative."""
    with connect() as conn:
        a = _row(conn, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if a is None:
            return {"ok": False, "message": "No approval with that id."}
        if a["status"] != "pending":
            return {"ok": False, "message": f"Approval #{approval_id} is already {a['status']}."}
        today = _today(conn).isoformat()
        if a["kind"] == "purchase_order":
            po = _row(conn, "SELECT * FROM purchase_orders WHERE id = ?", (a["ref_id"],))
            blockers = _open_invoices(conn, po["vendor_id"])
            if blockers:
                return {
                    "ok": False,
                    "message": f"Approve invoice(s) {[i['id'] for i in blockers]} first. The vendor won't ship while they're unpaid.",
                }
        balance = _balance(conn)
        if a["amount"] > balance:
            conn.execute(
                "UPDATE approvals SET status = 'refused', decided_at = ?, decided_by = ?, result = ? WHERE id = ?",
                (_now(), approved_by, f"Refused: balance ${balance:,.2f} < ${a['amount']:,.2f}", approval_id),
            )
            return {"ok": False, "message": f"Refused: checking has ${balance:,.2f}, payment is ${a['amount']:,.2f}. No negative balances."}

        new_balance = round(balance - a["amount"], 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = 'checking'", (new_balance, today))
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?, 'checking', ?, ?)",
            (a["kind"], a["ref_id"], a["amount"], today, approved_by),
        )
        if a["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (a["ref_id"],))
            effect = f"Invoice {a['ref_id']} marked paid."
        elif a["kind"] == "rent":
            lease = _row(conn, "SELECT next_due FROM leases WHERE id = ?", (a["ref_id"],))
            nxt = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (nxt, a["ref_id"]))
            effect = f"Lease {a['ref_id']} next_due moved {lease['next_due']} -> {nxt}."
        else:
            po = _row(conn, "SELECT * FROM purchase_orders WHERE id = ?", (a["ref_id"],))
            vendor = _row(conn, "SELECT lead_days FROM vendors WHERE id = ?", (po["vendor_id"],))
            eta = (_today(conn) + timedelta(days=vendor["lead_days"])).isoformat()
            conn.execute("UPDATE purchase_orders SET status = 'ordered', eta = ? WHERE id = ?", (eta, a["ref_id"]))
            effect = f"PO {a['ref_id']} ordered, ETA {eta}."
        conn.execute(
            "UPDATE approvals SET status = 'approved', decided_at = ?, decided_by = ?, result = ? WHERE id = ?",
            (_now(), approved_by, effect, approval_id),
        )
        ticket_status = _maybe_close_ticket(conn, a["ticket_id"])
    return {
        "ok": True,
        "approval_id": approval_id,
        "payment_id": cur.lastrowid,
        "amount": a["amount"],
        "balance_before": balance,
        "balance_after": new_balance,
        "effect": effect,
        "ticket_id": a["ticket_id"],
        "ticket_status": ticket_status,
    }


def reject_request(approval_id: int, rejected_by: str) -> dict:
    with connect() as conn:
        a = _row(conn, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if a is None or a["status"] != "pending":
            return {"ok": False, "message": "No pending approval with that id."}
        conn.execute(
            "UPDATE approvals SET status = 'rejected', decided_at = ?, decided_by = ?, result = 'Rejected by human' WHERE id = ?",
            (_now(), rejected_by, approval_id),
        )
        if a["kind"] == "purchase_order":
            conn.execute("UPDATE purchase_orders SET status = 'cancelled' WHERE id = ?", (a["ref_id"],))
        ticket_status = _maybe_close_ticket(conn, a["ticket_id"])
    return {"ok": True, "approval_id": approval_id, "ticket_status": ticket_status}


def reset_database() -> dict:
    """Copy the untouched original over the working copy."""
    shutil.copyfile(ORIGINAL_DB, DB_PATH)
    return {"ok": True, "message": f"{DB_PATH.name} reset from {ORIGINAL_DB.name}.", **get_cash_balance()}
