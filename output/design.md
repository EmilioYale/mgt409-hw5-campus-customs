# Campus Customs: Chapel Street Desk (dashboard design)

React + Vite + TypeScript in `frontend/`. It talks to the FastAPI backend at `http://localhost:8000` (set in `frontend/src/api.ts`, overridable with `VITE_API_BASE`). Start it with `npm run dev`, which opens on http://localhost:5173. The backend allows that origin through CORS.

## The idea

The shop is a little merch store on Chapel Street, so the board should feel like the **actual desk in the back room**, not a generic admin panel: a walnut desktop, a cork board with index cards pinned to it, an in-tray of payment slips, a cash register, and a shift report. Every physical object maps to one thing a manager needs to see. Nothing is decoration only.

## Layout (three columns, left to right = the flow of work)

| column | what's there | why |
|---|---|---|
| **Left: "The board" + "In-tray"** | One pinned index card per ticket (101, 102, 103) with requester, the request in handwriting, SKU/size/qty or lease, and a **Send in the team** button. Under it, the in-tray of payment slips waiting on a human. | This is where a person *acts*: start a ticket, approve or reject a payment. Both actions live in one column so you never hunt for them. |
| **Center: "The team" + "Desk chatter"** | A map of the five agents wired together, then the live feed of everything they say and do. | This is what you *watch* while a ticket runs. |
| **Right: "Shift report"** | The Boss's final call, one card per agent that worked the ticket, the paperwork they left (quotes, POs, held stock), and any customer draft. | This is what you *read* afterwards. It answers "who did what?" without scrolling the feed. |

The top bar has the brand, the shop date (`desk.date_today`, not the real date), a "gpt-6-luna via Portkey" chip, a backend-live indicator, **Reset DB**, and the cash register.

## How the agents look different

- **Each agent has its own color everywhere it shows up**: Boss = Yale blue, Inventory = green, Accounting = mustard/ledger gold, Facilities = purple, Customer Service = burnt orange. The color is the same on the map node, the feed pill, the shift-report card border and the draft-letter header, so you learn it once.
- **The team map** puts the five agents in a pentagon with the Boss on top, and draws a faint dashed wire between *every* pair. That's the full-connectivity rule made visible.
  - When an agent delegates, that wire turns **solid blue**. While the hand-off is in flight it becomes a **thick animated gold arrow** flowing from caller to callee.
  - Each node shows a live status under its name: `idle` (faded), `thinking…` (pulsing gold halo), the **name of the MCP tool it's calling right now** (e.g. `get_vendor_invoices`), `waiting on accounting`, or `reported back`.
  - Agents the Boss never called stay faded. You can see at a glance that ticket 102 didn't wake up Inventory or Customer Service, which was a grading point in the plan.
- **The feed** gives each kind of event its own look. Speech is a chat bubble. Tool calls are a monospace `tool_name` chip with its arguments. Tool results are collapsible, so the raw JSON is there if you want it but doesn't flood the screen. Hand-offs are a gold-edged card quoting the exact task that was delegated, and hand-backs are a green-edged line.

## How resolved tickets show up

- Index cards get a colored top edge: red = open, gold = waiting on approval, green = resolved.
- When the Boss closes a ticket but payments are still pending, the card gets a gold **NEEDS YOUR OK · n** stamp.
- When the last payment is approved, the card gets a green **RESOLVED** rubber stamp that *thunks* onto the card (scale-down + rotate animation).
- The shift report's status tag switches to "resolved", and the Boss's call box shows the final outcome text from `resolve_ticket`.

## How cash shows up

- The top-right **cash register** is a dark LCD with glowing green digits showing the live checking balance from `cash_accounts`.
- Under it: how much is waiting on approval and how much is "free" after that. That's the same number the agents check before preparing a payment, so the human sees what the agents see.
- When a payment is approved and the balance drops, a red **−$840.00** (or whatever the amount was) drops down out of the display and fades. You *feel* money leave the shop, which matters in a homework where cash only goes out.
- The in-tray slips show the amount in red, the payee, why it's needed, which ticket and which agent prepared it, plus **Approve / Reject** buttons and an "Approving as ___" name that's written to `payments.approved_by`. Decided slips collapse into a little log with APPROVED / REJECTED / REFUSED mini-stamps.

## Creative touches

- **Cork board and index cards**: slightly tilted cards, a red push-pin, ruled lines, and the customer's note in a handwriting font, like someone jotted the request at the counter.
- **Rubber stamps** for RESOLVED and NEEDS YOUR OK, because approving money should feel like a deliberate physical act.
- **Walnut desk background** with a faint wood grain, plus a navy + gold Yale top bar with a "CC" crest.
- **Customer drafts look like a letter**: a sheet with a red margin line, a serif font and a "DRAFT · not sent" header. That reinforces the rule that nothing gets emailed.
- **"Stayed at their desk"** line in the shift report lists the agents who were *not* needed. Picking the right specialists matters as much as doing the work.
- **Token counts per agent** on every shift-report card, so you can see which agent was expensive on which ticket.
- `?ticket=103` in the URL pre-selects a ticket. That's handy for screenshots and for sharing "look at this one" with a teammate.

## Why this works for a human

A manager can sit here, press one button, watch the hand-offs happen on the map, and step in only where the rules say a person must: approving money. Everything the agents prepared is on the desk to check before anything leaves the shop.
