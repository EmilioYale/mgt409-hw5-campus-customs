# HW 5: Campus Customs Multi-Agent Operations

MGT 409 · Emilio Gonzalez

A five-agent team (Boss, Inventory, Accounting, Facilities, Customer Service) that works the Campus Customs ticket board. It has three pieces:

- **MCP server** (`mcp_server/`, FastMCP): every shop fact and action the agents use, over `data/campus_customs_new.db`.
- **FastAPI backend** (`backend/`): the PydanticAI agent team (gpt-6-luna via Portkey, full delegation between agents), the event feed, and the human approve route.
- **React dashboard** (`frontend/`, Vite + TypeScript): the "Chapel Street Desk", where you start the team, watch them work, approve payments and watch cash drop.

Agents only *prepare* payments. Cash moves only when a human clicks **Approve** on the board.

## Setup (once)

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then put your PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

The backend also finds a `.env` in any parent folder, so a class-wide `.env` works too.

## 1. Copy the original DB to the working copy (clean run)

`data/campus_customs.db` is the original and is never edited. Everything runs against the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

## 2. Start the MCP server

```bash
.venv/bin/python mcp_server/server.py
```

It speaks MCP over stdio, so on its own it just waits for a client.
- **Claude Code** starts it from `.mcp.json` at the project root (server name `campus-customs`).
- **The backend** starts its own stdio connection to `mcp_server/server.py` when uvicorn boots. You don't need to run it separately for the app.

## 3. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

The API is at http://localhost:8000. See `output/harness.md` §7 for every route.

## 4. Start the React board

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. It talks to `http://localhost:8000` (change it with `VITE_API_BASE` in `frontend/.env`).

## 5. Reset the DB before a full three-ticket run

Click **Reset DB** on the board, or:

```bash
curl -X POST http://localhost:8000/api/reset
```

Either way, `campus_customs.db` is copied over `campus_customs_new.db`, putting checking back at $3,400 and all tickets back to open. `output/audit_trail.json` is kept, since it's append-only. Then on the board, run **101 → 102 → 103** with **Send in the team**, and approve each payment slip in the in-tray.

## Layout

```
hw5/
├── AI_prompts.md            every prompt I gave my vibe coder, per problem
├── requirements.txt  .env.example  .gitignore  .mcp.json  README.md
├── data/                    campus_customs.db (original) + campus_customs_new.db (working copy, after the graded run)
├── mcp_server/              server.py (MCP tools) + shop_db.py (SQLite logic) + README.md
├── backend/                 main.py (routes), team.py (agents), models.py, events.py, config.py, prompts/*.md
├── frontend/                React + Vite + TypeScript dashboard
└── output/                  harness.md, mcp_smoke.json, desk_tickets.html, design.md,
                             resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt
```

## Results of the graded run

| ticket | outcome | cash |
|---|---|---|
| 101 Bulldog tee | paid overdue invoice 501, ordered 1 tee (ETA 2026-09-05), drafted a reply | −$848 |
| 102 Rent due | rent for lease 1 paid before 2026-09-02 | −$2,400 |
| 103 Bulk hoodies | 8 of 20 in stock, $264 restock not affordable, offered the 8 | $0 |

Checking: **$3,400.00 → $152.00**, which matches `cash_accounts` in `data/campus_customs_new.db`.
