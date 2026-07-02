"""Minimal chat web app for TaxAgent.

Wraps `TaxSession` behind a tiny HTTP API and serves a single static page. The
chat endpoint returns the *structured* Recommendation (not markdown) plus the
accumulated profile facts, so the frontend renders clean sections and a live
"user profile" panel. Multi-turn continuity and async profile persistence come
for free from TaxSession / persistence.
"""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..agent.reasoner import Reasoner
from ..agent.session import TaxSession

DEFAULT_TAX_YEAR = 2025
_STATIC = Path(__file__).parent / "static"

app = FastAPI(title="TaxAgent Canada")

# One shared reasoner (stateless per call, expensive to build) across all sessions.
_reasoner: Reasoner | None = None
_reasoner_lock = threading.Lock()
_sessions: dict[str, TaxSession] = {}
_session_locks: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def _get_reasoner() -> Reasoner:
    global _reasoner
    with _reasoner_lock:
        if _reasoner is None:
            _reasoner = Reasoner()
    return _reasoner


def _get_session(user_id: str) -> tuple[TaxSession, threading.Lock]:
    with _registry_lock:
        if user_id not in _sessions:
            _sessions[user_id] = TaxSession(
                reasoner=_get_reasoner(), user_id=user_id, default_tax_year=DEFAULT_TAX_YEAR
            )
            _session_locks[user_id] = threading.Lock()
        return _sessions[user_id], _session_locks[user_id]


class ChatRequest(BaseModel):
    user_id: str
    message: str
    tax_year: int | None = None


def _facts_payload(session: TaxSession) -> list[dict]:
    return [
        {"key": f.key, "value": f.value, "evidence_status": f.evidence_status, "confidence": f.confidence}
        for f in session.known_facts
    ]


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    session, lock = _get_session(req.user_id)
    # serialize turns per user — TaxSession has mutable history/fact state
    with lock:
        rec = session.ask(req.message, tax_year=req.tax_year)
        return {"recommendation": rec.model_dump(), "profile_facts": _facts_payload(session)}


@app.get("/api/profile/{user_id}")
def profile(user_id: str) -> dict:
    session, _ = _get_session(user_id)
    return {"user_id": user_id, "profile_facts": _facts_payload(session)}


@app.post("/api/reset/{user_id}")
def reset(user_id: str) -> dict:
    """Start a fresh conversation (keeps the persisted profile on disk)."""
    with _registry_lock:
        _sessions.pop(user_id, None)
        _session_locks.pop(user_id, None)
    return {"ok": True}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
