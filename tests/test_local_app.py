from __future__ import annotations

import sys
import types
from decimal import Decimal

from fastapi.testclient import TestClient

from taxagent.returns.models import LineValue, TaxReturnResult
from taxagent.web import local_app


def _client() -> TestClient:
    return TestClient(local_app.app, base_url="http://127.0.0.1:8056")


def _sample_input(client: TestClient) -> dict:
    response = client.get("/api/sample")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sample_only"] is True
    return payload["input"]


def test_schema_starts_blank_and_assets_are_served():
    client = _client()

    schema = client.get("/api/schema").json()
    page = client.get("/")
    script = client.get("/static/local.js")
    styles = client.get("/static/local.css")

    assert schema["blank_input"]["slips"] == []
    assert schema["blank_input"]["taxpayer"]["has_self_employment"] is None
    assert schema["blank_input"]["instalments"]["federal_reviewed"] is None
    assert schema["blank_input"]["quebec_schedule_b"]["living_alone_reviewed"] is None
    assert schema["blank_input"]["student_loan_interest"]["reviewed"] is None
    assert schema["blank_input"]["scholarships"]["reviewed"] is None
    assert schema["blank_input"]["scholarships"]["part_time_programs"] is None
    assert schema["blank_input"]["resp_eap"]["reviewed"] is None
    assert schema["blank_input"]["additional_return_screens"]["immigrated_or_emigrated_2025"] is None
    assert schema["supported_slips"] == ["T4", "T4A", "RL1", "T5", "RL3", "T2202", "RRSP_RECEIPT", "RC210", "RL19"]
    assert schema["default_sample_loaded"] is False
    assert "TaxAgent local return workspace" in page.text
    assert "frame-src 'self' blob:" in page.headers["content-security-policy"]
    assert page.status_code == script.status_code == styles.status_code == 200


