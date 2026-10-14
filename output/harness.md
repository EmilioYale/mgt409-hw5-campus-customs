# Campus Customs Harness

This is the map the agent team works from: the shop's tables, the MCP tools that read and write them, the five agents, the API routes, the dashboard and the safety rules.

- Original database (never edited): `data/campus_customs.db`
- Working copy (every tool and route points here): `data/campus_customs_new.db`

## 1. Tables

### `desk` — the shop's clock
| field | type | notes |
|---|---|---|
| `date_today` | TEXT | "today" for the shop: **2026-08-31** |
| `notes` | TEXT | free-text desk note (empty) |

**Why agents care:** every "overdue" and "due soon" call is made against `date_today`, not the real calendar.

### `tickets` — the board
| field | type | notes |
|---|---|---|
| `id` | INTEGER PK | 101, 102, 103 |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override` |
| `requester` | TEXT | who opened it |
| `subject` | TEXT | short title |
| `sku`, `size`, `qty` | TEXT, TEXT, INTEGER | the product asked for (order tickets only) |
| `lease_id` | INTEGER → `leases.id` | set on the rent ticket |
| `invoice_id` | INTEGER → `invoices.id` | set on the tee order |
| `status` | TEXT | `open` / `resolved` |
| `notes` | TEXT | the request in the requester's words |
| `created_at` | TEXT | ISO timestamp |

**Why agents care:** this is the work queue. The Boss reads a ticket and its foreign keys tell it which specialist to call.

### `inventory` — what is on the shelf
| field | type | notes |
|---|---|---|
| `sku` | TEXT (PK with size) | e.g. `CC-TEE-WHITE` |
| `name` | TEXT | e.g. Classic Bulldog Tee |
| `size` | TEXT (PK with sku) | S/M/L/XL, or OS for one-size |
| `qty` | INTEGER | units on hand |
| `location` | TEXT | aisle |

**Why agents care:** Inventory checks this before anything is promised to a customer and to size any restock shortfall.

### `pricing` — cost vs. price per SKU
| field | type | notes |
|---|---|---|
| `sku` | TEXT PK | |
| `unit_cost` | REAL | what the shop pays the vendor |
| `list_price` | REAL | normal selling price |

**Why agents care:** Accounting uses it to cost a restock and to test whether a discount still leaves a margin.

### `vendors` — who can restock
| field | type | notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT | Bulldog Print Co, Elm City Gifts, QuickShip CT |
| `specialty` | TEXT | apparel reprint / mugs and small goods / local courier |
| `lead_days` | INTEGER | days from order to delivery (5 / 3 / 1) |

**Why agents care:** Inventory picks the vendor whose specialty fits the SKU, and `lead_days` sets the delivery date it can promise.

### `invoices` — bills the shop owes vendors
| field | type | notes |
|---|---|---|
| `id` | INTEGER PK | 501 |
| `vendor_id` | INTEGER → `vendors.id` | |
| `amount` | REAL | |
| `due_date` | TEXT | |
| `status` | TEXT | `open` / `paid` |
| `description` | TEXT | |

**Why agents care:** a vendor with an open invoice will not ship, so Accounting has to clear it before any restock order is placed.

### `leases` — the shop space
| field | type | notes |
|---|---|---|
| `id` | INTEGER PK | 1 |
| `space_name` | TEXT | Chapel Street shop |
| `landlord` | TEXT | Elm City Properties |
| `monthly_rent` | REAL | 2400.00 |
| `next_due` | TEXT | 2026-09-02 |
| `notes` | TEXT | |

**Why agents care:** Facilities confirms the rent amount and due date before Accounting prepares the payment.

### `cash_accounts` — money available
| field | type | notes |
|---|---|---|
| `name` | TEXT PK | `checking` |
| `balance` | REAL | 3400.00 at the start |
| `date` | TEXT | as-of date |

**Why agents care:** every payment is checked against this balance, and the balance can never go negative.

### `payments` — money that has gone out
| field | type | notes |
|---|---|---|
| `id` | INTEGER PK | |
| `kind` | TEXT | e.g. `invoice`, `rent`, `purchase_order` |
| `ref_id` | INTEGER | the invoice / lease / purchase-order id |
| `amount` | REAL | |
| `account` | TEXT | `checking` |
| `paid_at` | TEXT | |
| `approved_by` | TEXT | the human who approved it |

**Why agents care:** it is the audit record of cash leaving the shop (empty at the start), written only after a human approves.

## 2. How the three open tickets link to the tables

| ticket | what it asks | links | what the data says |
|---|---|---|---|
| **101** customer_order (Tauhid Zaman) | 1 Classic Bulldog Tee, size S | `sku/size` → `inventory`, `pricing`; `invoice_id 501` → `invoices` → `vendor_id 1` → `vendors` | Tee S has **0** on hand. Restock comes from Bulldog Print Co (apparel reprint, 5-day lead), which has invoice 501 for **$840**, still **open** and due 2026-08-28, so 3 days overdue on 2026-08-31. Bulldog won't ship until 501 is paid. Unit cost $8, list $28. |
| **102** rent_notice (Elm City Properties) | rent due in 2 days | `lease_id 1` → `leases`; pays from `cash_accounts` into `payments` | Chapel Street shop, **$2,400** due **2026-09-02**. Checking has $3,400. |
| **103** price_override (Yale AI Club) | 20 hoodies, size M, bulk discount | `sku/size` → `inventory`, `pricing`; restock → `vendors` (Bulldog again) | Hoodie M has **8** on hand, so **12 short**. Unit cost $22, list $58. Restock goes through Bulldog, which is blocked by invoice 501. |

Because the tickets share data, the cash has to cover all three: $3,400 − $840 (invoice) − $2,400 (rent) leaves **$160** for any restock purchases. Twelve hoodies at $22 would cost $264, more than that.

## 3. MCP tools (Problem 3 starter set)

Server: `mcp_server/server.py` (FastMCP, stdio), reading `data/campus_customs_new.db`.

| tool | table it reads | ticket it unlocks | why it's the right tool for that ticket |
|---|---|---|---|
| `check_stock(sku, size?)` | `inventory` | **101** | Tauhid wants one CC-TEE-WHITE in size S. This tool shows the shelf has 0, so 101 can't be filled from stock and needs a restock. |
| `get_lease(lease_id)` | `leases` | **102** | The rent email only says "due in 2 days." `get_lease(1)` gives the exact amount ($2,400), landlord and due date (2026-09-02) needed before any payment is prepared. |
| `get_pricing(sku)` | `pricing` | **103** | The AI Club wants a bulk discount on CC-HOOD-NAVY. The $22 unit cost against the $58 list price is the floor any discount has to stay above. |

## 4. MCP tools (full set after Problem 5)

All tools live in `mcp_server/server.py` (logic in `mcp_server/shop_db.py`). The `created_by` / `requested_by` / `agent` arguments are overwritten with the real calling agent by the backend (`_stamp_agent` in `backend/team.py`), so an agent can't act under another agent's name.

| tool | table(s) used | read / write | used by |
|---|---|---|---|
| `get_desk_today` | `desk` | read | all |
| `list_tickets` | `tickets` | read | boss |
| `get_ticket` | `tickets`, `ticket_updates` | read | all |
| `get_ticket_work` | `quotes`, `purchase_orders`, `reservations`, `drafts`, `approvals`, `ticket_updates` | read | all |
| `check_stock` | `inventory` | read | inventory, customer_service |
| `get_pricing` | `pricing` | read | inventory, accounting, customer_service |
| `list_vendors` | `vendors`, `invoices` | read | inventory |
| `get_vendor_invoices` | `invoices`, `vendors`, `desk` | read | inventory, accounting |
| `get_invoice` | `invoices`, `vendors`, `desk` | read | accounting |
| `get_lease` | `leases`, `desk` | read | facilities |
| `get_cash_balance` | `cash_accounts`, `approvals` | read | boss, accounting, facilities |
| `list_payments` | `payments` | read | accounting |
| `list_approvals` | `approvals` | read | boss, accounting |
| `quote_bulk_discount` | `pricing` | read (what-if) | accounting |
| `record_quote` | `pricing` → `quotes` | write | accounting |
| `reserve_stock` | `inventory` → `reservations` | write (stock) | inventory |
| `request_payment` | `invoices` / `leases`, `cash_accounts` → `approvals` | write (prepare only) | accounting |
| `create_purchase_order` | `vendors`, `pricing`, `inventory`, `invoices`, `cash_accounts` → `purchase_orders`, `approvals` | write (prepare only) | accounting |
| `draft_customer_message` | `drafts` | write (draft only) | customer_service |
| `log_ticket_update` | `ticket_updates` | write | all |
| `resolve_ticket` | `tickets`, `approvals` → `ticket_updates` | write | boss only |

The workflow tables (`approvals`, `purchase_orders`, `quotes`, `reservations`, `drafts`, `ticket_updates`) are created on first use in the working copy only. The original DB keeps its schema.

**Not an MCP tool (human only):** `approve_request` / `reject_request` / `reset_database` in `shop_db.py`. These are called only by the FastAPI approve/reject/reset routes. This is the only code that moves cash: it re-checks the balance (refusing rather than going negative), writes `payments`, lowers `cash_accounts.balance`, and marks the invoice paid, moves `leases.next_due` forward a month, or sets the PO to ordered.

## 5. The five agents

PydanticAI agents in `backend/team.py`, prompts in `backend/prompts/<agent>.md`, model **gpt-6-luna via Portkey** for every agent (`backend/config.py`). Every agent has a `delegate(to_agent, task)` tool, so any agent can hand work to any other (**full connectivity**). Delegations nest: a specialist can delegate again.

| agent | job | MCP tools it can see |
|---|---|---|
| **Boss** | reads each ticket, decides who works it and in what order, makes the final call, resolves it | `get_desk_today`, `get_ticket`, `get_ticket_work`, `log_ticket_update`, `list_tickets`, `get_cash_balance`, `list_approvals`, `resolve_ticket` |
| **Inventory** | stock by SKU/size, shortfalls, which vendor restocks and when, blocking invoices | common + `check_stock`, `get_pricing`, `list_vendors`, `get_vendor_invoices`, `reserve_stock` |
| **Accounting** | cash, invoices, margins, discount quotes; prepares payments and POs for human approval | common + `get_cash_balance`, `get_invoice`, `get_vendor_invoices`, `get_pricing`, `quote_bulk_discount`, `record_quote`, `request_payment`, `create_purchase_order`, `list_payments`, `list_approvals` |
| **Facilities** | leases, rent amount and due date, landlord | common + `get_lease`, `get_cash_balance` |
| **Customer Service** | drafts customer messages (never sent) | common + `check_stock`, `get_pricing`, `draft_customer_message` |

("common" = `get_desk_today`, `get_ticket`, `get_ticket_work`, `log_ticket_update`.)

**Audit trail:** every agent-loop step (user prompt, model response with token usage, each tool call with args, each tool result, delegations, agent done, run start/end) is appended to `output/audit_trail.json`. The file is read, appended to and rewritten, never wiped. An unreadable file is set aside rather than overwritten.

## 6. Safety

### Guardrails for real money and real customers
1. **Humans approve every payment.** Agents can only *prepare* (`request_payment`, `create_purchase_order`), which writes a pending row in `approvals`. Cash moves only when a person clicks Approve on the board, and that code isn't reachable over MCP.
2. **Amounts come from the database, not the model.** Invoice, rent and PO amounts are looked up from `invoices`, `leases` and `pricing` × qty. An agent can't type in a dollar figure.
3. **No negative balances, checked twice.** At prepare time against balance minus everything already pending, and again at approval time against the live balance. Both refuse rather than overdraw.
4. **Vendor-invoice rule enforced in code.** A PO to a vendor with an unpaid invoice is refused unless that invoice is already queued, and the PO can't be approved until the invoice is actually paid.
5. **No duplicate payments.** A second request for the same invoice/lease/PO returns the existing approval.
6. **Least privilege.** Each agent sees only the MCP tools for its role, only the Boss can resolve tickets, and identity arguments are stamped by the backend.
7. **Nothing leaves the building.** Customer messages are saved as drafts. There are no email or vendor-contact tools at all.
8. **Discount floor.** `record_quote` refuses any price below unit cost. The Boss makes the final discount call.
9. **Full audit + reset.** Every step is in `audit_trail.json`, every payment row records `approved_by`, and the original DB is never touched, so a bad run can be reset.
10. **What a real business would add:** spending limits per approver, two-person approval above a threshold, approver login, PII redaction in logs, and alerts on refusals.

### Token limits
- One model only: `gpt-6-luna` (hard-coded, no override).
- Per agent loop: at most **12 model requests** and **80k tokens** (`UsageLimits`).
- Per ticket: at most **10 delegations**, delegation depth **3**, and a **300k-token** budget. Once a limit is hit, `delegate` refuses and the agent has to finish with what it has.
- No self-delegation, and a ticket can't be started twice at once.
- Tool results are clipped before they go in the feed and audit log.

## 7. API routes (`backend/main.py`, http://localhost:8000)

Start from `backend/` with `uvicorn main:app --reload --port 8000`.

- `GET /api/health`: model name (gpt-6-luna), the five agents, which DB file is live.
- `GET /api/tickets`: the three tickets with status (`open` / `awaiting_approval` / `resolved`), `is_resolved`, whether the team is running on it, and its pending-approval count.
- `POST /api/tickets/{id}/run`: start the agent team (Boss first) on one ticket in the background. 409 if it's already running.
- `GET /api/events?since={seq}&ticket_id={id}`: recent agent events (prompts, what each agent said, every tool call with args and result, delegations) for the live feed.
- `GET /api/tickets/{id}/summary`: per-agent summary of the latest run (tools used, delegated to/by, final report, tokens) plus the quotes, POs, reservations, drafts and approvals on the ticket.
- `GET /api/approvals?status=pending&ticket_id={id}`: payment / purchase requests the agents prepared.
- `POST /api/approvals/{id}/approve` `{approved_by}`: a human approves a prepared payment or PO. **The only route that moves cash.** Refuses on insufficient funds or an unpaid vendor invoice.
- `POST /api/approvals/{id}/reject` `{approved_by}`: a human rejects a prepared payment (cancels a PO).
- `GET /api/cash`: checking balance from `cash_accounts`, pending total, and the `payments` rows.
- `POST /api/reset`: copy `campus_customs.db` over `campus_customs_new.db` for a clean run (keeps `audit_trail.json`).

## 8. Dashboard (`frontend/`, http://localhost:5173)

React + Vite + TypeScript. `npm run dev` from `frontend/`. Talks to `http://localhost:8000` (`src/api.ts`, `VITE_API_BASE`), and the backend allows the Vite origin through CORS. It polls `/api/events` every second and tickets/cash/approvals every two seconds. Full design notes are in `output/design.md`.

