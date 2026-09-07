from decimal import Decimal

import pytest

from taxagent.returns import ANNUAL_RULES, SlipInput, TaxReturnInput, calculate_return

from test_federal_return import _input, _with_resp_eap, _with_scholarship


def annual_input(year: int, salary: str = "40000") -> TaxReturnInput:
    data = _input(employed=True)
    qpp = {
        2020: "2080.50",
        2021: "2153.50",
        2022: "2244.75",
        2023: "2336.00",
        2024: "2336.00",
    }[year]
    ei = {2020: "480", 2021: "472", 2022: "480", 2023: "508", 2024: "528"}[year]
    t4 = data.slips[0].model_copy(
        update={
            "tax_year": year,
            "fields": {
                "14": Decimal(salary),
                "17": Decimal(qpp),
                **({"17A": Decimal("0")} if year >= 2024 else {}),
                "18": Decimal(ei),
                "20": Decimal("0"),
                "22": Decimal("0"),
                "24": Decimal(salary),
                "26": Decimal(salary),
                "44": Decimal("0"),
                "52": Decimal("0"),
                "55": Decimal("197.60"),
                **({"57": Decimal("5000")} if year == 2020 else {}),
            },
        }
    )
    rl1 = data.slips[1].model_copy(
        update={
            "tax_year": year,
            "fields": {
                "A": Decimal(salary),
                ("B.A" if year >= 2024 else "B"): Decimal(qpp),
                **({"B.B": Decimal("0")} if year >= 2024 else {}),
                "C": Decimal(ei),
                "D": Decimal("0"),
                "E": Decimal("0"),
                "F": Decimal("0"),
                "G": Decimal(salary),
                "H": Decimal("197.60"),
                "I": Decimal(salary),
                "211": Decimal("0"),
            },
        }
    )
    payload = data.model_dump()
    payload.update(schema_version="qc-return-v2", tax_year=year, slips=[t4, rl1])
    payload["additional_return_screens"]["immigrated_or_emigrated_in_tax_year"] = False
    payload["student_loan_interest"]["federal_unused_by_origin_year"] = {
        origin: Decimal("0") for origin in range(year - 5, year)
    }
    return TaxReturnInput.model_validate(payload)


def by_form(result, form_id: str):
    return {line.line_id: line for line in result.lines if line.form_id == form_id}


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2020, "-2851.68"), (2021, "-2769.52"), (2022, "-2679.43"),
     (2023, "-2578.95"), (2024, "-2480.00")],
)
def test_independent_federal_salary_balances(year, expected):
    result = calculate_return(annual_input(year))

    assert result.status == "complete"
    assert result.federal_refund_or_balance == Decimal(expected)
    assert by_form(result, "T1")["10100"].value == Decimal("40000.00")
    assert result.coverage_profile_id.startswith(f"{year}-qc-")


def test_2020_information_boxes_are_not_added_to_employment_income():
    result = calculate_return(annual_input(2020))

    assert by_form(result, "T1")["10100"].value == Decimal("40000.00")


def test_2021_pandemic_benefits_and_repayment_use_distinct_lines():
    data = annual_input(2021)
    data.slips.append(
        SlipInput(
            slip_type="T4A",
            document_id="benefits",
            issuer_id="cra",
            tax_year=2021,
            confirmed=True,
            fields={"203": Decimal("1000"), "204": Decimal("500"), "201": Decimal("300"), "22": Decimal("150")},
        )
    )
    data.pandemic_repayment = data.pandemic_repayment.model_copy(update={
        "reviewed": True,
        "repayment_year": 2021,
        "benefit_receipt_year": 2020,
        "eligible_repayment_amount": Decimal("300"),
        "federal_claim_allocations_by_tax_year": {2021: Decimal("300")},
        "quebec_claim_amount": Decimal("300"),
    })

    result = calculate_return(data)
    federal = by_form(result, "T1")

    assert result.status == "complete"
    assert federal["13000"].value == Decimal("1500.00")
    assert federal["23210"].value == Decimal("300.00")
    assert federal["43700"].value == Decimal("150.00")
    assert by_form(result, "TP1")["246"].value == Decimal("300.00")


