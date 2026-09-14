from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from taxagent.intake.bridge import (
    calculate_ready_years,
    reconcile_workspace,
    workspace_from_import,
)
from taxagent.intake.models import ExtractedField, ImportedDocument, ImportedSlipCandidate, PdfImportBatchResult
from taxagent.returns import LineValue, TaxReturnResult
from taxagent.web import local_app


def _client() -> TestClient:
    return TestClient(local_app.app, base_url="http://127.0.0.1:8056")


def _field(value: str, box: str = "14") -> ExtractedField:
    return ExtractedField(
        value=value,
        method="digital_text",
        confidence=0.96,
        review_required=False,
        page=1,
        bbox=(72.0, 100.0, 210.0, 115.0),
        raw_text=f"Box {box} amount {value}",
    )


def _candidate(
    *,
    candidate_id: str,
    slip_type: str | None = "T4",
    tax_year: int | None = 2025,
    decision: str = "accepted_auto",
    fields: dict[str, ExtractedField] | None = None,
    review_reasons: list[str] | None = None,
    document_id: str | None = None,
    contribution_period: str | None = None,
    issuer_id: str = "Example Robotics Inc.",
) -> ImportedSlipCandidate:
    return ImportedSlipCandidate(
        candidate_id=candidate_id,
        document_id=document_id or f"doc_{candidate_id}",
        slip_type=slip_type,
        tax_year=tax_year,
        issuer_id=issuer_id,
        contribution_period=contribution_period,
        amended_status="original",
        decision=decision,  # type: ignore[arg-type]
        fields=fields or {"14": _field("45000.00")},
        review_reasons=review_reasons or [],
    )


def _import_result(candidates: list[ImportedSlipCandidate]) -> PdfImportBatchResult:
    return PdfImportBatchResult(
        documents=[
            ImportedDocument(
                document_id=candidate.document_id,
                filename=f"{candidate.document_id}.pdf",
                sha256="a" * 64,
                status="processed",
                page_count=1,
            )
            for candidate in candidates
        ],
        candidates=candidates,
    )


def _result_line(result: dict, form_id: str, line_id: str) -> dict:
    return next(line for line in result["lines"] if line["form_id"] == form_id and line["line_id"] == line_id)


def test_workspace_maps_accepted_slip_fields_without_confirming_missing_facts():
    result = _import_result([_candidate(candidate_id="001")])

    workspace = workspace_from_import(result)
    year = workspace.years["2025"]

    assert year.ready_to_calculate is False
    assert year.input["schema_version"] == "qc-return-v2"
    assert year.input["tax_year"] == 2025
    assert year.input["slips"][0]["slip_type"] == "T4"
    assert year.input["slips"][0]["document_id"] == "001"
    assert year.input["slips"][0]["fields"]["14"] == "45000.00"
    assert year.input["slips"][0]["confirmed"] is True
    assert year.input["taxpayer"]["full_year_canada_resident"] is None
    assert year.missing_facts
    assert year.evidence["001"]["document_id"] == "doc_001"
    assert year.evidence["001"]["fields"]["14"]["raw_text"] == "Box 14 amount 45000.00"


def test_workspace_keeps_review_candidates_unresolved_and_groups_all_six_years():
    accepted_2024 = _candidate(candidate_id="001", tax_year=2024)
    review_2025 = _candidate(
        candidate_id="002",
        tax_year=2025,
        decision="needs_review",
        review_reasons=["conflicting_values_for_same_slip"],
    )

    workspace = workspace_from_import(_import_result([accepted_2024, review_2025]))

    assert set(workspace.years) == {"2020", "2021", "2022", "2023", "2024", "2025"}
    assert workspace.years["2024"].ready_to_calculate is False
    assert workspace.years["2025"].ready_to_calculate is False
    assert workspace.years["2025"].input["slips"] == []
    assert workspace.years["2025"].unresolved_candidates[0]["candidate_id"] == "002"
    assert workspace.years["2025"].unresolved_candidates[0]["candidate"]["fields"]["14"]["value"] == "45000.00"


