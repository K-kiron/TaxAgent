from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject, NumberObject, TextStringObject

from taxagent.intake.pdf import FormField, _canonical_form_field
from taxagent.web import local_app


RELEASE_DIR = Path(__file__).parent / "fixtures" / "pdf" / "official" / "generated" / "release"
OFFICIAL_DIR = Path(__file__).parent / "fixtures" / "pdf" / "official" / "official"


def _client() -> TestClient:
    return TestClient(local_app.app, base_url="http://127.0.0.1:8056")


def _release_pdf(name: str) -> bytes:
    return (RELEASE_DIR / name).read_bytes()


def _official_pdf(name: str) -> bytes:
    return (OFFICIAL_DIR / name).read_bytes()


def _filled_official_rl1_2024_with_case_s() -> bytes:
    reader = PdfReader(BytesIO(_official_pdf("rq-rl1-fill-2024.pdf")))
    if reader.is_encrypted:
        assert reader.decrypt("")
    writer = PdfWriter(clone_from=reader)
    writer.update_page_form_field_values(
        writer.pages[0],
        {
            "nom2": "EXAMPLE ROBOTICS INC.",
            "caseA": "40000.00",
            "caseB-A": "2336.00",
            "caseB-B": "0.00",
            "caseC": "528.00",
            "caseD": "0.00",
            "caseE": "0.00",
            "caseF": "0.00",
            "caseG": "40000.00",
            "caseH": "197.60",
            "caseI": "40000.00",
            "caseS": "1000.00",
        },
        auto_regenerate=False,
    )
    _append_text_field(writer, "case211", "0.00", (72, 42, 180, 58))
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _append_text_field(
    writer: PdfWriter,
    name: str,
    value: str,
    rect: tuple[float, float, float, float],
) -> None:
    page = writer.pages[0]
    field = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/FT"): NameObject("/Tx"),
            NameObject("/T"): TextStringObject(name),
            NameObject("/V"): TextStringObject(value),
            NameObject("/DV"): TextStringObject(value),
            NameObject("/DA"): TextStringObject("/Helv 8 Tf 0 g"),
            NameObject("/Rect"): ArrayObject([FloatObject(item) for item in rect]),
            NameObject("/F"): NumberObject(4),
        }
    )
    field_ref = writer._add_object(field)
    annotations = page.get(NameObject("/Annots"), ArrayObject())
    if hasattr(annotations, "get_object"):
        annotations = annotations.get_object()
    annotations.append(field_ref)
    page[NameObject("/Annots")] = annotations


def _apply_complete_2024_non_pdf_facts(data: dict) -> None:
    data["schema_version"] = "qc-return-v2"
    data["province_dec31"] = "QC"
    data["taxpayer"].update(
        {
            "full_year_canada_resident": True,
            "full_year_quebec_resident": True,
            "province_dec31": "QC",
            "age_dec31": 30,
            "marital_status": "single",
            "dependant_count": 0,
            "deceased_return": False,
            "bankruptcy_return": False,
            "has_self_employment": False,
            "has_capital_gains": False,
            "has_rental_income": False,
            "has_foreign_income_or_tax": False,
            "has_foreign_property_over_100k": False,
            "has_crypto_transactions": False,
            "has_pension_or_benefit_income": False,
            "has_indian_act_exempt_income": False,
            "has_disability_or_caregiver_claim": False,
            "has_employment_expenses": False,
            "has_medical_expenses": False,
            "has_donations": False,
            "has_childcare_expenses": False,
            "has_moving_expenses": False,
            "has_tips_or_other_employment_income": False,
            "has_student_loan_interest": False,
            "received_qpp_disability_pension": False,
            "made_qpp_cpt30_election": False,
            "was_full_time_student_more_than_13_weeks": False,
        }
    )
    data["inventory"].update(
        {
            "income_sources_reviewed": True,
            "deductions_reviewed": True,
            "credits_reviewed": True,
            "cra_records_reviewed": True,
            "revenu_quebec_records_reviewed": True,
            "no_income_sources": False,
        }
    )
    data["federal_tuition"].update(
        {
            "has_current_tuition": False,
            "has_prior_unused": False,
            "wants_transfer": False,
            "wants_canada_training_credit": False,
        }
    )
    data["quebec_tuition"].update(
        {
            "has_current_tuition": False,
            "institution_outside_quebec": False,
            "has_prior_unused": False,
            "wants_transfer": False,
        }
    )
    data["rrsp"].update(
        {
            "has_contributions": False,
            "has_prior_unused_contributions": False,
            "has_hbp_or_llp_activity": False,
        }
    )
    data["instalments"].update(
        {
            "federal_reviewed": True,
            "federal_paid": "0.00",
            "quebec_reviewed": True,
            "quebec_paid": "0.00",
        }
    )
    data["quebec_schedule_b"].update(
        {
            "living_alone_reviewed": True,
            "eligible_for_living_alone_amount": False,
        }
    )
    data["student_loan_interest"].update(
        {
            "reviewed": True,
            "qualifying_government_loans_confirmed": True,
            "federal_current_year_paid": "0.00",
            "federal_unused_by_origin_year": {
                "2019": "0.00",
                "2020": "0.00",
                "2021": "0.00",
                "2022": "0.00",
                "2023": "0.00",
            },
            "federal_unused_2020": "0.00",
            "federal_unused_2021": "0.00",
            "federal_unused_2022": "0.00",
            "federal_unused_2023": "0.00",
            "federal_claim_amount": "0.00",
            "quebec_prior_unused": "0.00",
            "quebec_current_year_paid": "0.00",
            "quebec_claim_amount": "0.00",
        }
    )
    data["scholarships"].update({"reviewed": True, "awards": [], "part_time_programs": []})
    data["resp_eap"].update(
        {
            "reviewed": True,
            "has_other_resp_payments": False,
            "qesi_cumulative_amount_over_3600": False,
            "payments": [],
        }
    )
    data.setdefault("pandemic_repayment", {}).update({"reviewed": False})
    data["additional_return_screens"].update(
        {
            "immigrated_or_emigrated_2025": False,
            "immigrated_or_emigrated_in_tax_year": False,
            "quebec_trust_return": False,
            "separate_post_death_return": False,
            "quebec_enterprise_registration_or_annual_fee": False,
        }
    )
    data["drug_insurance"].update(
        {
            "reviewed": True,
            "group_plan_months": list(range(1, 13)),
            "group_plan_source": "self",
            "eligible_student_months": [],
            "other_exemption_applies": False,
        }
    )
    data["refundable_credits"].update(
        {
            "work_premium_answers_reviewed": True,
            "solidarity_answers_reviewed": True,
            "canada_workers_benefit_answers_reviewed": True,
            "rl19_advance_payments_reviewed": True,
            "rl19_box_a": "0.00",
            "rl19_box_b": "0.00",
            "rl19_has_other_advance_boxes": False,
            "cwb_incarcerated_90_days": False,
            "cwb_foreign_officer_exempt": False,
            "advanced_cwb_paid": "0.00",
            "advanced_cwb_disability_paid": "0.00",
            "work_premium_eligible_status": True,
            "quebec_work_premium_full_time_student": False,
            "transferred_schedule_s_amount": False,
            "family_allowance_received_for_self": False,
            "turned_18_before_december": True,
            "designated_as_dependent_child": False,
            "incarcerated_over_183_days": False,
            "adapted_work_premium_eligible": False,
            "work_premium_supplement_months": 0,
            "request_tax_shield": False,
            "wants_solidarity_credit": False,
        }
    )