def test_2022_t4e_detail_repayment_is_not_double_counted():
    data = annual_input(2022)
    data.slips.append(
        SlipInput(
            slip_type="T4E",
            document_id="service-canada",
            issuer_id="service-canada",
            tax_year=2022,
            confirmed=True,
            fields={"14": Decimal("3000"), "18": Decimal("0"), "22": Decimal("300"), "26": Decimal("400"), "30": Decimal("400")},
        )
    )
    data.pandemic_repayment = data.pandemic_repayment.model_copy(update={
        "reviewed": True,
        "repayment_year": 2022,
        "benefit_receipt_year": 2020,
        "eligible_repayment_amount": Decimal("400"),
        "federal_claim_allocations_by_tax_year": {2022: Decimal("400")},
        "quebec_claim_amount": Decimal("400"),
    })

    result = calculate_return(data)
    federal = by_form(result, "T1")

    assert result.status == "complete"
    assert federal["11900"].value == Decimal("3000.00")
    assert federal["23210"].value == Decimal("400.00")
    assert federal["43700"].value == Decimal("300.00")
    assert by_form(result, "TP1")["111"].value == Decimal("3000.00")
    assert by_form(result, "TP1")["154"].value == Decimal("0.00")


def test_pandemic_repayment_requires_explicit_annual_allocation():
    data = annual_input(2021)
    data.slips.append(SlipInput(
        slip_type="T4A", document_id="repayment", issuer_id="cra", tax_year=2021,
        confirmed=True, fields={"201": Decimal("300")},
    ))

    result = calculate_return(data)

    assert result.status == "blocked"
    assert "missing_pandemic_repayment_allocation" in {blocker.code for blocker in result.blockers}


def test_2024_qpp2_is_deducted_above_the_second_ceiling():
    data = annual_input(2024, salary="73200")
    data.slips[0].fields.update({"17": Decimal("4160"), "17A": Decimal("188")})
    data.slips[1].fields.update({"B.A": Decimal("4160"), "B.B": Decimal("188")})

    result = calculate_return(data)
    federal = by_form(result, "T1")
    quebec = by_form(result, "TP1")

    assert result.status == "complete"
    assert federal["22215"].value == Decimal("838.00")
    assert quebec["248"].value == Decimal("838.00")
    schedule = by_form(result, "T1-S8")
    assert schedule["B"].value == Decimal("73200.00")
    assert schedule["C"].value == Decimal("68500.00")
    assert schedule["E"].value == Decimal("4700.00")
    assert schedule["15"].value == Decimal("188.00")
    assert schedule["42"].value == Decimal("838.00")


@pytest.mark.parametrize("year", range(2020, 2024))
def test_pre_qpp2_schedule_8_uses_the_annual_part_2_rows(year):
    result = calculate_return(annual_input(year))
    schedule = by_form(result, "T1-S8")

    assert schedule["A"].value == Decimal("12.00")
    assert schedule["1"].value == ANNUAL_RULES[year].qpp_ympe
    assert schedule["7"].value == by_form(result, "T1")["30800"].value
    assert schedule["8"].value == by_form(result, "T1")["22215"].value
    assert "B" not in schedule


def test_v2_student_loan_window_rejects_out_of_window_origin():
    data = annual_input(2020)
    data.student_loan_interest.federal_unused_by_origin_year[2014] = Decimal("10")
    data.taxpayer.has_student_loan_interest = True
    data.student_loan_interest.federal_claim_amount = Decimal("10")

    result = calculate_return(data)

    assert result.status == "blocked"
    assert "student_loan_origin_outside_claim_window" in {b.code for b in result.blockers}