def test_calculate_rejects_cross_origin_bad_json_and_oversize_payload():
    client = _client()

    cross_origin = client.post(
        "/api/calculate",
        json=_sample_input(client),
        headers={"Origin": "https://example.test"},
    )
    malformed = client.post(
        "/api/calculate",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    oversize = client.post(
        "/api/calculate",
        content=b'{"padding":"' + (b"x" * (local_app.MAX_REQUEST_BYTES + 1)) + b'"}',
        headers={"Content-Type": "application/json"},
    )

    assert cross_origin.status_code == 403
    assert cross_origin.json()["detail"]["code"] == "cross_origin_blocked"
    assert malformed.status_code == 400
    assert malformed.json()["detail"]["code"] == "invalid_json"
    assert oversize.status_code == 413
    assert oversize.json()["detail"]["code"] == "request_too_large"


def test_calculate_reports_schema_errors_without_echoing_tax_payload():
    client = _client()

    response = client.post(
        "/api/calculate",
        json={"schema_version": "2025-qc-v1", "tax_year": 2025, "secret": "do-not-echo"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["code"] == "invalid_schema"
    assert "do-not-echo" not in response.text
    assert body["detail"]["errors"]


def test_calculate_uses_preflight_and_keeps_blocked_headlines_empty():
    client = _client()
    data = _sample_input(client)
    data["province_dec31"] = "ON"

    response = client.post("/api/calculate", json=data)

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "blocked"
    assert result["federal_refund_or_balance"] is None
    assert result["quebec_refund_or_balance"] is None
    assert "unsupported_province" in {b["code"] for b in result["blockers"]}


def test_calculate_surfaces_latest_slip_collection_gates():
    client = _client()
    data = _sample_input(client)
    data["slips"][0].pop("cpp_qpp_exempt")

    response = client.post("/api/calculate", json=data)

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "blocked"
    assert "missing_t4_exemption_answer" in {b["code"] for b in result["blockers"]}


def test_calculate_delegates_supported_input_to_return_engine(monkeypatch):
    client = _client()
    calls = []

    def calculate_return(data):
        calls.append(data)
        return TaxReturnResult(
            status="complete",
            coverage_profile_id="2025-qc-single-salaried-student-v1",
            ruleset_hash="b" * 64,
            federal_refund_or_balance=Decimal("123.45"),
            quebec_refund_or_balance=Decimal("-67.89"),
            lines=[
                LineValue(
                    form_id="T1",
                    line_id="10100",
                    value=Decimal("42000.00"),
                    status="input",
                    inputs=["slips.0.fields.14"],
                    formula_id="t1_employment_income",
                    source_ids=["cra_2025_5005_r"],
                    explanation="Employment income",
                )
            ],
        )

    fake_engine = types.SimpleNamespace(calculate_return=calculate_return)
    monkeypatch.setitem(sys.modules, "taxagent.returns.engine", fake_engine)

    response = client.post("/api/calculate", json=_sample_input(client))

    assert response.status_code == 200
    body = response.json()
    assert len(calls) == 1
    assert calls[0].schema_version == "2025-qc-v1"
    assert body["result"]["status"] == "complete"
    assert body["result"]["lines"][0]["source_ids"] == ["cra_2025_5005_r"]
    assert body["sources"]["cra_2025_5005_r"]["url"].startswith("https://")


def test_labelled_sample_calculates_with_real_engine():
    client = _client()

    response = client.post("/api/calculate", json=_sample_input(client))

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "complete"
    assert result["blockers"] == []
    assert result["federal_refund_or_balance"] == "3055.21"
    assert result["quebec_refund_or_balance"] == "1199.84"
    form_ids = {line["form_id"] for line in result["lines"]}
    assert {"T1", "TP1", "T1-S8", "T1-S11", "T1-S6", "TP1-F", "TP1-K", "TP1-P", "TP1-T", "TP1-U"} <= form_ids
    assert len(result["lines"]) >= 600


def test_labelled_sample_uses_current_public_input_contract():
    client = _client()

    sample = _sample_input(client)

    assert "was_full_time_student_13_weeks_or_more" not in sample["taxpayer"]
    assert sample["taxpayer"]["was_full_time_student_more_than_13_weeks"] is True
    assert sample["slips"][0]["cpp_qpp_exempt"] is False
    assert sample["slips"][0]["ei_exempt"] is False
    assert sample["slips"][0]["ppip_exempt"] is False
    assert sample["slips"][2]["fields"] == {"24": "0.00", "25": "8.00", "26": "4200.00"}
    assert sample["rrsp"]["has_prior_unused_contributions"] is False
    assert sample["instalments"] == {
        "federal_reviewed": True,
        "federal_paid": "0.00",
        "quebec_reviewed": True,
        "quebec_paid": "0.00",
    }
    assert sample["quebec_schedule_b"] == {
        "living_alone_reviewed": True,
        "eligible_for_living_alone_amount": False,
    }
    assert sample["student_loan_interest"] == {
        "reviewed": True,
        "qualifying_government_loans_confirmed": True,
        "federal_current_year_paid": "0.00",
        "federal_unused_2020": "0.00",
        "federal_unused_2021": "0.00",
        "federal_unused_2022": "0.00",
        "federal_unused_2023": "0.00",
        "federal_unused_2024": "0.00",
        "federal_claim_amount": "0.00",
        "quebec_prior_unused": "0.00",
        "quebec_current_year_paid": "0.00",
        "quebec_claim_amount": "0.00",
    }
    assert sample["taxpayer"]["has_moving_expenses"] is False
    assert sample["taxpayer"]["has_tips_or_other_employment_income"] is False
    assert sample["scholarships"] == {"reviewed": True, "awards": [], "part_time_programs": []}
    assert sample["resp_eap"] == {
        "reviewed": True,
        "has_other_resp_payments": False,
        "qesi_cumulative_amount_over_3600": False,
        "payments": [],
    }
    assert sample["additional_return_screens"] == {
        "immigrated_or_emigrated_2025": False,
        "quebec_trust_return": False,
        "separate_post_death_return": False,
        "quebec_enterprise_registration_or_annual_fee": False,
    }
    assert sample["refundable_credits"]["rl19_advance_payments_reviewed"] is True
    assert sample["refundable_credits"]["advanced_cwb_disability_paid"] == "0.00"
    assert sample["refundable_credits"]["quebec_work_premium_full_time_student"] is True
