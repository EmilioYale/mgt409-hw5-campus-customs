# AI Prompts — HW 5: Campus Customs Multi-Agent Operations

Every prompt I gave my vibe coder (Claude Code), one section per problem.

## Problem 1: Vibe coder prompts

**Prompt:**

> hey can you make an ai_prompts.md file at the root of the projct? im gonna log evry prompt i give you in there as we go thru the homework so keep it updated eachtime we finish a problem

**Follow-up prompt:**

> set up ai_prompts.md with one secton per problem (1 thru 11). each section needs the problem numbr and title, the main prompt i typed, and a spot for a folow up prompt with one sentance explaning what was mising the first time

## Problem 2: Study the Campus Customs database

**Prompt:**

> unzip data.zip and open data/campus_customs.db. walk me thru every tabel and colum (desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, invoices), then copy it to data/campus_customs_new.db. dont touch the orignal

**Follow-up prompt:**

> look at the three open tickts and show me how each one links to the other tables. then start output/harness.md with a secion per table listing its feilds and one short line on why the agents care abt it

## Problem 3: Build the MCP server

**Prompt:**

> build an mcp server in mcp_server/server.py using fastmcp that points to campus_customs_new.db. for now just three tools the tickets will clearly need, with clear names. they can only retrun whats actualy in the db, no made up values. dont run it yet

**Follow-up prompt:**

> add the three tools to harness.md, each with the table it reads, which ticket it unlcoks (101, 102 or 103), and one specfic sentance on why its the right tool for that ticket. also write a short mcp_server/readme.md on what the server dose, which db it uses, and the three tools

## Problem 4: Add the MCP server to your vibe coder and test each tool

**Prompt:**

> conect the mcp server to claude code and save the config in a .mcp.json at the projet root, making sure its pointng at the right python and server.py path. then test all three tools thru the mcp conection and save the resuts to output/mcp_smoke.json with the prompt i used, the tool name and the raw ouput for each one, and check the values agianst campus_customs_new.db so we know they match

**Follow-up prompt:** None needed.

## Problem 5: Build the agent team and grow the MCP tools

**Prompt:**

> build the five agents (boss, inventory, accounting, facilites, customer service) with pydanticai so any agent can hand work to any othr. put one prompt file per agent in backend/prompts/, data types in backend/models.py, agent code under backend/. only use gpt-6-luna thru portkey with portkey_api_key, no other modle anywhere. each prompt shoud be detailed and include the shop rules that agent needs, like payments needing human aproval, no negative balance, vendors not shiping with unpaid invoices, and desk.date_today counting as today

**Follow-up prompt:**

> add whatevr mcp tools the agents need to reslove the open tickets, and route every shop fact thru the mcp server, no side tools layer. have every agent loop step apend to output/audit_trail.json and never wipe it. update harness.md with every agent and tool plus the table each tool uses, add a saftey section on guardrails for real money and customers plus token limts, and update the mcp readme tool list

## Problem 6: Plan the three tickets

**Prompt:**

> make output/desk_tickets.html that opens with a doubel click, with one tab each for tickets 101, 102 and 103 plus cash and reflection tabs that just say comming later. each ticket tab gets an expected section and an empty actual secton for later. in the expected sections write who the boss shoud call first and why, every delegaton we expect between agents, and which mcp tools the run should use. dont send evry specialist to every ticket, only the ones that acutally make sense

**Follow-up prompt:** None needed.

## Problem 7: Backend routes

**Prompt:**

> in backend/main.py add fastapi routes to list the three tickets with open/resolved status, run the agent team on a ticket id, get recent agent events (what each agent said and which tools it caled), approve a payment or purchse after a human clicks approve, get the checkng balance from cash_accounts, and reset the db to the original. agents only prepare payments, the aprove route is the only thing that moves cash. start it from backend/ with uvicorn main:app --reload --port 8000, make sure evry route works at localhost:8000, and add each route to harness.md in one line with its url and what it dose

**Follow-up prompt:** None needed.

## Problem 8: Agent dashboard

**Prompt:**

> build a dashbaord in frontend/ with react, vite and typescript that uses the backend routes. it should list the tickets, let me pick one and start the team, show each agent and what its doing live, mark the ticket resolvd when done, show a short sumary per agent, have an approve button when a payment comes up, and show the checking balence dropping after approvals. make it look good and creatve, like a desk people would want to work at

**Follow-up prompt:**

> point the frontend at localhost:8000, add cors on the backend for localhost:5173, and make sure npm run dev starts it. then write output/design.md explainng the layout, how the agents look difrent, how resolved tickets and cash are shown, and the creative touchs

## Problem 9: Resolve the tickets

**Prompt:**

> reset campus_customs_new.db and write down the startng checking balance. then help me run tickets 101, 102 and 103 on the board untill theyre all resolved, and fill in each actual section in desk_tickets.html with which agents worked, what they delgated, and which tools they used. keep expected as is so we can compair

**Follow-up prompt:**

> fill the cash tab with the starting balance, how cash changd on each ticket and why (which payment and how much), and the ending balance, which has to match cash_accounts. save output/resolved_tickets.json with id, status, outcome, each agents contribuion and any approvals. make output/resolved_board.html with a screenshot of the board per ticket, make sure the runs are in audit_trail.json, and finsh harness.md

## Problem 11: Submit to GitHub

**Prompt:**

> get the repo ready to push by matching the expectd hw5 layout and adding requirements.txt, .env.example and a .gitignore that keeps my real .env out but includes both db files in data/. write the root readme.md explaning how to copy the original db to the working copy, start the mcp server, start the fastapi backend, start the react board, and reset the db before a full three ticket run. then push it to a public github repo and put the url in output/github_url.txt

**Follow-up prompt:** None needed.