def test_legacy_schema_remains_accepted_for_2025_only():
    assert calculate_return(_input(employed=False)).status == "complete"
    payload = _input(employed=False).model_dump()
    payload["tax_year"] = 2024
    result = calculate_return(TaxReturnInput.model_validate(payload))
    assert result.status == "blocked"
    assert "unsupported_schema_version" in {b.code for b in result.blockers}


@pytest.mark.parametrize(
    ("year", "qpp", "expected"),
    [(2020, "940.50", "1087.18"), (2021, "973.50", "1187.63"),
     (2022, "1014.75", "1281.38"), (2023, "1056.00", "1415.97"),
     (2024, "1056.00", "1522.24")],
)
def test_independent_quebec_salary_student_refunds(year, qpp, expected):
    data = annual_input(year, salary="20000")
    data.slips[0].fields.update({"17": Decimal(qpp), "18": Decimal("0"), "55": Decimal("98.80")})
    data.slips[1].fields.update({
        ("B.A" if year >= 2024 else "B"): Decimal(qpp),
        "E": Decimal("1000"), "H": Decimal("98.80"),
    })
    data.quebec_schedule_b.eligible_for_living_alone_amount = True
    data.taxpayer.has_student_loan_interest = True
    data.student_loan_interest.quebec_current_year_paid = Decimal("100")
    data.student_loan_interest.quebec_claim_amount = Decimal("100")
    data.quebec_tuition = data.quebec_tuition.model_copy(update={
        "has_current_tuition": True,
        "institution_outside_quebec": False,
        "eligible_tuition_or_exam_receipts": Decimal("2000"),
    })

    result = calculate_return(data)

    assert result.status == "complete"
    assert result.quebec_refund_or_balance == Decimal(expected)


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2020, "-2225.43"), (2021, "-2143.27"), (2022, "-2053.18"),
     (2023, "-1952.70"), (2024, "-1853.75")],
)
def test_current_tuition_uses_each_years_federal_credit_chain(year, expected):
    data = annual_input(year)
    data.slips.append(SlipInput(
        slip_type="T2202", document_id="t2202", issuer_id="school", tax_year=year,
        confirmed=True, fields={"24": Decimal("8"), "25": Decimal("0"), "26": Decimal("5000")},
    ))
    data.federal_tuition = data.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "t2202_eligible_fees": Decimal("5000"),
    })

    result = calculate_return(data)

    assert result.status == "complete"
    assert result.federal_refund_or_balance == Decimal(expected)


@pytest.mark.parametrize("period", ["march_to_december", "first_60_days"])
def test_v2_rrsp_receipt_periods_feed_assessed_limit_claim(period):
    data = annual_input(2023)
    data.slips.append(SlipInput(
        slip_type="RRSP_RECEIPT", document_id=f"rrsp-{period}", issuer_id="bank",
        tax_year=2023, rrsp_period=period, confirmed=True, fields={"amount": Decimal("1000")},
    ))
    data.rrsp = data.rrsp.model_copy(update={
        "has_contributions": True,
        "contribution_receipts": Decimal("1000"),
        "march_to_december_contributions": Decimal("1000") if period == "march_to_december" else Decimal("0"),
        "first_60_days_contributions": Decimal("1000") if period == "first_60_days" else Decimal("0"),
        "deduction_limit": Decimal("1000"),
        "deduction_requested": Decimal("1000"),
    })

    result = calculate_return(data)

    assert result.status == "complete"
    assert by_form(result, "T1")["20800"].value == Decimal("1000.00")
    assert by_form(result, "TP1")["214"].value == Decimal("1000.00")


