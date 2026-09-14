from decimal import Decimal

import pytest

from taxagent.returns import (
    AdditionalReturnScreenInput,
    DocumentInventory,
    DrugInsuranceInput,
    FederalTuitionInput,
    InstalmentInput,
    QuebecScheduleBInput,
    QuebecTuitionInput,
    RefundableCreditInput,
    RespEapInput,
    RespEapPaymentInput,
    RrspInput,
    SlipInput,
    ScholarshipAwardInput,
    ScholarshipInput,
    ScholarshipPartTimeProgramInput,
    StudentLoanInterestInput,
    TaxReturnInput,
    TaxpayerFacts,
    calculate_federal,
    calculate_qpp_schedule8,
    calculate_return,
    preflight,
)
from taxagent.returns.federal_2025_qc import _federal_top_up


def _facts(*, full_time_student: bool = False) -> TaxpayerFacts:
    return TaxpayerFacts(
        full_year_canada_resident=True,
        full_year_quebec_resident=True,
        province_dec31="QC",
        age_dec31=30,
        marital_status="single",
        dependant_count=0,
        deceased_return=False,
        bankruptcy_return=False,
        has_self_employment=False,
        has_capital_gains=False,
        has_rental_income=False,
        has_foreign_income_or_tax=False,
        has_foreign_property_over_100k=False,
        has_crypto_transactions=False,
        has_pension_or_benefit_income=False,
        has_indian_act_exempt_income=False,
        has_disability_or_caregiver_claim=False,
        has_employment_expenses=False,
        has_medical_expenses=False,
        has_donations=False,
        has_childcare_expenses=False,
        has_moving_expenses=False,
        has_tips_or_other_employment_income=False,
        has_student_loan_interest=False,
        received_qpp_disability_pension=False,
        made_qpp_cpt30_election=False,
        was_full_time_student_more_than_13_weeks=full_time_student,
    )


def _t4(issuer: str = "employer-a") -> SlipInput:
    return SlipInput(
        slip_type="T4",
        document_id=f"t4-{issuer}",
        issuer_id=issuer,
        tax_year=2025,
        province_of_employment="QC",
        cpp_qpp_exempt=False,
        ei_exempt=False,
        ppip_exempt=False,
        confirmed=True,
        fields={
            "14": Decimal("50000.00"),
            "17": Decimal("2976.00"),
            "17A": Decimal("0.00"),
            "18": Decimal("655.00"),
            "20": Decimal("0.00"),
            "22": Decimal("6000.00"),
            "24": Decimal("50000.00"),
            "26": Decimal("50000.00"),
            "44": Decimal("0.00"),
            "52": Decimal("0.00"),
            "55": Decimal("247.00"),
        },
    )


def _rl1(issuer: str = "employer-a") -> SlipInput:
    return SlipInput(
        slip_type="RL1",
        document_id=f"rl1-{issuer}",
        issuer_id=issuer,
        tax_year=2025,
        confirmed=True,
        fields={
            "A": Decimal("50000.00"),
            "B.A": Decimal("2976.00"),
            "B.B": Decimal("0.00"),
            "C": Decimal("655.00"),
            "D": Decimal("0.00"),
            "E": Decimal("5000.00"),
            "F": Decimal("0.00"),
            "G": Decimal("50000.00"),
            "H": Decimal("247.00"),
            "I": Decimal("50000.00"),
            "211": Decimal("0.00"),
        },
    )


def _t2202(
    issuer: str,
    fees: str,
    *,
    part_time_months: str = "0",
    full_time_months: str = "0",
) -> SlipInput:
    return SlipInput(
        slip_type="T2202",
        document_id=f"t2202-{issuer}-{fees}",
        issuer_id=issuer,
        tax_year=2025,
        confirmed=True,
        fields={
            "24": Decimal(part_time_months),
            "25": Decimal(full_time_months),
            "26": Decimal(fees),
        },
    )


def _rrsp_receipt(document: str, amount: str, period: str) -> SlipInput:
    return SlipInput(
        slip_type="RRSP_RECEIPT",
        document_id=document,
        issuer_id="rrsp-issuer",
        tax_year=2025,
        rrsp_period=period,
        confirmed=True,
        fields={"amount": Decimal(amount)},
    )


def _rc210(*, basic: str, disability: str = "0") -> SlipInput:
    return SlipInput(
        slip_type="RC210",
        document_id="rc210-2025",
        issuer_id="cra",
        tax_year=2025,
        confirmed=True,
        fields={"10": Decimal(basic), "11": Decimal(disability)},
    )


