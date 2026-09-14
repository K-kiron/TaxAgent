from decimal import Decimal
from pathlib import Path
import re

import pytest
from pydantic import ValidationError

from taxagent.returns import (
    CompletenessBlocker,
    DrugInsuranceInput,
    FederalTuitionInput,
    LineValue,
    QuebecTuitionInput,
    ScheduleResult,
    TaxReturnResult,
    TaxpayerFacts,
    RrspInput,
    SlipInput,
)
from taxagent.returns.sources import SOURCES, SourceRef
from taxagent.returns import gates


def test_coverage_answers_remain_unknown_until_user_confirms_them():
    facts = TaxpayerFacts()

    assert facts.full_year_canada_resident is None
    assert facts.full_year_quebec_resident is None
    assert facts.has_self_employment is None
    assert facts.has_capital_gains is None


def test_line_values_serialize_decimal_as_exact_strings():
    line = LineValue(
        form_id="T1",
        line_id="44000",
        value=Decimal("1234.50"),
        status="calculated",
        inputs=["T1:42900"],
        formula_id="t1_44000_qc_abatement_2025",
        source_ids=["cra_2025_5005_r"],
        rounding_id="cents_half_up",
    )

    assert '"value":"1234.50"' in line.model_dump_json()


def test_blocked_result_cannot_expose_refund_or_balance_headlines():
    blocker = CompletenessBlocker(
        code="unsupported_tax_year",
        message="Only the 2025 return is implemented.",
        input_paths=["tax_year"],
        source_ids=["cra_2025_5005_r"],
        resolution="Use authorized software for another year.",
    )

    with pytest.raises(ValidationError):
        TaxReturnResult(
            status="blocked",
            coverage_profile_id="2025-qc-salaried-student-v1",
            ruleset_hash="a" * 64,
            blockers=[blocker],
            federal_refund_or_balance=Decimal("10.00"),
        )


def test_federal_and_quebec_tuition_evidence_are_distinct():
    federal = FederalTuitionInput(
        has_current_tuition=True,
        t2202_eligible_fees=Decimal("5000.00"),
        prior_unused_amount=Decimal("1200.00"),
        canada_training_credit_limit=Decimal("250.00"),
    )
    quebec = QuebecTuitionInput(
        has_current_tuition=True,
        eligible_tuition_or_exam_receipts=Decimal("4800.00"),
        prior_unused_at_8_percent=Decimal("700.00"),
        prior_unused_at_20_percent=Decimal("0.00"),
    )

    assert federal.t2202_eligible_fees == Decimal("5000.00")
    assert quebec.eligible_tuition_or_exam_receipts == Decimal("4800.00")
    assert "rl8" not in " ".join(QuebecTuitionInput.model_fields).lower()


def test_schedule_result_is_incomplete_when_it_has_a_blocker():
    schedule = ScheduleResult(
        schedule_id="TP1-K",
        blockers=[
            CompletenessBlocker(
                code="missing_monthly_drug_coverage",
                message="Drug coverage is unknown for March.",
                input_paths=["drug_insurance.months.3"],
                source_ids=["rq_2025_schedule_k"],
                resolution="Confirm qualifying group coverage or an exemption for March.",
            )
        ],
    )

    assert schedule.complete is False


def test_source_manifest_contains_versioned_primary_forms():
    assert SOURCES["cra_2025_5005_r"].form_id == "5005-R"
    assert SOURCES["rq_2025_tp1"].form_id == "TP-1.D-V"
    assert SOURCES["cra_2025_t2204"].form_id == "T2204"
    assert not {
        "cra_2025_schedule_10",
        "cra_2025_schedule_11",
    } & SOURCES.keys()
    assert all(isinstance(source, SourceRef) for source in SOURCES.values())
    assert all(source.tax_year == 2025 and source.url.startswith("https://") for source in SOURCES.values())


def test_every_gate_source_id_is_registered():
    gate_source = Path(gates.__file__).read_text(encoding="utf-8")
    referenced = set(re.findall(r'"((?:cra|rq)_2025_[a-z0-9_]+)"', gate_source))

    assert referenced <= SOURCES.keys()


def test_public_models_reject_unknown_fields_and_invalid_money():
    with pytest.raises(ValidationError):
        TaxpayerFacts(has_unreported_income=False)

    with pytest.raises(ValidationError):
        RrspInput(has_contributions=True, contribution_receipts=Decimal("-1"))

    with pytest.raises(ValidationError):
        FederalTuitionInput(t2202_eligible_fees=Decimal("NaN"))


def test_complete_result_requires_both_final_balances():
    with pytest.raises(ValidationError):
        TaxReturnResult(
            status="complete",
            coverage_profile_id="2025-qc-salaried-student-v1",
            ruleset_hash="a" * 64,
            federal_refund_or_balance=Decimal("0.00"),
        )


def test_drug_insurance_months_are_strict_integers():
    with pytest.raises(ValidationError):
        DrugInsuranceInput(group_plan_months={True})
    with pytest.raises(ValidationError):
        DrugInsuranceInput(group_plan_months={"1"})

    parsed = DrugInsuranceInput.model_validate_json('{"group_plan_months":[1,12]}')
    assert parsed.group_plan_months == {1, 12}


def test_public_boolean_and_integer_answers_reject_coercion():
    with pytest.raises(ValidationError):
        TaxpayerFacts(has_capital_gains="false")
    with pytest.raises(ValidationError):
        TaxpayerFacts(dependant_count=True)
    with pytest.raises(ValidationError):
        SlipInput(
            slip_type="T5",
            document_id="t5",
            issuer_id="bank",
            tax_year="2025",
        )