def test_rrsp_receipts_must_reconcile_to_entered_period_totals():
    data = annual_input(2023)
    data.slips.append(SlipInput(
        slip_type="RRSP_RECEIPT", document_id="rrsp", issuer_id="bank", tax_year=2023,
        rrsp_period="first_60_days", confirmed=True, fields={"amount": Decimal("1000")},
    ))
    data.rrsp = data.rrsp.model_copy(update={
        "has_contributions": True, "contribution_receipts": Decimal("1000"),
        "march_to_december_contributions": Decimal("1000"), "first_60_days_contributions": Decimal("0"),
        "deduction_limit": Decimal("1000"), "deduction_requested": Decimal("1000"),
    })

    result = calculate_return(data)

    assert result.status == "blocked"
    assert "rrsp_receipt_period_mismatch" in {b.code for b in result.blockers}


def test_positive_interest_calculates_annual_schedule_f():
    data = annual_input(2020)
    data.slips.extend([
        SlipInput(slip_type="T5", document_id="t5", issuer_id="bank", tax_year=2020, confirmed=True, fields={"13": Decimal("20000")}),
        SlipInput(slip_type="RL3", document_id="rl3", issuer_id="bank", tax_year=2020, confirmed=True, fields={"D": Decimal("20000")}),
    ])

    result = calculate_return(data)
    quebec = by_form(result, "TP1")
    schedule_f = by_form(result, "TP1-F")

    assert result.status == "complete"
    assert schedule_f["70"].value == Decimal("20000.00")
    assert schedule_f["82"].value == Decimal("48.30")
    assert quebec["446"].value == Decimal("48.30")


def test_supported_scholarship_and_resp_paths_reconcile_both_returns():
    data = _with_scholarship(
        annual_input(2022), amount="4000", qualifying_student=True,
        attendance="full_time", intended_support="4000",
    )
    data = _with_resp_eap(data, amount="1000", withholding="100", quebec_withholding="50")
    for slip in data.slips:
        slip.tax_year = 2022

    result = calculate_return(data)
    federal = by_form(result, "T1")
    quebec = by_form(result, "TP1")

    assert result.status == "complete"
    assert federal["13010"].value == Decimal("0.00")
    assert federal["13000"].value == Decimal("1000.00")
    assert quebec["154"].value == Decimal("5000.00")
    assert quebec["295"].value == Decimal("4000.00")


@pytest.mark.parametrize("year", range(2020, 2025))
def test_every_annual_main_form_tax_line_has_a_source_label(year):
    result = calculate_return(annual_input(year))

    federal = by_form(result, "T1")
    quebec = by_form(result, "TP1")
    assert len(federal) >= 160
    assert len(quebec) >= 120
    assert all(line.source_ids and line.explanation for line in (*federal.values(), *quebec.values()))


def test_v2_2025_relative_fields_preserve_legacy_calculation():
    legacy = _input(employed=True)
    payload = legacy.model_dump()
    payload["schema_version"] = "qc-return-v2"
    payload["additional_return_screens"].pop("immigrated_or_emigrated_2025")
    payload["additional_return_screens"]["immigrated_or_emigrated_in_tax_year"] = False
    for field in [f"federal_unused_{year}" for year in range(2020, 2025)]:
        payload["student_loan_interest"].pop(field)
    payload["student_loan_interest"]["federal_unused_by_origin_year"] = {year: Decimal("0") for year in range(2020, 2025)}

    v2 = TaxReturnInput.model_validate(payload)

    assert calculate_return(v2).model_dump(exclude={"input_digest"}) == calculate_return(legacy).model_dump(exclude={"input_digest"})


def test_v2_2025_relative_rrsp_periods_calculate_schedule_7():
    data = _input(employed=True)
    payload = data.model_dump()
    payload["schema_version"] = "qc-return-v2"
    payload["additional_return_screens"]["immigrated_or_emigrated_in_tax_year"] = False
    payload["slips"].append({
        "slip_type": "RRSP_RECEIPT", "document_id": "rrsp", "issuer_id": "bank",
        "tax_year": 2025, "rrsp_period": "march_to_december", "confirmed": True,
        "fields": {"amount": Decimal("1000")},
    })
    payload["rrsp"].update({
        "has_contributions": True, "contribution_receipts": Decimal("1000"),
        "march_to_december_contributions": Decimal("1000"), "first_60_days_contributions": Decimal("0"),
        "deduction_limit": Decimal("1000"), "deduction_requested": Decimal("1000"),
    })

    result = calculate_return(TaxReturnInput.model_validate(payload))

    assert result.status == "complete"
    assert by_form(result, "T1")["20800"].value == Decimal("1000.00")


