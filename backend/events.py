"""Event feed for the board and the append-only audit trail.

Every agent-loop step becomes one AgentEvent. It is kept in memory for
GET /api/events and appended to output/audit_trail.json (never wiped).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any

from config import AUDIT_PATH, MODEL_NAME
from models import AgentEvent

_lock = threading.Lock()
_events: list[AgentEvent] = []
_seq = 0


def clip(value: Any, limit: int = 1200) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + f"… (+{len(text) - limit} chars)"


def _append_audit(entry: dict) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows: list = []
    if AUDIT_PATH.exists():
        raw = AUDIT_PATH.read_text(encoding="utf-8").strip()
        if raw:
            try:
                rows = json.loads(raw)
            except json.JSONDecodeError:
                # Never lose history: park the unreadable file and start a new list.
                AUDIT_PATH.with_suffix(f".corrupt-{datetime.now():%Y%m%d%H%M%S}.json").write_text(raw, encoding="utf-8")
                rows = []
    rows.append(entry)
    AUDIT_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def emit(**data: Any) -> AgentEvent:
    global _seq
    with _lock:
        _seq += 1
        event = AgentEvent(seq=_seq, ts=datetime.now().isoformat(timespec="milliseconds"), **data)
        _events.append(event)
        _append_audit({"model": MODEL_NAME, **event.model_dump(mode="json", exclude_none=True)})
    return event


def since(seq: int = 0, ticket_id: int | None = None, limit: int = 500) -> list[AgentEvent]:
    with _lock:
        out = [e for e in _events if e.seq > seq and (ticket_id is None or e.ticket_id == ticket_id)]
    return out[-limit:]


def clear_memory() -> None:
    """Forget the in-memory feed (used on DB reset). The audit file is never touched."""
    with _lock:
        _events.clear()
