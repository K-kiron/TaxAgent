from decimal import Decimal

import pytest
from pydantic import ValidationError

from taxagent.returns.quebec_schedules import (
    ScheduleDInput,
    ScheduleKInput,
    SchedulePInput,
    ScheduleTInput,
    calculate_schedule_d,
    calculate_schedule_k,
    calculate_schedule_p,
    calculate_schedule_t,
)


def test_schedule_k_blocks_unknown_month_coverage():
    result = calculate_schedule_k(ScheduleKInput(net_income_275=Decimal("40000")))

    assert not result.complete
    assert result.blockers[0].code == "K_MISSING_COVERAGE_MONTHS"
    assert result.lines["98"].status == "blocked"
    assert result.lines["98"].value is None


def test_schedule_k_low_income_uses_full_year_exemption_code_32():
    result = calculate_schedule_k(ScheduleKInput(net_income_275=Decimal("19890")))

    assert result.complete
    assert result.lines["32"].value is True
    assert "98" not in result.lines


def test_schedule_k_full_year_own_group_plan_uses_code_14():
    result = calculate_schedule_k(
        ScheduleKInput(
            net_income_275=Decimal("40000"),
            group_plan_months=set(range(1, 13)),
            group_plan_source="self",
            eligible_student_months=set(),
            other_exemption_applies=False,
        )
    )

    assert result.complete
    assert result.lines["14"].value is True
    assert "98" not in result.lines


def test_schedule_k_non_group_non_student_pays_2025_annual_maximum():
    result = calculate_schedule_k(
        ScheduleKInput(
            net_income_275=Decimal("40000"),
            group_plan_months=set(),
            eligible_student_months=set(),
            other_exemption_applies=False,
        )
    )

    assert result.complete
    assert result.lines["48"].value == Decimal("20110.00")
    assert result.lines["84"].value == Decimal("766.00")
    assert result.lines["98"].value == Decimal("755.00")


def test_schedule_k_student_exemption_months_apply_both_proration_limits():
    result = calculate_schedule_k(
        ScheduleKInput(
            net_income_275=Decimal("40000"),
            group_plan_months=set(),
            eligible_student_months={9, 10, 11, 12},
            other_exemption_applies=False,
        )
    )

    assert result.complete
    assert result.lines["60"].value == 0
    assert result.lines["61"].value == 4
    assert result.lines["85"].value == Decimal("255.33")
    assert result.lines["89"].value == Decimal("499.68")
    assert result.lines["98"].value == Decimal("499.68")


def _work_premium_input(**updates) -> SchedulePInput:
    values = {
        "resident_qc_dec31": True,
        "eligible_status": True,
        "age_eligible": True,
        "transferred_schedule_s_amount": False,
        "family_allowance_received_for_self": False,
        "designated_as_dependent_child": False,
        "full_time_student": False,
        "incarcerated_over_183_days": False,
        "adapted_work_premium_eligible": False,
        "supplement_months": 0,
        "request_tax_shield": False,
        "employment_income_101": Decimal("10000"),
        "positive_employment_correction_105": Decimal("0"),
        "former_employment_benefits_box_211": Decimal("0"),
        "other_employment_income_107": Decimal("0"),
        "net_research_grants": Decimal("0"),
        "schedule_l_positive_work_income": Decimal("0"),
        "wepp_income": Decimal("0"),
        "line_293_work_income": Decimal("0"),
        "net_income_275": Decimal("10000"),
    }
    values.update(updates)
    return SchedulePInput(**values)


def test_schedule_p_full_time_student_without_child_is_ineligible():
    result = calculate_schedule_p(SchedulePInput(full_time_student=True))

    assert result.complete
    assert result.lines["90"].value == Decimal("0.00")
    assert result.lines["90"].status == "zero"


def test_schedule_p_single_worker_calculates_ordinary_work_premium():
    result = calculate_schedule_p(_work_premium_input())

    assert result.complete
    assert result.lines["29"].value == Decimal("10000.00")
    assert result.lines["76"].value == Decimal("881.60")
    assert result.lines["90"].value == Decimal("881.60")