@pytest.mark.parametrize(
    ("year", "row_count", "tax_row", "rate_row", "final_row"),
    [
        (2020, 317, "71", "68", "154"),
        (2021, 332, "74", "71", "167"),
        (2022, 335, "74", "71", "169"),
        (2023, 341, "76", "73", "172"),
        (2024, 350, "82", "79", "177"),
    ],
)
def test_annual_t1_contains_every_canonical_and_printed_row(year, row_count, tax_row, rate_row, final_row):
    result = calculate_return(annual_input(year))
    federal = by_form(result, "T1")

    assert len(federal) == row_count
    assert federal[rate_row].value == Decimal("0.15")
    assert federal[tax_row].value == federal["40400"].value
    assert federal[final_row].value == abs(result.federal_refund_or_balance)


@pytest.mark.parametrize("year", range(2020, 2025))
def test_annual_cwb_and_work_premium_are_positive_when_eligible(year):
    data = annual_input(year, salary="20000")
    qpp = Decimal({2020: "940.50", 2021: "973.50", 2022: "1014.75", 2023: "1056", 2024: "1056"}[year])
    data.slips[0].fields.update({"17": qpp, "18": Decimal("0"), "55": Decimal("98.80")})
    data.slips[1].fields.update({("B.A" if year >= 2024 else "B"): qpp, "H": Decimal("98.80")})

    result = calculate_return(data)

    assert result.status == "complete"
    assert by_form(result, "T1")["45300"].value > 0
    assert by_form(result, "T1-S6")["28"].value == by_form(result, "T1")["45300"].value
    assert by_form(result, "TP1")["456"].value > 0
    assert by_form(result, "TP1-P")["90"].value == by_form(result, "TP1")["456"].value


def test_annual_tuition_and_resp_lines_are_numeric_when_applicable():
    data = _with_resp_eap(annual_input(2022), amount="1000", withholding="100", quebec_withholding="50")
    for slip in data.slips:
        slip.tax_year = 2022
    data.slips.append(SlipInput(
        slip_type="T2202", document_id="t2202", issuer_id="school", tax_year=2022,
        confirmed=True, fields={"24": Decimal("8"), "25": Decimal("0"), "26": Decimal("5000")},
    ))
    data.federal_tuition = data.federal_tuition.model_copy(update={"has_current_tuition": True, "t2202_eligible_fees": Decimal("5000")})
    data.quebec_tuition = data.quebec_tuition.model_copy(update={"has_current_tuition": True, "institution_outside_quebec": False, "eligible_tuition_or_exam_receipts": Decimal("5000")})

    result = calculate_return(data)

    assert result.status == "complete"
    assert by_form(result, "T1")["13000"].value == Decimal("1000.00")
    assert by_form(result, "T1")["32300"].value > 0
    assert by_form(result, "TP1")["154"].value == Decimal("1000.00")
    assert by_form(result, "TP1")["398"].value > 0