def _with_scholarship(
    data: TaxReturnInput,
    *,
    amount: str,
    qualifying_student: bool,
    attendance: str,
    intended_support: str = "0",
    part_time_costs: str = "0",
) -> TaxReturnInput:
    award_amount = Decimal(amount)
    award = ScholarshipAwardInput(
        award_id="award-a",
        issuer_id="university-a",
        amount=award_amount,
        category="ordinary_postsecondary",
        qualifying_student=qualifying_student,
        attendance=attendance,
        intended_enrolment_support=Decimal(intended_support),
        part_time_program_id="program-a" if attendance == "part_time" else None,
    )
    return data.model_copy(
        update={
            "slips": [
                *data.slips,
                SlipInput(
                    slip_type="T4A",
                    document_id="t4a-award-a",
                    issuer_id="university-a",
                    tax_year=2025,
                    confirmed=True,
                    fields={"105": award_amount, "22": Decimal("0")},
                ),
                SlipInput(
                    slip_type="RL1",
                    document_id="rl1-award-a",
                    issuer_id="university-a",
                    tax_year=2025,
                    confirmed=True,
                    rl1_box_o_allocations={"RB": award_amount},
                    fields={"O": award_amount},
                ),
            ],
            "inventory": data.inventory.model_copy(update={"no_income_sources": False}),
            "scholarships": ScholarshipInput(
                reviewed=True,
                awards=[award],
                part_time_programs=(
                    [
                        ScholarshipPartTimeProgramInput(
                            program_id="program-a",
                            eligible_tuition_and_required_materials=Decimal(part_time_costs),
                        )
                    ]
                    if attendance == "part_time"
                    else []
                ),
            ),
        }
    )


def _with_resp_eap(
    data: TaxReturnInput,
    *,
    amount: str,
    withholding: str = "0",
    quebec_withholding: str = "0",
) -> TaxReturnInput:
    payment_amount = Decimal(amount)
    return data.model_copy(
        update={
            "slips": [
                *data.slips,
                SlipInput(
                    slip_type="T4A",
                    document_id="t4a-resp-a",
                    issuer_id="resp-promoter-a",
                    tax_year=2025,
                    confirmed=True,
                    fields={"042": payment_amount, "22": Decimal(withholding)},
                ),
                SlipInput(
                    slip_type="RL1",
                    document_id="rl1-resp-a",
                    issuer_id="resp-promoter-a",
                    tax_year=2025,
                    confirmed=True,
                    rl1_box_o_allocations={"RU": payment_amount},
                    fields={"O": payment_amount, "E": Decimal(quebec_withholding)},
                ),
            ],
            "inventory": data.inventory.model_copy(update={"no_income_sources": False}),
            "resp_eap": RespEapInput(
                reviewed=True,
                has_other_resp_payments=False,
                qesi_cumulative_amount_over_3600=False,
                payments=[
                    RespEapPaymentInput(
                        payment_id="resp-a",
                        issuer_id="resp-promoter-a",
                        amount=payment_amount,
                    )
                ],
            ),
        }
    )


