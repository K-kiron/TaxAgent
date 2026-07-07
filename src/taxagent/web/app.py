"""Festival demo web app for TaxAgent.

The public surface is safe-by-default: static scenario demos work without a
model, while live reasoning is opt-in, PIN-gated, rate-limited, and backed only
by ephemeral in-memory sessions. The web demo never creates disk profiles.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

from fastapi import Cookie, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from ..agent.reasoner import Reasoner
from ..agent.session import TaxSession

DEFAULT_TAX_YEAR = 2025
_STATIC = Path(__file__).parent / "static"
_SCENARIOS = _STATIC / "demo_scenarios.json"
_SESSION_COOKIE = "taxagent_demo_session"
_SESSION_TTL_SECONDS = 30 * 60
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = 8
_STATIC_WORKFLOWS = [
    {
        "id": "tax_question",
        "title": "Ask a tax question",
        "description": "Answer a tax question from non-sensitive sample facts.",
    },
    {
        "id": "manual_intake",
        "title": "Fill tax situation",
        "description": "Enter sample facts and see how TaxAgent structures the return work.",
    },
    {
        "id": "document_review",
        "title": "Review tax slips",
        "description": "Use sample slips to preview extraction, checks, and next steps.",
    },
]
_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "before",
    "can",
    "could",
    "does",
    "for",
    "from",
    "had",
    "have",
    "how",
    "into",
    "later",
    "might",
    "my",
    "need",
    "should",
    "show",
    "that",
    "the",
    "this",
    "through",
    "want",
    "what",
    "when",
    "which",
    "with",
    "would",
    "year",
    "your",
}

app = FastAPI(
    title="TaxAgent Canada",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_reasoner: Reasoner | None = None
_reasoner_lock = threading.Lock()
_sessions: dict[str, TaxSession] = {}
_session_seen: dict[str, float] = {}
_session_turns: dict[str, list[float]] = {}
_session_locks: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()
_active_live = 0
_active_live_lock = threading.Lock()


def _get_reasoner() -> Reasoner:
    global _reasoner
    with _reasoner_lock:
        if _reasoner is None:
            _reasoner = Reasoner()
    return _reasoner


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


def _live_enabled() -> bool:
    return _env_bool("TAXAGENT_DEMO_LIVE_ENABLED", False)


def _demo_pin() -> str:
    return os.environ.get("TAXAGENT_DEMO_PIN", "")


def _max_chars() -> int:
    return _env_int("TAXAGENT_DEMO_MAX_CHARS", 800)


def _max_concurrent() -> int:
    return _env_int("TAXAGENT_DEMO_MAX_CONCURRENT", 1)


def _load_demo_scenarios() -> list[dict]:
    return json.loads(_SCENARIOS.read_text(encoding="utf-8"))


def _normalize_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    expanded = set(tokens)
    if {"permanent", "resident"} <= tokens:
        expanded.add("pr")
    if {"prescription", "drug"} & tokens:
        expanded.add("medication")
    if "medication" in tokens:
        expanded.update({"prescription", "drug"})
    if "university" in tokens or "college" in tokens:
        expanded.add("tuition")
    if "refund" in tokens:
        expanded.add("credit")
    return {t for t in expanded if len(t) > 2 and t not in _STOPWORDS}


def _scenario_terms(scenario: dict) -> set[str]:
    parts = [
        scenario.get("id", ""),
        scenario.get("title", ""),
        scenario.get("tagline", ""),
        scenario.get("prompt", ""),
        scenario.get("workflow", ""),
        " ".join(scenario.get("keywords", [])),
    ]
    return _normalize_tokens(" ".join(parts))


def _score_static_scenario(message: str, scenario: dict) -> tuple[int, list[str]]:
    message_terms = _normalize_tokens(message)
    scenario_terms = _scenario_terms(scenario)
    hits = sorted(message_terms & scenario_terms)
    score = len(hits)
    normalized_message = " ".join(re.findall(r"[a-z0-9]+", message.lower()))
    for phrase in scenario.get("keywords", []):
        phrase_text = " ".join(re.findall(r"[a-z0-9]+", phrase.lower()))
        if len(phrase_text) >= 4 and phrase_text in normalized_message:
            score += 3
            hits.append(phrase)
    return score, hits


def _fallback_recommendation(message: str) -> dict:
    return {
        "answer": (
            "There is not enough demo context to map that input to a tax situation. "
            "Choose a workflow or describe sample facts such as province, tax year, "
            "slips, tuition, insurance, residency timing, or software discrepancy."
        ),
        "rationale": (
            "The public demo uses static, prebuilt examples. It should not pretend to "
            "understand a low-information or unrelated message."
        ),
        "facts_used": [
            {
                "key": "demo_input",
                "value": message[:80],
                "evidence_status": "user_reported",
                "confidence": "low",
            }
        ],
        "required_evidence": [
            {
                "type": "sample_fact",
                "description": "Provide non-sensitive sample facts or use one of the demo workflows.",
                "status": "requested",
            }
        ],
        "assumptions": [
            "The input was too short, too generic, or outside the static demo scenarios."
        ],
        "confidence": "low",
        "risks": [
            "A static public demo should not infer tax advice from insufficient context.",
            "Do not enter SIN, addresses, account numbers, full slip text, or exact real income.",
        ],
        "next_step": "Pick Ask a tax question, Fill tax situation, or Review tax slips and use sample facts.",
        "source_card_ids": ["static_demo_fallback_v1"],
        "professional_help_recommended": False,
    }


def _match_static_scenario(message: str) -> tuple[dict | None, int, list[str]]:
    message_terms = _normalize_tokens(message)
    if len(message_terms) < 2:
        return None, 0, []
    scored = []
    for scenario in _load_demo_scenarios():
        score, hits = _score_static_scenario(message, scenario)
        scored.append((score, scenario, hits))
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_scenario, best_hits = scored[0]
    if best_score < 2:
        return None, best_score, best_hits
    return best_scenario, best_score, best_hits


def _prune_expired_sessions(now: float) -> None:
    expired = [sid for sid, seen in _session_seen.items() if now - seen > _SESSION_TTL_SECONDS]
    for sid in expired:
        _sessions.pop(sid, None)
        _session_locks.pop(sid, None)
        _session_seen.pop(sid, None)
        _session_turns.pop(sid, None)


def _get_session(session_id: str) -> tuple[TaxSession, threading.Lock]:
    now = time.monotonic()
    with _registry_lock:
        _prune_expired_sessions(now)
        if session_id not in _sessions:
            _sessions[session_id] = TaxSession(
                reasoner=_get_reasoner(), default_tax_year=DEFAULT_TAX_YEAR
            )
            _session_locks[session_id] = threading.Lock()
        _session_seen[session_id] = now
        return _sessions[session_id], _session_locks[session_id]


def _get_or_create_session_id(response: Response, cookie_session_id: str | None) -> str:
    with _registry_lock:
        if cookie_session_id and cookie_session_id in _sessions:
            return cookie_session_id
    session_id = uuid.uuid4().hex
    response.set_cookie(
        _SESSION_COOKIE,
        session_id,
        max_age=_SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return session_id


def _check_pin(pin: str | None) -> None:
    configured = _demo_pin()
    if not configured:
        raise HTTPException(
            status_code=503,
            detail={"code": "pin_not_configured", "message": "Live demo PIN is not configured."},
        )
    if pin is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "pin_required", "message": "Enter the demo PIN to use live mode."},
        )
    if pin != configured:
        raise HTTPException(
            status_code=403,
            detail={"code": "pin_invalid", "message": "The demo PIN is incorrect."},
        )


def _check_rate_limit(session_id: str) -> None:
    now = time.monotonic()
    with _registry_lock:
        recent = [t for t in _session_turns.get(session_id, []) if now - t <= _RATE_WINDOW_SECONDS]
        if len(recent) >= _RATE_MAX_REQUESTS:
            _session_turns[session_id] = recent
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limited",
                    "message": "Live demo is rate-limited. Try again in a minute.",
                },
            )
        recent.append(now)
        _session_turns[session_id] = recent


def _enter_live_slot() -> None:
    global _active_live
    with _active_live_lock:
        if _active_live >= _max_concurrent():
            raise HTTPException(
                status_code=429,
                detail={"code": "live_busy", "message": "Live demo is busy. Try again shortly."},
            )
        _active_live += 1


def _leave_live_slot() -> None:
    global _active_live
    with _active_live_lock:
        _active_live = max(0, _active_live - 1)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    tax_year: int | None = None


class StaticChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)


def _facts_payload(session: TaxSession) -> list[dict]:
    return [
        {
            "key": f.key,
            "value": f.value,
            "evidence_status": f.evidence_status,
            "confidence": f.confidence,
        }
        for f in session.known_facts
    ]


@app.post("/api/chat")
def chat(
    req: ChatRequest,
    response: Response,
    x_demo_pin: str | None = Header(default=None),
    cookie_session_id: str | None = Cookie(default=None, alias=_SESSION_COOKIE),
) -> dict:
    if not _live_enabled():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "live_disabled",
                "message": "Live mode is disabled. Use the public static scenarios.",
            },
        )
    if len(req.message) > _max_chars():
        raise HTTPException(
            status_code=413,
            detail={
                "code": "message_too_long",
                "message": f"Demo questions are limited to {_max_chars()} characters.",
            },
        )

    _check_pin(x_demo_pin)
    session_id = _get_or_create_session_id(response, cookie_session_id)
    _check_rate_limit(session_id)
    _enter_live_slot()
    try:
        session, lock = _get_session(session_id)
        with lock:
            rec = session.ask(req.message, tax_year=req.tax_year)
            return {"recommendation": rec.model_dump(), "profile_facts": _facts_payload(session)}
    finally:
        _leave_live_slot()


@app.post("/api/static-chat")
def static_chat(req: StaticChatRequest) -> dict:
    if len(req.message) > _max_chars():
        raise HTTPException(
            status_code=413,
            detail={
                "code": "message_too_long",
                "message": f"Demo questions are limited to {_max_chars()} characters.",
            },
        )
    scenario, score, hits = _match_static_scenario(req.message)
    if scenario is None:
        scenarios = [
            {"id": s["id"], "title": s["title"], "workflow": s.get("workflow", "tax_question")}
            for s in _load_demo_scenarios()[:4]
        ]
        return {
            "matched": False,
            "mode": "fallback",
            "scenario_id": None,
            "scenario_title": None,
            "score": score,
            "matched_terms": hits,
            "suggested_scenarios": scenarios,
            "recommendation": _fallback_recommendation(req.message),
        }
    return {
        "matched": True,
        "mode": scenario.get("workflow", "tax_question"),
        "scenario_id": scenario["id"],
        "scenario_title": scenario["title"],
        "score": score,
        "matched_terms": hits,
        "suggested_scenarios": [],
        "recommendation": scenario["recommendation"],
    }


@app.get("/api/demo-config")
def demo_config() -> dict:
    scenarios = [
        {
            "id": s["id"],
            "title": s["title"],
            "prompt": s["prompt"],
            "workflow": s.get("workflow", "tax_question"),
        }
        for s in _load_demo_scenarios()
    ]
    return {
        "live_enabled": _live_enabled(),
        "max_chars": _max_chars(),
        "workflows": _STATIC_WORKFLOWS,
        "scenarios": scenarios,
    }


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


def _clear_demo_state_for_tests() -> None:
    global _active_live
    with _registry_lock:
        _sessions.clear()
        _session_seen.clear()
        _session_turns.clear()
        _session_locks.clear()
    with _active_live_lock:
        _active_live = 0