def test_annual_carryforward_outputs_are_named_proposed_balances():
    data = annual_input(2024, salary="20000")
    data.slips.append(SlipInput(
        slip_type="T2202", document_id="t2202", issuer_id="school", tax_year=2024,
        confirmed=True, fields={"24": Decimal("8"), "25": Decimal("0"), "26": Decimal("30000")},
    ))
    data.federal_tuition = data.federal_tuition.model_copy(update={"has_current_tuition": True, "t2202_eligible_fees": Decimal("30000")})
    data.quebec_tuition = data.quebec_tuition.model_copy(update={"has_current_tuition": True, "institution_outside_quebec": False, "eligible_tuition_or_exam_receipts": Decimal("30000")})

    result = calculate_return(data)

    assert result.status == "complete"
    assert result.carryforwards["federal_tuition_unused_fees"].amount == by_form(result, "T1-S11")["25"].value
    assert result.carryforwards["quebec_tuition_unused_fees_8_percent"].amount == by_form(result, "TP1-T")["48"].value
    assert result.carryforwards["quebec_tuition_unused_fees_8_percent"].basis == "proposed_closing"


def test_pension_adjustment_is_reported_without_being_deducted():
    data = annual_input(2023)
    data.slips[0].fields["52"] = Decimal("4500")

    result = calculate_return(data)

    assert result.status == "complete"
    assert by_form(result, "T1")["20600"].value == Decimal("4500.00")
    assert by_form(result, "T1")["23300"].value != Decimal("4500.00")


def _add_t2202(data: TaxReturnInput, fees: str) -> None:
    data.slips.append(SlipInput(
        slip_type="T2202", document_id="t2202", issuer_id="school",
        tax_year=data.tax_year, confirmed=True,
        fields={"24": Decimal("8"), "25": Decimal("0"), "26": Decimal(fees)},
    ))


def test_positive_t2202_conflicting_with_negative_tuition_answer_blocks():
    data = annual_input(2023)
    _add_t2202(data, "5000")

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert "federal_tuition_evidence_mismatch" in {item.code for item in result.blockers}


def test_canada_training_credit_above_half_current_tuition_blocks():
    data = annual_input(2023)
    _add_t2202(data, "5000")
    data.federal_tuition = data.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "wants_canada_training_credit": True,
        "canada_training_credit_limit": Decimal("5000"),
        "canada_training_credit_claim": Decimal("5000"),
    })

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert "training_credit_claim_exceeds_available" in {item.code for item in result.blockers}


def test_positive_canada_training_credit_claim_requires_an_affirmative_election():
    data = annual_input(2023)
    _add_t2202(data, "5000")
    data.federal_tuition = data.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "canada_training_credit_limit": Decimal("2500"),
        "canada_training_credit_claim": Decimal("1000"),
    })

    result = calculate_return(data)

    assert result.status == "blocked"
    assert "training_credit_election_mismatch" in {item.code for item in result.blockers}


def test_lawful_canada_training_credit_uses_annual_schedule_11_rows():
    data = annual_input(2023)
    _add_t2202(data, "5000")
    data.federal_tuition = data.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "wants_canada_training_credit": True,
        "canada_training_credit_limit": Decimal("5000"),
        "canada_training_credit_claim": Decimal("2500"),
    })

    result = calculate_return(data)
    schedule = by_form(result, "T1-S11")

    assert result.status == "complete"
    assert schedule["3"].value == Decimal("2500.00")
    assert schedule["4"].value == Decimal("5000.00")
    assert schedule["5"].value == Decimal("2500.00")
    assert schedule["6"].value == Decimal("2500.00")
    assert by_form(result, "T1")["45350"].value == Decimal("2500.00")
    assert by_form(result, "T1")["32300"].value == Decimal("2500.00")
    assert result.federal_refund_or_balance == Decimal("234.18")


@pytest.mark.parametrize(
    ("year", "month", "expected"),
    [
        (2020, 1, "589.00"), (2020, 7, "588.00"),
        (2021, 1, "630.83"), (2021, 7, "626.83"),
        (2022, 1, "650.83"), (2022, 7, "650.83"),
        (2023, 1, "661.33"), (2023, 7, "659.58"),
        (2024, 1, "676.58"), (2024, 7, "675.50"),
    ],
)
def test_schedule_k_preserves_first_and_second_half_exempt_months(year, month, expected):
    data = annual_input(year)
    data.drug_insurance.group_plan_months = {month}
    data.drug_insurance.eligible_student_months = set()

    result = calculate_return(data)
    schedule = by_form(result, "TP1-K")

    assert result.status == "complete"
    assert schedule["60"].value == Decimal(int(month <= 6))
    assert schedule["61"].value == Decimal(int(month > 6))
    assert schedule["62"].value == Decimal("1.00")
    assert schedule["90"].value == Decimal(expected)


