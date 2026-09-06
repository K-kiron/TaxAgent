"""Official-form arithmetic for the covered 2025 Quebec federal return."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import CompletenessBlocker, LineValue, ScheduleResult, TaxReturnInput


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
T1_SOURCE = "cra_2025_5005_r"
S6_SOURCE = "cra_2025_schedule_6_qc"
S7_SOURCE = "cra_2025_schedule_7"
S8_SOURCE = "cra_2025_schedule_8_qc"
T2204_SOURCE = "cra_2025_t2204"
STUDENT_LOAN_SOURCE = "cra_2025_line_31900"
SCHOLARSHIP_SOURCE = "cra_2025_line_13010"
RESP_SOURCE = "cra_2025_t4a"
S11_SOURCE = "cra_2025_schedule_11_qc"
WORKSHEET_SOURCE = "cra_2025_federal_worksheet"
ROUNDING_ID = "money_cents_half_up"


_LINE_LABELS: dict[tuple[str, str], str] = {
    # Schedule 8 — Quebec Pension Plan contributions
    ("T1-S8", "A"): "Number of months for the QPP contribution calculation",
    ("T1-S8", "B"): "Year's maximum pensionable earnings",
    ("T1-S8", "C"): "Second earnings ceiling range",
    ("T1-S8", "D"): "Year's additional maximum pensionable earnings",
    ("T1-S8", "E"): "Basic exemption",
    ("T1-S8", "1"): "Pensionable earnings from T4 slips",
    ("T1-S8", "2"): "Pensionable earnings limited to the additional maximum",
    ("T1-S8", "3"): "Year's maximum pensionable earnings",
    ("T1-S8", "4"): "Pensionable earnings above the first ceiling",
    ("T1-S8", "5"): "Pensionable earnings up to the first ceiling",
    ("T1-S8", "6"): "Basic exemption",
    ("T1-S8", "7"): "Contributory earnings below the first ceiling",
    ("T1-S8", "8"): "QPP contributions from T4 box 17",
    ("T1-S8", "9"): "Base QPP contributions paid",
    ("T1-S8", "10"): "First additional QPP contributions paid",
    ("T1-S8", "11"): "Required base QPP contributions",
    ("T1-S8", "12"): "Required first additional QPP contributions",
    ("T1-S8", "13"): "Required contributions below the first ceiling",
    ("T1-S8", "14"): "Base QPP contributions paid",
    ("T1-S8", "15"): "Required base QPP contributions",
    ("T1-S8", "16"): "Difference in base QPP contributions",
    ("T1-S8", "17"): "First additional QPP contributions paid",
    ("T1-S8", "18"): "Required first additional QPP contributions",
    ("T1-S8", "19"): "Difference in first additional QPP contributions",
    ("T1-S8", "20"): "Combined difference below the first ceiling",
    ("T1-S8", "21"): "Second additional QPP contributions paid",
    ("T1-S8", "22"): "Required second additional QPP contributions",
    ("T1-S8", "23"): "Difference in second additional QPP contributions",
    ("T1-S8", "24"): "Total QPP contribution difference",
    ("T1-S8", "25"): "Base QPP contribution credit",
    ("T1-S8", "26"): "First additional QPP contribution deduction",
    ("T1-S8", "27"): "Second additional QPP contribution deduction",
    ("T1-S8", "28"): "Total enhanced QPP contribution deduction",
    ("T1-S8", "29"): "Base contribution amount before reallocations",
    ("T1-S8", "30"): "Base contribution shortfall",
    ("T1-S8", "31"): "First additional amount applied to the base shortfall",
    ("T1-S8", "32"): "Base shortfall remaining",
    ("T1-S8", "33"): "Base contribution after first additional reallocation",
    ("T1-S8", "34"): "Second additional amount applied to the base shortfall",
    ("T1-S8", "35"): "Base QPP contribution credit",
    ("T1-S8", "36"): "First additional contribution before reallocations",
    ("T1-S8", "37"): "First additional contribution shortfall",
    ("T1-S8", "38"): "Base amount applied to the first additional shortfall",
    ("T1-S8", "39"): "First additional shortfall remaining",
    ("T1-S8", "40"): "First additional contribution after base reallocation",
    ("T1-S8", "41"): "Second additional amount applied to the first additional shortfall",
    ("T1-S8", "42"): "First additional QPP contribution deduction",
    ("T1-S8", "43"): "Second additional contribution before reallocation",
    ("T1-S8", "44"): "Second additional contribution shortfall",
    ("T1-S8", "45"): "Base and first additional amount applied to the second shortfall",
    ("T1-S8", "46"): "Second additional QPP contribution deduction",
    ("T1-S8", "47"): "Total enhanced QPP contribution deduction",
    # Schedule 7 — RRSP, PRPP and SPP contributions
    ("T1-S7", "1"): "Unused RRSP contributions available before 2025",
    ("T1-S7", "2"): "Contributions from March through December 2025",
    ("T1-S7", "3"): "Contributions in the first 60 days of 2026",
    ("T1-S7", "4"): "Total current contribution receipts",
    ("T1-S7", "5"): "Total available contributions before repayments",
    ("T1-S7", "6"): "Available contributions carried to the repayment calculation",
    ("T1-S7", "9"): "Total HBP and LLP repayments designated",
    ("T1-S7", "10"): "Contributions available to deduct",
    ("T1-S7", "11"): "RRSP deduction limit for 2025",
    ("T1-S7", "13"): "RRSP deduction limit after PRPP contributions",
    ("T1-S7", "14"): "Contributions available to deduct",
    ("T1-S7", "16"): "Contributions after eligible transfers",
    ("T1-S7", "17"): "Maximum RRSP deduction",
    ("T1-S7", "18"): "RRSP deduction claimed for 2025",
    ("T1-S7", "19"): "Deduction including eligible transfers",
    ("T1-S7", "20"): "Allowable RRSP deduction",
    ("T1-S7", "21"): "Contributions available for carryforward",
    ("T1-S7", "22"): "Contributions deducted for 2025",
    ("T1-S7", "23"): "Unused RRSP contributions available after 2025",
    # Schedule 6 — Canada workers benefit
    ("T1-S6", "1"): "Employment income",
    ("T1-S6", "2"): "Taxable scholarships included in working income",
    ("T1-S6", "3"): "Self-employment income included in working income",
    ("T1-S6", "4"): "Elected tax-exempt working income",
    ("T1-S6", "5"): "Working income",
    ("T1-S6", "6"): "Family working income",
    ("T1-S6", "7"): "Net income",
    ("T1-S6", "8"): "Elected tax-exempt net income",
    ("T1-S6", "9"): "UCCB and RDSP repayments",
    ("T1-S6", "10"): "Adjusted net income before exclusions",
    ("T1-S6", "11"): "UCCB and RDSP income",
    ("T1-S6", "12"): "Adjusted net income",
    ("T1-S6", "13"): "Family adjusted net income",
    ("T1-S6", "15"): "Adjusted family net income",
    ("T1-S6", "16"): "Family working income",
    ("T1-S6", "17"): "Basic CWB working-income threshold",
    ("T1-S6", "18"): "Working income above the threshold",
    ("T1-S6", "19"): "Basic CWB rate",
    ("T1-S6", "20"): "Basic CWB before the maximum",
    ("T1-S6", "21"): "Maximum basic CWB",
    ("T1-S6", "22"): "Basic CWB before income reduction",
    ("T1-S6", "23"): "Adjusted family net income",
    ("T1-S6", "24"): "Basic CWB income-reduction threshold",
    ("T1-S6", "25"): "Family income above the reduction threshold",
    ("T1-S6", "26"): "Basic CWB reduction rate",
    ("T1-S6", "27"): "Basic CWB income reduction",
    ("T1-S6", "28"): "Basic Canada workers benefit",
    ("T1-S6", "43"): "Current-year Canada workers benefit entitlement",
    ("T1-S6", "44"): "Basic advanced CWB payments from RC210 box 10",
    ("T1-S6", "46"): "Total basic advanced CWB payments",
    ("T1-S6", "47"): "Disability advanced CWB payments from RC210 box 11",
    ("T1-S6", "48"): "Total advanced CWB payments received",
    ("T1-S6", "49"): "Advanced CWB amount included in federal tax",
    # Schedule 11 — tuition and Canada training credit
    ("T1-S11", "1"): "Eligible Canadian tuition fees over $100 per institution",
    ("T1-S11", "2"): "One-half of current eligible tuition fees",
    ("T1-S11", "3"): "Canada training credit limit",
    ("T1-S11", "4"): "Maximum Canada training credit claim",
    ("T1-S11", "5"): "Canada training credit claimed",
    ("T1-S11", "6"): "Current tuition after the training credit",
    ("T1-S11", "8"): "Current-year tuition available",
    ("T1-S11", "9"): "Unused federal tuition from prior years",
    ("T1-S11", "10"): "Total tuition available",
    ("T1-S11", "11"): "Taxable-income equivalent for the tuition limit",
    ("T1-S11", "12"): "Federal non-refundable credits before tuition",
    ("T1-S11", "13"): "Tax room available for tuition",
    ("T1-S11", "14"): "Prior-year tuition claimed",
    ("T1-S11", "15"): "Tax room remaining for current tuition",
    ("T1-S11", "16"): "Current-year tuition claimed",
    ("T1-S11", "17"): "Federal tuition amount claimed",
    ("T1-S11", "18"): "Total tuition available",
    ("T1-S11", "19"): "Tuition claimed in 2025",
    ("T1-S11", "20"): "Unused federal tuition after the 2025 claim",
    ("T1-S11", "25"): "Federal tuition carried forward",
    ("T1-S11", "32010"): "Part-time enrolment months",
    ("T1-S11", "32020"): "Full-time enrolment months",
    # Federal T1 return
    ("T1", "10100"): "Employment income",
    ("T1", "12100"): "Interest and other investment income",
    ("T1", "13000"): "Other income: RESP educational assistance payments",
    ("T1", "13010"): "Taxable scholarships, fellowships, bursaries, and awards",
    ("T1", "15000"): "Total income",
    ("T1", "20700"): "Registered pension plan deduction",
    ("T1", "20800"): "RRSP deduction",
    ("T1", "21200"): "Annual union, professional, or like dues",
    ("T1", "22215"): "Deduction for CPP or QPP enhanced contributions on employment income",
    ("T1", "23300"): "Total deductions",
    ("T1", "23400"): "Net income before adjustments",
    ("T1", "23500"): "Social benefits repayment",
    ("T1", "23600"): "Net income",
    ("T1", "25700"): "Total deductions from net income",
    ("T1", "26000"): "Taxable income",
    ("T1", "77"): "Federal tax on taxable income",
    ("T1", "30000"): "Basic personal amount",
    ("T1", "30800"): "Base CPP or QPP contributions through employment",
    ("T1", "31200"): "Employment insurance premiums through employment",
    ("T1", "31205"): "Provincial parental insurance plan premiums",
    ("T1", "31210"): "PPIP premiums payable on employment income",
    ("T1", "31260"): "Canada employment amount",
    ("T1", "31900"): "Interest paid on qualifying student loans",
    ("T1", "105"): "Federal non-refundable credits before tuition",
    ("T1", "32300"): "Tuition amount claimed",
    ("T1", "33500"): "Total federal non-refundable credit amounts",
    ("T1", "33800"): "Federal non-refundable credits at 14.5%",
    ("T1", "34990"): "2025 federal non-refundable tax-credit top-up",
    ("T1", "35000"): "Total federal non-refundable tax credits",
    ("T1", "40400"): "Federal tax before credits",
    ("T1", "40600"): "Federal tax",
    ("T1", "41500"): "Advanced Canada workers benefit payments",
    ("T1", "41700"): "Federal tax after other credits",
    ("T1", "42000"): "Net federal tax",
    ("T1", "42900"): "Basic federal tax",
    ("T1", "43500"): "Total payable",
    ("T1", "43700"): "Total income tax deducted",
    ("T1", "43800"): "Tax transfer for residents of Quebec",
    ("T1", "43850"): "Tax deducted after the Quebec transfer",
    ("T1", "44000"): "Refundable Quebec abatement",
    ("T1", "45000"): "Employment insurance overpayment",
    ("T1", "45100"): "Net PPIP premiums payable or EI overpayment",
    ("T1", "45300"): "Canada workers benefit",
    ("T1", "45350"): "Canada training credit",
    ("T1", "47600"): "Tax paid by instalments",
    ("T1", "48200"): "Total credits",
    ("T1", "48400"): "Refund",
    ("T1", "48500"): "Balance owing",
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _line(
    form_id: str,
    line_id: str,
    value: Decimal,
    *,
    source_id: str,
    inputs: tuple[str, ...] = (),
    formula_id: str | None = None,
    input_line: bool = False,
) -> LineValue:
    label = _LINE_LABELS.get((form_id, line_id), f"{form_id} line {line_id}")
    origin = "Entered from source records" if input_line else "Calculated from the listed inputs"
    return LineValue(
        form_id=form_id,
        line_id=line_id,
        value=_money(value),
        status="input" if input_line else ("zero" if value == ZERO else "calculated"),
        inputs=list(inputs),
        formula_id=formula_id,
        source_ids=[source_id],
        rounding_id=None if input_line else ROUNDING_ID,
        explanation=f"{label}. {origin}.",
    )


def _not_applicable(form_id: str, line_id: str, *, source_id: str, explanation: str) -> LineValue:
    return LineValue(
        form_id=form_id,
        line_id=line_id,
        value=None,
        status="not_applicable",
        source_ids=[source_id],
        explanation=explanation,
    )


def _blocker(code: str, message: str, paths: list[str], source_id: str) -> CompletenessBlocker:
    return CompletenessBlocker(
        code=code,
        message=message,
        input_paths=paths,
        source_ids=[source_id],
        resolution="Review the source slips and complete this return in authorized software.",
    )


def _slips(data: TaxReturnInput, slip_type: str):
    return [slip for slip in data.slips if slip.slip_type == slip_type]


def _sum_box(data: TaxReturnInput, slip_type: str, box: str) -> Decimal:
    return _money(
        sum(
            (
                value
                for slip in _slips(data, slip_type)
                if isinstance((value := slip.fields.get(box)), Decimal)
            ),
            start=ZERO,
        )
    )


def _sum_t4_earnings(data: TaxReturnInput, box: str, exemption_field: str) -> Decimal:
    total = ZERO
    for slip in _slips(data, "T4"):
        if getattr(slip, exemption_field) is True:
            continue
        value = slip.fields.get(box, slip.fields.get("14", ZERO))
        if isinstance(value, Decimal):
            total += value
    return _money(total)


def calculate_qpp_schedule8(data: TaxReturnInput) -> ScheduleResult:
    """Calculate Schedule 8 Part 2 for employment income earned only in Quebec."""

    t4s = _slips(data, "T4")
    if not t4s:
        return ScheduleResult(schedule_id="T1-S8")

    pensionable = _sum_t4_earnings(data, "26", "cpp_qpp_exempt")
    actual_base_and_first = _sum_box(data, "T4", "17")
    actual_second = _sum_box(data, "T4", "17A")
    line2 = min(pensionable, Decimal("81200.00"))
    line4 = max(line2 - Decimal("71300.00"), ZERO)
    line5 = max(line2 - line4, ZERO)
    line7 = min(max(line5 - Decimal("3500.00"), ZERO), Decimal("67800.00"))
    line9 = _money(actual_base_and_first * Decimal("0.84375"))
    line10 = _money(actual_base_and_first - line9)
    line11 = min(_money(line7 * Decimal("0.054")), Decimal("3661.20"))
    line12 = min(_money(line7 * Decimal("0.01")), Decimal("678.00"))
    line16 = _money(line9 - line11)
    line19 = _money(line10 - line12)
    line20 = _money(line16 + line19)
    line22 = min(_money(line4 * Decimal("0.04")), Decimal("396.00"))
    line23 = _money(actual_second - line22)
    line24 = _money(line20 + line23)

    lines = {
        "A": _line("T1-S8", "A", Decimal("12"), source_id=S8_SOURCE, formula_id="qpp_full_year_months"),
        "B": _line("T1-S8", "B", Decimal("71300"), source_id=S8_SOURCE, formula_id="qpp_ympe_2025"),
        "C": _line("T1-S8", "C", Decimal("9900"), source_id=S8_SOURCE, formula_id="qpp_second_band_2025"),
        "D": _line("T1-S8", "D", Decimal("81200"), source_id=S8_SOURCE, formula_id="qpp_yampe_2025"),
        "E": _line("T1-S8", "E", Decimal("3500"), source_id=S8_SOURCE, formula_id="qpp_basic_exemption_2025"),
        "1": _line("T1-S8", "1", pensionable, source_id=S8_SOURCE, inputs=("T4:26",), input_line=True),
        "2": _line("T1-S8", "2", line2, source_id=S8_SOURCE, inputs=("D", "1"), formula_id="qpp_min_yampe"),
        "3": _line("T1-S8", "3", Decimal("71300"), source_id=S8_SOURCE, inputs=("B",), formula_id="qpp_ympe"),
        "4": _line("T1-S8", "4", line4, source_id=S8_SOURCE, inputs=("2", "3"), formula_id="qpp_second_earnings"),
        "5": _line("T1-S8", "5", line5, source_id=S8_SOURCE, inputs=("2", "4"), formula_id="qpp_first_band_earnings"),
        "6": _line("T1-S8", "6", Decimal("3500"), source_id=S8_SOURCE, inputs=("E",), formula_id="qpp_basic_exemption"),
        "7": _line("T1-S8", "7", line7, source_id=S8_SOURCE, inputs=("5", "6"), formula_id="qpp_contributory_earnings"),
        "8": _line("T1-S8", "8", actual_base_and_first, source_id=S8_SOURCE, inputs=("T4:17",), input_line=True),
        "9": _line("T1-S8", "9", line9, source_id=S8_SOURCE, inputs=("8",), formula_id="qpp_actual_base_84_375_percent"),
        "10": _line("T1-S8", "10", line10, source_id=S8_SOURCE, inputs=("8", "9"), formula_id="qpp_actual_first_additional"),
        "11": _line("T1-S8", "11", line11, source_id=S8_SOURCE, inputs=("7",), formula_id="qpp_required_base_5_4_percent"),
        "12": _line("T1-S8", "12", line12, source_id=S8_SOURCE, inputs=("7",), formula_id="qpp_required_first_1_percent"),
        "13": _line("T1-S8", "13", line11 + line12, source_id=S8_SOURCE, inputs=("11", "12"), formula_id="qpp_required_base_first"),
        "14": _line("T1-S8", "14", line9, source_id=S8_SOURCE, inputs=("9",), formula_id="qpp_actual_base_copy"),
        "15": _line("T1-S8", "15", line11, source_id=S8_SOURCE, inputs=("11",), formula_id="qpp_required_base_copy"),
        "16": _line("T1-S8", "16", line16, source_id=S8_SOURCE, inputs=("14", "15"), formula_id="qpp_base_difference"),
        "17": _line("T1-S8", "17", line10, source_id=S8_SOURCE, inputs=("10",), formula_id="qpp_actual_first_copy"),
        "18": _line("T1-S8", "18", line12, source_id=S8_SOURCE, inputs=("12",), formula_id="qpp_required_first_copy"),
        "19": _line("T1-S8", "19", line19, source_id=S8_SOURCE, inputs=("17", "18"), formula_id="qpp_first_difference"),
        "20": _line("T1-S8", "20", line20, source_id=S8_SOURCE, inputs=("16", "19"), formula_id="qpp_base_first_difference"),
        "21": _line("T1-S8", "21", actual_second, source_id=S8_SOURCE, inputs=("T4:17A",), input_line=True),
        "22": _line("T1-S8", "22", line22, source_id=S8_SOURCE, inputs=("4",), formula_id="qpp_required_second_4_percent"),
        "23": _line("T1-S8", "23", line23, source_id=S8_SOURCE, inputs=("21", "22"), formula_id="qpp_second_difference"),
        "24": _line("T1-S8", "24", line24, source_id=S8_SOURCE, inputs=("20", "23"), formula_id="qpp_total_difference"),
    }
    if line24 > ZERO:
        lines.update(
            {
                "25": _line("T1-S8", "25", line11, source_id=S8_SOURCE, inputs=("15",), formula_id="qpp_base_credit_positive_branch"),
                "26": _line("T1-S8", "26", line12, source_id=S8_SOURCE, inputs=("18",), formula_id="qpp_first_additional_positive_branch"),
                "27": _line("T1-S8", "27", line22, source_id=S8_SOURCE, inputs=("22",), formula_id="qpp_second_additional_positive_branch"),
                "28": _line("T1-S8", "28", line12 + line22, source_id=S8_SOURCE, inputs=("26", "27"), formula_id="qpp_enhanced_deduction_positive_branch"),
            }
        )
        return ScheduleResult(schedule_id="T1-S8", lines=lines)

    if line16 >= ZERO:
        line29 = line11
        line35 = line11
        for line_id in ("30", "31", "32", "33", "34"):
            lines[line_id] = _not_applicable(
                "T1-S8", line_id, source_id=S8_SOURCE,
                explanation="Skipped because Schedule 8 line 16 is zero or positive.",
            )
    else:
        line29 = line9
        line30 = -line16
        line31 = min(line19, line30) if line19 > ZERO else ZERO
        line32 = _money(line30 - line31)
        line33 = _money(line29 + line31)
        line34 = min(line23, line32) if line23 > ZERO and line32 > ZERO else ZERO
        line35 = _money(line33 + line34)
        lines.update(
            {
                "30": _line("T1-S8", "30", line30, source_id=S8_SOURCE, inputs=("16",), formula_id="qpp_base_shortfall"),
                "31": _line("T1-S8", "31", line31, source_id=S8_SOURCE, inputs=("19", "30"), formula_id="qpp_first_additional_reallocated_to_base"),
                "32": _line("T1-S8", "32", line32, source_id=S8_SOURCE, inputs=("30", "31"), formula_id="qpp_remaining_base_shortfall"),
                "33": _line("T1-S8", "33", line33, source_id=S8_SOURCE, inputs=("29", "31"), formula_id="qpp_base_after_first_reallocation"),
                "34": _line("T1-S8", "34", line34, source_id=S8_SOURCE, inputs=("23", "32"), formula_id="qpp_second_additional_reallocated_to_base"),
            }
        )
    lines["29"] = _line("T1-S8", "29", line29, source_id=S8_SOURCE, inputs=(("15",) if line16 >= ZERO else ("14",)), formula_id="qpp_base_branch_start")
    lines["35"] = _line("T1-S8", "35", line35, source_id=S8_SOURCE, inputs=(("15",) if line16 >= ZERO else ("33", "34")), formula_id="qpp_base_credit_employment")

    if line19 >= ZERO:
        line36 = line12
        line42 = line12
        for line_id in ("37", "38", "39", "40", "41"):
            lines[line_id] = _not_applicable(
                "T1-S8", line_id, source_id=S8_SOURCE,
                explanation="Skipped because Schedule 8 line 19 is zero or positive.",
            )
    else:
        line36 = line10
        line37 = -line19
        line38 = min(line16, line37) if line16 > ZERO else ZERO
        line39 = _money(line37 - line38)
        line40 = _money(line36 + line38)
        line41 = min(line39, _money(line23 - (line34 if line16 < ZERO else ZERO))) if line23 > ZERO and line39 > ZERO else ZERO
        line42 = _money(line40 + line41)
        lines.update(
            {
                "37": _line("T1-S8", "37", line37, source_id=S8_SOURCE, inputs=("19",), formula_id="qpp_first_additional_shortfall"),
                "38": _line("T1-S8", "38", line38, source_id=S8_SOURCE, inputs=("16", "37"), formula_id="qpp_base_excess_reallocated_to_first"),
                "39": _line("T1-S8", "39", line39, source_id=S8_SOURCE, inputs=("37", "38"), formula_id="qpp_remaining_first_shortfall"),
                "40": _line("T1-S8", "40", line40, source_id=S8_SOURCE, inputs=("36", "38"), formula_id="qpp_first_after_base_reallocation"),
                "41": _line("T1-S8", "41", line41, source_id=S8_SOURCE, inputs=("23", "34", "39"), formula_id="qpp_second_reallocated_to_first"),
            }
        )
    lines["36"] = _line("T1-S8", "36", line36, source_id=S8_SOURCE, inputs=(("18",) if line19 >= ZERO else ("17",)), formula_id="qpp_first_additional_branch_start")
    lines["42"] = _line("T1-S8", "42", line42, source_id=S8_SOURCE, inputs=(("18",) if line19 >= ZERO else ("40", "41")), formula_id="qpp_first_additional_deduction")

    if line23 >= ZERO:
        line43 = line22
        line46 = line22
        for line_id in ("44", "45"):
            lines[line_id] = _not_applicable(
                "T1-S8", line_id, source_id=S8_SOURCE,
                explanation="Skipped because Schedule 8 line 23 is zero or positive.",
            )
    else:
        line43 = actual_second
        line44 = -line23
        line45 = min(line20, line44) if line20 > ZERO else ZERO
        line46 = _money(line43 + line45)
        lines.update(
            {
                "44": _line("T1-S8", "44", line44, source_id=S8_SOURCE, inputs=("23",), formula_id="qpp_second_additional_shortfall"),
                "45": _line("T1-S8", "45", line45, source_id=S8_SOURCE, inputs=("20", "44"), formula_id="qpp_base_first_excess_reallocated_to_second"),
            }
        )
    lines["43"] = _line("T1-S8", "43", line43, source_id=S8_SOURCE, inputs=(("22",) if line23 >= ZERO else ("21",)), formula_id="qpp_second_additional_branch_start")
    lines["46"] = _line("T1-S8", "46", line46, source_id=S8_SOURCE, inputs=(("22",) if line23 >= ZERO else ("43", "45")), formula_id="qpp_second_additional_deduction")
    lines["47"] = _line("T1-S8", "47", line42 + line46, source_id=S8_SOURCE, inputs=("42", "46"), formula_id="qpp_enhanced_deduction_employment")
    return ScheduleResult(schedule_id="T1-S8", lines=lines)


def _federal_tax(taxable_income: Decimal) -> Decimal:
    brackets = (
        (Decimal("253414"), Decimal("0.33"), Decimal("58399.85")),
        (Decimal("177882"), Decimal("0.29"), Decimal("36495.57")),
        (Decimal("114750"), Decimal("0.26"), Decimal("20081.25")),
        (Decimal("57375"), Decimal("0.205"), Decimal("8319.38")),
        (ZERO, Decimal("0.145"), ZERO),
    )
    for floor, rate, base_tax in brackets:
        if taxable_income > floor or floor == ZERO:
            return _money((taxable_income - floor) * rate + base_tax)
    raise AssertionError("unreachable")


def _basic_personal_amount(net_income: Decimal) -> Decimal:
    if net_income <= Decimal("177882"):
        return Decimal("16129.00")
    if net_income >= Decimal("253414"):
        return Decimal("14538.00")
    reduction = (net_income - Decimal("177882")) / Decimal("75532") * Decimal("1591")
    return min(_money(Decimal("16129") - reduction), Decimal("16129.00"))


def _federal_top_up(credit_at_rate: Decimal) -> Decimal:
    return _money(max(credit_at_rate - Decimal("8319.38"), ZERO) * Decimal("0.0345"))


def _student_loan_interest_claim(data: TaxReturnInput) -> tuple[Decimal, tuple[str, ...]]:
    interest = data.student_loan_interest
    claim = _money(interest.federal_claim_amount or ZERO)
    remaining = claim
    inputs: list[str] = []
    for name in (
        "federal_unused_2020",
        "federal_unused_2021",
        "federal_unused_2022",
        "federal_unused_2023",
        "federal_unused_2024",
        "federal_current_year_paid",
    ):
        amount = _money(getattr(interest, name) or ZERO)
        if remaining > ZERO and amount > ZERO:
            inputs.append(f"student_loan_interest.{name}")
            remaining = max(_money(remaining - amount), ZERO)
    return claim, tuple(inputs)


def _taxable_scholarships(data: TaxReturnInput) -> Decimal:
    awards = data.scholarships.awards or []
    gross = sum((award.amount or ZERO for award in awards), start=ZERO)
    full_time_exemption = ZERO
    part_time_awards = ZERO
    referenced_programs: set[str] = set()
    for award in awards:
        amount = award.amount or ZERO
        if award.qualifying_student is not True:
            continue
        if award.attendance == "full_time":
            full_time_exemption += min(amount, award.intended_enrolment_support or ZERO)
        elif award.attendance == "part_time":
            part_time_awards += amount
            if award.part_time_program_id:
                referenced_programs.add(award.part_time_program_id)
    part_time_costs = sum(
        (
            program.eligible_tuition_and_required_materials or ZERO
            for program in (data.scholarships.part_time_programs or [])
            if program.program_id in referenced_programs
        ),
        start=ZERO,
    )
    enrolment_exemption = full_time_exemption + min(part_time_awards, part_time_costs)
    remaining = max(_money(gross - enrolment_exemption), ZERO)
    return max(_money(remaining - min(remaining, Decimal("500.00"))), ZERO)


def _rrsp_schedule7(data: TaxReturnInput) -> tuple[Decimal, dict[str, LineValue]]:
    rrsp = data.rrsp
    if not (rrsp.has_contributions or rrsp.has_prior_unused_contributions):
        return ZERO, {}

    prior = _money(rrsp.prior_unused_contributions or ZERO)
    contributions = {
        period: _money(
            sum(
                (
                    amount
                    for slip in _slips(data, "RRSP_RECEIPT")
                    if slip.rrsp_period == period
                    and isinstance((amount := slip.fields.get("amount")), Decimal)
                ),
                start=ZERO,
            )
        )
        for period in ("march_to_december_2025", "first_60_days_2026")
    }
    line2 = contributions["march_to_december_2025"]
    line3 = contributions["first_60_days_2026"]
    line4 = _money(line2 + line3)
    line5 = _money(prior + line4)
    line9 = ZERO
    line10 = _money(line5 - line9)
    line11 = _money(rrsp.deduction_limit or ZERO)
    line12 = ZERO
    line13 = _money(line11 - line12)
    line14 = line10
    line15 = ZERO
    line16 = _money(line14 - line15)
    line17 = min(line13, line16)
    line18 = _money(rrsp.deduction_requested or ZERO)
    line19 = _money(line15 + line18)
    line20 = min(line10, line19)
    line23 = _money(line10 - line20)
    lines = {
        "S7:1": _line("T1-S7", "1", prior, source_id=S7_SOURCE, inputs=("rrsp.prior_unused_contributions",), input_line=True),
        "S7:2": _line("T1-S7", "2", line2, source_id=S7_SOURCE, inputs=("RRSP_RECEIPT:march_to_december_2025",), input_line=True),
        "S7:3": _line("T1-S7", "3", line3, source_id=S7_SOURCE, inputs=("RRSP_RECEIPT:first_60_days_2026",), input_line=True),
        "S7:4": _line("T1-S7", "4", line4, source_id=S7_SOURCE, inputs=("2", "3"), formula_id="current_rrsp_contributions"),
        "S7:5": _line("T1-S7", "5", line5, source_id=S7_SOURCE, inputs=("1", "4"), formula_id="total_rrsp_contributions"),
        "S7:6": _line("T1-S7", "6", line5, source_id=S7_SOURCE, inputs=("5",), formula_id="total_contributions_copy"),
        "S7:7": _not_applicable("T1-S7", "7", source_id=S7_SOURCE, explanation="No Home Buyers' Plan repayment is designated."),
        "S7:8": _not_applicable("T1-S7", "8", source_id=S7_SOURCE, explanation="No Lifelong Learning Plan repayment is designated."),
        "S7:9": _line("T1-S7", "9", line9, source_id=S7_SOURCE, inputs=("7", "8"), formula_id="no_hbp_llp_repayment"),
        "S7:10": _line("T1-S7", "10", line10, source_id=S7_SOURCE, inputs=("6", "9"), formula_id="contributions_available_to_deduct"),
        "S7:11": _line("T1-S7", "11", line11, source_id=S7_SOURCE, inputs=("rrsp.deduction_limit",), input_line=True),
        "S7:12": _not_applicable("T1-S7", "12", source_id=S7_SOURCE, explanation="Employer PRPP contributions are outside the supported RRSP profile."),
        "S7:13": _line("T1-S7", "13", line13, source_id=S7_SOURCE, inputs=("11", "12"), formula_id="rrsp_limit_after_prpp"),
        "S7:14": _line("T1-S7", "14", line14, source_id=S7_SOURCE, inputs=("10",), formula_id="available_contributions_copy"),
        "S7:15": _not_applicable("T1-S7", "15", source_id=S7_SOURCE, explanation="No eligible transfer to an RRSP, PRPP, or SPP is reported."),
        "S7:16": _line("T1-S7", "16", line16, source_id=S7_SOURCE, inputs=("14", "15"), formula_id="contributions_after_transfers"),
        "S7:17": _line("T1-S7", "17", line17, source_id=S7_SOURCE, inputs=("13", "16"), formula_id="maximum_rrsp_deduction"),
        "S7:18": _line("T1-S7", "18", line18, source_id=S7_SOURCE, inputs=("rrsp.deduction_requested",), input_line=True),
        "S7:19": _line("T1-S7", "19", line19, source_id=S7_SOURCE, inputs=("15", "18"), formula_id="rrsp_deduction_before_available_cap"),
        "S7:20": _line("T1-S7", "20", line20, source_id=S7_SOURCE, inputs=("10", "19"), formula_id="rrsp_deduction"),
        "S7:21": _line("T1-S7", "21", line10, source_id=S7_SOURCE, inputs=("10",), formula_id="available_contributions_copy"),
        "S7:22": _line("T1-S7", "22", line20, source_id=S7_SOURCE, inputs=("20",), formula_id="rrsp_deduction_copy"),
        "S7:23": _line("T1-S7", "23", line23, source_id=S7_SOURCE, inputs=("21", "22"), formula_id="unused_rrsp_carryforward"),
    }
    return line20, lines


def _answer_line(
    form_id: str,
    line_id: str,
    value: bool,
    *,
    source_id: str,
    inputs: tuple[str, ...],
    explanation: str,
) -> LineValue:
    return LineValue(
        form_id=form_id,
        line_id=line_id,
        value=value,
        status="calculated",
        inputs=list(inputs),
        formula_id="supported_persona_answer",
        source_ids=[source_id],
        explanation=explanation,
    )


def _cwb_schedule6(
    data: TaxReturnInput,
    employment_income: Decimal,
    taxable_scholarship: Decimal,
    net_income: Decimal,
) -> tuple[Decimal, Decimal, dict[str, LineValue]]:
    facts = data.taxpayer
    credits = data.refundable_credits
    rc210_basic = _money(credits.advanced_cwb_paid or ZERO)
    rc210_disability = _money(credits.advanced_cwb_disability_paid or ZERO)
    has_rc210 = rc210_basic + rc210_disability > ZERO
    working_income = _money(employment_income + taxable_scholarship)
    if working_income == ZERO and not has_rc210:
        return ZERO, ZERO, {}

    personally_eligible = (
        facts.age_dec31 is not None
        and facts.age_dec31 >= 19
        and facts.was_full_time_student_more_than_13_weeks is not True
        and credits.cwb_incarcerated_90_days is not True
        and credits.cwb_foreign_officer_exempt is not True
    )
    claiming_basic = personally_eligible and working_income > Decimal("2400")
    lines: dict[str, LineValue] = {
        "S6:38100": _answer_line("T1-S6", "38100", False, source_id=S6_SOURCE, inputs=("taxpayer.dependant_count",), explanation="No eligible dependant."),
        "S6:38101": _answer_line("T1-S6", "38101", False, source_id=S6_SOURCE, inputs=("taxpayer.marital_status",), explanation="No eligible spouse."),
        "S6:38102": _answer_line("T1-S6", "38102", claiming_basic, source_id=S6_SOURCE, inputs=("taxpayer", "T1:10100"), explanation="Whether the taxpayer claims the basic Canada workers benefit."),
        "S6:38103": _answer_line("T1-S6", "38103", False, source_id=S6_SOURCE, inputs=("taxpayer.has_disability_or_caregiver_claim",), explanation="No disability tax credit eligibility."),
        "S6:38104": _answer_line("T1-S6", "38104", False, source_id=S6_SOURCE, inputs=("taxpayer.marital_status",), explanation="No eligible spouse with disability tax credit eligibility."),
        "S6:38105": _answer_line("T1-S6", "38105", False, source_id=S6_SOURCE, inputs=("taxpayer.has_indian_act_exempt_income",), explanation="No elected tax-exempt income is included."),
    }
    if claiming_basic:
        line18 = _money(max(working_income - Decimal("2400"), ZERO))
        line20 = _money(line18 * Decimal("0.373"))
        line22 = min(line20, Decimal("3812.06"))
        line25 = _money(max(net_income - Decimal("14170.05"), ZERO))
        line27 = _money(line25 * Decimal("0.20"))
        line28 = _money(max(line22 - line27, ZERO))
        values = {
            "1": (employment_income, ("T1:10100", "T1:10400"), "employment_income"),
            "2": (taxable_scholarship, ("T1:13010",), "taxable_scholarships"),
            "3": (ZERO, ("T1:13500", "T1:13700", "T1:13900", "T1:14100", "T1:14300"), "no_self_employment_income"),
            "4": (ZERO, ("T90:10000", "T1:10105"), "no_tax_exempt_working_income"),
            "5": (working_income, ("1", "2", "3", "4"), "working_income"),
            "6": (working_income, ("5",), "family_working_income"),
            "7": (net_income, ("T1:23600",), "net_income"),
            "8": (ZERO, ("T90:10026", "T1:10105"), "no_net_exempt_income"),
            "9": (ZERO, ("T1:21300", "T1:23200"), "no_uccb_rdsp_repayments"),
            "10": (net_income, ("7", "8", "9"), "adjusted_net_income_before_exclusions"),
            "11": (ZERO, ("T1:11700", "T1:12500"), "no_uccb_rdsp_income"),
            "12": (net_income, ("10", "11"), "adjusted_net_income"),
            "13": (net_income, ("12",), "family_adjusted_net_income"),
            "15": (net_income, ("13",), "adjusted_family_net_income"),
            "16": (working_income, ("6",), "family_working_income_copy"),
            "17": (Decimal("2400"), (), "single_cwb_working_income_base"),
            "18": (line18, ("16", "17"), "working_income_over_base"),
            "19": (Decimal("0.373"), (), "single_cwb_rate"),
            "20": (line20, ("18", "19"), "gross_basic_cwb"),
            "21": (Decimal("3812.06"), (), "single_cwb_maximum"),
            "22": (line22, ("20", "21"), "capped_basic_cwb"),
            "23": (net_income, ("15",), "adjusted_family_net_income_copy"),
            "24": (Decimal("14170.05"), (), "single_cwb_reduction_base"),
            "25": (line25, ("23", "24"), "family_income_over_reduction_base"),
            "26": (Decimal("0.20"), (), "single_cwb_reduction_rate"),
            "27": (line27, ("25", "26"), "basic_cwb_reduction"),
            "28": (line28, ("22", "27"), "basic_cwb"),
        }
        lines.update(
            {
                f"S6:{line_id}": _line("T1-S6", line_id, value, source_id=S6_SOURCE, inputs=inputs, formula_id=formula_id)
                for line_id, (value, inputs, formula_id) in values.items()
            }
        )
        lines["S6:14"] = _not_applicable(
            "T1-S6", "14", source_id=S6_SOURCE,
            explanation="The secondary-earner exemption does not apply without a spouse.",
        )
        cwb = line28
    else:
        cwb = ZERO

    if has_rc210:
        lines.update(
            {
                "S6:43": _line("T1-S6", "43", cwb, source_id=S6_SOURCE, inputs=(("28",) if claiming_basic else ()), formula_id="current_cwb_entitlement"),
                "S6:44": _line("T1-S6", "44", rc210_basic, source_id=S6_SOURCE, inputs=("refundable_credits.advanced_cwb_paid",), input_line=True),
                "S6:45": _not_applicable("T1-S6", "45", source_id=S6_SOURCE, explanation="No spouse or common-law partner."),
                "S6:46": _line("T1-S6", "46", rc210_basic, source_id=S6_SOURCE, inputs=("44", "45"), formula_id="total_basic_acwb_paid"),
                "S6:47": _line("T1-S6", "47", rc210_disability, source_id=S6_SOURCE, inputs=("refundable_credits.advanced_cwb_disability_paid",), input_line=True),
                "S6:48": _line("T1-S6", "48", rc210_basic + rc210_disability, source_id=S6_SOURCE, inputs=("46", "47"), formula_id="total_acwb_paid"),
            }
        )
        line49 = min(cwb, _money(rc210_basic + rc210_disability))
    else:
        for line_id in ("43", "44", "45", "46", "47", "48"):
            lines[f"S6:{line_id}"] = _not_applicable(
                "T1-S6", line_id, source_id=S6_SOURCE,
                explanation="Skipped because no RC210 advance payment was received.",
            )
        line49 = ZERO
    lines["S6:49"] = _line(
        "T1-S6", "49", line49, source_id=S6_SOURCE,
        inputs=(("43", "48") if has_rc210 else ()),
        formula_id="advanced_cwb_lesser_of_entitlement_and_payments",
    )
    return cwb, line49, lines


def _tuition(
    data: TaxReturnInput,
    taxable_income: Decimal,
    federal_tax: Decimal,
    credit_base_before_tuition: Decimal,
) -> tuple[Decimal, Decimal, dict[str, LineValue], list[CompletenessBlocker]]:
    tuition = data.federal_tuition
    applicable = bool(_slips(data, "T2202")) or any(
        (
            tuition.has_current_tuition,
            tuition.has_prior_unused,
            tuition.wants_transfer,
            tuition.wants_canada_training_credit,
        )
    )
    if not applicable:
        return ZERO, ZERO, {}, []

    t2202_by_institution: dict[str, Decimal] = {}
    for slip in _slips(data, "T2202"):
        fee = slip.fields.get("26")
        if isinstance(fee, Decimal):
            t2202_by_institution[slip.issuer_id] = (
                t2202_by_institution.get(slip.issuer_id, ZERO) + fee
            )
    current = _money(
        sum(
            (fee for fee in t2202_by_institution.values() if fee > Decimal("100")),
            start=ZERO,
        )
    )
    prior = tuition.prior_unused_amount if tuition.has_prior_unused else ZERO
    ctc = tuition.canada_training_credit_claim if tuition.wants_canada_training_credit else ZERO
    prior = _money(prior or ZERO)
    ctc = _money(ctc or ZERO)
    blockers: list[CompletenessBlocker] = []
    max_ctc = min(_money(current * Decimal("0.50")), tuition.canada_training_credit_limit or ZERO)
    if ctc > max_ctc:
        blockers.append(
            _blocker(
                "CTC_CLAIM_EXCEEDS_LIMIT",
                "The Canada training credit claim exceeds one-half of current fees or the evidenced limit.",
                ["federal_tuition.canada_training_credit_claim"],
                S11_SOURCE,
            )
        )
    available_current = _money(current - ctc)
    total_available = _money(available_current + prior)
    line11 = taxable_income if taxable_income <= Decimal("57375") else _money(federal_tax / Decimal("0.145"))
    tax_room = max(_money(line11 - credit_base_before_tuition), ZERO)
    prior_claim = min(prior, tax_room)
    current_room = _money(max(tax_room - prior_claim, ZERO))
    current_claim = min(available_current, current_room)
    tuition_claim = _money(prior_claim + current_claim)
    total_unused = _money(total_available - tuition_claim)
    carryforward = total_unused
    part_time_months = min(_sum_box(data, "T2202", "24"), Decimal("12"))
    full_time_months = min(_sum_box(data, "T2202", "25"), Decimal("12"))
    lines = {
        "S11:1": _line("T1-S11", "1", current, source_id=S11_SOURCE, inputs=("T2202:26 by institution",), formula_id="eligible_canadian_tuition_over_100_per_institution"),
        "S11:6": _line("T1-S11", "6", available_current, source_id=S11_SOURCE, inputs=("1", "5"), formula_id="tuition_after_ctc"),
        "S11:7": _not_applicable("T1-S11", "7", source_id=S11_SOURCE, explanation="Foreign-institution tuition is outside the supported T2202 profile."),
        "S11:8": _line("T1-S11", "8", available_current, source_id=S11_SOURCE, inputs=("6", "7"), formula_id="current_tuition_available"),
        "S11:9": _line("T1-S11", "9", prior, source_id=S11_SOURCE, inputs=("federal_tuition.prior_unused_amount",), input_line=True),
        "S11:10": _line("T1-S11", "10", total_available, source_id=S11_SOURCE, inputs=("8", "9"), formula_id="tuition_total_available"),
        "S11:11": _line("T1-S11", "11", line11, source_id=S11_SOURCE, inputs=("T1:26000", "T1:77"), formula_id="tuition_taxable_income_equivalent"),
        "S11:12": _line("T1-S11", "12", credit_base_before_tuition, source_id=S11_SOURCE, inputs=("T1:105",), formula_id="tuition_prior_credit_base"),
        "S11:13": _line("T1-S11", "13", tax_room, source_id=S11_SOURCE, inputs=("11", "12"), formula_id="tuition_tax_room"),
        "S11:14": _line("T1-S11", "14", prior_claim, source_id=S11_SOURCE, inputs=("9", "13"), formula_id="tuition_prior_claim"),
        "S11:15": _line("T1-S11", "15", current_room, source_id=S11_SOURCE, inputs=("13", "14"), formula_id="tuition_current_year_room"),
        "S11:16": _line("T1-S11", "16", current_claim, source_id=S11_SOURCE, inputs=("8", "15"), formula_id="tuition_current_claim"),
        "S11:17": _line("T1-S11", "17", tuition_claim, source_id=S11_SOURCE, inputs=("14", "16"), formula_id="tuition_claim"),
        "S11:18": _line("T1-S11", "18", total_available, source_id=S11_SOURCE, inputs=("10",), formula_id="tuition_total_available_copy"),
        "S11:19": _line("T1-S11", "19", tuition_claim, source_id=S11_SOURCE, inputs=("17",), formula_id="tuition_claim_copy"),
        "S11:20": _line("T1-S11", "20", total_unused, source_id=S11_SOURCE, inputs=("18", "19"), formula_id="unused_federal_tuition"),
        "S11:25": _line("T1-S11", "25", carryforward, source_id=S11_SOURCE, inputs=("20",), formula_id="tuition_carryforward"),
        "S11:32010": _line("T1-S11", "32010", part_time_months, source_id=S11_SOURCE, inputs=("T2202:24",), formula_id="part_time_enrolment_months"),
        "S11:32020": _line("T1-S11", "32020", full_time_months, source_id=S11_SOURCE, inputs=("T2202:25",), formula_id="full_time_enrolment_months"),
    }
    lines["S11:32005"] = LineValue(
        form_id="T1-S11",
        line_id="32005",
        value=False,
        status="calculated",
        inputs=["taxpayer.has_disability_or_caregiver_claim"],
        formula_id="no_disability_enrolment_exception",
        source_ids=[S11_SOURCE],
        explanation="The disability or impairment enrolment exception does not apply.",
    )
    if tuition.wants_canada_training_credit:
        lines.update(
            {
                "S11:2": _line("T1-S11", "2", _money(current * Decimal("0.50")), source_id=S11_SOURCE, inputs=("1",), formula_id="half_current_tuition"),
                "S11:3": _line("T1-S11", "3", tuition.canada_training_credit_limit or ZERO, source_id=S11_SOURCE, inputs=("federal_tuition.canada_training_credit_limit",), input_line=True),
                "S11:4": _line("T1-S11", "4", max_ctc, source_id=S11_SOURCE, inputs=("2", "3"), formula_id="maximum_training_credit"),
                "S11:5": _line("T1-S11", "5", ctc, source_id=S11_SOURCE, inputs=("federal_tuition.canada_training_credit_claim",), input_line=True),
            }
        )
    else:
        for line_id in ("2", "3", "4", "5"):
            lines[f"S11:{line_id}"] = _not_applicable(
                "T1-S11", line_id, source_id=S11_SOURCE,
                explanation="Skipped because no Canada training credit is claimed.",
            )
    for line_id in ("21", "22", "23", "24"):
        lines[f"S11:{line_id}"] = _not_applicable(
            "T1-S11", line_id, source_id=S11_SOURCE,
            explanation="Skipped because no tuition amount is transferred.",
        )
    return tuition_claim, ctc, lines, blockers


def calculate_federal(data: TaxReturnInput) -> ScheduleResult:
    """Calculate the complete federal main return for the declared covered facts."""

    qpp = calculate_qpp_schedule8(data)
    if qpp.blockers:
        return ScheduleResult(schedule_id="T1", blockers=qpp.blockers)

    employment = _sum_box(data, "T4", "14")
    interest = _sum_box(data, "T5", "13")
    resp_eap = _sum_box(data, "T4A", "042")
    taxable_scholarship = _taxable_scholarships(data)
    total_income = _money(employment + interest + resp_eap + taxable_scholarship)
    rpp = _sum_box(data, "T4", "20")
    union_dues = _sum_box(data, "T4", "44")
    rrsp, rrsp_lines = _rrsp_schedule7(data)
    qpp_branch = "25" if qpp.lines and qpp.lines["24"].value > ZERO else "35"
    qpp_enhanced_branch = "28" if qpp_branch == "25" else "47"
    qpp_enhanced = qpp.lines.get(qpp_enhanced_branch)
    qpp_enhanced_amount = qpp_enhanced.value if qpp_enhanced else ZERO
    assert isinstance(qpp_enhanced_amount, Decimal)
    deductions = _money(rpp + union_dues + rrsp + qpp_enhanced_amount)
    net_before_adjustments = _money(total_income - deductions)
    net_income = max(net_before_adjustments, ZERO)
    taxable_income = net_income
    federal_tax = _federal_tax(taxable_income)
    bpa = _basic_personal_amount(net_income)

    qpp_base_line = qpp.lines.get(qpp_branch)
    qpp_base = qpp_base_line.value if qpp_base_line else ZERO
    assert isinstance(qpp_base, Decimal)
    ei_actual = _sum_box(data, "T4", "18")
    ei_earnings = min(
        _sum_t4_earnings(data, "24", "ei_exempt"), Decimal("65700.00")
    )
    ei_required = ZERO if ei_earnings <= Decimal("2000") else min(
        _money(ei_earnings * Decimal("0.0131")), Decimal("860.67")
    )
    ei_credit = min(ei_actual, ei_required)
    ei_overpayment = max(_money(ei_actual - ei_required), ZERO)
    ppip = min(_sum_box(data, "T4", "55"), Decimal("484.12"))
    canada_employment = min(employment, Decimal("1471.00"))
    student_loan_interest, student_loan_inputs = _student_loan_interest_claim(data)
    credit_base_before_tuition = _money(
        bpa + qpp_base + ei_credit + ppip + canada_employment
    )
    tuition_claim, ctc, tuition_lines, tuition_blockers = _tuition(
        data, taxable_income, federal_tax, credit_base_before_tuition
    )
    if tuition_blockers:
        return ScheduleResult(schedule_id="T1", blockers=tuition_blockers)
    credit_base = _money(
        credit_base_before_tuition + student_loan_interest + tuition_claim
    )
    credit_at_rate = _money(credit_base * Decimal("0.145"))
    top_up = _federal_top_up(credit_at_rate)
    total_nonrefundable = _money(credit_at_rate + top_up)
    basic_federal_tax = max(_money(federal_tax - total_nonrefundable), ZERO)
    cwb, advanced_cwb, cwb_lines = _cwb_schedule6(
        data, employment, taxable_scholarship, net_income
    )
    net_federal_tax = _money(basic_federal_tax + advanced_cwb)
    total_payable = net_federal_tax
    tax_deducted = _money(
        _sum_box(data, "T4", "22") + _sum_box(data, "T4A", "22")
    )
    instalments = _money(data.instalments.federal_paid or ZERO)
    abatement = _money(basic_federal_tax * Decimal("0.165"))
    total_credits = _money(
        tax_deducted + abatement + ei_overpayment + cwb + ctc + instalments
    )
    difference = _money(total_payable - total_credits)
    refund = abs(difference) if difference < ZERO else ZERO
    balance = difference if difference > ZERO else ZERO

    values: list[tuple[str, Decimal, str, tuple[str, ...], str]] = [
        ("10100", employment, T1_SOURCE, ("T4:14",), "employment_income"),
        ("12100", interest, WORKSHEET_SOURCE, ("T5:13",), "interest_income"),
        ("13000", resp_eap, RESP_SOURCE, ("T4A:042",), "resp_educational_assistance_payments"),
        ("13010", taxable_scholarship, SCHOLARSHIP_SOURCE, ("T4A:105", "scholarships.awards"), "taxable_scholarships"),
        ("15000", total_income, T1_SOURCE, ("10100", "12100", "13000", "13010"), "total_income"),
        ("20700", rpp, T1_SOURCE, ("T4:20",), "rpp_deduction"),
        ("20800", rrsp, S7_SOURCE if rrsp_lines else T1_SOURCE, (("T1-S7:20",) if rrsp_lines else ()), "rrsp_deduction"),
        ("21200", union_dues, T1_SOURCE, ("T4:44",), "union_dues"),
        ("22215", qpp_enhanced_amount, S8_SOURCE, (f"T1-S8:{qpp_enhanced_branch}",), "qpp_enhanced_deduction"),
        ("23300", deductions, T1_SOURCE, ("20700", "20800", "21200", "22215"), "total_deductions"),
        ("23400", net_before_adjustments, T1_SOURCE, ("15000", "23300"), "net_income_before_adjustments"),
        ("23500", ZERO, T1_SOURCE, ("23400",), "no_social_benefit_repayment"),
        ("23600", net_income, T1_SOURCE, ("23400", "23500"), "net_income"),
        ("25700", ZERO, T1_SOURCE, (), "no_taxable_income_deductions"),
        ("26000", taxable_income, T1_SOURCE, ("23600", "25700"), "taxable_income"),
        ("77", federal_tax, T1_SOURCE, ("26000",), "federal_bracket_tax"),
        ("30000", bpa, WORKSHEET_SOURCE, ("23600",), "basic_personal_amount"),
        ("30800", qpp_base, S8_SOURCE, (f"T1-S8:{qpp_branch}",), "qpp_base_credit"),
        ("31200", ei_credit, T2204_SOURCE, ("T4:18", "T4:24", "T4:14"), "ei_premium_credit"),
        ("31205", ppip, T1_SOURCE, ("T4:55",), "ppip_premium_credit"),
        ("31210", ZERO, T1_SOURCE, (), "all_employment_in_quebec"),
        ("31260", canada_employment, T1_SOURCE, ("10100",), "canada_employment_amount"),
        ("31900", student_loan_interest, STUDENT_LOAN_SOURCE, student_loan_inputs, "student_loan_interest_claim"),
        ("105", credit_base_before_tuition, T1_SOURCE, ("30000", "30800", "31200", "31205", "31260"), "credit_base_before_tuition"),
        ("32300", tuition_claim, S11_SOURCE if tuition_lines else T1_SOURCE, (("T1-S11:17",) if tuition_lines else ()), "federal_tuition_amount"),
        ("33500", credit_base, T1_SOURCE, ("105", "31900", "32300"), "nonrefundable_credit_base"),
        ("33800", credit_at_rate, T1_SOURCE, ("33500",), "credits_at_14_5_percent"),
        ("34990", top_up, WORKSHEET_SOURCE, ("33800",), "top_up_credit_2025"),
        ("35000", total_nonrefundable, T1_SOURCE, ("33800", "34990"), "total_nonrefundable_credits"),
        ("40400", federal_tax, T1_SOURCE, ("77",), "federal_tax_before_credits"),
        ("42900", basic_federal_tax, T1_SOURCE, ("40400", "35000"), "basic_federal_tax"),
        ("40600", basic_federal_tax, T1_SOURCE, ("42900",), "federal_tax"),
        ("41700", basic_federal_tax, T1_SOURCE, ("40600",), "federal_tax_after_other_credits"),
        ("41500", advanced_cwb, S6_SOURCE, ("T1-S6:49",), "advanced_cwb"),
        ("42000", net_federal_tax, T1_SOURCE, ("41700", "41500"), "net_federal_tax"),
        ("43500", total_payable, T1_SOURCE, ("42000",), "total_payable"),
        ("43700", tax_deducted, T1_SOURCE, ("T4:22", "T4A:22"), "tax_deducted"),
        ("43800", ZERO, T1_SOURCE, (), "no_outside_quebec_tax_transfer"),
        ("43850", tax_deducted, T1_SOURCE, ("43700", "43800"), "tax_after_transfer"),
        ("44000", abatement, T1_SOURCE, ("42900",), "refundable_quebec_abatement_16_5_percent"),
        ("45000", ei_overpayment, T2204_SOURCE, ("T4:18", "T4:24", "T4:14"), "ei_overpayment"),
        ("45100", ei_overpayment, T1_SOURCE, ("45000", "31210"), "net_ei_overpayment"),
        ("45300", cwb, S6_SOURCE, (("T1-S6:28",) if "S6:28" in cwb_lines else ()), "canada_workers_benefit_single_qc"),
        ("45350", ctc, S11_SOURCE if tuition_lines else T1_SOURCE, (("T1-S11:5",) if tuition_lines else ()), "canada_training_credit"),
        ("47600", instalments, T1_SOURCE, ("instalments.federal_paid",), "federal_instalments_paid"),
        ("48200", total_credits, T1_SOURCE, ("43850", "44000", "45100", "45300", "45350", "47600"), "total_credits"),
        ("48400", refund, T1_SOURCE, ("43500", "48200"), "refund"),
        ("48500", balance, T1_SOURCE, ("43500", "48200"), "balance_owing"),
    ]
    lines = {
        line_id: _line(
            "T1",
            line_id,
            value,
            source_id=source_id,
            inputs=inputs,
            formula_id=formula_id,
        )
        for line_id, value, source_id, inputs, formula_id in values
    }
    lines.update(tuition_lines)
    lines.update(rrsp_lines)
    lines.update(cwb_lines)
    return ScheduleResult(schedule_id="T1", lines=lines)
