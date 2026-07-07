import json
import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from taxagent.models import EvidenceItem, Recommendation, UserFact

app_module = importlib.import_module("taxagent.web.app")


def _client(monkeypatch, *, live: bool = False, pin: str = "demo-pin") -> TestClient:
    monkeypatch.setenv("TAXAGENT_DEMO_LIVE_ENABLED", "1" if live else "0")
    monkeypatch.setenv("TAXAGENT_DEMO_PIN", pin)
    monkeypatch.setenv("TAXAGENT_DEMO_MAX_CHARS", "120")
    monkeypatch.setenv("TAXAGENT_DEMO_MAX_CONCURRENT", "1")
    app_module._clear_demo_state_for_tests()
    return TestClient(app_module.app)


def test_demo_config_exposes_static_mode_without_secret(monkeypatch):
    client = _client(monkeypatch, live=False)

    res = client.get("/api/demo-config")

    assert res.status_code == 200
    body = res.json()
    assert body["live_enabled"] is False
    assert body["max_chars"] == 120
    assert len(body["scenarios"]) >= 4
    assert "demo-pin" not in res.text


def test_live_chat_disabled_by_default_and_does_not_require_user_id(monkeypatch):
    client = _client(monkeypatch, live=False)

    res = client.post("/api/chat", json={"message": "Can I claim this?"})

    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "live_disabled"


def test_live_chat_requires_pin(monkeypatch):
    client = _client(monkeypatch, live=True, pin="correct-pin")

    missing = client.post("/api/chat", json={"message": "Can I claim this?"})
    wrong = client.post(
        "/api/chat",
        headers={"X-Demo-Pin": "wrong-pin"},
        json={"message": "Can I claim this?"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 403


def test_live_chat_with_pin_uses_ephemeral_session_without_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("TAXAGENT_PROFILE_DIR", str(tmp_path / "profiles"))

    class FakeResult:
        def all_messages(self):
            return []

    class FakeReasoner:
        def run_turn(self, question, **kwargs):
            return (
                Recommendation(
                    answer=f"Demo answer for: {question}",
                    rationale="This is a fake live response for API testing.",
                    facts_used=[
                        UserFact(
                            key="demo_question",
                            value=question,
                            evidence_status="user_reported",
                        )
                    ],
                    required_evidence=[
                        EvidenceItem(
                            type="user_statement",
                            description="Use non-sensitive demo facts only.",
                        )
                    ],
                    confidence="low",
                    risks=["Do not treat this as certified tax advice."],
                    next_step="Verify with official records before filing.",
                    source_card_ids=["demo_card"],
                ),
                [],
                FakeResult(),
            )

    monkeypatch.setattr(app_module, "_get_reasoner", lambda: FakeReasoner())
    client = _client(monkeypatch, live=True, pin="correct-pin")

    res = client.post(
        "/api/chat",
        headers={"X-Demo-Pin": "correct-pin"},
        json={"message": "I had an internship in Quebec."},
    )

    assert res.status_code == 200
    assert res.json()["recommendation"]["answer"].startswith("Demo answer")
    assert not (tmp_path / "profiles").exists()


def test_live_chat_rejects_too_long_input(monkeypatch):
    client = _client(monkeypatch, live=True, pin="correct-pin")

    res = client.post(
        "/api/chat",
        headers={"X-Demo-Pin": "correct-pin"},
        json={"message": "x" * 121},
    )

    assert res.status_code == 413


def test_public_profile_and_docs_surfaces_are_closed(monkeypatch):
    client = _client(monkeypatch, live=False)

    assert client.get("/api/profile/public").status_code == 404
    assert client.post("/api/reset/public").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_static_demo_scenarios_are_complete():
    data_path = (
        Path(__file__).parents[1]
        / "src"
        / "taxagent"
        / "web"
        / "static"
        / "demo_scenarios.json"
    )

    scenarios = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {s["id"] for s in scenarios}

    assert {
        "quebec_group_drug_insurance",
        "tuition_carryforward",
        "new_pr_ramq_timeline",
        "tax_software_discrepancy",
    } <= ids
    for scenario in scenarios:
        assert scenario["title"]
        assert scenario["prompt"]
        rec = scenario["recommendation"]
        assert rec["answer"]
        assert rec["required_evidence"]
        assert rec["risks"]
        assert rec["next_step"]
