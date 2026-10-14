"""Paths, Portkey model and guardrail limits for the Campus Customs backend.

Every agent uses gpt-6-luna through Portkey. There is deliberately no way to
pick another model: the assignment allows luna only.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
PROMPTS = BACKEND / "prompts"
OUTPUT = ROOT / "output"
AUDIT_PATH = Path(os.getenv("CAMPUS_CUSTOMS_AUDIT") or OUTPUT / "audit_trail.json")
MCP_SERVER = ROOT / "mcp_server" / "server.py"

# .env in the project, or any folder above it (nearest wins).
for folder in [ROOT, *ROOT.parents]:
    if (folder / ".env").exists():
        load_dotenv(folder / ".env", override=False)

MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")

# Token guardrails (per ticket run).
MAX_DELEGATION_DEPTH = 3          # boss -> specialist -> specialist -> specialist
MAX_DELEGATIONS_PER_TICKET = 10
MAX_REQUESTS_PER_AGENT_RUN = 12   # model round-trips in one agent loop
MAX_TOKENS_PER_AGENT_RUN = 80_000
MAX_TOKENS_PER_TICKET = 300_000


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Put it in .env at the project root (see .env.example).")
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )
    # gpt-6-luna needs the Responses API for function tools.
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