def test_workspace_maps_tuition_rrsp_and_rl19_without_eligibility_inference():
    tuition = _candidate(
        candidate_id="001",
        slip_type="T2202",
        fields={"26": _field("4200.00", "26")},
    )
    rrsp = _candidate(
        candidate_id="002",
        slip_type="RRSP_RECEIPT",
        contribution_period="march_to_december",
        fields={
            "contribution_amount": ExtractedField(
                value="1250.00",
                method="digital_text",
                confidence=0.96,
                review_required=False,
                page=1,
                bbox=(1.0, 2.0, 3.0, 4.0),
                raw_text="March 2 to December 31, 2025 contribution period 1,250.00",
            )
        },
    )
    rl19 = _candidate(
        candidate_id="003",
        slip_type="RL-19",
        fields={"A": _field("100.00", "A"), "B": _field("50.00", "B")},
    )

    workspace = workspace_from_import(_import_result([tuition, rrsp, rl19]))
    data = workspace.years["2025"].input

    assert data["federal_tuition"]["t2202_eligible_fees"] == "4200.00"
    assert data["quebec_tuition"]["eligible_tuition_or_exam_receipts"] == "4200.00"
    assert data["rrsp"]["has_contributions"] is True
    assert data["rrsp"]["contribution_receipts"] == "1250.00"
    assert data["rrsp"]["march_to_december_contributions"] == "1250.00"
    assert data["slips"][1]["rrsp_period"] == "march_to_december"
    assert data["slips"][1]["fields"] == {"amount": "1250.00"}
    assert data["refundable_credits"]["rl19_box_a"] == "100.00"
    assert data["taxpayer"]["was_full_time_student_more_than_13_weeks"] is None


def test_workspace_keeps_two_slips_from_same_pdf_as_distinct_candidates():
    t4 = _candidate(candidate_id="page1-region1", document_id="doc_bundle", slip_type="T4")
    rl1 = _candidate(
        candidate_id="page1-region2",
        document_id="doc_bundle",
        slip_type="RL-1",
        fields={"A": _field("45000.00", "A"), "E": _field("5000.00", "E")},
    )

    workspace = workspace_from_import(_import_result([t4, rl1]))
    slips = workspace.years["2025"].input["slips"]

    assert [slip["document_id"] for slip in slips] == ["page1-region1", "page1-region2"]
    assert workspace.years["2025"].evidence["page1-region1"]["document_id"] == "doc_bundle"
    assert workspace.years["2025"].evidence["page1-region2"]["document_id"] == "doc_bundle"


def test_workspace_aggregates_tuition_rrsp_and_rl19_amounts():
    tuition_a = _candidate(candidate_id="tuition-a", slip_type="T2202", fields={"26": _field("1000.00", "26")})
    tuition_b = _candidate(candidate_id="tuition-b", slip_type="T2202", fields={"26": _field("250.00", "26")})
    rrsp_a = _candidate(
        candidate_id="rrsp-a",
        slip_type="RRSP_RECEIPT",
        contribution_period="first_60_days",
        fields={"contribution_amount": _field("300.00", "contribution_amount")},
    )
    rrsp_b = _candidate(
        candidate_id="rrsp-b",
        slip_type="RRSP_RECEIPT",
        contribution_period="first_60_days",
        fields={"contribution_amount": _field("200.00", "contribution_amount")},
    )
    rl19_a = _candidate(candidate_id="rl19-a", slip_type="RL-19", fields={"A": _field("10.00", "A")})
    rl19_b = _candidate(candidate_id="rl19-b", slip_type="RL-19", fields={"A": _field("15.00", "A")})

    workspace = workspace_from_import(_import_result([tuition_a, tuition_b, rrsp_a, rrsp_b, rl19_a, rl19_b]))
    data = workspace.years["2025"].input

    assert data["federal_tuition"]["t2202_eligible_fees"] == "1250.00"
    assert data["quebec_tuition"]["eligible_tuition_or_exam_receipts"] == "1250.00"
    assert data["rrsp"]["contribution_receipts"] == "500.00"
    assert data["rrsp"]["first_60_days_contributions"] == "500.00"
    assert data["refundable_credits"]["rl19_box_a"] == "25.00"