def _input(*, employed: bool, full_time_student: bool = False) -> TaxReturnInput:
    slips = [_t4(), _rl1()] if employed else []
    return TaxReturnInput(
        tax_year=2025,
        province_dec31="QC",
        taxpayer=_facts(full_time_student=full_time_student),
        slips=slips,
        inventory=DocumentInventory(
            income_sources_reviewed=True,
            deductions_reviewed=True,
            credits_reviewed=True,
            cra_records_reviewed=True,
            revenu_quebec_records_reviewed=True,
            no_income_sources=not employed,
        ),
        federal_tuition=FederalTuitionInput(
            has_current_tuition=False,
            has_prior_unused=False,
            wants_transfer=False,
            wants_canada_training_credit=False,
        ),
        quebec_tuition=QuebecTuitionInput(
            has_current_tuition=False,
            has_prior_unused=False,
            wants_transfer=False,
        ),
        rrsp=RrspInput(has_contributions=False, has_prior_unused_contributions=False, has_hbp_or_llp_activity=False),
        instalments=InstalmentInput(
            federal_reviewed=True,
            federal_paid=Decimal("0"),
            quebec_reviewed=True,
            quebec_paid=Decimal("0"),
        ),
        quebec_schedule_b=QuebecScheduleBInput(
            living_alone_reviewed=True,
            eligible_for_living_alone_amount=False,
        ),
        student_loan_interest=StudentLoanInterestInput(
            reviewed=True,
            qualifying_government_loans_confirmed=True,
            federal_current_year_paid=Decimal("0"),
            federal_unused_2020=Decimal("0"),
            federal_unused_2021=Decimal("0"),
            federal_unused_2022=Decimal("0"),
            federal_unused_2023=Decimal("0"),
            federal_unused_2024=Decimal("0"),
            federal_claim_amount=Decimal("0"),
            quebec_prior_unused=Decimal("0"),
            quebec_current_year_paid=Decimal("0"),
            quebec_claim_amount=Decimal("0"),
        ),
        scholarships=ScholarshipInput(reviewed=True, awards=[], part_time_programs=[]),
        resp_eap=RespEapInput(
            reviewed=True,
            has_other_resp_payments=False,
            qesi_cumulative_amount_over_3600=False,
            payments=[],
        ),
        additional_return_screens=AdditionalReturnScreenInput(
            immigrated_or_emigrated_2025=False,
            quebec_trust_return=False,
            separate_post_death_return=False,
            quebec_enterprise_registration_or_annual_fee=False,
        ),
        drug_insurance=DrugInsuranceInput(
            reviewed=True,
            group_plan_months=set(range(1, 13)),
            group_plan_source="self",
            eligible_student_months=set(),
            other_exemption_applies=False,
        ),
        refundable_credits=RefundableCreditInput(
            work_premium_answers_reviewed=True,
            solidarity_answers_reviewed=True,
            canada_workers_benefit_answers_reviewed=True,
            rl19_advance_payments_reviewed=True,
            rl19_box_a=Decimal("0.00"),
            rl19_box_b=Decimal("0.00"),
            rl19_has_other_advance_boxes=False,
            cwb_incarcerated_90_days=False,
            cwb_foreign_officer_exempt=False,
            advanced_cwb_paid=Decimal("0.00"),
            advanced_cwb_disability_paid=Decimal("0.00"),
            work_premium_eligible_status=True,
            quebec_work_premium_full_time_student=full_time_student,
            transferred_schedule_s_amount=False,
            family_allowance_received_for_self=False,
            turned_18_before_december=True,
            designated_as_dependent_child=False,
            incarcerated_over_183_days=False,
            adapted_work_premium_eligible=False,
            work_premium_supplement_months=0,
            request_tax_shield=False,
            wants_solidarity_credit=False,
        ),
    )


def test_schedule8_allocates_required_qpp_base_and_enhanced_contributions():
    result = calculate_qpp_schedule8(_input(employed=True))

    assert result.complete
    assert result.lines["7"].value == Decimal("46500.00")
    assert result.lines["11"].value == Decimal("2511.00")
    assert result.lines["12"].value == Decimal("465.00")
    assert result.lines["24"].value == Decimal("0.00")
    assert set(map(str, range(29, 48))) <= result.lines.keys()
    assert result.lines["29"].value == Decimal("2511.00")
    assert result.lines["35"].value == Decimal("2511.00")
    assert result.lines["42"].value == Decimal("465.00")
    assert result.lines["47"].value == Decimal("465.00")


def test_schedule8_emits_part_2a_when_contributions_exceed_required_amounts():
    data = _input(employed=True)
    t4 = data.slips[0]
    data.slips[0] = t4.model_copy(
        update={"fields": {**t4.fields, "17": Decimal("3000.00")}}
    )

    result = calculate_qpp_schedule8(data)

    assert result.complete
    assert result.lines["24"].value == Decimal("24.00")
    assert set(map(str, range(25, 29))) <= result.lines.keys()
    assert "29" not in result.lines
    assert result.lines["25"].value == Decimal("2511.00")
    assert result.lines["28"].value == Decimal("465.00")


def test_schedule8_undercontribution_uses_part_2b_without_optional_contribution():
    data = _input(employed=True)
    t4 = data.slips[0]
    data.slips[0] = t4.model_copy(
        update={"fields": {**t4.fields, "17": Decimal("2900.00")}}
    )

    result = calculate_qpp_schedule8(data)

    assert result.complete
    assert result.lines["24"].value == Decimal("-76.00")
    assert result.lines["35"].value == Decimal("2446.88")
    assert result.lines["42"].value == Decimal("453.12")
    assert result.lines["47"].value == Decimal("453.12")


