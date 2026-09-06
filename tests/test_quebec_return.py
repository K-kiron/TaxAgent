from decimal import Decimal

import pytest

from taxagent.returns import (
    FederalTuitionInput,
    QuebecTuitionInput,
    calculate_qpp_schedule_u,
    calculate_quebec,
    preflight,
)
from taxagent.returns.quebec_2025 import calculate_quebec_schedule_b
from test_federal_return import _input, _with_resp_eap, _with_scholarship


def test_quebec_no_income_student_return_has_zero_tax_and_balance():
    result = calculate_quebec(_input(employed=False, full_time_student=True))

    assert result.complete
    assert result.lines["101"].value == Decimal("0.00")
    assert result.lines["199"].value == Decimal("0.00")
    assert result.lines["275"].value == Decimal("0.00")
    assert result.lines["299"].value == Decimal("0.00")
    assert result.lines["401"].value == Decimal("0.00")
    assert result.lines["447"].value == Decimal("0.00")
    assert result.lines["478"].value == Decimal("0.00")
    assert result.lines["479"].value == Decimal("0.00")


def test_quebec_employment_return_calculates_worker_deduction_and_refund():
    result = calculate_quebec(_input(employed=True))

    assert result.complete
    assert result.lines["97"].value == Decimal("247.00")
    assert result.lines["98"].value == Decimal("2976.00")
    assert result.lines["98.2"].value == Decimal("0.00")
    assert result.lines["101"].value == Decimal("50000.00")
    assert result.lines["201"].value == Decimal("1420.00")
    assert result.lines["248"].value == Decimal("465.00")
    assert result.lines["275"].value == Decimal("48115.00")
    assert result.lines["401"].value == Decimal("6736.10")
    assert result.lines["399"].value == Decimal("2599.94")
    assert result.lines["447"].value == Decimal("0.00")
    assert result.lines["456"].value == Decimal("0.00")
    assert result.lines["457"].value == Decimal("0.00")
    assert result.lines["478"].value == Decimal("863.84")
    assert result.lines["479"].value == Decimal("0.00")
    assert "K:14" in result.lines
    assert "P:90" in result.lines
    assert all(line.source_ids for line in result.lines.values())


def test_current_tuition_passes_institution_location_to_schedule_t():
    data = _input(employed=True).model_copy(
        update={
            "federal_tuition": FederalTuitionInput(
                has_current_tuition=True,
                t2202_eligible_fees=Decimal("4200"),
                has_prior_unused=False,
                wants_transfer=False,
                wants_canada_training_credit=False,
            ),
            "quebec_tuition": QuebecTuitionInput(
                has_current_tuition=True,
                institution_outside_quebec=False,
                eligible_tuition_or_exam_receipts=Decimal("4200"),
                has_prior_unused=False,
                wants_transfer=False,
            ),
        }
    )

    result = calculate_quebec(data)

    assert result.complete
    assert result.lines["T:40.5"].value is False
    assert result.lines["T:40.6"].value == Decimal("4200.00")


def test_schedule_u_uses_rl1_contributions_and_pensionable_wages():
    data = _input(employed=True)
    rl1 = data.slips[1].model_copy(
        update={
            "fields": {
                **data.slips[1].fields,
                "B.A": Decimal("2336.00"),
                "G": Decimal("40000.00"),
            }
        }
    )
    data = data.model_copy(update={"slips": [data.slips[0], rl1]})

    schedule = calculate_qpp_schedule_u(data)
    result = calculate_quebec(data)

    assert schedule.lines["23"].value == Decimal("365.00")
    assert result.complete
    assert result.lines["98.1"].value == Decimal("40000.00")
    assert result.lines["248"].value == Decimal("365.00")
    assert result.lines["U:23"].value == Decimal("365.00")


def test_schedule_u_preserves_raw_wages_for_second_qpp_band():
    data = _input(employed=True)
    rl1 = data.slips[1].model_copy(
        update={
            "fields": {
                **data.slips[1].fields,
                "B.A": Decimal("4339.20"),
                "B.B": Decimal("348.00"),
                "G": Decimal("80000.00"),
            }
        }
    )
    data = data.model_copy(update={"slips": [data.slips[0], rl1]})

    schedule = calculate_qpp_schedule_u(data)
    result = calculate_quebec(data)

    assert schedule.lines["12"].value == Decimal("71300.00")
    assert schedule.lines["18.5"].value == Decimal("80000.00")
    assert schedule.lines["16"].value == Decimal("678.00")
    assert schedule.lines["22"].value == Decimal("348.00")
    assert schedule.lines["23"].value == Decimal("1026.00")
    assert result.lines["248"].value == Decimal("1026.00")
    assert result.lines["248"].inputs == ["TP1-U:23"]
    assert result.lines["248"].source_ids == ["rq_2025_schedule_u"]


def test_quebec_instalments_are_included_on_line_453():
    data = _input(employed=True)
    data = data.model_copy(
        update={
            "instalments": data.instalments.model_copy(update={"quebec_paid": Decimal("300")})
        }
    )

    result = calculate_quebec(data)

    assert result.lines["453"].value == Decimal("300.00")
    assert result.lines["478"].value == Decimal("1163.84")


def test_schedule_b_living_alone_amount_uses_official_income_reduction():
    threshold = calculate_quebec_schedule_b(
        Decimal("42090.00"), eligible_for_living_alone_amount=True
    )
    phased_out = calculate_quebec_schedule_b(
        Decimal("53440.00"), eligible_for_living_alone_amount=True
    )

    assert {str(line) for line in (10, 12, 14, 15, 16, 18, 20, 21, 22, 23, 27, 28, 30, 31, 32, 33, 34)} <= threshold.lines.keys()
    assert threshold.lines["18"].value == Decimal("0.00")
    assert threshold.lines["20"].value == Decimal("2128.00")
    assert threshold.lines["34"].value == Decimal("2128.00")
    assert phased_out.lines["31"].value == Decimal("2128.13")
    assert phased_out.lines["34"].value == Decimal("0.00")