def test_workspace_keeps_unknown_year_candidates_unassigned():
    unknown = _candidate(candidate_id="unknown", tax_year=None, decision="needs_review")

    workspace = workspace_from_import(_import_result([unknown]))

    assert workspace.unassigned_candidates[0]["candidate_id"] == "unknown"
    assert all(not year.unresolved_candidates for year in workspace.years.values())
    assert all(not year.input["slips"] for year in workspace.years.values())


def test_workspace_maps_rl8_box_b_to_quebec_tuition_without_treating_box_a_as_fees():
    rl8 = _candidate(
        candidate_id="rl8",
        slip_type="RL-8",
        fields={"A": _field("500.00", "A"), "B": _field("3200.00", "B")},
    )

    workspace = workspace_from_import(_import_result([rl8]))

    assert workspace.years["2025"].input["slips"] == []
    assert workspace.years["2025"].unresolved_candidates == []
    assert workspace.years["2025"].input["quebec_tuition"]["eligible_tuition_or_exam_receipts"] == "3200.00"
    assert workspace.years["2025"].evidence["rl8"]["fields"]["A"]["value"] == "500.00"


def test_workspace_reconciles_paired_t2202_and_rl8_tuition_without_double_counting():
    t2202 = _candidate(
        candidate_id="t2202-school-a",
        slip_type="T2202",
        issuer_id="Example University",
        fields={"26": _field("3000.00", "26")},
    )
    rl8 = _candidate(
        candidate_id="rl8-school-a",
        slip_type="RL-8",
        issuer_id=" example   university ",
        fields={"B": _field("3000.00", "B")},
    )
    other_t2202 = _candidate(
        candidate_id="t2202-school-b",
        slip_type="T2202",
        issuer_id="Other College",
        fields={"26": _field("500.00", "26")},
    )

    workspace = workspace_from_import(_import_result([t2202, rl8, other_t2202]))
    data = workspace.years["2025"].input

    assert workspace.years["2025"].unresolved_candidates == []
    assert data["federal_tuition"]["t2202_eligible_fees"] == "3500.00"
    assert data["quebec_tuition"]["eligible_tuition_or_exam_receipts"] == "3500.00"


def test_conflicting_paired_t2202_and_rl8_tuition_requires_targeted_review():
    t2202 = _candidate(
        candidate_id="t2202-school",
        slip_type="T2202",
        issuer_id="Example University",
        fields={"26": _field("3000.00", "26")},
    )
    rl8 = _candidate(
        candidate_id="rl8-school",
        slip_type="RL-8",
        issuer_id="Example University",
        fields={"B": _field("2500.00", "B")},
    )

    workspace = workspace_from_import(_import_result([t2202, rl8]))
    year = workspace.years["2025"]

    assert year.input["federal_tuition"]["t2202_eligible_fees"] == "3000.00"
    assert year.input["quebec_tuition"]["eligible_tuition_or_exam_receipts"] is None
    assert {item["reason"] for item in year.unresolved_candidates} == {"conflicting_tuition_evidence"}


def test_rl8_box_c_requires_targeted_review_until_donation_mapping_exists():
    rl8 = _candidate(
        candidate_id="rl8-donation",
        slip_type="RL-8",
        fields={"B": _field("1200.00", "B"), "C": _field("50.00", "C")},
    )

    workspace = workspace_from_import(_import_result([rl8]))

    assert workspace.years["2025"].input["quebec_tuition"]["eligible_tuition_or_exam_receipts"] == "1200.00"
    assert workspace.years["2025"].unresolved_candidates[0]["reason"] == "unsupported_rl8_donation"