def test_blank_t4_pensionable_and_insurable_boxes_fall_back_to_box_14():
    data = _input(employed=True)
    t4 = data.slips[0]
    fields = {box: value for box, value in t4.fields.items() if box not in {"24", "26"}}
    data.slips[0] = t4.model_copy(update={"fields": fields})

    qpp = calculate_qpp_schedule8(data)
    federal = calculate_federal(data)

    assert qpp.lines["1"].value == Decimal("50000.00")
    assert federal.lines["31200"].value == Decimal("655.00")
    assert federal.lines["45000"].value == Decimal("0.00")
    assert federal.lines["31200"].source_ids == ["cra_2025_t2204"]
    assert federal.lines["45000"].source_ids == ["cra_2025_t2204"]


def test_2025_federal_top_up_uses_official_3_45_percent_rate():
    assert _federal_top_up(Decimal("17057.51")) == Decimal("301.47")


def test_schedule11_emits_full_claim_carryforward_and_enrolment_trace():
    data = _input(employed=True)
    data.slips.append(
        _t2202("university-a", "4000.00", part_time_months="2", full_time_months="8")
    )
    data.federal_tuition = FederalTuitionInput(
        has_current_tuition=True,
        t2202_eligible_fees=Decimal("4000.00"),
        has_prior_unused=False,
        wants_transfer=False,
        wants_canada_training_credit=False,
    )

    result = calculate_federal(data)

    assert result.complete
    assert {f"S11:{line}" for line in range(1, 26)} <= result.lines.keys()
    assert result.lines["S11:1"].value == Decimal("4000.00")
    assert result.lines["S11:8"].value == Decimal("4000.00")
    assert result.lines["S11:17"].value == Decimal("4000.00")
    assert result.lines["S11:20"].value == Decimal("0.00")
    assert result.lines["S11:25"].value == Decimal("0.00")
    assert result.lines["S11:32010"].value == Decimal("2.00")
    assert result.lines["S11:32020"].value == Decimal("8.00")


def test_schedule11_line_12_uses_t1_row_105_before_student_loan_interest():
    data = _input(employed=True)
    data.slips.append(_t2202("university-a", "40000.00", full_time_months="8"))
    data.federal_tuition = FederalTuitionInput(
        has_current_tuition=True,
        t2202_eligible_fees=Decimal("40000.00"),
        has_prior_unused=False,
        wants_transfer=False,
        wants_canada_training_credit=False,
    )
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

    result = calculate_federal(data)

    assert result.lines["105"].value == Decimal("21013.00")
    assert result.lines["S11:12"].value == Decimal("21013.00")
    assert result.lines["S11:17"].value == Decimal("28522.00")
    assert result.lines["S11:25"].value == Decimal("11478.00")
    assert result.lines["33500"].value == Decimal("50135.00")

    final = calculate_return(data)
    final_lines = {(line.form_id, line.line_id): line for line in final.lines}
    assert final.status == "complete"
    assert final_lines[("T1", "105")].value == final_lines[("T1-S11", "12")].value
    assert final_lines[("T1-S11", "17")].value == Decimal("28522.00")
    assert final_lines[("T1-S11", "25")].value == Decimal("11478.00")


def test_schedule11_applies_100_dollar_threshold_per_institution():
    split = _input(employed=True)
    split.slips.extend([_t2202("college-a", "60.00"), _t2202("college-b", "60.00")])
    split.federal_tuition = FederalTuitionInput(
        has_current_tuition=True,
        t2202_eligible_fees=Decimal("0.00"),
        has_prior_unused=False,
        wants_transfer=False,
        wants_canada_training_credit=False,
    )
    combined = _input(employed=True)
    combined.slips.extend([_t2202("college-a", "60.00"), _t2202("college-a", "60.00")])
    combined.federal_tuition = split.federal_tuition.model_copy(
        update={"t2202_eligible_fees": Decimal("120.00")}
    )

    assert calculate_federal(split).lines["S11:1"].value == Decimal("0.00")
    assert calculate_federal(combined).lines["S11:1"].value == Decimal("120.00")