def test_quebec_living_alone_amount_flows_from_schedule_b_to_line_361():
    data = _input(employed=True)
    data.quebec_schedule_b = data.quebec_schedule_b.model_copy(
        update={"eligible_for_living_alone_amount": True}
    )

    result = calculate_quebec(data)

    assert result.lines["B:10"].value == result.lines["275"].value
    assert result.lines["361"].value == Decimal("998.31")
    assert result.lines["361"].inputs == ["TP1-B:34"]
    assert result.lines["399"].value == Decimal("2739.70")
    assert result.lines["478"].value == Decimal("1003.60")


def test_quebec_student_loan_interest_uses_schedule_m_and_20_percent_credit():
    data = _input(employed=True)
    data.taxpayer = data.taxpayer.model_copy(update={"has_student_loan_interest": True})
    data.student_loan_interest = data.student_loan_interest.model_copy(
        update={
            "federal_current_year_paid": Decimal("100.00"),
            "federal_unused_2020": Decimal("500.00"),
            "federal_claim_amount": Decimal("600.00"),
            "quebec_prior_unused": Decimal("500.00"),
            "quebec_current_year_paid": Decimal("100.00"),
            "quebec_claim_amount": Decimal("600.00"),
        }
    )

    result = calculate_quebec(data)

    assert result.lines["M:46"].value == Decimal("500.00")
    assert result.lines["M:48"].value == Decimal("100.00")
    assert result.lines["M:52"].value == Decimal("600.00")
    assert result.lines["M:60"].value == Decimal("600.00")
    assert result.lines["M:62"].value == Decimal("0.00")
    assert result.lines["385"].value == Decimal("600.00")
    assert result.lines["389"].value == Decimal("120.00")
    assert result.lines["399"].value == Decimal("2719.94")
    assert result.lines["478"].value == Decimal("983.84")


def test_quebec_ordinary_scholarship_is_income_then_line_295_deduction():
    data = _with_scholarship(
        _input(employed=False, full_time_student=True),
        amount="4500",
        qualifying_student=True,
        attendance="full_time",
        intended_support="4500",
    )

    result = calculate_quebec(data)

    assert result.lines["154"].value == Decimal("4500.00")
    assert result.lines["295"].value == Decimal("4500.00")
    assert result.lines["199"].value == Decimal("4500.00")
    assert result.lines["275"].value == Decimal("4500.00")
    assert result.lines["299"].value == Decimal("0.00")
    assert "U:23" not in result.lines


def test_quebec_resp_eap_is_code_03_other_income_without_scholarship_deduction():
    data = _with_resp_eap(_input(employed=False), amount="3000")

    result = calculate_quebec(data)

    assert result.complete
    assert result.lines["154"].value == Decimal("3000.00")
    assert result.lines["154.code"].value == "03"
    assert result.lines["199"].value == Decimal("3000.00")
    assert result.lines["275"].value == Decimal("3000.00")
    assert result.lines["295"].value == Decimal("0.00")
    assert result.lines["299"].value == Decimal("3000.00")


@pytest.mark.parametrize("income_kind", ["scholarship", "resp"])
def test_quebec_other_income_rl1_box_e_withholding_does_not_require_employment_box_a(
    income_kind,
):
    if income_kind == "scholarship":
        data = _with_scholarship(
            _input(employed=False, full_time_student=True),
            amount="3000",
            qualifying_student=True,
            attendance="full_time",
            intended_support="3000",
        )
        other_rl1 = next(slip for slip in data.slips if slip.slip_type == "RL1")
        data = data.model_copy(
            update={
                "slips": [
                    slip.model_copy(update={"fields": {**slip.fields, "E": Decimal("50")}})
                    if slip is other_rl1
                    else slip
                    for slip in data.slips
                ]
            }
        )
    else:
        data = _with_resp_eap(
            _input(employed=False), amount="3000", quebec_withholding="50"
        )

    assert preflight(data) == []
    assert calculate_quebec(data).lines["451"].value == Decimal("50.00")


def test_quebec_resp_eap_over_schedule_f_threshold_adds_line_446_contribution():
    result = calculate_quebec(_with_resp_eap(_input(employed=False), amount="20000"))

    assert result.lines["F:82"].value == Decimal("18.70")
    assert result.lines["446"].value == Decimal("18.70")
    assert "TP1-F:82" in result.lines["446"].inputs
    assert result.lines["450"].value == Decimal("218.76")


@pytest.mark.parametrize(
    ("earnings", "premium", "expected"),
    [
        ("1999.99", "100.00", "100.00"),
        ("2000.00", "100.00", "0.00"),
        ("50000.00", "484.12", "0.00"),
        ("50000.00", "484.13", "0.01"),
    ],
)
def test_quebec_qpip_overpayment_uses_only_taxpayer_entry_boundaries(
    earnings, premium, expected
):
    data = _input(employed=True)
    rl1 = next(slip for slip in data.slips if slip.slip_type == "RL1")
    updated_fields = {**rl1.fields, "I": Decimal(earnings), "H": Decimal(premium)}
    data = data.model_copy(
        update={
            "slips": [
                slip.model_copy(update={"fields": updated_fields})
                if slip is rl1
                else slip
                for slip in data.slips
            ]
        }
    )

    result = calculate_quebec(data)

    assert result.lines["457"].value == Decimal(expected)
    assert "Revenu Québec may calculate" in result.lines["457"].explanation
    assert result.lines["457"].source_ids == ["rq_2025_line_457"]
