from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from fastapi.testclient import TestClient

from taxagent.intake.bridge import workspace_from_import
from taxagent.intake.models import PdfImportBatchResult
from taxagent.web import local_app

from test_annual_returns import annual_input


def _client() -> TestClient:
    return TestClient(local_app.app, base_url="http://127.0.0.1:8056")


def _empty_workspace():
    workspace = workspace_from_import(PdfImportBatchResult(documents=[], candidates=[]))
    first = annual_input(2020, salary="20000")
    first.slips.append(
        first.slips[0].model_copy(
            update={
                "slip_type": "T2202",
                "document_id": "tuition-2020",
                "issuer_id": "school",
                "fields": {"24": Decimal("8"), "25": Decimal("0"), "26": Decimal("30000")},
            }
        )
    )
    first.federal_tuition = first.federal_tuition.model_copy(
        update={
            "has_current_tuition": True,
            "t2202_eligible_fees": Decimal("30000"),
        }
    )
    second = annual_input(2021, salary="20000")
    workspace.years["2020"].input = first.model_dump(mode="json")
    workspace.years["2021"].input = second.model_dump(mode="json")
    workspace.active_years = [2020, 2021]
    return workspace.model_dump(mode="json")


def _calculate(client: TestClient, workspace: dict) -> dict:
    response = client.post("/api/calculate-years", json=workspace)
    assert response.status_code == 200
    return response.json()


def _reconcile(client: TestClient, workspace: dict) -> dict:
    response = client.post(
        "/api/reconcile-workspace",
        json={"workspace": workspace, "active_years": [2020, 2021]},
    )
    assert response.status_code == 200
    return response.json()


def _seed_assessed_conflict(client: TestClient, amount: str = "975") -> dict:
    workspace = _empty_workspace()
    workspace["years"]["2021"]["input"]["federal_tuition"]["has_prior_unused"] = True
    workspace["years"]["2021"]["input"]["federal_tuition"]["prior_unused_amount"] = amount
    blocked = _calculate(client, workspace)
    assert blocked["results"]["2021"]["reason"] == "carryforward_conflict"
    conflict = blocked["workspace"]["years"]["2021"]["carryforwards"]["conflicts"][0]
    assert conflict["assessed_amount"] == amount
    return blocked["workspace"]


def test_public_clear_from_positive_assessed_to_explicit_false_records_zero_and_repeats_cleanly():
    client = _client()
    workspace = _seed_assessed_conflict(client)
    edited = deepcopy(workspace)
    edited["years"]["2021"]["input"]["federal_tuition"]["has_prior_unused"] = False
    edited["years"]["2021"]["input"]["federal_tuition"]["prior_unused_amount"] = None

    recalculated = _calculate(client, _reconcile(client, edited))
    repeated = _calculate(client, _reconcile(client, recalculated["workspace"]))
    year = repeated["workspace"]["years"]["2021"]
    conflict = year["carryforwards"]["conflicts"][0]

    assert repeated["results"]["2021"]["reason"] == "carryforward_conflict"
    assert conflict["assessed_amount"] == "0"
    assert year["carryforwards"]["assessed_opening_balances"]["federal_tuition_unused_fees"] == "0"
    assert conflict["resolved_selection"] is None
    assert not repeated["workspace"]["carryforward_choices"]
    assert any(
        item.get("kind") == "assessed_opening_update"
        and item.get("previous_assessed_amount") == "975"
        and item.get("new_assessed_amount") == "0"
        for item in repeated["workspace"]["correction_audit"]
    )


def test_public_fresh_explicit_false_without_amount_records_zero_like_later_clear():
    client = _client()
    workspace = _empty_workspace()
    workspace["years"]["2021"]["input"]["federal_tuition"]["has_prior_unused"] = False
    workspace["years"]["2021"]["input"]["federal_tuition"]["prior_unused_amount"] = None

    blocked = _calculate(client, _reconcile(client, workspace))
    repeated = _calculate(client, _reconcile(client, blocked["workspace"]))
    year = repeated["workspace"]["years"]["2021"]
    conflict = year["carryforwards"]["conflicts"][0]

    assert repeated["results"]["2021"]["reason"] == "carryforward_conflict"
    assert conflict["assessed_amount"] == "0"
    assert year["carryforwards"]["assessed_opening_balances"]["federal_tuition_unused_fees"] == "0"
    assert "federal_tuition_unused_fees" not in year["carryforwards"]["applied_proposed_balances"]