def test_schedule_p_reduces_credit_using_family_income():
    result = calculate_schedule_p(
        _work_premium_input(
            employment_income_101=Decimal("20000"),
            net_income_275=Decimal("20000"),
        )
    )

    assert result.complete
    assert result.lines["76"].value == Decimal("1185.52")
    assert result.lines["83"].value == Decimal("738.00")
    assert result.lines["90"].value == Decimal("447.52")


def test_schedule_p_blocks_missing_eligibility_instead_of_assuming_false():
    result = calculate_schedule_p(SchedulePInput())

    assert not result.complete
    assert result.blockers[0].code == "P_MISSING_ELIGIBILITY"


def _schedule_d_input(**updates) -> ScheduleDInput:
    values = {
        "age_eligible": True,
        "resident_qc_dec31": True,
        "eligible_immigration_status": True,
        "refugee_claimant_dec31": False,
        "incarcerated_over_183_days": False,
        "family_allowance_paid_for_user_december": False,
        "turned_18_in_december": False,
        "lived_alone_all_year": True,
        "address_same_as_return": True,
        "occupancy": "tenant",
        "rl31_dwelling_number": "1234567890",
        "rl31_occupant_number": "01",
    }
    values.update(updates)
    return ScheduleDInput(**values)


def test_schedule_d_prepares_tenant_information_without_inventing_benefit_amount():
    result = calculate_schedule_d(_schedule_d_input())

    assert result.complete
    assert result.lines["12"].value is True
    assert result.lines["32"].value == "1234567890"
    assert result.lines["33"].value == "01"
    assert set(result.lines) == {"12", "13", "32", "33"}


def test_schedule_d_blocks_missing_rl31_identifiers():
    result = calculate_schedule_d(_schedule_d_input(rl31_dwelling_number=None))

    assert not result.complete
    assert result.blockers[0].code == "D_MISSING_RL31"


def test_schedule_d_blocks_blank_rl31_identifiers():
    result = calculate_schedule_d(_schedule_d_input(rl31_dwelling_number=" "))

    assert not result.complete
    assert result.blockers[0].code == "D_MISSING_RL31"


def test_schedule_d_blocks_different_address_without_collecting_address_lines():
    result = calculate_schedule_d(_schedule_d_input(address_same_as_return=False))

    assert not result.complete
    assert result.blockers[0].code == "D_DIFFERENT_ADDRESS_UNSUPPORTED"
    assert set(result.lines) == {"12", "13"}


def test_schedule_d_blocks_blank_owner_roll_number():
    result = calculate_schedule_d(
        _schedule_d_input(
            occupancy="owner",
            rl31_dwelling_number=None,
            rl31_occupant_number=None,
            owner_has_municipal_tax_bill=True,
            owner_roll_number="",
            owners_in_dwelling=1,
        )
    )

    assert not result.complete
    assert result.blockers[0].code == "D_MISSING_OWNER_INFORMATION"


def test_schedule_d_owner_requires_tax_bill_status_before_roll_number_path():
    result = calculate_schedule_d(
        _schedule_d_input(
            occupancy="owner",
            rl31_dwelling_number=None,
            rl31_occupant_number=None,
            owner_roll_number="1234",
            owners_in_dwelling=1,
        )
    )

    assert not result.complete
    assert result.blockers[0].code == "D_MISSING_OWNER_TAX_BILL_STATUS"


def test_schedule_d_owner_without_municipal_tax_bill_is_explicitly_unsupported():
    result = calculate_schedule_d(
        _schedule_d_input(
            occupancy="owner",
            rl31_dwelling_number="1234567890",
            rl31_occupant_number="01",
            owner_has_municipal_tax_bill=False,
            owner_roll_number=None,
            owners_in_dwelling=1,
        )
    )

    assert not result.complete
    assert result.blockers[0].code == "D_OWNER_WITHOUT_MUNICIPAL_TAX_BILL_UNSUPPORTED"


def test_schedule_d_owner_count_must_be_positive():
    result = calculate_schedule_d(
        _schedule_d_input(
            occupancy="owner",
            rl31_dwelling_number=None,
            rl31_occupant_number=None,
            owner_has_municipal_tax_bill=True,
            owner_roll_number="1234",
            owners_in_dwelling=0,
        )
    )

    assert not result.complete
    assert result.blockers[0].code == "D_INVALID_OWNER_COUNT"


