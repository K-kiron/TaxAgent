from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from taxagent.returns import TaxReturnInput, calculate_return
from taxagent.web import local_app

from test_federal_return import _input


def _client() -> TestClient:
    return TestClient(local_app.app, base_url="http://127.0.0.1:8056")


def _sample_payload() -> dict:
    return local_app._sample_input().model_dump(mode="json")


def test_v2_2025_canonical_part_year_flag_blocks_when_legacy_export_is_stale():
    payload = _sample_payload()
    payload["schema_version"] = "qc-return-v2"
    payload["additional_return_screens"]["immigrated_or_emigrated_2025"] = False
    payload["additional_return_screens"]["immigrated_or_emigrated_in_tax_year"] = True

    response = _client().post("/api/calculate", json=payload)

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "blocked"
    assert result["federal_refund_or_balance"] is None
    assert result["quebec_refund_or_balance"] is None
    assert "unsupported_immigrated_or_emigrated_2025" in {
        blocker["code"] for blocker in result["blockers"]
    }


def test_v2_2025_canonical_student_loan_origins_replace_stale_legacy_export():
    payload = _sample_payload()
    payload["schema_version"] = "qc-return-v2"
    payload["taxpayer"]["has_student_loan_interest"] = True
    payload["student_loan_interest"]["federal_unused_2021"] = "0.00"
    payload["student_loan_interest"]["federal_unused_by_origin_year"] = {
        "2020": "0.00",
        "2021": "350.00",
        "2022": "0.00",
        "2023": "0.00",
        "2024": "0.00",
    }
    payload["student_loan_interest"]["federal_claim_amount"] = "350.00"
    payload["student_loan_interest"]["quebec_prior_unused"] = "350.00"
    payload["student_loan_interest"]["quebec_claim_amount"] = "350.00"

    parsed = local_app._decimalize_json_money(TaxReturnInput.model_validate(payload))
    result = calculate_return(parsed)

    assert result.status == "complete"
    assert next(
        line for line in result.lines if line.form_id == "T1" and line.line_id == "31900"
    ).value == Decimal("350.00")


@pytest.mark.parametrize(
    "canonical_origins",
    [
        {},
        {"2021": "0.00"},
    ],
)
def test_v2_2025_canonical_student_loan_origin_map_does_not_reuse_omitted_legacy_amounts(
    canonical_origins,
):
    payload = _sample_payload()
    payload["schema_version"] = "qc-return-v2"
    payload["taxpayer"]["has_student_loan_interest"] = True
    payload["student_loan_interest"]["federal_unused_2020"] = "500.00"
    payload["student_loan_interest"]["federal_unused_by_origin_year"] = canonical_origins
    payload["student_loan_interest"]["federal_claim_amount"] = "500.00"
    payload["student_loan_interest"]["quebec_prior_unused"] = "500.00"
    payload["student_loan_interest"]["quebec_claim_amount"] = "500.00"

    response = _client().post("/api/calculate", json=payload)

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["status"] == "blocked"
    assert result["federal_refund_or_balance"] is None
    assert result["quebec_refund_or_balance"] is None
    assert "missing_student_loan_interest_answers" in {
        blocker["code"] for blocker in result["blockers"]
    }


def test_v2_2025_rejects_out_of_window_student_loan_origin_exports():
    payload = _sample_payload()
    payload["schema_version"] = "qc-return-v2"
    payload["student_loan_interest"]["federal_unused_by_origin_year"] = {
        "2019": "125.00"
    }

    with pytest.raises(ValueError, match="origin years"):
        TaxReturnInput.model_validate(payload)


def test_2025_v1_fixture_result_is_preserved_after_schema_migration_support():
    legacy = _input(employed=True)

    result = calculate_return(legacy)

    assert result.status == "complete"
    assert result.federal_refund_or_balance == Decimal("2546.70")
    assert result.quebec_refund_or_balance == Decimal("863.84")