@pytest.mark.parametrize("year", range(2020, 2025))
def test_t4_and_rl1_qpp_contributions_must_reconcile(year):
    data = annual_input(year)
    data.slips[1].fields["B.A" if year >= 2024 else "B"] = Decimal("0")

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert result.quebec_refund_or_balance is None
    assert "qpp_slip_contribution_mismatch" in {item.code for item in result.blockers}


def test_2024_t4_and_rl1_second_qpp_contributions_must_reconcile():
    data = annual_input(2024, salary="73200")
    data.slips[0].fields.update({"17": Decimal("4160"), "17A": Decimal("188")})
    data.slips[1].fields.update({"B.A": Decimal("4160"), "B.B": Decimal("0")})

    result = calculate_return(data)

    assert result.status == "blocked"
    assert "qpp_slip_contribution_mismatch" in {item.code for item in result.blockers}


def test_unknown_qpp_contribution_period_facts_block_annual_schedule_8():
    data = annual_input(2023)
    data.taxpayer = data.taxpayer.model_copy(update={
        "age_dec31": None,
        "received_qpp_disability_pension": None,
        "made_qpp_cpt30_election": None,
    })

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert "missing_qpp_contribution_period" in {item.code for item in result.blockers}


@pytest.mark.parametrize(
    ("year", "box"),
    [
        (2020, "22"),
        (2021, "24"),
        (2022, "26"),
        (2023, "55"),
        (2024, "17A"),
    ],
)
def test_annual_t4_required_payroll_boxes_cannot_be_absent(year, box):
    data = annual_input(year)
    data.slips[0].fields.pop(box)

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert result.quebec_refund_or_balance is None
    assert "missing_slip_box" in {item.code for item in result.blockers}
    assert any(f"fields.{box}" in path for item in result.blockers for path in item.input_paths)


@pytest.mark.parametrize("metadata_field", ["province_of_employment", "cpp_qpp_exempt", "ei_exempt", "ppip_exempt"])
def test_annual_t4_required_metadata_cannot_be_unknown(metadata_field):
    data = annual_input(2024)
    data.slips[0] = data.slips[0].model_copy(update={metadata_field: None})

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert result.quebec_refund_or_balance is None
    assert any(metadata_field in path for item in result.blockers for path in item.input_paths)


def test_annual_t4_explicit_zero_payroll_boxes_remain_accepted():
    data = annual_input(2024)
    data.slips[0].fields.update({"17A": Decimal("0"), "20": Decimal("0"), "22": Decimal("0")})

    result = calculate_return(data)

    assert result.status == "complete"


@pytest.mark.parametrize("year", range(2020, 2025))
def test_annual_t2202_enrolment_month_boxes_cannot_be_absent(year):
    data = annual_input(year, salary="20000")
    _add_t2202(data, "5000")
    data.slips[-1].fields.pop("24")
    data.federal_tuition = data.federal_tuition.model_copy(update={"has_current_tuition": True})

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert "missing_slip_box" in {item.code for item in result.blockers}
    assert any("fields.24" in path for item in result.blockers for path in item.input_paths)


def test_2020_schedule_11_uses_line_24_for_the_closing_carryforward():
    data = annual_input(2020, salary="20000")
    _add_t2202(data, "30000")
    data.federal_tuition = data.federal_tuition.model_copy(update={"has_current_tuition": True})

    result = calculate_return(data)
    schedule = by_form(result, "T1-S11")

    assert result.status == "complete"
    assert schedule["2"].value == Decimal("30000.00")
    assert schedule["24"].value == Decimal("25852.07")
    assert "25" not in schedule
    assert result.carryforwards["federal_tuition_unused_fees"].source_line_ids == ["T1-S11:24"]