def test_workspace_skips_duplicate_candidates_without_blocking_review_queue():
    accepted = _candidate(candidate_id="001")
    duplicate = _candidate(candidate_id="002", decision="duplicate", review_reasons=["exact_duplicate"])
    file_duplicate = _candidate(
        candidate_id="003",
        tax_year=None,
        decision="duplicate",
        review_reasons=["exact_duplicate"],
    )

    workspace = workspace_from_import(_import_result([accepted, duplicate, file_duplicate]))

    assert workspace.years["2025"].unresolved_candidates == []
    assert workspace.years["2025"].duplicate_candidates[0]["candidate_id"] == "002"
    assert workspace.duplicate_candidates[0]["candidate_id"] == "003"
    assert workspace.unassigned_candidates == []
    assert len(workspace.years["2025"].input["slips"]) == 1


def test_import_pdfs_endpoint_is_loopback_guarded_and_bounded(monkeypatch):
    candidate = _candidate(candidate_id="001")

    def fake_import(files, **kwargs):
        assert files == [("t4.pdf", b"%PDF-1.7 fake")]
        assert kwargs["max_files"] == local_app.MAX_BATCH_PDF_FILES
        return _import_result([candidate])

    monkeypatch.setattr(local_app, "import_pdf_batch", fake_import)
    client = _client()

    blocked = client.post(
        "/api/import-pdfs",
        files=[("files", ("t4.pdf", b"%PDF-1.7 fake", "application/pdf"))],
        headers={"Origin": "https://example.test"},
    )
    response = client.post(
        "/api/import-pdfs",
        files=[
            ("files", ("t4.pdf", b"%PDF-1.7 fake", "application/pdf")),
            ("files", ("notes.txt", b"not a pdf", "text/plain")),
        ],
    )

    assert blocked.status_code == 403
    assert response.status_code == 200
    body = response.json()
    assert body["import_result"]["candidates"][0]["fields"]["14"]["value"] == "45000.00"
    assert body["import_result"]["documents"][-1]["status"] == "unsupported"
    assert body["workspace"]["years"]["2025"]["input"]["slips"][0]["fields"]["14"] == "45000.00"
    assert body["workspace"]["years"]["2025"]["ready_to_calculate"] is False