def test_public_calculate_blocks_positive_unsupported_official_rl1_widget() -> None:
    client = _client()
    imported = client.post(
        "/api/import-pdfs",
        files=[
            (
                "files",
                (
                    "release-official-t4-2024.pdf",
                    _release_pdf("release-official-t4-2024.pdf"),
                    "application/pdf",
                ),
            ),
            (
                "files",
                (
                    "official-rl1-2024-case-s-positive.pdf",
                    _filled_official_rl1_2024_with_case_s(),
                    "application/pdf",
                ),
            ),
        ],
    )
    assert imported.status_code == 200
    payload = imported.json()
    rl1 = next(
        candidate
        for candidate in payload["import_result"]["candidates"]
        if candidate["slip_type"] == "RL-1"
    )
    assert rl1["decision"] == "accepted_auto"
    assert rl1["fields"]["S"]["value"] == "1000.00"

    workspace = payload["workspace"]
    workspace["active_years"] = [2024]
    _apply_complete_2024_non_pdf_facts(workspace["years"]["2024"]["input"])

    calculated = client.post("/api/calculate-years", json=workspace)

    assert calculated.status_code == 200
    body = calculated.json()
    result = body["results"]["2024"]
    assert result["status"] == "blocked"
    assert any(fact["code"] == "unsupported_positive_slip_box" for fact in result["missing_facts"])
    assert any(fact["path"].endswith(".fields.S") for fact in result["missing_facts"])
    rebuilt_rl1 = next(
        slip for slip in body["workspace"]["years"]["2024"]["input"]["slips"] if slip["slip_type"] == "RL1"
    )
    assert rebuilt_rl1["fields"]["A"] == "40000.00"
    assert rebuilt_rl1["fields"]["B.A"] == "2336.00"
    assert rebuilt_rl1["fields"]["211"] == "0.00"
    assert rebuilt_rl1["fields"]["S"] == "1000.00"


def test_official_form_money_widgets_are_preserved_without_guessing_non_money_fields() -> None:
    source_text = "T4A Statement of Pension Retirement Annuity and Other Income"
    assert (
        _canonical_form_field(
            "T4A",
            FormField("Slip1Box205[0]", "123.45", 1, (1.0, 2.0, 3.0, 4.0), "Other income"),
            source_text,
        )
        == "Box 205 123.45"
    )
    assert (
        _canonical_form_field(
            "T4E",
            FormField("Slip1Box31[0]", "234.56", 1, (1.0, 2.0, 3.0, 4.0), "Other amount"),
            "T4E Statement of Employment Insurance and Other Benefits",
        )
        == "Box 31 234.56"
    )
    assert (
        _canonical_form_field(
            "RL-1",
            FormField("caseK", "345.67", 1, (1.0, 2.0, 3.0, 4.0), "K- Voyages"),
            "RL-1 Releve 1 Revenus emploi",
        )
        == "Case K 345.67"
    )
    assert (
        _canonical_form_field(
            "T4",
            FormField("Slip1Box61[0]", "456.78", 1, (1.0, 2.0, 3.0, 4.0), "Other amount"),
            "T4 Statement of Remuneration Paid",
        )
        == "Box 61 456.78"
    )
    assert (
        _canonical_form_field(
            "T4",
            FormField("Slip1Box61[0]", "2024-04-30", 1, None, "Date"),
            "T4 Statement of Remuneration Paid",
        )
        is None
    )
    assert (
        _canonical_form_field(
            "RL-1",
            FormField("nas", "123 456 789", 1, None, "NAS"),
            "RL-1 Releve 1 Revenus emploi",
        )
        is None
    )