def test_schedule_d_known_ineligibility_is_not_a_missing_data_blocker():
    result = calculate_schedule_d(ScheduleDInput(resident_qc_dec31=False))

    assert result.complete
    assert result.lines["12"].status == "not_applicable"


def _schedule_t_input(**updates) -> ScheduleTInput:
    values = {
        "prior_20_percent_fees": Decimal("0"),
        "claim_20_percent_credit": Decimal("0"),
        "current_eligible_fees": Decimal("1000"),
        "institution_outside_quebec": False,
        "federal_training_credit_45350": Decimal("300"),
        "current_year_transfer_credit": Decimal("0"),
        "prior_8_percent_fees": Decimal("0"),
        "claim_8_percent_credit": Decimal("0"),
    }
    values.update(updates)
    return ScheduleTInput(**values)


def test_schedule_t_subtracts_federal_training_credit_before_quebec_credit():
    result = calculate_schedule_t(_schedule_t_input())

    assert result.complete
    assert result.lines["40.5"].value is False
    assert result.lines["41"].value == Decimal("700.00")
    assert result.lines["45"].value == Decimal("56.00")
    assert result.lines["48"].value == Decimal("700.00")


def test_schedule_t_claim_reduces_carryforward():
    result = calculate_schedule_t(_schedule_t_input(claim_8_percent_credit=Decimal("56")))

    assert result.complete
    assert result.lines["46"].value == Decimal("56.00")
    assert result.lines["48"].value == Decimal("0.00")


def test_schedule_t_uses_product_half_up_cents_for_fractional_cent_inputs():
    result = calculate_schedule_t(
        _schedule_t_input(
            current_eligible_fees=Decimal("1000.125"),
            federal_training_credit_45350=Decimal("0"),
        )
    )

    assert result.complete
    assert result.lines["40.6"].value == Decimal("1000.13")
    assert result.lines["45"].value == Decimal("80.01")
    assert result.lines["48"].value == Decimal("1000.13")


def test_schedule_t_blocks_ctc_greater_than_current_fees():
    result = calculate_schedule_t(
        _schedule_t_input(federal_training_credit_45350=Decimal("1000.01"))
    )

    assert not result.complete
    assert result.blockers[0].code == "T_CTC_EXCEEDS_FEES"


def test_schedule_t_missing_claim_choice_blocks_instead_of_using_zero():
    result = calculate_schedule_t(_schedule_t_input(claim_8_percent_credit=None))

    assert not result.complete
    assert result.blockers[0].code == "T_MISSING_AMOUNTS"


def test_schedule_t_blocks_missing_outside_quebec_answer_when_current_fees_apply():
    result = calculate_schedule_t(_schedule_t_input(institution_outside_quebec=None))

    assert not result.complete
    assert result.blockers[0].code == "T_MISSING_INSTITUTION_LOCATION"
    assert result.blockers[0].input_paths == ["institution_outside_quebec"]


def test_schedule_inputs_reject_unknown_and_coerced_fields_but_accept_decimal_strings():
    schedule = ScheduleTInput(
        prior_20_percent_fees="0",
        claim_20_percent_credit="0",
        current_eligible_fees="1000.25",
        institution_outside_quebec=False,
        federal_training_credit_45350="300",
        current_year_transfer_credit="0",
        prior_8_percent_fees="0",
        claim_8_percent_credit="0",
    )
    assert schedule.current_eligible_fees == Decimal("1000.25")

    with pytest.raises(ValidationError):
        ScheduleTInput(
            prior_20_percent_fees=Decimal("0"),
            claim_20_percent_credit=Decimal("0"),
            current_eligible_fees=Decimal("1000"),
            institution_outside_quebec=False,
            federal_training_credit_45350=Decimal("300"),
            current_year_transfer_credit=Decimal("0"),
            prior_8_percent_fees=Decimal("0"),
            claim_8_percent_credit=Decimal("0"),
            untrusted_extra=True,
        )

    with pytest.raises(ValidationError):
        ScheduleDInput(owners_in_dwelling=True)

    with pytest.raises(ValidationError):
        ScheduleDInput(age_eligible=1)

    with pytest.raises(ValidationError):
        ScheduleTInput(current_eligible_fees=Decimal("-0.01"))