def test_calculate_years_calls_engine_for_ready_2020_and_2025(monkeypatch):
    workspace = workspace_from_import(_import_result([_candidate(candidate_id="001")]))
    candidate_2020 = _candidate(candidate_id="002", tax_year=2020)
    workspace = workspace_from_import(_import_result([_candidate(candidate_id="001"), candidate_2020]))
    for year in ("2020", "2025"):
        workspace.years[year].missing_facts = []
        workspace.years[year].ready_to_calculate = True
    calls = []

    def fake_calculate(data):
        calls.append(data)
        return TaxReturnResult(
            status="complete",
            coverage_profile_id="2025-qc-test",
            ruleset_hash="b" * 64,
            federal_refund_or_balance=Decimal("1.00"),
            quebec_refund_or_balance=Decimal("2.00"),
            lines=[
                LineValue(
                    form_id="T1",
                    line_id="10100",
                    value=Decimal("45000.00"),
                    status="input",
                    inputs=["slips.0.fields.14"],
                )
            ],
        )

    monkeypatch.setattr("taxagent.intake.bridge.calculate_return", fake_calculate)
    response = _client().post("/api/calculate-years", json=workspace.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert [call.tax_year for call in calls] == [2020, 2025]
    assert body["status"] == "complete"
    assert body["results"]["2025"]["status"] == "complete"
    assert "2024" not in body["results"]


def test_calculate_years_blocks_when_unassigned_candidates_remain(monkeypatch):
    workspace = workspace_from_import(_import_result([_candidate(candidate_id="001")]))
    workspace.unassigned_candidates.append({"candidate_id": "unknown", "reason": "unsupported_or_missing_year"})
    workspace.years["2025"].missing_facts = []
    workspace.years["2025"].ready_to_calculate = True

    def fake_calculate(data):  # pragma: no cover - should not be called
        raise AssertionError("unassigned candidates must block calculate-all")

    monkeypatch.setattr("taxagent.intake.bridge.calculate_return", fake_calculate)
    response = _client().post("/api/calculate-years", json=workspace.model_dump(mode="json"))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["reason"] == "unassigned_candidates_require_review"


def test_2025_workspace_missing_facts_match_authoritative_calculation_queue():
    workspace = workspace_from_import(_import_result([_candidate(candidate_id="001")]))

    calculated = calculate_ready_years(workspace)

    assert workspace.years["2025"].missing_facts == calculated["results"]["2025"]["missing_facts"]


def test_calculate_years_rejects_nested_input_year_mismatch():
    workspace = workspace_from_import(_import_result([_candidate(candidate_id="001")]))
    payload = workspace.model_dump(mode="json")
    payload["years"]["2024"]["input"]["tax_year"] = 2025

    response = _client().post("/api/calculate-years", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_schema"


def test_calculate_years_rejects_year_key_mismatch():
    workspace = workspace_from_import(_import_result([_candidate(candidate_id="001")]))
    payload = workspace.model_dump(mode="json")
    payload["years"]["2024"]["tax_year"] = 2025

    response = _client().post("/api/calculate-years", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_schema"


def test_reconcile_correction_is_idempotent_and_keeps_original_provenance_and_user_facts():
    candidate = _candidate(
        candidate_id="review-me",
        slip_type=None,
        tax_year=None,
        decision="needs_review",
    )
    workspace = workspace_from_import(_import_result([candidate]))
    workspace.years["2024"].input["taxpayer"]["age_dec31"] = 23
    workspace.years["2024"].input["federal_tuition"]["has_prior_unused"] = True
    workspace.years["2024"].input["federal_tuition"]["prior_unused_amount"] = "975.00"
    request = {
        "workspace": workspace.model_dump(mode="json"),
        "active_years": [2024],
        "corrections": [{
            "candidate_id": "review-me",
            "tax_year": 2024,
            "slip_type": "T4",
            "issuer_id": "Corrected Employer",
            "fields": {"14": "40000.00"},
            "reason": "Verified against the source PDF.",
        }],
        "decisions": [{
            "candidate_id": "review-me",
            "action": "accept",
            "reason": "Type, year, issuer, and amount reviewed.",
        }],
    }

    first = _client().post("/api/reconcile-workspace", json=request)
    assert first.status_code == 200
    second_request = dict(request, workspace=first.json())
    second = _client().post("/api/reconcile-workspace", json=second_request)

    assert second.status_code == 200
    normalized = second.json()
    year = normalized["years"]["2024"]
    assert normalized["active_years"] == [2024]
    assert year["input"]["taxpayer"]["age_dec31"] == 23
    assert year["input"]["federal_tuition"]["prior_unused_amount"] == "975.00"
    assert len(year["input"]["slips"]) == 1
    assert year["input"]["slips"][0]["fields"]["14"] == "40000.00"
    assert year["evidence"]["review-me"]["fields"]["14"]["value"] == "45000.00"
    assert year["evidence"]["review-me"]["fields"]["14"]["accepted_value"] == "40000.00"
    assert len(normalized["correction_audit"]) == len(first.json()["correction_audit"])


def test_imported_t4e_reaches_real_annual_ei_calculation():
    from test_annual_returns import annual_input

    t4e = _candidate(
        candidate_id="service-canada",
        slip_type="T4E",
        tax_year=2022,
        issuer_id="Service Canada",
        fields={
            "14": _field("2000.00", "14"),
            "18": _field("0.00", "18"),
            "22": _field("200.00", "22"),
            "23": _field("100.00", "23"),
        },
    )
    workspace = workspace_from_import(_import_result([t4e]))
    imported_slip = workspace.years["2022"].input["slips"][0]
    data = annual_input(2022).model_dump(mode="json")
    data["slips"].append(imported_slip)
    workspace.years["2022"].input = data
    workspace.active_years = [2022]

    response = calculate_ready_years(workspace)

    assert imported_slip["slip_type"] == "T4E"
    assert response["results"]["2022"]["status"] == "complete"
    assert _result_line(response["results"]["2022"], "T1", "11900")["value"] == "2000.00"
    assert _result_line(response["results"]["2022"], "TP1", "111")["value"] == "2000.00"


def test_reconcile_recomputes_readiness_and_rejects_malicious_or_invalid_controls():
    workspace = workspace_from_import(_import_result([_candidate(candidate_id="001")]))
    payload = workspace.model_dump(mode="json")
    payload["years"]["2025"]["ready_to_calculate"] = True

    normalized = _client().post(
        "/api/reconcile-workspace",
        json={"workspace": payload, "active_years": [2025]},
    )
    duplicate_year = _client().post(
        "/api/reconcile-workspace",
        json={"workspace": payload, "active_years": [2025, 2025]},
    )
    malicious = _client().post(
        "/api/reconcile-workspace",
        json={
            "workspace": payload,
            "active_years": [2025],
            "decisions": [{
                "candidate_id": "001",
                "action": "accept",
                "reason": "reviewed",
                "ready_to_calculate": True,
            }],
        },
    )

    assert normalized.status_code == 200
    assert normalized.json()["years"]["2025"]["ready_to_calculate"] is False
    assert duplicate_year.status_code == 422
    assert malicious.status_code == 422


def test_explicit_no_income_active_year_reaches_the_real_annual_engine():
    from test_annual_returns import annual_input

    workspace = workspace_from_import(_import_result([]))
    data = annual_input(2020).model_dump(mode="json")
    data["slips"] = []
    data["inventory"]["no_income_sources"] = True
    workspace.years["2020"].input = data
    workspace.active_years = [2020]

    response = calculate_ready_years(workspace)

    assert response["status"] == "complete"
    assert set(response["results"]) == {"2020"}
    assert response["results"]["2020"]["status"] == "complete"


def test_two_successive_years_use_real_tuition_carryforward_chronologically():
    from test_annual_returns import annual_input

    workspace = workspace_from_import(_import_result([]))
    first = annual_input(2020, salary="20000")
    first.slips.append(
        first.slips[0].model_copy(update={
            "slip_type": "T2202",
            "document_id": "tuition-2020",
            "issuer_id": "school",
            "fields": {"24": Decimal("8"), "25": Decimal("0"), "26": Decimal("30000")},
        })
    )
    first.federal_tuition = first.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "t2202_eligible_fees": Decimal("30000"),
    })
    first.quebec_tuition = first.quebec_tuition.model_copy(update={
        "has_current_tuition": True,
        "institution_outside_quebec": False,
        "eligible_tuition_or_exam_receipts": Decimal("30000"),
    })
    second = annual_input(2021, salary="20000")
    second.federal_tuition = second.federal_tuition.model_copy(update={"has_prior_unused": None})
    second.quebec_tuition = second.quebec_tuition.model_copy(update={"has_prior_unused": None})
    workspace.years["2020"].input = first.model_dump(mode="json")
    workspace.years["2021"].input = second.model_dump(mode="json")
    workspace.active_years = [2020, 2021]

    response = calculate_ready_years(workspace)

    assert response["results"]["2020"]["status"] == "complete"
    assert response["results"]["2021"]["status"] == "complete"
    closing = response["results"]["2020"]["carryforwards"]["federal_tuition_unused_fees"]["amount"]
    assert Decimal(closing) == Decimal("25852.07")
    assert response["workspace"]["years"]["2021"]["input"]["federal_tuition"]["prior_unused_amount"] == closing
    assert response["workspace"]["years"]["2021"]["carryforwards"]["depends_on"]["tax_year"] == 2020


def test_assessed_carryforward_conflict_blocks_until_explicit_choice():
    from test_annual_returns import annual_input

    workspace = workspace_from_import(_import_result([]))
    first = annual_input(2020, salary="20000")
    first.slips.append(
        first.slips[0].model_copy(update={
            "slip_type": "T2202",
            "document_id": "tuition-2020",
            "issuer_id": "school",
            "fields": {"24": Decimal("8"), "25": Decimal("0"), "26": Decimal("30000")},
        })
    )
    first.federal_tuition = first.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "t2202_eligible_fees": Decimal("30000"),
    })
    second = annual_input(2021, salary="20000")
    second.federal_tuition = second.federal_tuition.model_copy(update={
        "has_prior_unused": True,
        "prior_unused_amount": Decimal("975"),
    })
    workspace.years["2020"].input = first.model_dump(mode="json")
    workspace.years["2021"].input = second.model_dump(mode="json")
    workspace.active_years = [2020, 2021]

    blocked = calculate_ready_years(workspace)
    conflict = blocked["workspace"]["years"]["2021"]["carryforwards"]["conflicts"][0]
    resolved = reconcile_workspace({
        "workspace": blocked["workspace"],
        "active_years": [2020, 2021],
        "carryforward_choices": [{
            "tax_year": 2021,
            "key": conflict["key"],
            "selection": "proposed",
            "reason": "Use the freshly calculated prior-year closing balance.",
        }],
    })
    complete = calculate_ready_years(resolved)

    assert blocked["results"]["2021"]["reason"] == "carryforward_conflict"
    assert complete["results"]["2021"]["status"] == "complete"
    assert complete["workspace"]["years"]["2021"]["carryforwards"]["conflicts"][0]["resolved_selection"] == "proposed"


