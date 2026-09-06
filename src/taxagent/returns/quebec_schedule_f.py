"""2025 Quebec Schedule F health-services-fund contribution."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .models import LineValue, ScheduleResult


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
THRESHOLD = Decimal("18130.00")
UPPER_THRESHOLD = Decimal("63060.00")
SOURCE_ID = "rq_2025_schedule_f"
ROUNDING_ID = "rq_2025_money_cents_half_up"
NonNegativeMoney = Annotated[Decimal, Field(ge=ZERO, allow_inf_nan=False)]
SignedMoney = Annotated[Decimal, Field(allow_inf_nan=False)]


class ScheduleFInput(BaseModel):
    """Every amount printed in Schedule F Part A, before its own subtotals."""

    model_config = ConfigDict(extra="forbid")

    total_income_199: NonNegativeMoney
    forest_averaging_276: NonNegativeMoney = ZERO
    employment_income_101: NonNegativeMoney = ZERO
    employment_correction_105: SignedMoney = ZERO
    profit_sharing_107_point3: NonNegativeMoney = ZERO
    old_age_security_114: NonNegativeMoney = ZERO
    taxable_dividends_128: NonNegativeMoney = ZERO
    actual_dividends_166_167: NonNegativeMoney = ZERO
    taxable_support_142: NonNegativeMoney = ZERO
    social_assistance_147: NonNegativeMoney = ZERO
    indemnities_and_supplements_148: NonNegativeMoney = ZERO
    ordinary_scholarships_154_point1: NonNegativeMoney = ZERO
    spousal_rrsp_recovery_122: NonNegativeMoney = ZERO
    excluded_other_income_154_points_2_5_12: NonNegativeMoney = ZERO
    eligible_repayments_246: NonNegativeMoney = ZERO
    wage_loss_repayment_207_point12: NonNegativeMoney = ZERO
    schedule_r_26: NonNegativeMoney = ZERO
    schedule_u_101: NonNegativeMoney = ZERO
    schedule_u_103: NonNegativeMoney = ZERO
    schedule_u_115: NonNegativeMoney = ZERO
    ei_repayment_250_point3: NonNegativeMoney = ZERO
    eligible_other_deductions_250: NonNegativeMoney = ZERO
    pension_transfer_245: NonNegativeMoney = ZERO
    deductible_support_225: NonNegativeMoney = ZERO
    carrying_charges_231: NonNegativeMoney = ZERO
    business_investment_loss_234: NonNegativeMoney = ZERO
    eligible_deduction_293: NonNegativeMoney = ZERO
    eligible_deduction_297: NonNegativeMoney = ZERO


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _line(line_id: str, value: Decimal, inputs: tuple[str, ...], formula_id: str) -> LineValue:
    value = _money(value)
    return LineValue(
        form_id="TP1-F",
        line_id=line_id,
        value=value,
        status="zero" if value == ZERO else "calculated",
        inputs=list(inputs),
        formula_id=formula_id,
        source_ids=[SOURCE_ID],
        rounding_id=ROUNDING_ID,
        explanation=f"Schedule F line {line_id} follows the printed 2025 form calculation.",
    )


def _na(line_id: str, reason: str) -> LineValue:
    return LineValue(
        form_id="TP1-F",
        line_id=line_id,
        status="not_applicable",
        source_ids=[SOURCE_ID],
        explanation=reason,
    )


def _stop(lines: dict[str, LineValue], remaining: tuple[str, ...], reason: str) -> ScheduleResult:
    lines.update({line_id: _na(line_id, reason) for line_id in remaining})
    lines["82"] = _line("82", ZERO, (), "schedule_f_no_contribution")
    return ScheduleResult(schedule_id="TP1-F", lines=lines)


def calculate_quebec_schedule_f(data: ScheduleFInput) -> ScheduleResult:
    """Calculate every reached printed row and preserve the form's early-stop branches."""

    line10 = _money(data.total_income_199 + data.forest_averaging_276)
    lines = {
        "10": _line("10", line10, ("TP1:199", "TP1:276:forest_averaging"), "total_income_plus_forest_averaging")
    }
    if line10 <= THRESHOLD:
        return _stop(
            lines,
            ("12", "14", "16", "18", "20", "22", "23", "24", "25", "26", "28", "29", "30", "31", "33", "34", "36", "41", "42", "43", "43.1", "44", "45", "46", "54", "56", "58", "60", "62", "68", "70", "76", "77", "78", "80", "81"),
            "Schedule F stops after line 10 because the amount is $18,130 or less.",
        )

    line16 = _money(data.employment_income_101 + data.employment_correction_105)
    line18 = _money(line10 - line16)
    lines.update(
        {
            "12": _line("12", data.employment_income_101, ("TP1:101",), "employment_income"),
            "14": _line("14", data.employment_correction_105, ("TP1:105",), "employment_income_correction"),
            "16": _line("16", line16, ("12", "14"), "employment_income_after_correction"),
            "18": _line("18", line18, ("10", "16"), "income_after_employment_exclusion"),
        }
    )
    if line18 <= THRESHOLD:
        return _stop(
            lines,
            ("20", "22", "23", "24", "25", "26", "28", "29", "30", "31", "33", "34", "36", "41", "42", "43", "43.1", "44", "45", "46", "54", "56", "58", "60", "62", "68", "70", "76", "77", "78", "80", "81"),
            "Schedule F stops after line 18 because the amount is $18,130 or less.",
        )

    line25 = _money(data.taxable_dividends_128 - data.actual_dividends_166_167)
    exclusion_values = {
        "20": (data.profit_sharing_107_point3, ("TP1:107:point3",), "profit_sharing_exclusion"),
        "22": (data.old_age_security_114, ("TP1:114",), "old_age_security_exclusion"),
        "23": (data.taxable_dividends_128, ("TP1:128",), "taxable_dividends"),
        "24": (data.actual_dividends_166_167, ("TP1:166", "TP1:167"), "actual_dividends"),
        "25": (line25, ("23", "24"), "dividend_gross_up_exclusion"),
        "26": (data.taxable_support_142, ("TP1:142",), "support_payments_exclusion"),
        "28": (data.social_assistance_147, ("TP1:147",), "social_assistance_exclusion"),
        "29": (data.indemnities_and_supplements_148, ("TP1:148",), "indemnities_exclusion"),
        "30": (data.ordinary_scholarships_154_point1, ("TP1:154:point1",), "scholarship_exclusion"),
        "31": (data.spousal_rrsp_recovery_122, ("TP1:122:spousal_rrsp_recovery",), "spousal_rrsp_recovery_exclusion"),
        "33": (data.excluded_other_income_154_points_2_5_12, ("TP1:154:points2_5_12",), "other_income_exclusion"),
    }
    lines.update(
        {
            line_id: _line(line_id, value, inputs, formula_id)
            for line_id, (value, inputs, formula_id) in exclusion_values.items()
        }
    )
    # Lines 23 and 24 feed their net amount at line 25; do not add them again.
    line34 = _money(
        data.profit_sharing_107_point3
        + data.old_age_security_114
        + line25
        + data.taxable_support_142
        + data.social_assistance_147
        + data.indemnities_and_supplements_148
        + data.ordinary_scholarships_154_point1
        + data.spousal_rrsp_recovery_122
        + data.excluded_other_income_154_points_2_5_12
    )
    line36 = _money(line18 - line34)
    lines["34"] = _line("34", line34, ("20", "22", "25", "26", "28", "29", "30", "31", "33"), "total_exclusions")
    lines["36"] = _line("36", line36, ("18", "34"), "income_after_exclusions")
    if line36 <= THRESHOLD:
        return _stop(
            lines,
            ("41", "42", "43", "43.1", "44", "45", "46", "54", "56", "58", "60", "62", "68", "70", "76", "77", "78", "80", "81"),
            "Schedule F stops after line 36 because the amount is $18,130 or less.",
        )

    deduction_values = {
        "41": (data.eligible_repayments_246, ("TP1:246",), "eligible_repayments"),
        "42": (data.wage_loss_repayment_207_point12, ("TP1:207:point12",), "wage_loss_repayment"),
        "43": (data.schedule_r_26, ("TP1-R:26",), "schedule_r_deduction"),
        "43.1": (data.schedule_u_101 + data.schedule_u_103 + data.schedule_u_115, ("TP1-U:101", "TP1-U:103", "TP1-U:115"), "schedule_u_deductions"),
        "44": (data.ei_repayment_250_point3, ("TP1:250:point3",), "ei_benefit_repayment"),
        "45": (data.eligible_other_deductions_250, ("TP1:250:points4_5_6_11_13_14_15",), "other_line_250_deductions"),
        "46": (data.pension_transfer_245, ("TP1:245",), "pension_transfer"),
        "54": (data.deductible_support_225, ("TP1:225",), "deductible_support"),
        "56": (data.carrying_charges_231, ("TP1:231",), "carrying_charges"),
        "58": (data.business_investment_loss_234, ("TP1:234",), "business_investment_loss"),
        "60": (data.eligible_deduction_293, ("TP1:293",), "eligible_line_293_deduction"),
        "62": (data.eligible_deduction_297, ("TP1:297",), "eligible_line_297_deduction"),
    }
    lines.update(
        {
            line_id: _line(line_id, value, inputs, formula_id)
            for line_id, (value, inputs, formula_id) in deduction_values.items()
        }
    )
    line68 = _money(sum((value[0] for value in deduction_values.values()), start=ZERO))
    line70 = _money(line36 - line68)
    lines["68"] = _line("68", line68, tuple(deduction_values), "total_deductions")
    lines["70"] = _line("70", line70, ("36", "68"), "income_subject_to_contribution")
    if line70 <= THRESHOLD:
        return _stop(
            lines,
            ("76", "77", "78", "80", "81"),
            "Schedule F Part B does not apply because line 70 is $18,130 or less.",
        )

    bracket_floor = THRESHOLD if line70 <= UPPER_THRESHOLD else UPPER_THRESHOLD
    base = ZERO if line70 <= UPPER_THRESHOLD else Decimal("150.00")
    maximum = Decimal("150.00") if line70 <= UPPER_THRESHOLD else Decimal("1000.00")
    line78 = max(_money(line70 - bracket_floor), ZERO)
    line80 = _money(line78 * Decimal("0.01"))
    contribution = min(_money(line80 + base), maximum)
    lines.update(
        {
            "76": _line("76", line70, ("70",), "income_subject_copy"),
            "77": _line("77", bracket_floor, (), "schedule_f_bracket_floor"),
            "78": _line("78", line78, ("76", "77"), "income_above_bracket_floor"),
            "80": _line("80", line80, ("78",), "one_percent_of_excess"),
            "81": _line("81", base, (), "schedule_f_bracket_base"),
            "82": _line("82", contribution, ("80", "81"), "health_services_fund_contribution"),
        }
    )
    return ScheduleResult(schedule_id="TP1-F", lines=lines)