def test_schedule11_traces_canada_training_credit_before_tuition_claim():
    data = _input(employed=True)
    data.slips.append(_t2202("university-a", "4000.00", full_time_months="8"))
    data.federal_tuition = FederalTuitionInput(
        has_current_tuition=True,
        t2202_eligible_fees=Decimal("4000.00"),
        has_prior_unused=False,
        wants_transfer=False,
        wants_canada_training_credit=True,
        canada_training_credit_limit=Decimal("1000.00"),
        canada_training_credit_claim=Decimal("1000.00"),
    )

    result = calculate_federal(data)

    assert result.lines["S11:2"].value == Decimal("2000.00")
    assert result.lines["S11:4"].value == Decimal("1000.00")
    assert result.lines["S11:5"].value == Decimal("1000.00")
    assert result.lines["S11:6"].value == Decimal("3000.00")
    assert result.lines["S11:17"].value == Decimal("3000.00")
    assert result.lines["32300"].value == Decimal("3000.00")
    assert result.lines["45350"].value == Decimal("1000.00")


def test_schedule7_traces_current_prior_deduction_and_carryforward():
    data = _input(employed=True)
    data.slips.extend(
        [
            _rrsp_receipt("rrsp-2025", "2000.00", "march_to_december_2025"),
            _rrsp_receipt("rrsp-2026", "500.00", "first_60_days_2026"),
        ]
    )
    data.rrsp = RrspInput(
        has_contributions=True,
        contribution_receipts=Decimal("2500.00"),
        march_to_december_contributions=Decimal("2000.00"),
        first_60_days_contributions=Decimal("500.00"),
        has_prior_unused_contributions=True,
        prior_unused_contributions=Decimal("1000.00"),
        deduction_limit=Decimal("3000.00"),
        deduction_requested=Decimal("2500.00"),
        has_hbp_or_llp_activity=False,
    )

    result = calculate_federal(data)

    assert {f"S7:{line}" for line in range(1, 24)} <= result.lines.keys()
    assert result.lines["S7:5"].value == Decimal("3500.00")
    assert result.lines["S7:10"].value == Decimal("3500.00")
    assert result.lines["S7:17"].value == Decimal("3000.00")
    assert result.lines["S7:20"].value == Decimal("2500.00")
    assert result.lines["S7:23"].value == Decimal("1000.00")
    assert result.lines["20800"].value == Decimal("2500.00")


def test_schedule6_traces_basic_cwb_and_rc210_lesser_of_calculation():
    data = _input(employed=True)
    t4 = data.slips[0]
    data.slips[0] = t4.model_copy(
        update={
            "fields": {
                **t4.fields,
                "14": Decimal("10000.00"),
                "17": Decimal("416.00"),
                "18": Decimal("131.00"),
                "22": Decimal("500.00"),
                "24": Decimal("10000.00"),
                "26": Decimal("10000.00"),
                "55": Decimal("49.40"),
            }
        }
    )
    data.slips.append(_rc210(basic="500.00"))
    data.refundable_credits = data.refundable_credits.model_copy(
        update={
            "advanced_cwb_paid": Decimal("500.00"),
            "advanced_cwb_disability_paid": Decimal("0.00"),
        }
    )

    result = calculate_federal(data)

    assert {f"S6:{line}" for line in range(1, 29)} <= result.lines.keys()
    assert {f"S6:{line}" for line in range(43, 50)} <= result.lines.keys()
    assert result.lines["S6:5"].value == Decimal("10000.00")
    assert result.lines["S6:15"].value == Decimal("9935.00")
    assert result.lines["S6:28"].value == Decimal("2834.80")
    assert result.lines["S6:44"].value == Decimal("500.00")
    assert result.lines["S6:49"].value == Decimal("500.00")
    assert result.lines["45300"].value == Decimal("2834.80")
    assert result.lines["41500"].value == Decimal("500.00")


def test_schedule6_limits_line_41500_to_current_entitlement():
    data = _input(employed=True)
    t4 = data.slips[0]
    data.slips[0] = t4.model_copy(
        update={
            "fields": {
                **t4.fields,
                "14": Decimal("3000.00"),
                "17": Decimal("0.00"),
                "17A": Decimal("0.00"),
                "18": Decimal("39.30"),
                "22": Decimal("0.00"),
                "24": Decimal("3000.00"),
                "26": Decimal("3000.00"),
                "55": Decimal("14.82"),
            }
        }
    )
    data.slips.append(_rc210(basic="500.00"))
    data.refundable_credits = data.refundable_credits.model_copy(
        update={"advanced_cwb_paid": Decimal("500.00")}
    )

    result = calculate_federal(data)

    assert result.lines["S6:28"].value == Decimal("223.80")
    assert result.lines["S6:48"].value == Decimal("500.00")
    assert result.lines["S6:49"].value == Decimal("223.80")
    assert result.lines["41500"].value == Decimal("223.80")