def test_edited_assessed_opening_updates_conflict_and_invalidates_prior_choice():
    from test_annual_returns import annual_input

    workspace = workspace_from_import(_import_result([]))
    first = annual_input(2020, salary="20000")
    first.slips.append(
        first.slips[0].model_copy(update={
            "slip_type": "T2202",
            "document_id": "tuition-2020",
            "issuer_id": "school",
            "fields": {"24": Decimal("8"), "25": Decimal("0"), "26": Decimal("30000")},
        })
    )
    first.federal_tuition = first.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "t2202_eligible_fees": Decimal("30000"),
    })
    second = annual_input(2021, salary="20000")
    second.federal_tuition = second.federal_tuition.model_copy(update={
        "has_prior_unused": True,
        "prior_unused_amount": Decimal("975"),
    })
    workspace.years["2020"].input = first.model_dump(mode="json")
    workspace.years["2021"].input = second.model_dump(mode="json")
    workspace.active_years = [2020, 2021]
    blocked = calculate_ready_years(workspace)
    key = blocked["workspace"]["years"]["2021"]["carryforwards"]["conflicts"][0]["key"]
    resolved = reconcile_workspace({
        "workspace": blocked["workspace"],
        "active_years": [2020, 2021],
        "carryforward_choices": [{
            "tax_year": 2021,
            "key": key,
            "selection": "proposed",
            "reason": "Use the freshly calculated prior-year closing balance.",
        }],
    })
    complete = calculate_ready_years(resolved)
    edited = complete["workspace"]
    edited["years"]["2021"]["input"]["federal_tuition"]["has_prior_unused"] = True
    edited["years"]["2021"]["input"]["federal_tuition"]["prior_unused_amount"] = "1375"

    recalculated = calculate_ready_years(edited)
    conflict = recalculated["workspace"]["years"]["2021"]["carryforwards"]["conflicts"][0]

    assert recalculated["results"]["2021"]["reason"] == "carryforward_conflict"
    assert conflict["assessed_amount"] == "1375"
    assert conflict["resolved_selection"] is None
    assert any(
        item.get("kind") == "assessed_opening_update"
        and item.get("previous_assessed_amount") == "975"
        and item.get("new_assessed_amount") == "1375"
        for item in recalculated["workspace"]["correction_audit"]
    )