def test_federal_tuition_transfer_reduces_2024_carryforward():
    data = annual_input(2024, salary="20000")
    _add_t2202(data, "30000")
    data.federal_tuition = data.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "wants_transfer": True,
        "transfer_amount": Decimal("3000"),
    })

    result = calculate_return(data)
    schedule = by_form(result, "T1-S11")

    assert result.status == "complete"
    assert schedule["23"].value == Decimal("3655.60")
    assert schedule["24"].value == Decimal("3000.00")
    assert schedule["25"].value == Decimal("25655.60")
    assert result.carryforwards["federal_tuition_unused_fees"].amount == Decimal("25655.60")


def test_federal_tuition_transfer_above_current_year_limit_blocks():
    data = annual_input(2024, salary="20000")
    _add_t2202(data, "30000")
    data.federal_tuition = data.federal_tuition.model_copy(update={
        "has_current_tuition": True,
        "wants_transfer": True,
        "transfer_amount": Decimal("4000"),
    })

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert "federal_tuition_transfer_exceeds_available" in {item.code for item in result.blockers}


def test_quebec_tuition_transfer_reduces_current_fee_pool_before_carryforward():
    data = annual_input(2024, salary="20000")
    data.quebec_tuition = data.quebec_tuition.model_copy(update={
        "has_current_tuition": True,
        "institution_outside_quebec": False,
        "eligible_tuition_or_exam_receipts": Decimal("30000"),
        "wants_transfer": True,
        "transfer_amount": Decimal("1000"),
    })

    result = calculate_return(data)
    schedule = by_form(result, "TP1-T")

    assert result.status == "complete"
    assert schedule["66"].value == Decimal("2318.94")
    assert schedule["68"].value == Decimal("1000.00")
    assert schedule["42"].value == Decimal("12500.00")
    assert schedule["43"].value == Decimal("17500.00")
    assert schedule["48"].value == Decimal("16486.75")


def test_quebec_tuition_transfer_above_available_credit_blocks():
    data = annual_input(2024, salary="20000")
    data.quebec_tuition = data.quebec_tuition.model_copy(update={
        "has_current_tuition": True,
        "institution_outside_quebec": False,
        "eligible_tuition_or_exam_receipts": Decimal("30000"),
        "wants_transfer": True,
        "transfer_amount": Decimal("2400"),
    })

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.quebec_refund_or_balance is None
    assert "quebec_tuition_transfer_exceeds_available" in {item.code for item in result.blockers}


def test_post_2022_pandemic_repayment_cannot_be_allocated_to_the_benefit_year():
    data = annual_input(2020)
    data.pandemic_repayment = data.pandemic_repayment.model_copy(update={
        "reviewed": True,
        "repayment_year": 2024,
        "benefit_receipt_year": 2020,
        "eligible_repayment_amount": Decimal("300"),
        "federal_claim_allocations_by_tax_year": {2020: Decimal("300")},
        "quebec_claim_amount": Decimal("0"),
    })

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert "invalid_pandemic_repayment_claim_year" in {item.code for item in result.blockers}


def test_post_2022_pandemic_repayment_uses_line_23200_in_repayment_year():
    data = annual_input(2024)
    data.pandemic_repayment = data.pandemic_repayment.model_copy(update={
        "reviewed": True,
        "repayment_year": 2024,
        "benefit_receipt_year": 2020,
        "eligible_repayment_amount": Decimal("300"),
        "federal_claim_allocations_by_tax_year": {2024: Decimal("300")},
        "quebec_claim_amount": Decimal("0"),
    })

    result = calculate_return(data)

    assert result.status == "complete"
    assert by_form(result, "T1")["23200"].value == Decimal("300.00")
