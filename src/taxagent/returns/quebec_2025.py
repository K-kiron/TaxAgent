"""Official-form arithmetic for the covered 2025 Quebec TP-1 return."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .federal_2025_qc import calculate_federal, calculate_qpp_schedule8
from .models import LineValue, ScheduleResult, TaxReturnInput
from .quebec_schedule_f import ScheduleFInput, calculate_quebec_schedule_f
from .quebec_schedules import (
    ScheduleDInput,
    ScheduleKInput,
    SchedulePInput,
    ScheduleTInput,
    calculate_schedule_d,
    calculate_schedule_k,
    calculate_schedule_p,
    calculate_schedule_t,
)


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
TP1_SOURCE = "rq_2025_tp1"
WORK_CHART_SOURCE = "rq_2025_work_charts"
ROUNDING_ID = "rq_2025_money_cents_half_up"
SCHEDULE_U_SOURCE = "rq_2025_schedule_u"
SCHEDULE_B_SOURCE = "rq_2025_schedule_b"
SCHEDULE_M_SOURCE = "rq_2025_schedule_m"
SCHOLARSHIP_SOURCE = "rq_2025_line_154_scholarship"
RESP_SOURCE = "rq_2025_line_154_resp"
LINE_295_SOURCE = "rq_2025_line_295"
SCHEDULE_F_SOURCE = "rq_2025_schedule_f"
QPIP_OVERPAYMENT_SOURCE = "rq_2025_line_457"


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _line(
    line_id: str,
    value: Decimal,
    *,
    source_id: str = TP1_SOURCE,
    inputs: tuple[str, ...] = (),
    formula_id: str,
) -> LineValue:
    return LineValue(
        form_id="TP1",
        line_id=line_id,
        value=_money(value),
        status="zero" if value == ZERO else "calculated",
        inputs=list(inputs),
        formula_id=formula_id,
        source_ids=[source_id],
        rounding_id=ROUNDING_ID,
    )


def _slips(data: TaxReturnInput, slip_type: str):
    return [slip for slip in data.slips if slip.slip_type == slip_type]


def _sum_box(data: TaxReturnInput, slip_type: str, box: str) -> Decimal:
    return _money(sum((slip.fields.get(box, ZERO) for slip in _slips(data, slip_type)), start=ZERO))


def _sum_rl1_box_o_allocations(data: TaxReturnInput, codes: set[str]) -> Decimal:
    return _money(
        sum(
            (
                amount
                for slip in _slips(data, "RL1")
                for code, amount in (slip.rl1_box_o_allocations or {}).items()
                if code in codes
            ),
            start=ZERO,
        )
    )


def _quebec_tax(taxable_income: Decimal) -> Decimal:
    brackets = (
        (Decimal("129590"), Decimal("0.2575"), Decimal("23114.10")),
        (Decimal("106495"), Decimal("0.24"), Decimal("17571.30")),
        (Decimal("53255"), Decimal("0.19"), Decimal("7455.70")),
        (ZERO, Decimal("0.14"), ZERO),
    )
    for floor, rate, base_tax in brackets:
        if taxable_income > floor or floor == ZERO:
            return _money((taxable_income - floor) * rate + base_tax)
    raise AssertionError("unreachable")


def _merge_schedule(lines: dict[str, LineValue], prefix: str, result: ScheduleResult) -> None:
    lines.update({f"{prefix}:{line_id}": line for line_id, line in result.lines.items()})


def _schedule_line(
    form_id: str,
    line_id: str,
    value: Decimal,
    *,
    source_id: str,
    inputs: tuple[str, ...] = (),
    formula_id: str,
    explanation: str,
) -> LineValue:
    return LineValue(
        form_id=form_id,
        line_id=line_id,
        value=_money(value),
        status="zero" if value == ZERO else "calculated",
        inputs=list(inputs),
        formula_id=formula_id,
        source_ids=[source_id],
        rounding_id=ROUNDING_ID,
        explanation=explanation,
    )


def _schedule_na(form_id: str, line_id: str, *, source_id: str, explanation: str) -> LineValue:
    return LineValue(
        form_id=form_id,
        line_id=line_id,
        value=None,
        status="not_applicable",
        source_ids=[source_id],
        explanation=explanation,
    )


def calculate_quebec_schedule_b(
    net_income: Decimal, *, eligible_for_living_alone_amount: bool
) -> ScheduleResult:
    """Calculate Schedule B Part B for the supported single, working-age branch."""

    if not eligible_for_living_alone_amount:
        return ScheduleResult(schedule_id="TP1-B")
    line18 = max(_money(net_income - Decimal("42090.00")), ZERO)
    line20 = Decimal("2128.00")
    line31 = _money(line18 * Decimal("0.1875"))
    line32 = max(_money(line20 - line31), ZERO)
    lines = {
        "10": _schedule_line("TP1-B", "10", net_income, source_id=SCHEDULE_B_SOURCE, inputs=("TP1:275",), formula_id="schedule_b_net_income", explanation="Net income from TP-1 line 275."),
        "12": _schedule_na("TP1-B", "12", source_id=SCHEDULE_B_SOURCE, explanation="No spouse on December 31, 2025."),
        "14": _schedule_line("TP1-B", "14", net_income, source_id=SCHEDULE_B_SOURCE, inputs=("10", "12"), formula_id="schedule_b_family_income", explanation="Family income for the single-person branch."),
        "15": _schedule_line("TP1-B", "15", net_income, source_id=SCHEDULE_B_SOURCE, inputs=("14",), formula_id="schedule_b_family_income_copy", explanation="Family income used for the Schedule B reduction."),
        "16": _schedule_line("TP1-B", "16", Decimal("42090"), source_id=SCHEDULE_B_SOURCE, formula_id="schedule_b_2025_threshold", explanation="2025 Schedule B family-income threshold."),
        "18": _schedule_line("TP1-B", "18", line18, source_id=SCHEDULE_B_SOURCE, inputs=("15", "16"), formula_id="schedule_b_income_over_threshold", explanation="Family income above the Schedule B threshold."),
        "20": _schedule_line("TP1-B", "20", line20, source_id=SCHEDULE_B_SOURCE, inputs=("quebec_schedule_b.eligible_for_living_alone_amount",), formula_id="schedule_b_living_alone_amount", explanation="2025 amount for a person living alone."),
        "30": _schedule_line("TP1-B", "30", line20, source_id=SCHEDULE_B_SOURCE, inputs=("20",), formula_id="schedule_b_amounts_before_reduction", explanation="Living-alone amount before the income reduction."),
        "31": _schedule_line("TP1-B", "31", line31, source_id=SCHEDULE_B_SOURCE, inputs=("18",), formula_id="schedule_b_reduction_18_75_percent", explanation="Schedule B income reduction at 18.75%."),
        "32": _schedule_line("TP1-B", "32", line32, source_id=SCHEDULE_B_SOURCE, inputs=("30", "31"), formula_id="schedule_b_amount_after_reduction", explanation="Living-alone amount after the income reduction."),
        "33": _schedule_na("TP1-B", "33", source_id=SCHEDULE_B_SOURCE, explanation="No spouse claims any part of this amount."),
        "34": _schedule_line("TP1-B", "34", line32, source_id=SCHEDULE_B_SOURCE, inputs=("32", "33"), formula_id="schedule_b_line_361_amount", explanation="Amount carried to TP-1 line 361."),
    }
    for line_id, reason in {
        "21": "The additional single-parent amount does not apply without dependants.",
        "22": "The taxpayer is under age 65.",
        "23": "No spouse on December 31, 2025.",
        "27": "No retirement income is reported by the taxpayer.",
        "28": "No spouse or spousal retirement income is reported.",
    }.items():
        lines[line_id] = _schedule_na("TP1-B", line_id, source_id=SCHEDULE_B_SOURCE, explanation=reason)
    return ScheduleResult(schedule_id="TP1-B", lines=lines)


def calculate_quebec_schedule_m(data: TaxReturnInput) -> ScheduleResult:
    """Calculate Schedule M for current and prior unused qualifying interest."""

    interest = data.student_loan_interest
    prior = _money(interest.quebec_prior_unused or ZERO)
    current = _money(interest.quebec_current_year_paid or ZERO)
    claim = _money(interest.quebec_claim_amount or ZERO)
    if prior + current + claim == ZERO:
        return ScheduleResult(schedule_id="TP1-M")
    available = _money(prior + current)
    carryforward = max(_money(available - claim), ZERO)
    values = {
        "46": (prior, ("student_loan_interest.quebec_prior_unused",), "Unused qualifying interest from prior years"),
        "48": (current, ("student_loan_interest.quebec_current_year_paid",), "Qualifying student-loan interest paid in 2025"),
        "52": (available, ("46", "48"), "Total student-loan interest available"),
        "60": (claim, ("student_loan_interest.quebec_claim_amount",), "Student-loan interest claimed on TP-1 line 385"),
        "62": (carryforward, ("52", "60"), "Student-loan interest carried forward"),
    }
    lines = {
        line_id: _schedule_line(
            "TP1-M",
            line_id,
            value,
            source_id=SCHEDULE_M_SOURCE,
            inputs=inputs,
            formula_id=f"schedule_m_{line_id}",
            explanation=f"{label}.",
        )
        for line_id, (value, inputs, label) in values.items()
    }
    return ScheduleResult(schedule_id="TP1-M", lines=lines)


def calculate_qpp_schedule_u(data: TaxReturnInput) -> ScheduleResult:
    """Calculate Schedule U Part B for Quebec employment income only."""

    if not any("A" in slip.fields for slip in _slips(data, "RL1")):
        return ScheduleResult(schedule_id="TP1-U")

    def uline(
        line_id: str,
        value: Decimal,
        *inputs: str,
        formula_id: str | None = None,
        input_line: bool = False,
    ) -> LineValue:
        return LineValue(
            form_id="TP1-U",
            line_id=line_id,
            value=_money(value),
            status="input" if input_line else ("zero" if value == ZERO else "calculated"),
            inputs=list(inputs),
            formula_id=formula_id,
            source_ids=[SCHEDULE_U_SOURCE],
            rounding_id=None if input_line else ROUNDING_ID,
        )

    qpp_base_first_raw = _sum_box(data, "RL1", "B.A")
    qpp_base_first = min(qpp_base_first_raw, Decimal("4339.20"))
    raw_pensionable_wages = _sum_box(data, "RL1", "G")
    pensionable_wages = min(raw_pensionable_wages, Decimal("71300.00"))
    qpp_second = _sum_box(data, "RL1", "B.B")
    line11 = _money(qpp_base_first * Decimal("0.156250"))
    line14 = max(_money(pensionable_wages - Decimal("3500")), ZERO)
    line14_3 = Decimal("67800.00")
    line14_4 = min(line14, line14_3)
    line15 = _money(line14_4 * Decimal("0.01"))
    line16 = min(line11, line15)
    line17_2 = _money(line14_4 * Decimal("0.064"))
    line17_3 = max(_money(qpp_base_first_raw - line17_2), ZERO)
    line17_5 = _money(line17_3 + qpp_second)
    line18_7 = max(_money(raw_pensionable_wages - Decimal("71300")), ZERO)
    line19 = Decimal("9900.00")
    line20 = min(line18_7, line19)
    line21 = _money(line20 * Decimal("0.04"))
    line22 = min(line17_5, line21)
    line23 = _money(line22 + line16)

    values = (
        ("10", qpp_base_first, ("TP1:98",), None, True),
        ("11", line11, ("10",), "u_qpp_contribution_15_625_percent", False),
        ("12", pensionable_wages, ("TP1:98.1",), None, True),
        ("13", Decimal("3500"), (), "u_personal_qpp_exemption", False),
        ("14", line14, ("12", "13"), "u_pensionable_wages_after_exemption", False),
        ("14.1", Decimal("71300"), (), "u_maximum_pensionable_earnings", False),
        ("14.2", Decimal("3500"), ("13",), "u_personal_exemption_copy", False),
        ("14.3", line14_3, ("14.1", "14.2"), "u_maximum_contributory_earnings", False),
        ("14.4", line14_4, ("14", "14.3"), "u_first_band_earnings", False),
        ("15", line15, ("14.4",), "u_first_additional_required", False),
        ("16", line16, ("11", "15"), "u_first_additional_deduction", False),
        ("17", qpp_base_first_raw, ("TP1:98",), None, True),
        ("17.1", line14_4, ("14.4",), "u_first_band_copy", False),
        ("17.2", line17_2, ("17.1",), "u_total_first_band_required_6_4_percent", False),
        ("17.3", line17_3, ("17", "17.2"), "u_excess_first_band_contribution", False),
        ("17.4", qpp_second, ("TP1:98.2",), None, True),
        ("17.5", line17_5, ("17.3", "17.4"), "u_additional_contribution_available", False),
        ("18.5", raw_pensionable_wages, ("TP1:98.1",), None, True),
        ("18.6", Decimal("71300"), ("14.1",), "u_ympe_copy", False),
        ("18.7", line18_7, ("18.5", "18.6"), "u_second_band_wages", False),
        ("18.8", Decimal("81200"), (), "u_additional_maximum_pensionable_earnings", False),
        ("18.9", Decimal("71300"), ("14.1",), "u_ympe_second_copy", False),
        ("19", line19, ("18.8", "18.9"), "u_maximum_second_band", False),
        ("20", line20, ("18.7", "19"), "u_second_band_earnings_capped", False),
        ("21", line21, ("20",), "u_second_qpp_required_4_percent", False),
        ("22", line22, ("17.5", "21"), "u_second_qpp_deduction", False),
        ("22.1", line16, ("16",), "u_first_additional_copy", False),
        ("23", line23, ("22", "22.1"), "u_qpp_employment_deduction", False),
    )
    return ScheduleResult(
        schedule_id="TP1-U",
        lines={
            line_id: uline(
                line_id,
                value,
                *inputs,
                formula_id=formula_id,
                input_line=input_line,
            )
            for line_id, value, inputs, formula_id, input_line in values
        },
    )


def calculate_quebec(data: TaxReturnInput) -> ScheduleResult:
    """Calculate the TP-1 main return and every applicable supported schedule."""

    federal = calculate_federal(data)
    if federal.blockers:
        return ScheduleResult(schedule_id="TP1", blockers=federal.blockers)
    qpp = calculate_qpp_schedule8(data)
    schedule_u = calculate_qpp_schedule_u(data)

    employment = _sum_box(data, "RL1", "A")
    interest = _sum_box(data, "RL3", "D")
    scholarship_income = _sum_rl1_box_o_allocations(data, {"RB", "RZ-RB"})
    resp_eap_income = _sum_rl1_box_o_allocations(data, {"RU", "RZ-RU"})
    qpip_paid = _sum_box(data, "RL1", "H")
    qpp_base_first_paid = _sum_box(data, "RL1", "B.A")
    qpp_second_paid = _sum_box(data, "RL1", "B.B")
    other_income = _money(scholarship_income + resp_eap_income)
    total_income = _money(employment + interest + other_income)
    worker_eligible_income = max(employment - _sum_box(data, "RL1", "211"), ZERO)
    worker_deduction = min(_money(worker_eligible_income * Decimal("0.06")), Decimal("1420.00"))
    rpp = _sum_box(data, "RL1", "D")
    rrsp = data.rrsp.deduction_requested if data.rrsp.has_contributions else ZERO
    qpp_enhanced_line = schedule_u.lines.get("23")
    qpp_enhanced = qpp_enhanced_line.value if qpp_enhanced_line else ZERO
    assert isinstance(qpp_enhanced, Decimal)
    deductions = _money(worker_deduction + rpp + (rrsp or ZERO) + qpp_enhanced)
    net_income = max(_money(total_income - deductions), ZERO)
    taxable_income_deductions = scholarship_income
    taxable_income = max(_money(net_income - taxable_income_deductions), ZERO)
    gross_tax = _quebec_tax(taxable_income)
    schedule_b = calculate_quebec_schedule_b(
        net_income,
        eligible_for_living_alone_amount=(
            data.quebec_schedule_b.eligible_for_living_alone_amount is True
        ),
    )
    living_alone_line = schedule_b.lines.get("34")
    living_alone_amount = living_alone_line.value if living_alone_line else ZERO
    assert isinstance(living_alone_amount, Decimal)
    personal_credit_base = _money(Decimal("18571.00") + living_alone_amount)
    basic_credit = _money(personal_credit_base * Decimal("0.14"))
    schedule_m = calculate_quebec_schedule_m(data)
    student_interest_line = schedule_m.lines.get("60")
    student_interest_claim = student_interest_line.value if student_interest_line else ZERO
    assert isinstance(student_interest_claim, Decimal)
    student_interest_credit = _money(student_interest_claim * Decimal("0.20"))
    union_dues = _sum_box(data, "RL1", "F")
    union_credit = _money(union_dues * Decimal("0.10"))

    federal_ctc_line = federal.lines["45350"].value
    assert isinstance(federal_ctc_line, Decimal)
    current_qc_fees = (
        data.quebec_tuition.eligible_tuition_or_exam_receipts
        if data.quebec_tuition.has_current_tuition
        else ZERO
    )
    prior_20 = (
        data.quebec_tuition.prior_unused_at_20_percent
        if data.quebec_tuition.has_prior_unused
        else ZERO
    )
    prior_8 = (
        data.quebec_tuition.prior_unused_at_8_percent
        if data.quebec_tuition.has_prior_unused
        else ZERO
    )
    current_qc_fees = _money(current_qc_fees or ZERO)
    prior_20 = _money(prior_20 or ZERO)
    prior_8 = _money(prior_8 or ZERO)
    available_20_credit = _money(prior_20 * Decimal("0.20"))
    available_8_credit = _money(
        max(current_qc_fees - federal_ctc_line, ZERO) * Decimal("0.08")
        + prior_8 * Decimal("0.08")
    )
    tax_room = max(
        _money(gross_tax - basic_credit - student_interest_credit - union_credit), ZERO
    )
    claim_20 = min(available_20_credit, tax_room)
    claim_8 = min(available_8_credit, max(_money(tax_room - claim_20), ZERO))
    schedule_t = calculate_schedule_t(
        ScheduleTInput(
            prior_20_percent_fees=prior_20,
            claim_20_percent_credit=claim_20,
            current_eligible_fees=current_qc_fees,
            institution_outside_quebec=data.quebec_tuition.institution_outside_quebec,
            federal_training_credit_45350=federal_ctc_line,
            current_year_transfer_credit=ZERO,
            prior_8_percent_fees=prior_8,
            claim_8_percent_credit=claim_8,
        )
    )
    if schedule_t.blockers:
        return ScheduleResult(schedule_id="TP1", blockers=schedule_t.blockers)
    tuition_credit = _money(
        (schedule_t.lines["38"].value or ZERO) + (schedule_t.lines["46"].value or ZERO)
    )
    nonrefundable_credits = _money(
        basic_credit + student_interest_credit + union_credit + tuition_credit
    )
    tax_after_nonrefundable = max(_money(gross_tax - nonrefundable_credits), ZERO)

    drug = data.drug_insurance
    schedule_k = calculate_schedule_k(
        ScheduleKInput(
            net_income_275=net_income,
            group_plan_months=drug.group_plan_months,
            group_plan_source=drug.group_plan_source,
            eligible_student_months=drug.eligible_student_months,
            other_exemption_applies=drug.other_exemption_applies,
        )
    )
    if schedule_k.blockers:
        return ScheduleResult(schedule_id="TP1", blockers=schedule_k.blockers)
    drug_premium_line = schedule_k.lines.get("90")
    drug_premium = drug_premium_line.value if drug_premium_line else ZERO
    assert isinstance(drug_premium, Decimal)

    credits = data.refundable_credits
    schedule_p = calculate_schedule_p(
        SchedulePInput(
            resident_qc_dec31=True,
            eligible_status=credits.work_premium_eligible_status,
            age_eligible=(data.taxpayer.age_dec31 or 0) >= 18,
            transferred_schedule_s_amount=credits.transferred_schedule_s_amount,
            family_allowance_received_for_self=credits.family_allowance_received_for_self,
            turned_18_before_december=credits.turned_18_before_december,
            designated_as_dependent_child=credits.designated_as_dependent_child,
            full_time_student=credits.quebec_work_premium_full_time_student,
            incarcerated_over_183_days=credits.incarcerated_over_183_days,
            adapted_work_premium_eligible=credits.adapted_work_premium_eligible,
            supplement_months=credits.work_premium_supplement_months,
            request_tax_shield=credits.request_tax_shield,
            employment_income_101=employment,
            positive_employment_correction_105=ZERO,
            former_employment_benefits_box_211=_sum_box(data, "RL1", "211"),
            other_employment_income_107=ZERO,
            net_research_grants=ZERO,
            schedule_l_positive_work_income=ZERO,
            wepp_income=ZERO,
            line_293_work_income=ZERO,
            net_income_275=net_income,
        )
    )
    if schedule_p.blockers:
        return ScheduleResult(schedule_id="TP1", blockers=schedule_p.blockers)
    work_premium_line = schedule_p.lines.get("90")
    work_premium = work_premium_line.value if work_premium_line else ZERO
    assert isinstance(work_premium, Decimal)

    schedule_f = calculate_quebec_schedule_f(
        ScheduleFInput(
            total_income_199=total_income,
            forest_averaging_276=ZERO,
            employment_income_101=employment,
            employment_correction_105=ZERO,
            profit_sharing_107_point3=ZERO,
            old_age_security_114=ZERO,
            taxable_dividends_128=ZERO,
            actual_dividends_166_167=ZERO,
            taxable_support_142=ZERO,
            social_assistance_147=ZERO,
            indemnities_and_supplements_148=ZERO,
            ordinary_scholarships_154_point1=scholarship_income,
            spousal_rrsp_recovery_122=ZERO,
            excluded_other_income_154_points_2_5_12=ZERO,
            eligible_repayments_246=ZERO,
            wage_loss_repayment_207_point12=ZERO,
            schedule_r_26=ZERO,
            schedule_u_101=ZERO,
            schedule_u_103=ZERO,
            schedule_u_115=ZERO,
            ei_repayment_250_point3=ZERO,
            eligible_other_deductions_250=ZERO,
            pension_transfer_245=ZERO,
            deductible_support_225=ZERO,
            carrying_charges_231=ZERO,
            business_investment_loss_234=ZERO,
            eligible_deduction_293=ZERO,
            eligible_deduction_297=ZERO,
        )
    )
    health_services_fund_line = schedule_f.lines["82"].value
    assert isinstance(health_services_fund_line, Decimal)

    advance_work_credits = _money((credits.rl19_box_a or ZERO) + (credits.rl19_box_b or ZERO))
    income_tax_and_contributions = _money(
        tax_after_nonrefundable
        + drug_premium
        + advance_work_credits
        + health_services_fund_line
    )
    qc_tax_withheld = _sum_box(data, "RL1", "E")
    quebec_instalments = data.instalments.quebec_paid or ZERO
    qpp_difference_line = qpp.lines.get("24")
    qpp_overpayment = max(
        qpp_difference_line.value if qpp_difference_line and isinstance(qpp_difference_line.value, Decimal) else ZERO,
        ZERO,
    )
    qpip_earnings = min(_sum_box(data, "RL1", "I"), Decimal("98000.00"))
    if qpip_earnings < Decimal("2000.00"):
        qpip_overpayment = qpip_paid
    elif qpip_paid > Decimal("484.12"):
        qpip_overpayment = _money(qpip_paid - Decimal("484.12"))
    else:
        qpip_overpayment = ZERO
    paid_and_credits = _money(
        qc_tax_withheld + quebec_instalments + qpp_overpayment + work_premium + qpip_overpayment
    )
    difference = _money(income_tax_and_contributions - paid_and_credits)
    refund_before_transfer = abs(difference) if difference < ZERO else ZERO
    balance_before_small_balance_rule = difference if difference > ZERO else ZERO
    refund = refund_before_transfer
    balance = ZERO if balance_before_small_balance_rule < Decimal("2.00") else balance_before_small_balance_rule

    values: list[tuple[str, Decimal, str, tuple[str, ...], str]] = [
        ("96", ZERO, TP1_SOURCE, (), "no_cpp_contribution"),
        ("96.2", ZERO, TP1_SOURCE, (), "no_cpp_additional_contribution"),
        ("97", qpip_paid, TP1_SOURCE, ("RL1:H",), "qpip_premium"),
        ("98", qpp_base_first_paid, TP1_SOURCE, ("RL1:B.A",), "qpp_base_first_contribution"),
        ("98.1", _sum_box(data, "RL1", "G"), TP1_SOURCE, ("RL1:G",), "qpp_pensionable_salary"),
        ("98.2", qpp_second_paid, TP1_SOURCE, ("RL1:B.B",), "qpp_second_contribution"),
        ("101", employment, TP1_SOURCE, ("RL1:A",), "employment_income"),
        ("130", interest, TP1_SOURCE, ("RL3:D",), "interest_income"),
        ("154", other_income, RESP_SOURCE if resp_eap_income > ZERO else SCHOLARSHIP_SOURCE, ("RL1:O:RB", "RL1:O:RZ-RB", "RL1:O:RU", "RL1:O:RZ-RU"), "other_income"),
        ("199", total_income, TP1_SOURCE, ("101", "130", "154"), "total_income"),
        ("201", worker_deduction, WORK_CHART_SOURCE, ("101", "RL1:211"), "worker_deduction_6_percent_capped"),
        ("205", rpp, TP1_SOURCE, ("RL1:D",), "rpp_deduction"),
        ("214", rrsp or ZERO, TP1_SOURCE, ("rrsp.deduction_requested",), "rrsp_deduction"),
        ("248", qpp_enhanced, SCHEDULE_U_SOURCE, ("TP1-U:23",), "additional_qpp_deduction"),
        ("254", deductions, TP1_SOURCE, ("201", "205", "214", "248"), "total_deductions"),
        ("256", net_income, TP1_SOURCE, ("199", "254"), "income_after_deductions"),
        ("260", ZERO, TP1_SOURCE, (), "no_investment_expense_adjustment"),
        ("275", net_income, TP1_SOURCE, ("256", "260"), "net_income"),
        ("295", scholarship_income, LINE_295_SOURCE, ("154",), "scholarship_deduction"),
        ("298", taxable_income_deductions, TP1_SOURCE, ("295",), "taxable_income_deductions"),
        ("299", taxable_income, TP1_SOURCE, ("275", "298"), "taxable_income"),
        ("350", Decimal("18571"), TP1_SOURCE, (), "basic_personal_amount_2025"),
        ("359", Decimal("18571"), TP1_SOURCE, ("350",), "adjusted_basic_personal_amount"),
        ("361", living_alone_amount, SCHEDULE_B_SOURCE if schedule_b.lines else TP1_SOURCE, (("TP1-B:34",) if schedule_b.lines else ()), "living_alone_amount"),
        ("377", personal_credit_base, TP1_SOURCE, ("359", "361"), "personal_credit_amounts"),
        ("377.1", basic_credit, TP1_SOURCE, ("377",), "personal_credits_at_14_percent"),
        ("385", student_interest_claim, SCHEDULE_M_SOURCE if schedule_m.lines else TP1_SOURCE, (("TP1-M:60",) if schedule_m.lines else ()), "student_loan_interest_claim"),
        ("388", student_interest_claim, TP1_SOURCE, ("385",), "student_loan_interest_credit_base"),
        ("389", student_interest_credit, TP1_SOURCE, ("388",), "student_loan_interest_credit_20_percent"),
        ("397.1", union_dues, TP1_SOURCE, ("RL1:F",), "union_dues_credit_base"),
        ("397", union_credit, TP1_SOURCE, ("397.1",), "union_dues_credit_10_percent"),
        ("398", tuition_credit, TP1_SOURCE, ("TP1-T:38", "TP1-T:46"), "tuition_credit"),
        ("399", nonrefundable_credits, TP1_SOURCE, ("377.1", "389", "397", "398"), "nonrefundable_tax_credits"),
        ("401", gross_tax, WORK_CHART_SOURCE, ("299",), "quebec_bracket_tax"),
        ("406", nonrefundable_credits, TP1_SOURCE, ("399",), "nonrefundable_credit_copy"),
        ("413", tax_after_nonrefundable, TP1_SOURCE, ("401", "406"), "tax_after_nonrefundable_credits"),
        ("425", ZERO, TP1_SOURCE, (), "no_other_tax_credits"),
        ("430", tax_after_nonrefundable, TP1_SOURCE, ("413", "425"), "tax_after_other_credits"),
        ("431", ZERO, TP1_SOURCE, (), "no_spousal_credit_transfer"),
        ("432", tax_after_nonrefundable, TP1_SOURCE, ("430", "431"), "income_tax"),
        ("441", advance_work_credits, TP1_SOURCE, ("refundable_credits.rl19_box_a", "refundable_credits.rl19_box_b"), "advance_work_premium_payments"),
        ("446", health_services_fund_line, SCHEDULE_F_SOURCE, ("TP1-F:82",), "health_services_fund_contribution"),
        ("447", drug_premium, TP1_SOURCE, ("TP1-K:90",), "prescription_drug_insurance_premium"),
        ("450", income_tax_and_contributions, TP1_SOURCE, ("432", "441", "446", "447"), "income_tax_and_contributions"),
        ("451", qc_tax_withheld, TP1_SOURCE, ("RL1:E",), "quebec_tax_withheld"),
        ("451.2", qc_tax_withheld, TP1_SOURCE, ("451",), "tax_withheld_after_schedule_q"),
        ("452", qpp_overpayment, TP1_SOURCE, ("T1-S8:24",), "qpp_overpayment"),
        ("453", quebec_instalments, TP1_SOURCE, ("instalments.quebec_paid",), "quebec_instalments_paid"),
        ("456", work_premium, TP1_SOURCE, ("TP1-P:90",), "work_premium"),
        ("457", qpip_overpayment, QPIP_OVERPAYMENT_SOURCE, ("97", "RL1:I"), "qpip_overpayment"),
        ("465", paid_and_credits, TP1_SOURCE, ("451.2", "452", "453", "456", "457"), "income_tax_paid_and_credits"),
        ("468", paid_and_credits, TP1_SOURCE, ("465",), "total_payments_and_credits"),
        ("470", difference, TP1_SOURCE, ("450", "468"), "refund_or_balance_difference"),
        ("474", refund_before_transfer, TP1_SOURCE, ("470",), "refund_before_transfer"),
        ("478", refund, TP1_SOURCE, ("474",), "refund"),
        ("475", balance_before_small_balance_rule, TP1_SOURCE, ("470",), "balance_before_small_balance_rule"),
        ("479", balance, TP1_SOURCE, ("475",), "balance_due"),
    ]
    lines = {
        line_id: _line(
            line_id,
            value,
            source_id=source_id,
            inputs=inputs,
            formula_id=formula_id,
        )
        for line_id, value, source_id, inputs, formula_id in values
    }
    line_154_code = (
        "66"
        if scholarship_income > ZERO and resp_eap_income > ZERO
        else "01"
        if scholarship_income > ZERO
        else "03"
        if resp_eap_income > ZERO
        else ""
    )
    lines["154.code"] = LineValue(
        form_id="TP1",
        line_id="154.code",
        value=line_154_code,
        status="input" if line_154_code else "zero",
        inputs=["RL1:O"] if line_154_code else [],
        formula_id="other_income_code",
        source_ids=[SCHOLARSHIP_SOURCE, RESP_SOURCE],
        explanation="Other-income source code: 01 scholarship, 03 RESP, or 66 for both.",
    )
    if scholarship_income > ZERO and resp_eap_income > ZERO:
        lines["154"].source_ids = [SCHOLARSHIP_SOURCE, RESP_SOURCE]
    lines["154"].explanation = "Scholarships and RESP payments reported as other income."
    lines["457"].explanation = (
        "QPIP overpayment entered by the taxpayer: all premiums when relevant earnings are "
        "under $2,000, or premiums above the $484.12 annual maximum. Revenu Québec may "
        "calculate another below-maximum overpayment during assessment."
    )
    _merge_schedule(lines, "K", schedule_k)
    _merge_schedule(lines, "P", schedule_p)
    _merge_schedule(lines, "T", schedule_t)
    _merge_schedule(lines, "U", schedule_u)
    _merge_schedule(lines, "B", schedule_b)
    _merge_schedule(lines, "M", schedule_m)
    _merge_schedule(lines, "F", schedule_f)

    if credits.wants_solidarity_credit:
        schedule_d = calculate_schedule_d(
            ScheduleDInput(
                age_eligible=(data.taxpayer.age_dec31 or 0) >= 18,
                resident_qc_dec31=True,
                eligible_immigration_status=credits.solidarity_eligible_immigration_status,
                refugee_claimant_dec31=credits.solidarity_refugee_claimant_dec31,
                incarcerated_over_183_days=credits.incarcerated_over_183_days,
                family_allowance_paid_for_user_december=credits.solidarity_family_allowance_paid_for_user_december,
                turned_18_in_december=credits.solidarity_turned_18_in_december,
                lived_alone_all_year=credits.solidarity_lived_alone_all_year,
                address_same_as_return=credits.solidarity_address_same_as_return,
                occupancy=credits.solidarity_occupancy,
                rl31_dwelling_number=credits.solidarity_rl31_dwelling_number,
                rl31_occupant_number=credits.solidarity_rl31_occupant_number,
                owner_has_municipal_tax_bill=credits.solidarity_owner_has_municipal_tax_bill,
                owner_roll_number=credits.solidarity_owner_roll_number,
                owners_in_dwelling=credits.solidarity_owners_in_dwelling,
            )
        )
        if schedule_d.blockers:
            return ScheduleResult(schedule_id="TP1", lines=lines, blockers=schedule_d.blockers)
        _merge_schedule(lines, "D", schedule_d)

    return ScheduleResult(schedule_id="TP1", lines=lines)