def test_explicit_assessed_zero_blocks_proposed_carryforward_overwrite():
    from test_annual_returns import annual_input

    workspace = workspace_from_import(_import_result([]))
    first = annual_input(2020, salary="20000")
    first.slips.append(
        first.slips[0].model_copy(update={
            "slip_type": "T2202",
            "document_id": "tuition-2020",
            "issuer_id": "school",
            "fields": {"24": Decimal("8"), "25": Decimal("0"), "26": Decimal("30000")},
        })
    )
    first.federal_tuition = first.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "t2202_eligible_fees": Decimal("30000"),
    })
    second = annual_input(2021, salary="20000")
    second.federal_tuition = second.federal_tuition.model_copy(update={
        "has_prior_unused": False,
        "prior_unused_amount": Decimal("0"),
    })
    workspace.years["2020"].input = first.model_dump(mode="json")
    workspace.years["2021"].input = second.model_dump(mode="json")
    workspace.active_years = [2020, 2021]

    response = calculate_ready_years(workspace)
    conflict = response["workspace"]["years"]["2021"]["carryforwards"]["conflicts"][0]

    assert response["results"]["2021"]["reason"] == "carryforward_conflict"
    assert conflict["assessed_amount"] == "0"
    assert response["workspace"]["years"]["2021"]["input"]["federal_tuition"]["prior_unused_amount"] == "0"