def test_cwb_student_exclusion_applies_only_when_full_time_study_exceeds_13_weeks():
    eligible = _input(employed=True, full_time_student=False)
    excluded = _input(employed=True, full_time_student=True)
    for data in (eligible, excluded):
        t4 = data.slips[0]
        data.slips[0] = t4.model_copy(
            update={"fields": {**t4.fields, "14": Decimal("10000.00")}}
        )

    assert calculate_federal(eligible).lines["45300"].value > Decimal("0.00")
    assert calculate_federal(excluded).lines["45300"].value == Decimal("0.00")


def test_t5_interest_uses_box_13_and_never_box_22_identifier():
    data = _input(employed=False)
    data.slips.append(
        SlipInput(
            slip_type="T5",
            document_id="t5-bank",
            issuer_id="bank",
            tax_year=2025,
            confirmed=True,
            fields={"13": Decimal("100.00"), "22": Decimal("999999.00")},
        )
    )

    result = calculate_federal(data)

    assert result.lines["12100"].value == Decimal("100.00")
    assert result.lines["15000"].value == Decimal("100.00")


def test_federal_student_loan_interest_claim_uses_current_and_oldest_prior_amounts():
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

    result = calculate_federal(data)

    assert result.lines["31900"].value == Decimal("600.00")
    assert result.lines["31900"].inputs == [
        "student_loan_interest.federal_unused_2020",
        "student_loan_interest.federal_current_year_paid",
    ]
    assert result.lines["33500"].value == Decimal("21613.00")
    assert result.lines["48400"].value == Decimal("2619.34")


@pytest.mark.parametrize(
    ("amount", "qualifying", "attendance", "support", "part_time_costs", "taxable"),
    [
        ("4500", True, "full_time", "4500", "0", "0.00"),
        ("5000", True, "full_time", "4000", "0", "500.00"),
        ("2000", True, "part_time", "0", "1300", "200.00"),
        ("2000", False, "nonqualifying", "0", "0", "1500.00"),
    ],
)
def test_ordinary_scholarship_exemption_uses_enrolment_support_then_basic_500(
    amount, qualifying, attendance, support, part_time_costs, taxable
):
    data = _with_scholarship(
        _input(employed=False, full_time_student=attendance == "full_time"),
        amount=amount,
        qualifying_student=qualifying,
        attendance=attendance,
        intended_support=support,
        part_time_costs=part_time_costs,
    )

    result = calculate_federal(data)

    assert preflight(data) == []
    assert result.lines["13010"].value == Decimal(taxable)
    assert result.lines["15000"].value == Decimal(taxable)
    if "S6:2" in result.lines:
        assert result.lines["S6:2"].value == Decimal(taxable)


def test_part_time_program_cost_pool_is_used_once_across_multiple_awards():
    data = _input(employed=False)
    awards = [
        ScholarshipAwardInput(
            award_id=f"award-{index}",
            issuer_id="university-a",
            amount=Decimal("1000"),
            category="ordinary_postsecondary",
            qualifying_student=True,
            attendance="part_time",
            intended_enrolment_support=Decimal("0"),
            part_time_program_id="program-a",
        )
        for index in (1, 2)
    ]
    data = data.model_copy(
        update={
            "slips": [
                SlipInput(
                    slip_type="T4A",
                    document_id="t4a-awards",
                    issuer_id="university-a",
                    tax_year=2025,
                    confirmed=True,
                    fields={"105": Decimal("2000"), "22": Decimal("0")},
                ),
                SlipInput(
                    slip_type="RL1",
                    document_id="rl1-awards",
                    issuer_id="university-a",
                    tax_year=2025,
                    confirmed=True,
                    rl1_box_o_allocations={"RB": Decimal("2000")},
                    fields={"O": Decimal("2000")},
                ),
            ],
            "inventory": data.inventory.model_copy(update={"no_income_sources": False}),
            "scholarships": ScholarshipInput(
                reviewed=True,
                awards=awards,
                part_time_programs=[
                    ScholarshipPartTimeProgramInput(
                        program_id="program-a",
                        eligible_tuition_and_required_materials=Decimal("1300"),
                    )
                ],
            ),
        }
    )

    assert preflight(data) == []
    assert calculate_federal(data).lines["13010"].value == Decimal("200.00")


