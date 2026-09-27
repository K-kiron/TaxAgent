import json
from decimal import Decimal
from pathlib import Path

from taxagent.returns import SlipInput, calculate_quebec
from taxagent.returns.quebec_schedule_f import ScheduleFInput, calculate_quebec_schedule_f

from test_federal_return import _input, _with_scholarship


EXPECTED_LINES = frozenset(
    json.loads((Path(__file__).parent / "fixtures" / "schedule_f_2025_lines.json").read_text())
)


def _calculate(*, total: str, salary: str = "0", scholarship: str = "0"):
    return calculate_quebec_schedule_f(
        ScheduleFInput(
            total_income_199=Decimal(total),
            employment_income_101=Decimal(salary),
            ordinary_scholarships_154_point1=Decimal(scholarship),
        )
    )


def test_interest_above_threshold_is_subject_to_schedule_f():
    result = _calculate(total="70000", salary="50000")

    assert set(result.lines) == EXPECTED_LINES
    assert result.lines["70"].value == Decimal("20000.00")
    assert result.lines["82"].value == Decimal("18.70")


def test_resp_eap_is_not_removed_from_schedule_f_income():
    result = _calculate(total="70000", salary="50000")

    assert result.lines["30"].value == Decimal("0.00")
    assert result.lines["70"].value == Decimal("20000.00")
    assert result.lines["82"].value == Decimal("18.70")


def test_ordinary_scholarship_is_removed_at_line_30():
    result = _calculate(total="70000", salary="50000", scholarship="20000")

    assert set(result.lines) == EXPECTED_LINES
    assert result.lines["30"].value == Decimal("20000.00")
    assert result.lines["36"].value == Decimal("0.00")
    assert result.lines["82"].value == Decimal("0.00")


def test_upper_bracket_fixture_and_each_official_deduction_row():
    data = ScheduleFInput(total_income_199=Decimal("70000"))
    result = calculate_quebec_schedule_f(data)

    assert result.lines["70"].value == Decimal("70000.00")
    assert result.lines["77"].value == Decimal("63060.00")
    assert result.lines["80"].value == Decimal("69.40")
    assert result.lines["81"].value == Decimal("150.00")
    assert result.lines["82"].value == Decimal("219.40")
    assert all(result.lines[line].value == Decimal("0.00") for line in ("41", "42", "43", "43.1", "44", "45", "46", "54", "56", "58", "60", "62"))


def test_each_deduction_input_flows_through_its_official_row_and_subtotal():
    result = calculate_quebec_schedule_f(
        ScheduleFInput(
            total_income_199=Decimal("100000"),
            eligible_repayments_246=Decimal("1"),
            wage_loss_repayment_207_point12=Decimal("1"),
            schedule_r_26=Decimal("1"),
            schedule_u_101=Decimal("1"),
            schedule_u_103=Decimal("2"),
            schedule_u_115=Decimal("3"),
            ei_repayment_250_point3=Decimal("1"),
            eligible_other_deductions_250=Decimal("1"),
            pension_transfer_245=Decimal("1"),
            deductible_support_225=Decimal("1"),
            carrying_charges_231=Decimal("1"),
            business_investment_loss_234=Decimal("1"),
            eligible_deduction_293=Decimal("1"),
            eligible_deduction_297=Decimal("1"),
        )
    )

    assert result.lines["43.1"].value == Decimal("6.00")
    assert result.lines["68"].value == Decimal("17.00")
    assert result.lines["70"].value == Decimal("99983.00")


def test_schedule_f_stops_at_the_printed_threshold():
    result = _calculate(total="18130")

    assert set(result.lines) == EXPECTED_LINES
    assert result.lines["12"].status == "not_applicable"
    assert result.lines["82"].value == Decimal("0.00")


def test_interest_flows_to_tp1_446_and_450():
    base = _input(employed=True)
    rl3 = SlipInput(
        slip_type="RL3",
        document_id="rl3-interest",
        issuer_id="bank-a",
        tax_year=2025,
        confirmed=True,
        fields={"D": Decimal("20000")},
    )
    result = calculate_quebec(base.model_copy(update={"slips": [*base.slips, rl3]}))

    assert result.lines["446"].value == Decimal("18.70")
    assert result.lines["450"].value == (
        result.lines["432"].value
        + result.lines["441"].value
        + Decimal("18.70")
        + result.lines["447"].value
    )


def test_ordinary_scholarship_exclusion_flows_to_zero_tp1_446():
    data = _with_scholarship(
        _input(employed=True, full_time_student=True),
        amount="20000",
        qualifying_student=True,
        attendance="full_time",
        intended_support="20000",
    )
    result = calculate_quebec(data)

    assert result.lines["F:30"].value == Decimal("20000.00")
    assert result.lines["446"].value == Decimal("0.00")