def test_upstream_input_edit_invalidates_stored_downstream_dependency():
    from test_annual_returns import annual_input

    workspace = workspace_from_import(_import_result([]))
    workspace.years["2020"].input = annual_input(2020).model_dump(mode="json")
    workspace.years["2021"].input = annual_input(2021).model_dump(mode="json")
    workspace.active_years = [2020, 2021]
    calculated = calculate_ready_years(workspace)["workspace"]
    calculated["years"]["2020"]["input"]["taxpayer"]["age_dec31"] = 25

    reconciled = reconcile_workspace({"workspace": calculated, "active_years": [2020, 2021]})

    assert reconciled.years["2021"].carryforwards["downstream_invalidated"] is True


def test_one_batch_action_runs_all_six_real_annual_calculations():
    from test_annual_returns import annual_input

    workspace = workspace_from_import(_import_result([]))
    for year in range(2020, 2025):
        workspace.years[str(year)].input = annual_input(year).model_dump(mode="json")
    workspace.years["2025"].input = local_app._sample_input().model_copy(
        update={"schema_version": "qc-return-v2"}
    ).model_dump(mode="json")
    workspace.active_years = list(range(2020, 2026))

    response = calculate_ready_years(workspace)

    assert list(response["results"]) == [str(year) for year in range(2020, 2026)]
    assert all(result["status"] == "complete" for result in response["results"].values())


def test_reconcile_exclusion_has_a_reasoned_global_disposition():
    candidate = _candidate(candidate_id="exclude-me", decision="needs_review")
    workspace = workspace_from_import(_import_result([candidate]))

    reconciled = reconcile_workspace({
        "workspace": workspace,
        "active_years": [2025],
        "decisions": [{
            "candidate_id": "exclude-me",
            "action": "exclude",
            "reason": "This PDF belongs to another taxpayer.",
        }],
    })

    assert reconciled.years["2025"].unresolved_candidates == []
    assert reconciled.excluded_candidates[0]["candidate_id"] == "exclude-me"
    assert reconciled.correction_audit[-1]["reason"] == "This PDF belongs to another taxpayer."


def test_t4a_short_resp_box_code_is_normalized_for_the_annual_engine():
    candidate = _candidate(
        candidate_id="resp",
        slip_type="T4A",
        fields={"42": _field("1500.00", "42")},
    )

    workspace = workspace_from_import(_import_result([candidate]))

    assert workspace.years["2025"].input["slips"][0]["fields"] == {"042": "1500.00"}