def test_resp_eap_is_other_income_not_cwb_working_income_and_includes_withholding():
    data = _with_resp_eap(_input(employed=False), amount="3000", withholding="125")

    result = calculate_federal(data)

    assert preflight(data) == []
    assert result.complete
    assert result.lines["13000"].value == Decimal("3000.00")
    assert result.lines["13010"].value == Decimal("0.00")
    assert result.lines["15000"].value == Decimal("3000.00")
    assert result.lines["43700"].value == Decimal("125.00")
    assert not any(line_id.startswith("S6:") for line_id in result.lines)


def test_resp_and_taxable_scholarship_remain_separate_on_t1_and_schedule6():
    data = _with_scholarship(
        _input(employed=True),
        amount="1000",
        qualifying_student=False,
        attendance="nonqualifying",
    )
    data = _with_resp_eap(data, amount="3000")

    result = calculate_federal(data)

    assert preflight(data) == []
    assert result.complete
    assert result.lines["13000"].value == Decimal("3000.00")
    assert result.lines["13010"].value == Decimal("500.00")
    assert result.lines["15000"].value == Decimal("53500.00")
    assert result.lines["S6:2"].value == Decimal("500.00")


def test_amt_screen_includes_resp_and_only_the_taxable_part_of_scholarships():
    high_resp = _with_resp_eap(_input(employed=False), amount="180000")
    exempt_award = _with_scholarship(
        _input(employed=False, full_time_student=True),
        amount="200000",
        qualifying_student=True,
        attendance="full_time",
        intended_support="200000",
    )
    taxable_award = _with_scholarship(
        _input(employed=False),
        amount="180000",
        qualifying_student=False,
        attendance="nonqualifying",
    )

    assert "alternative_minimum_tax_screen" in {b.code for b in preflight(high_resp)}
    assert "alternative_minimum_tax_screen" not in {b.code for b in preflight(exempt_award)}
    assert "alternative_minimum_tax_screen" in {b.code for b in preflight(taxable_award)}


def test_federal_instalments_are_included_in_total_credits_and_refund():
    data = _input(employed=True)
    data.instalments = data.instalments.model_copy(
        update={"federal_paid": Decimal("1000.00")}
    )

    result = calculate_federal(data)

    assert result.lines["47600"].value == Decimal("1000.00")
    assert result.lines["48200"].value == Decimal("7682.39")
    assert result.lines["48400"].value == Decimal("3546.70")


def test_federal_no_income_student_return_has_zero_tax_and_balance():
    result = calculate_federal(_input(employed=False, full_time_student=True))

    assert result.complete
    assert result.lines["10100"].value == Decimal("0.00")
    assert result.lines["15000"].value == Decimal("0.00")
    assert result.lines["26000"].value == Decimal("0.00")
    assert result.lines["30000"].value == Decimal("16129.00")
    assert result.lines["42900"].value == Decimal("0.00")
    assert result.lines["44000"].value == Decimal("0.00")
    assert result.lines["48400"].value == Decimal("0.00")
    assert result.lines["48500"].value == Decimal("0.00")


def test_federal_employment_return_calculates_payroll_credits_abatement_and_refund():
    data = _input(employed=True)
    result = calculate_federal(data)
    qpp = calculate_qpp_schedule8(data)

    assert result.complete
    assert result.lines["10100"].value == Decimal("50000.00")
    assert result.lines["22215"].value == Decimal("465.00")
    assert result.lines["23600"].value == Decimal("49535.00")
    assert result.lines["31200"].value == Decimal("655.00")
    assert result.lines["31205"].value == Decimal("247.00")
    assert result.lines["31260"].value == Decimal("1471.00")
    assert result.lines["42900"].value == Decimal("4135.69")
    assert result.lines["44000"].value == Decimal("682.39")
    assert result.lines["48400"].value == Decimal("2546.70")
    assert result.lines["48500"].value == Decimal("0.00")
    assert not any(line_id.startswith("S11:") for line_id in result.lines)
    assert all(line.source_ids for line in result.lines.values())
    assert all(line.explanation for line in result.lines.values())
    assert all(line.explanation for line in qpp.lines.values())
    assert "Base QPP contribution credit" in qpp.lines["35"].explanation
    assert "Employment insurance premiums" in result.lines["31200"].explanation