def test_public_unknown_clear_removes_stale_assessed_claim_without_inventing_zero():
    client = _client()
    workspace = _seed_assessed_conflict(client)
    edited = deepcopy(workspace)
    edited["years"]["2021"]["input"]["federal_tuition"]["has_prior_unused"] = None
    edited["years"]["2021"]["input"]["federal_tuition"]["prior_unused_amount"] = None

    recalculated = _calculate(client, _reconcile(client, edited))
    repeated = _calculate(client, _reconcile(client, recalculated["workspace"]))
    year = repeated["workspace"]["years"]["2021"]
    assessed = year["carryforwards"]["assessed_opening_balances"]
    applied = year["carryforwards"]["applied_proposed_balances"]
    proposed = year["carryforwards"]["proposed_opening_balances"][
        "federal_tuition_unused_fees"
    ]["amount"]

    assert repeated["results"]["2021"]["status"] == "complete"
    assert "federal_tuition_unused_fees" not in assessed
    assert applied["federal_tuition_unused_fees"] == proposed
    assert year["input"]["federal_tuition"]["prior_unused_amount"] == proposed
    assert year["input"]["federal_tuition"]["has_prior_unused"] is True
    assert year["carryforwards"]["conflicts"] == []
    assert not any(
        item.get("kind") == "assessed_opening_update"
        and item.get("new_assessed_amount") == proposed
        for item in repeated["workspace"]["correction_audit"]
    )
    assert any(
        item.get("kind") == "assessed_opening_clear"
        and item.get("previous_assessed_amount") == "975"
        and item.get("new_assessed_amount") is None
        for item in repeated["workspace"]["correction_audit"]
    )


def test_public_explicit_zero_assessed_is_retained_across_reconcile_and_calculate():
    client = _client()
    workspace = _empty_workspace()
    workspace["years"]["2021"]["input"]["federal_tuition"]["has_prior_unused"] = False
    workspace["years"]["2021"]["input"]["federal_tuition"]["prior_unused_amount"] = "0"

    blocked = _calculate(client, _reconcile(client, workspace))
    repeated = _calculate(client, _reconcile(client, blocked["workspace"]))
    year = repeated["workspace"]["years"]["2021"]
    conflict = year["carryforwards"]["conflicts"][0]

    assert repeated["results"]["2021"]["reason"] == "carryforward_conflict"
    assert conflict["assessed_amount"] == "0"
    assert year["carryforwards"]["assessed_opening_balances"]["federal_tuition_unused_fees"] == "0"
    assert "federal_tuition_unused_fees" not in year["carryforwards"]["applied_proposed_balances"]


def test_public_positive_assessed_edit_refreshes_conflict_and_invalidates_previous_choice():
    client = _client()
    workspace = _seed_assessed_conflict(client)
    key = workspace["years"]["2021"]["carryforwards"]["conflicts"][0]["key"]
    resolved = client.post(
        "/api/reconcile-workspace",
        json={
            "workspace": workspace,
            "active_years": [2020, 2021],
            "carryforward_choices": [{
                "tax_year": 2021,
                "key": key,
                "selection": "proposed",
                "reason": "Use the freshly calculated prior-year closing balance.",
            }],
        },
    )
    assert resolved.status_code == 200
    completed = _calculate(client, resolved.json())
    edited = deepcopy(completed["workspace"])
    edited["years"]["2021"]["input"]["federal_tuition"]["has_prior_unused"] = True
    edited["years"]["2021"]["input"]["federal_tuition"]["prior_unused_amount"] = "1375"

    recalculated = _calculate(client, _reconcile(client, edited))
    conflict = recalculated["workspace"]["years"]["2021"]["carryforwards"]["conflicts"][0]

    assert recalculated["results"]["2021"]["reason"] == "carryforward_conflict"
    assert conflict["assessed_amount"] == "1375"
    assert conflict["resolved_selection"] is None
    assert not recalculated["workspace"]["carryforward_choices"]