| part | route(s) it uses | shows |
|---|---|---|
| The board (cork + index cards) | `GET /api/tickets`, `POST /api/tickets/{id}/run` | three tickets, status stamp (open / NEEDS YOUR OK / RESOLVED), **Send in the team** |
| In-tray | `GET /api/approvals`, `POST /api/approvals/{id}/approve` / `reject` | payment slips the agents prepared, with Approve / Reject and the approver's name |
| Cash register | `GET /api/cash` | live checking balance, pending total, red "−$x" flash when an approval drops cash |
| Team map | `GET /api/events` | five agents fully wired, live hand-off arrows, the tool each agent is calling right now |
| Desk chatter | `GET /api/events` | every message, tool call (args + collapsible result) and delegation |
| Shift report | `GET /api/tickets/{id}/summary` | Boss's call, a card per agent (tools, hand-offs, tokens, report), quotes/POs, draft letters |
| Reset DB | `POST /api/reset` | clean start before a full run |

## 9. Full three-ticket run (Problem 9)

Reset first, then run 101 → 102 → 103 from the board, approving payments in the in-tray as a human.

| ticket | agents (in order) | human approvals | cash | final status |
|---|---|---|---|---|
| 101 Bulldog tee | Boss → Inventory, Boss → Accounting, Boss → Customer Service | #1 invoice 501 $840, #2 PO #1 $8 | $3,400 → $2,552 | resolved |
| 102 Rent due | Boss → Facilities → Accounting (direct), Boss → Accounting (duplicate refused) | #3 rent $2,400 | $2,552 → $152 | resolved |
| 103 Bulk hoodies | Boss → Inventory, Boss → Accounting, Boss → Customer Service | none ($264 restock unaffordable) | $152 → $152 | resolved |

- Ending `cash_accounts.checking` = **$152.00** = $3,400 − $840 − $8 − $2,400. `payments` has 3 rows, all `approved_by = Emilio Gonzalez` (I clicked Approve in the in-tray).
- Tokens: 101 = 42,529 · 102 = 30,007 · 103 = 34,027 (106,563 total). Every model call was `gpt-6-luna`.
- `output/audit_trail.json` (append-only, 515 step records) holds the graded run (run ids `61f0225d52`, `580269d7d8`, `4175313094`) plus an earlier practice run of the same three tickets (`8d3b4ff68d`, `fb3e0d55c2`, `4a465c151c`) that ended the same way. Human approvals are recorded in the `approvals` table (`decided_by`, `decided_at`, `result`) and in `payments.approved_by`.
- Details: `output/desk_tickets.html` (Expected vs Actual, Cash tab), `output/resolved_tickets.json`, `output/resolved_board.html`.
