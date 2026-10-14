# Campus Customs MCP server

A [FastMCP](https://gofastmcp.com) server that gives the Campus Customs agent team its shop facts. Every agent reads the shop through these tools, and the tools only return what is actually in the database.

**Database:** `data/campus_customs_new.db`, the working copy. The original `data/campus_customs.db` is never touched. Set `CAMPUS_CUSTOMS_DB` to point somewhere else.

**Files:** `server.py` (the MCP tools) and `shop_db.py` (the SQLite logic behind them).

**Run (stdio):**

```bash
.venv/bin/python mcp_server/server.py
```

Claude Code picks it up from `.mcp.json` at the project root. The FastAPI backend starts its own stdio connection to it for the agents.

## Tools

| tool | table(s) | what it does |
|---|---|---|
| `get_desk_today()` | `desk` | the shop's "today" |
| `list_tickets(status?)` | `tickets` | the board |
| `get_ticket(ticket_id)` | `tickets`, `ticket_updates` | one ticket + logged updates |
| `get_ticket_work(ticket_id)` | workflow tables | quotes, POs, reservations, drafts, approvals for a ticket |
| `check_stock(sku, size?)` | `inventory` | units on hand and aisle |
| `get_pricing(sku)` | `pricing` | unit cost, list price, margin at list |
| `list_vendors()` | `vendors`, `invoices` | specialty, lead_days, blocked-by-invoice flag |
| `get_vendor_invoices(vendor_id)` | `invoices`, `vendors`, `desk` | invoices with days overdue, can-ship flag |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | one invoice with days overdue |
| `get_lease(lease_id)` | `leases`, `desk` | rent, landlord, next due, days until due |
| `get_cash_balance()` | `cash_accounts`, `approvals` | balance, pending total, available |
| `list_payments()` | `payments` | money already paid |
| `list_approvals(ticket_id?, status?)` | `approvals` | payment requests and their decisions |
| `quote_bulk_discount(sku, qty, discount_pct)` | `pricing` | what-if discount price and margin (saves nothing) |
| `record_quote(...)` | `quotes` | save a quote, refuses below cost |
| `reserve_stock(...)` | `inventory`, `reservations` | hold units for a ticket |
| `request_payment(ticket_id, kind, ref_id, ...)` | `invoices`/`leases` → `approvals` | prepare an invoice or rent payment for **human approval** |
| `create_purchase_order(...)` | `vendors`, `pricing`, `invoices` → `purchase_orders`, `approvals` | prepare a restock PO for **human approval** |
| `draft_customer_message(...)` | `drafts` | save a draft (never sent) |
| `log_ticket_update(...)` | `ticket_updates` | progress note |
| `resolve_ticket(ticket_id, outcome)` | `tickets` | Boss only, waits as `awaiting_approval` if payments are pending |

No tool moves cash. Approving a payment (`shop_db.approve_request`) is only reachable from the backend's human approve route.
