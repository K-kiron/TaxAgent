"""Deterministic 2025 Quebec schedules for the first supported return profile.

The formulas and printed line identifiers come from Revenu Quebec's 2025
Schedules K, P, D, and T.  These functions deliberately return blockers when a
required fact is unknown or when a branch is outside the first-release scope.
They never ask an LLM to calculate an amount and never turn missing data into 0.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from .models import CompletenessBlocker, LineValue, ScheduleResult

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
MONTHS = frozenset(range(1, 13))
ROUNDING_ID = "rq_2025_money_cents_half_up"

SOURCE_K = "rq_2025_schedule_k"
SOURCE_P = "rq_2025_schedule_p"
SOURCE_D = "rq_2025_schedule_d"
SOURCE_T = "rq_2025_schedule_t"
SOURCE_GUIDE = "rq_2025_tp1_guide"

NonNegativeMoney = Annotated[Decimal, Field(ge=ZERO, allow_inf_nan=False)]


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScheduleKInput(ScheduleInput):
    """Inputs for a single taxpayer with no spouse or dependent children."""

    net_income_275: NonNegativeMoney | None = None
    group_plan_months: set[StrictInt] | None = None
    group_plan_source: Literal["self", "parent"] | None = None
    eligible_student_months: set[StrictInt] | None = None
    other_exemption_applies: StrictBool | None = None


class SchedulePInput(ScheduleInput):
    """Inputs for the ordinary work premium of a single person without children."""

    resident_qc_dec31: StrictBool | None = None
    eligible_status: StrictBool | None = None
    age_eligible: StrictBool | None = None
    transferred_schedule_s_amount: StrictBool | None = None
    family_allowance_received_for_self: StrictBool | None = None
    turned_18_before_december: StrictBool | None = None
    designated_as_dependent_child: StrictBool | None = None
    full_time_student: StrictBool | None = None
    incarcerated_over_183_days: StrictBool | None = None
    adapted_work_premium_eligible: StrictBool | None = None
    supplement_months: StrictInt | None = None
    request_tax_shield: StrictBool | None = None

    employment_income_101: NonNegativeMoney | None = None
    positive_employment_correction_105: NonNegativeMoney | None = None
    former_employment_benefits_box_211: NonNegativeMoney | None = None
    other_employment_income_107: NonNegativeMoney | None = None
    net_research_grants: NonNegativeMoney | None = None
    schedule_l_positive_work_income: NonNegativeMoney | None = None
    wepp_income: NonNegativeMoney | None = None
    line_293_work_income: NonNegativeMoney | None = None
    net_income_275: NonNegativeMoney | None = None


class ScheduleDInput(ScheduleInput):
    """Eligibility and housing facts for Schedule D; RQ calculates the benefit."""

    age_eligible: StrictBool | None = None
    resident_qc_dec31: StrictBool | None = None
    eligible_immigration_status: StrictBool | None = None
    refugee_claimant_dec31: StrictBool | None = None
    incarcerated_over_183_days: StrictBool | None = None
    family_allowance_paid_for_user_december: StrictBool | None = None
    turned_18_in_december: StrictBool | None = None
    lived_alone_all_year: StrictBool | None = None
    address_same_as_return: StrictBool | None = None
    occupancy: Literal["tenant", "owner", "neither"] | None = None
    rl31_dwelling_number: str | None = None
    rl31_occupant_number: str | None = None
    owner_has_municipal_tax_bill: StrictBool | None = None
    owner_roll_number: str | None = None
    owners_in_dwelling: StrictInt | None = None


class ScheduleTInput(ScheduleInput):
    """Inputs for a student who does not transfer 2025 tuition to another person."""

    prior_20_percent_fees: NonNegativeMoney | None = None
    claim_20_percent_credit: NonNegativeMoney | None = None
    current_eligible_fees: NonNegativeMoney | None = None
    institution_outside_quebec: StrictBool | None = None
    federal_training_credit_45350: NonNegativeMoney | None = None
    current_year_transfer_credit: NonNegativeMoney | None = None
    prior_8_percent_fees: NonNegativeMoney | None = None
    claim_8_percent_credit: NonNegativeMoney | None = None


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _line(
    form_id: str,
    line_id: str,
    value: Decimal | int | str | bool | None,
    status: Literal["input", "calculated", "zero", "not_applicable", "blocked"],
    *,
    inputs: list[str] | None = None,
    formula_id: str | None = None,
    source_id: str,
    rounded: bool = False,
) -> LineValue:
    return LineValue(
        form_id=form_id,
        line_id=line_id,
        value=value,
        status=status,
        inputs=inputs or [],
        formula_id=formula_id,
        source_ids=[source_id],
        rounding_id=ROUNDING_ID if rounded else None,
    )


def _blocker(code: str, message: str, paths: list[str], source_id: str, resolution: str) -> CompletenessBlocker:
    return CompletenessBlocker(
        code=code,
        message=message,
        input_paths=paths,
        source_ids=[source_id],
        resolution=resolution,
    )


def _blocked(schedule_id: str, final_line: str, blockers: list[CompletenessBlocker], source_id: str) -> ScheduleResult:
    return ScheduleResult(
        schedule_id=schedule_id,
        lines={
            final_line: _line(
                schedule_id,
                final_line,
                None,
                "blocked",
                source_id=source_id,
            )
        },
        blockers=blockers,
    )


def _missing(data: BaseModel, fields: list[str]) -> list[str]:
    return [field for field in fields if getattr(data, field) is None]


def _blank_or_missing(data: BaseModel, fields: list[str]) -> list[str]:
    return [
        field
        for field in fields
        if getattr(data, field) is None or not str(getattr(data, field)).strip()
    ]


def _invalid_money(data: BaseModel, fields: list[str]) -> list[str]:
    return [field for field in fields if getattr(data, field) is not None and getattr(data, field) < 0]


def calculate_schedule_k(data: ScheduleKInput) -> ScheduleResult:
    """Calculate 2025 Schedule K for a single adult with no dependants."""

    if data.net_income_275 is None:
        return _blocked(
            "TP1-K",
            "98",
            [_blocker("K_MISSING_NET_INCOME", "Schedule K needs TP-1 line 275.", ["net_income_275"], SOURCE_K, "Complete TP-1 line 275.")],
            SOURCE_K,
        )
    if data.net_income_275 < 0:
        return _blocked(
            "TP1-K",
            "98",
            [_blocker("K_INVALID_NET_INCOME", "TP-1 line 275 cannot be negative for Schedule K.", ["net_income_275"], SOURCE_K, "Correct TP-1 line 275.")],
            SOURCE_K,
        )

    net_income = _money(data.net_income_275)
    if net_income <= Decimal("19890.00"):
        return ScheduleResult(
            schedule_id="TP1-K",
            lines={"32": _line("TP1-K", "32", True, "calculated", inputs=["net_income_275"], formula_id="k_full_year_low_income_exemption", source_id=SOURCE_K)},
        )

    missing = _missing(data, ["group_plan_months", "eligible_student_months", "other_exemption_applies"])
    if missing:
        return _blocked(
            "TP1-K",
            "98",
            [_blocker("K_MISSING_COVERAGE_MONTHS", "Schedule K needs an explicit status for every 2025 month.", missing, SOURCE_K, "Confirm group-plan, eligible full-time-student, and other exemption months.")],
            SOURCE_K,
        )
    if data.other_exemption_applies:
        return _blocked(
            "TP1-K",
            "98",
            [_blocker("K_OTHER_EXEMPTION_UNSUPPORTED", "Another Schedule K exemption applies outside the first-release profile.", ["other_exemption_applies"], SOURCE_K, "Review Schedule K lines 51-53 and 55-59 in authorized software.")],
            SOURCE_K,
        )

    group_months = set(data.group_plan_months or set())
    student_months = set(data.eligible_student_months or set())
    invalid_months = sorted((group_months | student_months) - MONTHS)
    if invalid_months:
        return _blocked(
            "TP1-K",
            "98",
            [_blocker("K_INVALID_MONTH", f"Invalid Schedule K month numbers: {invalid_months}.", ["group_plan_months", "eligible_student_months"], SOURCE_K, "Use month numbers 1 through 12.")],
            SOURCE_K,
        )
    if group_months and data.group_plan_source is None:
        return _blocked(
            "TP1-K",
            "98",
            [_blocker("K_MISSING_GROUP_PLAN_SOURCE", "The group-plan membership source is required.", ["group_plan_source"], SOURCE_K, "Confirm whether the plan membership was yours or a parent's.")],
            SOURCE_K,
        )
    if group_months == MONTHS:
        exemption_line = "14" if data.group_plan_source == "self" else "16"
        return ScheduleResult(
            schedule_id="TP1-K",
            lines={exemption_line: _line("TP1-K", exemption_line, True, "input", inputs=["group_plan_months", "group_plan_source"], source_id=SOURCE_K)},
        )

    exempt_months = group_months | student_months
    first_half = len(exempt_months & set(range(1, 7)))
    second_half = len(exempt_months & set(range(7, 13)))
    income_used = _money(max(net_income - Decimal("19890.00"), ZERO))

    if income_used <= Decimal("5000.00"):
        threshold = ZERO
        rate = Decimal("0.0784")
        base = ZERO
        premium_column = "A"
    elif income_used <= Decimal("14669.00"):
        threshold = Decimal("5000.00")
        rate = Decimal("0.1176")
        base = Decimal("392.00")
        premium_column = "B"
    else:
        threshold = Decimal("14669.00")
        rate = ZERO
        base = Decimal("766.00")
        premium_column = "maximum"

    line79 = _money(max(income_used - threshold, ZERO)) if premium_column != "maximum" else ZERO
    line81 = _money(line79 * rate) if premium_column != "maximum" else ZERO
    line83 = _money(min(line81 + base, Decimal("766.00")))
    line84 = line83
    line85 = _money(line84 * Decimal(len(exempt_months)) / Decimal(12))
    line86 = _money(max(line84 - line85, ZERO))
    line88 = _money(Decimal(first_half) * Decimal("62.00") + Decimal(second_half) * Decimal("63.83"))
    line89 = _money(max(Decimal("755.00") - line88, ZERO))
    line90 = _money(min(line86, line89))

    lines = {
        "36": _line("TP1-K", "36", net_income, "input", inputs=["net_income_275"], source_id=SOURCE_K),
        "40": _line("TP1-K", "40", net_income, "calculated", inputs=["36"], formula_id="k_40", source_id=SOURCE_K),
        "41": _line("TP1-K", "41", Decimal("19890.00"), "calculated", formula_id="k_single_exemption", source_id=SOURCE_K),
        "46": _line("TP1-K", "46", Decimal("19890.00"), "calculated", inputs=["41"], formula_id="k_46", source_id=SOURCE_K),
        "48": _line("TP1-K", "48", income_used, "calculated", inputs=["40", "46"], formula_id="k_income_used", source_id=SOURCE_K, rounded=True),
        "50": _line("TP1-K", "50", bool(group_months), "calculated", inputs=["group_plan_months"], formula_id="k_group_plan_applies", source_id=SOURCE_K),
        "54": _line("TP1-K", "54", bool(student_months), "calculated", inputs=["eligible_student_months"], formula_id="k_student_exemption_applies", source_id=SOURCE_K),
        "60": _line("TP1-K", "60", first_half, "calculated", inputs=["group_plan_months", "eligible_student_months"], formula_id="k_exempt_months_jan_jun", source_id=SOURCE_K),
        "61": _line("TP1-K", "61", second_half, "calculated", inputs=["group_plan_months", "eligible_student_months"], formula_id="k_exempt_months_jul_dec", source_id=SOURCE_K),
        "62": _line("TP1-K", "62", len(exempt_months), "calculated", inputs=["60", "61"], formula_id="k_total_exempt_months", source_id=SOURCE_K),
        "77": _line("TP1-K", "77", income_used, "calculated", inputs=["48"], formula_id="k_77", source_id=SOURCE_K),
        "78": _line("TP1-K", "78", threshold, "calculated", inputs=["48"], formula_id=f"k_column_{premium_column}_threshold", source_id=SOURCE_K),
        "79": _line("TP1-K", "79", line79, "calculated", inputs=["77", "78"], formula_id="k_79", source_id=SOURCE_K, rounded=True),
        "80": _line("TP1-K", "80", rate, "calculated", inputs=["48"], formula_id=f"k_column_{premium_column}_rate", source_id=SOURCE_K),
        "81": _line("TP1-K", "81", line81, "calculated", inputs=["79", "80"], formula_id="k_81", source_id=SOURCE_K, rounded=True),
        "82": _line("TP1-K", "82", base, "calculated", inputs=["48"], formula_id=f"k_column_{premium_column}_base", source_id=SOURCE_K),
        "83": _line("TP1-K", "83", line83, "calculated", inputs=["81", "82"], formula_id="k_83_max_766", source_id=SOURCE_K, rounded=True),
        "84": _line("TP1-K", "84", line84, "calculated", inputs=["83"], formula_id="k_84", source_id=SOURCE_K),
        "85": _line("TP1-K", "85", line85, "calculated", inputs=["84", "62"], formula_id="k_85_exempt_month_share", source_id=SOURCE_K, rounded=True),
        "86": _line("TP1-K", "86", line86, "calculated" if line86 else "zero", inputs=["84", "85"], formula_id="k_86", source_id=SOURCE_K, rounded=True),
        "87": _line("TP1-K", "87", Decimal("755.00"), "calculated", formula_id="k_2025_annual_max", source_id=SOURCE_K),
        "88": _line("TP1-K", "88", line88, "calculated" if line88 else "zero", inputs=["60", "61"], formula_id="k_monthly_max_reduction", source_id=SOURCE_K, rounded=True),
        "89": _line("TP1-K", "89", line89, "calculated" if line89 else "zero", inputs=["87", "88"], formula_id="k_89", source_id=SOURCE_K, rounded=True),
        "90": _line("TP1-K", "90", line90, "calculated" if line90 else "zero", inputs=["86", "89"], formula_id="k_lesser_proration", source_id=SOURCE_K, rounded=True),
        "98": _line("TP1-K", "98", line90, "calculated" if line90 else "zero", inputs=["90"], formula_id="k_premium_payable", source_id=SOURCE_K, rounded=True),
    }
    return ScheduleResult(schedule_id="TP1-K", lines=lines)


def calculate_schedule_p(data: SchedulePInput) -> ScheduleResult:
    """Calculate the ordinary 2025 work premium for the supported single profile."""

    eligibility_fields = [
        "resident_qc_dec31",
        "eligible_status",
        "age_eligible",
        "transferred_schedule_s_amount",
        "family_allowance_received_for_self",
        "designated_as_dependent_child",
        "full_time_student",
        "incarcerated_over_183_days",
        "adapted_work_premium_eligible",
        "supplement_months",
        "request_tax_shield",
    ]
    disqualified = (
        data.resident_qc_dec31 is False
        or data.eligible_status is False
        or data.age_eligible is False
        or data.transferred_schedule_s_amount is True
        or (
            data.family_allowance_received_for_self is True
            and data.turned_18_before_december is False
        )
        or data.designated_as_dependent_child is True
        or data.full_time_student is True
        or data.incarcerated_over_183_days is True
    )
    if disqualified:
        return ScheduleResult(
            schedule_id="TP1-P",
            lines={"90": _line("TP1-P", "90", ZERO, "zero", inputs=eligibility_fields, formula_id="p_basic_eligibility", source_id=SOURCE_GUIDE)},
        )

    if data.family_allowance_received_for_self is True and data.turned_18_before_december is None:
        return _blocked(
            "TP1-P",
            "90",
            [_blocker("P_MISSING_FAMILY_ALLOWANCE_EXCEPTION", "Work-premium eligibility depends on whether the taxpayer turned 18 before December 1, 2025.", ["turned_18_before_december"], SOURCE_GUIDE, "Confirm the taxpayer's eighteenth-birthday timing.")],
            SOURCE_P,
        )

    missing = _missing(data, eligibility_fields)
    if missing:
        return _blocked(
            "TP1-P",
            "90",
            [_blocker("P_MISSING_ELIGIBILITY", "Work-premium eligibility facts are incomplete.", missing, SOURCE_GUIDE, "Answer every line-456 eligibility question.")],
            SOURCE_P,
        )
    if data.adapted_work_premium_eligible:
        return _blocked(
            "TP1-P",
            "90",
            [_blocker("P_ADAPTED_PREMIUM_UNSUPPORTED", "The adapted work premium requires Schedule P column 2.", ["adapted_work_premium_eligible"], SOURCE_P, "Use authorized software for the adapted work premium.")],
            SOURCE_P,
        )
    if (data.supplement_months or 0) < 0 or (data.supplement_months or 0) > 12:
        return _blocked(
            "TP1-P",
            "90",
            [_blocker("P_INVALID_SUPPLEMENT_MONTHS", "Supplement months must be from 0 to 12.", ["supplement_months"], SOURCE_P, "Correct the number of months.")],
            SOURCE_P,
        )
    if (data.supplement_months or 0) > 0:
        return _blocked(
            "TP1-P",
            "90",
            [_blocker("P_SUPPLEMENT_UNSUPPORTED", "The supplement to the work premium requires RL-5 transition facts.", ["supplement_months"], SOURCE_P, "Use authorized software for the work-premium supplement.")],
            SOURCE_P,
        )

    amount_fields = [
        "employment_income_101",
        "positive_employment_correction_105",
        "former_employment_benefits_box_211",
        "other_employment_income_107",
        "net_research_grants",
        "schedule_l_positive_work_income",
        "wepp_income",
        "line_293_work_income",
        "net_income_275",
    ]
    missing = _missing(data, amount_fields)
    if missing:
        return _blocked(
            "TP1-P",
            "90",
            [_blocker("P_MISSING_AMOUNTS", "Schedule P work-income amounts are incomplete.", missing, SOURCE_P, "Enter each amount explicitly, including supported zero amounts.")],
            SOURCE_P,
        )
    invalid = _invalid_money(data, amount_fields)
    if invalid:
        return _blocked(
            "TP1-P",
            "90",
            [_blocker("P_INVALID_AMOUNTS", "Schedule P amounts cannot be negative in the supported profile.", invalid, SOURCE_P, "Correct the affected amounts.")],
            SOURCE_P,
        )

    line10 = _money(
        (data.employment_income_101 or ZERO)
        + (data.positive_employment_correction_105 or ZERO)
        - (data.former_employment_benefits_box_211 or ZERO)
    )
    if line10 < 0:
        return _blocked(
            "TP1-P",
            "90",
            [_blocker("P_NEGATIVE_LINE_10", "Schedule P line 10 would be negative.", ["employment_income_101", "positive_employment_correction_105", "former_employment_benefits_box_211"], SOURCE_P, "Review RL-1 box 211 and employment income.")],
            SOURCE_P,
        )
    line18 = _money(
        line10
        + (data.other_employment_income_107 or ZERO)
        + (data.net_research_grants or ZERO)
        + (data.schedule_l_positive_work_income or ZERO)
        + (data.wepp_income or ZERO)
    )
    line29 = _money(max(line18 - (data.line_293_work_income or ZERO), ZERO))
    family_income = _money(data.net_income_275 or ZERO)

    line68 = min(line29, Decimal("12620.00"))
    line72 = _money(max(line68 - Decimal("2400.00"), ZERO))
    line76 = _money(line72 * Decimal("0.116"))
    line82 = _money(max(family_income - Decimal("12620.00"), ZERO))
    line83 = _money(line82 * Decimal("0.10"))
    line84 = _money(max(line76 - line83, ZERO))
    # The guide states that a single person with family income >= $24,475 is
    # not entitled, even if cent-level form arithmetic would leave a few cents.
    line87 = ZERO if family_income >= Decimal("24475.00") or line29 <= Decimal("2400.00") else line84

    lines = {
        "5": _line("TP1-P", "5", bool(data.request_tax_shield), "input", inputs=["request_tax_shield"], source_id=SOURCE_GUIDE),
        "10": _line("TP1-P", "10", line10, "calculated", inputs=["employment_income_101", "positive_employment_correction_105", "former_employment_benefits_box_211"], formula_id="p_employment_income", source_id=SOURCE_P, rounded=True),
        "12": _line("TP1-P", "12", _money(data.other_employment_income_107 or ZERO), "input", inputs=["other_employment_income_107"], source_id=SOURCE_P),
        "13": _line("TP1-P", "13", _money(data.net_research_grants or ZERO), "input", inputs=["net_research_grants"], source_id=SOURCE_P),
        "14": _line("TP1-P", "14", _money(data.schedule_l_positive_work_income or ZERO), "input", inputs=["schedule_l_positive_work_income"], source_id=SOURCE_P),
        "15": _line("TP1-P", "15", _money(data.wepp_income or ZERO), "input", inputs=["wepp_income"], source_id=SOURCE_P),
        "18": _line("TP1-P", "18", line18, "calculated", inputs=["10", "12", "13", "14", "15"], formula_id="p_total_work_sources", source_id=SOURCE_P, rounded=True),
        "22": _line("TP1-P", "22", _money(data.line_293_work_income or ZERO), "input", inputs=["line_293_work_income"], source_id=SOURCE_P),
        "29": _line("TP1-P", "29", line29, "calculated", inputs=["18", "22"], formula_id="p_work_income", source_id=SOURCE_P, rounded=True),
        "52": _line("TP1-P", "52", family_income, "input", inputs=["net_income_275"], source_id=SOURCE_P),
        "54": _line("TP1-P", "54", family_income, "calculated", inputs=["52"], formula_id="p_single_family_income", source_id=SOURCE_P),
        "64": _line("TP1-P", "64", line29, "calculated", inputs=["29"], formula_id="p_64", source_id=SOURCE_P),
        "66": _line("TP1-P", "66", Decimal("12620.00"), "calculated", formula_id="p_single_work_cap", source_id=SOURCE_P),
        "68": _line("TP1-P", "68", line68, "calculated", inputs=["64", "66"], formula_id="p_68", source_id=SOURCE_P),
        "70": _line("TP1-P", "70", Decimal("2400.00"), "calculated", formula_id="p_single_work_floor", source_id=SOURCE_P),
        "72": _line("TP1-P", "72", line72, "calculated" if line72 else "zero", inputs=["68", "70"], formula_id="p_72", source_id=SOURCE_P, rounded=True),
        "74": _line("TP1-P", "74", Decimal("0.116"), "calculated", formula_id="p_single_no_child_rate", source_id=SOURCE_P),
        "76": _line("TP1-P", "76", line76, "calculated" if line76 else "zero", inputs=["72", "74"], formula_id="p_gross_work_premium", source_id=SOURCE_P, rounded=True),
        "78": _line("TP1-P", "78", family_income, "calculated", inputs=["54"], formula_id="p_78", source_id=SOURCE_P),
        "80": _line("TP1-P", "80", Decimal("12620.00"), "calculated", formula_id="p_single_reduction_threshold", source_id=SOURCE_P),
        "82": _line("TP1-P", "82", line82, "calculated" if line82 else "zero", inputs=["78", "80"], formula_id="p_82", source_id=SOURCE_P, rounded=True),
        "83": _line("TP1-P", "83", line83, "calculated" if line83 else "zero", inputs=["82"], formula_id="p_reduction_10_percent", source_id=SOURCE_P, rounded=True),
        "84": _line("TP1-P", "84", line84, "calculated" if line84 else "zero", inputs=["76", "83"], formula_id="p_84", source_id=SOURCE_P, rounded=True),
        "87": _line("TP1-P", "87", line87, "calculated" if line87 else "zero", inputs=["84", "54", "29"], formula_id="p_single_eligibility_limits", source_id=SOURCE_GUIDE, rounded=True),
        "88": _line("TP1-P", "88", ZERO, "zero", inputs=["supplement_months"], formula_id="p_no_supplement", source_id=SOURCE_P),
        "89": _line("TP1-P", "89", line87, "calculated" if line87 else "zero", inputs=["87"], formula_id="p_89", source_id=SOURCE_P),
        "90": _line("TP1-P", "90", line87, "calculated" if line87 else "zero", inputs=["88", "89"], formula_id="p_credit_total", source_id=SOURCE_P, rounded=True),
    }
    return ScheduleResult(schedule_id="TP1-P", lines=lines)


def calculate_schedule_d(data: ScheduleDInput) -> ScheduleResult:
    """Prepare Schedule D information; Revenu Quebec calculates and pays the credit."""

    eligibility_fields = [
        "age_eligible",
        "resident_qc_dec31",
        "eligible_immigration_status",
        "refugee_claimant_dec31",
        "incarcerated_over_183_days",
        "family_allowance_paid_for_user_december",
    ]
    if data.family_allowance_paid_for_user_december is True:
        eligibility_fields.append("turned_18_in_december")
    disqualified = (
        data.age_eligible is False
        or data.resident_qc_dec31 is False
        or data.eligible_immigration_status is False
        or data.refugee_claimant_dec31 is True
        or data.incarcerated_over_183_days is True
        or (data.family_allowance_paid_for_user_december is True and data.turned_18_in_december is False)
    )
    if disqualified:
        return ScheduleResult(
            schedule_id="TP1-D",
            lines={"12": _line("TP1-D", "12", None, "not_applicable", inputs=eligibility_fields, formula_id="d_eligibility", source_id=SOURCE_D)},
        )

    missing = _missing(data, eligibility_fields)
    if missing:
        return _blocked(
            "TP1-D",
            "12",
            [_blocker("D_MISSING_ELIGIBILITY", "Solidarity-credit eligibility facts are incomplete.", missing, SOURCE_D, "Confirm every Schedule D eligibility fact for December 31, 2025.")],
            SOURCE_D,
        )
    info_missing = _missing(data, ["lived_alone_all_year", "address_same_as_return", "occupancy"])
    if info_missing:
        return _blocked(
            "TP1-D",
            "12",
            [_blocker("D_MISSING_INFORMATION", "Schedule D residence information is incomplete.", info_missing, SOURCE_D, "Complete the Schedule D residence questions.")],
            SOURCE_D,
        )

    lines: dict[str, LineValue] = {
        "12": _line("TP1-D", "12", bool(data.lived_alone_all_year), "input", inputs=["lived_alone_all_year"], source_id=SOURCE_D),
        "13": _line("TP1-D", "13", bool(data.address_same_as_return), "input", inputs=["address_same_as_return"], source_id=SOURCE_D),
    }
    if data.address_same_as_return is False:
        return ScheduleResult(
            schedule_id="TP1-D",
            lines=lines,
            blockers=[
                _blocker(
                    "D_DIFFERENT_ADDRESS_UNSUPPORTED",
                    "Schedule D lines 14-16 require a different dwelling address, which is outside the first-release profile.",
                    ["address_same_as_return"],
                    SOURCE_D,
                    "Complete Schedule D address lines 14-16 in authorized software.",
                )
            ],
        )

    if data.occupancy == "tenant":
        missing = _blank_or_missing(data, ["rl31_dwelling_number", "rl31_occupant_number"])
        if missing:
            return ScheduleResult(
                schedule_id="TP1-D",
                lines=lines,
                blockers=[_blocker("D_MISSING_RL31", "A tenant needs both RL-31 identifiers for Schedule D.", missing, SOURCE_D, "Obtain the 2025 RL-31 from the landlord and enter boxes A and B.")],
            )
        lines["32"] = _line("TP1-D", "32", data.rl31_dwelling_number, "input", inputs=["rl31_dwelling_number"], source_id=SOURCE_D)
        lines["33"] = _line("TP1-D", "33", data.rl31_occupant_number, "input", inputs=["rl31_occupant_number"], source_id=SOURCE_D)
    elif data.occupancy == "owner":
        if data.owner_has_municipal_tax_bill is None:
            return ScheduleResult(
                schedule_id="TP1-D",
                lines=lines,
                blockers=[
                    _blocker(
                        "D_MISSING_OWNER_TAX_BILL_STATUS",
                        "Owner Schedule D handling depends on whether the dwelling has a municipal tax bill.",
                        ["owner_has_municipal_tax_bill"],
                        SOURCE_D,
                        "Confirm whether the owner received a municipal tax bill for the dwelling.",
                    )
                ],
            )
        if data.owner_has_municipal_tax_bill is False:
            return ScheduleResult(
                schedule_id="TP1-D",
                lines=lines,
                blockers=[
                    _blocker(
                        "D_OWNER_WITHOUT_MUNICIPAL_TAX_BILL_UNSUPPORTED",
                        "Owner dwellings without a municipal tax bill require a Schedule D branch outside the first-release profile.",
                        ["owner_has_municipal_tax_bill"],
                        SOURCE_D,
                        "Complete the no-municipal-tax-bill owner branch in authorized software.",
                    )
                ],
            )
        missing = _blank_or_missing(data, ["owner_roll_number", "owners_in_dwelling"])
        if missing:
            return ScheduleResult(
                schedule_id="TP1-D",
                lines=lines,
                blockers=[_blocker("D_MISSING_OWNER_INFORMATION", "An owner needs the roll number and number of resident owners.", missing, SOURCE_D, "Enter the municipal-tax-bill information for Schedule D.")],
            )
        if (data.owners_in_dwelling or 0) < 1:
            return ScheduleResult(
                schedule_id="TP1-D",
                lines=lines,
                blockers=[_blocker("D_INVALID_OWNER_COUNT", "The number of owners living in the dwelling must be at least 1.", ["owners_in_dwelling"], SOURCE_D, "Correct Schedule D line 36.")],
            )
        lines["35"] = _line("TP1-D", "35", data.owner_roll_number, "input", inputs=["owner_roll_number"], source_id=SOURCE_D)
        lines["36"] = _line("TP1-D", "36", data.owners_in_dwelling, "input", inputs=["owners_in_dwelling"], source_id=SOURCE_D)

    return ScheduleResult(schedule_id="TP1-D", lines=lines)


def calculate_schedule_t(data: ScheduleTInput) -> ScheduleResult:
    """Calculate 2025 Schedule T Part A for a student making no transfer."""

    fields = [
        "prior_20_percent_fees",
        "claim_20_percent_credit",
        "current_eligible_fees",
        "federal_training_credit_45350",
        "current_year_transfer_credit",
        "prior_8_percent_fees",
        "claim_8_percent_credit",
    ]
    missing = _missing(data, fields)
    if missing:
        return _blocked(
            "TP1-T",
            "48",
            [_blocker("T_MISSING_AMOUNTS", "Schedule T amounts and claim choices are incomplete.", missing, SOURCE_T, "Enter each amount explicitly, including zero and both prior carryforwards.")],
            SOURCE_T,
        )
    invalid = _invalid_money(data, fields)
    if invalid:
        return _blocked(
            "TP1-T",
            "48",
            [_blocker("T_INVALID_AMOUNTS", "Schedule T amounts cannot be negative.", invalid, SOURCE_T, "Correct the affected tuition amount.")],
            SOURCE_T,
        )
    if data.current_year_transfer_credit != ZERO:
        return _blocked(
            "TP1-T",
            "48",
            [_blocker("T_TRANSFER_UNSUPPORTED", "A current-year tuition transfer requires Schedule T Part B and the recipient's return facts.", ["current_year_transfer_credit"], SOURCE_T, "Set the transfer to zero or complete the return in authorized software.")],
            SOURCE_T,
        )

    current_fees = _money(data.current_eligible_fees or ZERO)
    if ZERO < current_fees <= Decimal("100.00"):
        return _blocked(
            "TP1-T",
            "48",
            [_blocker("T_FEES_NOT_OVER_100", "2025 fees must exceed $100 to enter them on Schedule T line 40.6.", ["current_eligible_fees"], SOURCE_T, "Confirm eligible receipts from an institution whose total exceeds $100, or enter zero.")],
            SOURCE_T,
        )
    if current_fees > Decimal("100.00") and data.institution_outside_quebec is None:
        return _blocked(
            "TP1-T",
            "48",
            [_blocker("T_MISSING_INSTITUTION_LOCATION", "Schedule T line 40.5 requires whether the institution is outside Quebec when current eligible fees are entered.", ["institution_outside_quebec"], SOURCE_T, "Confirm the institution location for the eligible 2025 tuition or examination fees.")],
            SOURCE_T,
        )
    ctc = _money(data.federal_training_credit_45350 or ZERO)
    if ctc > current_fees:
        return _blocked(
            "TP1-T",
            "48",
            [_blocker("T_CTC_EXCEEDS_FEES", "Federal training credit line 45350 exceeds current eligible fees.", ["current_eligible_fees", "federal_training_credit_45350"], SOURCE_T, "Review T1 Schedule 11 and the tuition receipt.")],
            SOURCE_T,
        )

    prior20 = _money(data.prior_20_percent_fees or ZERO)
    line37 = _money(prior20 * Decimal("0.20"))
    line38 = _money(data.claim_20_percent_credit or ZERO)
    if line38 > line37:
        return _blocked(
            "TP1-T",
            "48",
            [_blocker("T_20_PERCENT_CLAIM_TOO_HIGH", "The claimed 20% credit exceeds Schedule T line 37.", ["claim_20_percent_credit", "prior_20_percent_fees"], SOURCE_T, "Reduce line 38 to the available credit.")],
            SOURCE_T,
        )
    line39 = _money(line37 - line38)
    line40 = _money(line39 * Decimal(5))

    line41 = _money(current_fees - ctc)
    line68 = ZERO
    line42 = ZERO
    line43 = line41
    prior8 = _money(data.prior_8_percent_fees or ZERO)
    line44_1 = _money(line43 + prior8)
    line45 = _money(line44_1 * Decimal("0.08"))
    line46 = _money(data.claim_8_percent_credit or ZERO)
    if line46 > line45:
        return _blocked(
            "TP1-T",
            "48",
            [_blocker("T_8_PERCENT_CLAIM_TOO_HIGH", "The claimed 8% credit exceeds Schedule T line 45.", ["claim_8_percent_credit", "current_eligible_fees", "federal_training_credit_45350", "prior_8_percent_fees"], SOURCE_T, "Reduce line 46 to the available credit.")],
            SOURCE_T,
        )
    line47 = _money(line45 - line46)
    line48 = _money(line47 * Decimal("12.5"))

    lines = {
        "34": _line("TP1-T", "34", prior20, "input", inputs=["prior_20_percent_fees"], source_id=SOURCE_T),
        "37": _line("TP1-T", "37", line37, "calculated" if line37 else "zero", inputs=["34"], formula_id="t_prior_20_percent_credit", source_id=SOURCE_T, rounded=True),
        "38": _line("TP1-T", "38", line38, "input" if line38 else "zero", inputs=["claim_20_percent_credit"], source_id=SOURCE_T),
        "39": _line("TP1-T", "39", line39, "calculated" if line39 else "zero", inputs=["37", "38"], formula_id="t_unused_20_percent_credit", source_id=SOURCE_T, rounded=True),
        "40": _line("TP1-T", "40", line40, "calculated" if line40 else "zero", inputs=["39"], formula_id="t_20_percent_fee_carryforward", source_id=SOURCE_T, rounded=True),
        "40.5": _line("TP1-T", "40.5", bool(data.institution_outside_quebec), "input" if current_fees else "not_applicable", inputs=["institution_outside_quebec"], source_id=SOURCE_T),
        "40.6": _line("TP1-T", "40.6", current_fees, "input" if current_fees else "zero", inputs=["current_eligible_fees"], source_id=SOURCE_T),
        "40.7": _line("TP1-T", "40.7", ctc, "input" if ctc else "zero", inputs=["federal_training_credit_45350"], source_id=SOURCE_T),
        "41": _line("TP1-T", "41", line41, "calculated" if line41 else "zero", inputs=["40.6", "40.7"], formula_id="t_fees_after_ctc", source_id=SOURCE_T, rounded=True),
        "68": _line("TP1-T", "68", line68, "zero", inputs=["current_year_transfer_credit"], formula_id="t_no_transfer", source_id=SOURCE_T),
        "42": _line("TP1-T", "42", line42, "zero", inputs=["68"], formula_id="t_transferred_fee_equivalent", source_id=SOURCE_T),
        "43": _line("TP1-T", "43", line43, "calculated" if line43 else "zero", inputs=["41", "42"], formula_id="t_current_fees_after_transfer", source_id=SOURCE_T),
        "44": _line("TP1-T", "44", prior8, "input" if prior8 else "zero", inputs=["prior_8_percent_fees"], source_id=SOURCE_T),
        "44.1": _line("TP1-T", "44.1", line44_1, "calculated" if line44_1 else "zero", inputs=["43", "44"], formula_id="t_total_8_percent_fees", source_id=SOURCE_T, rounded=True),
        "45": _line("TP1-T", "45", line45, "calculated" if line45 else "zero", inputs=["44.1"], formula_id="t_available_8_percent_credit", source_id=SOURCE_T, rounded=True),
        "46": _line("TP1-T", "46", line46, "input" if line46 else "zero", inputs=["claim_8_percent_credit"], source_id=SOURCE_T),
        "47": _line("TP1-T", "47", line47, "calculated" if line47 else "zero", inputs=["45", "46"], formula_id="t_unused_8_percent_credit", source_id=SOURCE_T, rounded=True),
        "48": _line("TP1-T", "48", line48, "calculated" if line48 else "zero", inputs=["47"], formula_id="t_8_percent_fee_carryforward", source_id=SOURCE_T, rounded=True),
    }
    return ScheduleResult(schedule_id="TP1-T", lines=lines)
