from decimal import Decimal

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
    ScholarshipAwardInput,
    SlipInput,
    ScholarshipInput,
    ScholarshipPartTimeProgramInput,
    StudentLoanInterestInput,
    TaxReturnInput,
    TaxpayerFacts,
    preflight,
)


def _facts(**overrides) -> TaxpayerFacts:
    values = {
        "full_year_canada_resident": True,
        "full_year_quebec_resident": True,
        "province_dec31": "QC",
        "age_dec31": 24,
        "marital_status": "single",
        "dependant_count": 0,
        "deceased_return": False,
        "bankruptcy_return": False,
        "has_self_employment": False,
        "has_capital_gains": False,
        "has_rental_income": False,
        "has_foreign_income_or_tax": False,
        "has_foreign_property_over_100k": False,
        "has_crypto_transactions": False,
        "has_pension_or_benefit_income": False,
        "has_indian_act_exempt_income": False,
        "has_disability_or_caregiver_claim": False,
        "has_employment_expenses": False,
        "has_medical_expenses": False,
        "has_donations": False,
        "has_childcare_expenses": False,
        "has_moving_expenses": False,
        "has_tips_or_other_employment_income": False,
        "has_student_loan_interest": False,
        "received_qpp_disability_pension": False,
        "made_qpp_cpt30_election": False,
        "was_full_time_student_more_than_13_weeks": True,
    }
    values.update(overrides)
    return TaxpayerFacts(**values)


def _input(**overrides) -> TaxReturnInput:
    values = {
        "tax_year": 2025,
        "province_dec31": "QC",
        "taxpayer": _facts(),
        "inventory": DocumentInventory(
            income_sources_reviewed=True,
            deductions_reviewed=True,
            credits_reviewed=True,
            cra_records_reviewed=True,
            revenu_quebec_records_reviewed=True,
            no_income_sources=True,
        ),
        "federal_tuition": FederalTuitionInput(
            has_current_tuition=False,
            has_prior_unused=False,
            wants_transfer=False,
            wants_canada_training_credit=False,
        ),
        "quebec_tuition": QuebecTuitionInput(
            has_current_tuition=False,
            has_prior_unused=False,
            wants_transfer=False,
        ),
        "rrsp": RrspInput(has_contributions=False, has_prior_unused_contributions=False, has_hbp_or_llp_activity=False),
        "instalments": InstalmentInput(
            federal_reviewed=True,
            federal_paid=Decimal("0"),
            quebec_reviewed=True,
            quebec_paid=Decimal("0"),
        ),
        "quebec_schedule_b": QuebecScheduleBInput(
            living_alone_reviewed=True,
            eligible_for_living_alone_amount=False,
        ),
        "student_loan_interest": StudentLoanInterestInput(
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
        "scholarships": ScholarshipInput(reviewed=True, awards=[], part_time_programs=[]),
        "resp_eap": RespEapInput(
            reviewed=True,
            has_other_resp_payments=False,
            qesi_cumulative_amount_over_3600=False,
            payments=[],
        ),
        "additional_return_screens": AdditionalReturnScreenInput(
            immigrated_or_emigrated_2025=False,
            quebec_trust_return=False,
            separate_post_death_return=False,
            quebec_enterprise_registration_or_annual_fee=False,
        ),
        "drug_insurance": DrugInsuranceInput(
            reviewed=True,
            group_plan_months=set(range(1, 13)),
            group_plan_source="self",
            eligible_student_months=set(),
            other_exemption_applies=False,
        ),
        "refundable_credits": RefundableCreditInput(
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
            quebec_work_premium_full_time_student=True,
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
    }
    values.update(overrides)
    return TaxReturnInput(**values)


def _codes(data: TaxReturnInput) -> set[str]:
    return {b.code for b in preflight(data)}


def test_explicit_no_income_student_case_passes_preflight():
    assert preflight(_input()) == []


def test_rl19_advance_payment_inventory_cannot_be_unknown_or_omit_other_boxes():
    credits = _input().refundable_credits.model_copy(
        update={"rl19_advance_payments_reviewed": None, "rl19_has_other_advance_boxes": True}
    )

    assert {
        "missing_refundable_credit_answers",
        "unsupported_rl19_advance_boxes",
    } <= _codes(_input(refundable_credits=credits))


def test_instalment_payments_must_be_explicitly_reviewed():
    instalments = _input().instalments.model_copy(update={"federal_reviewed": None})

    assert "missing_instalment_answers" in _codes(_input(instalments=instalments))


def test_schedule_b_living_arrangement_must_be_reviewed_separately():
    schedule_b = _input().quebec_schedule_b.model_copy(
        update={"living_alone_reviewed": None, "eligible_for_living_alone_amount": None}
    )

    assert "missing_schedule_b_answers" in _codes(_input(quebec_schedule_b=schedule_b))


def test_student_loan_interest_claims_require_qualified_evidence_and_stay_within_available_amounts():
    base = _input()
    unknown = base.student_loan_interest.model_copy(update={"reviewed": None})
    excessive = base.student_loan_interest.model_copy(
        update={
            "federal_current_year_paid": Decimal("100"),
            "federal_claim_amount": Decimal("101"),
            "quebec_current_year_paid": Decimal("100"),
            "quebec_claim_amount": Decimal("101"),
        }
    )
    ineligible = base.student_loan_interest.model_copy(
        update={"qualifying_government_loans_confirmed": False}
    )

    assert "missing_student_loan_interest_answers" in _codes(
        _input(student_loan_interest=unknown)
    )
    assert "student_loan_interest_claim_exceeds_available" in _codes(
        _input(
            taxpayer=_facts(has_student_loan_interest=True),
            student_loan_interest=excessive,
        )
    )
    assert "ineligible_student_loan_interest" in _codes(
        _input(
            taxpayer=_facts(has_student_loan_interest=True),
            student_loan_interest=ineligible,
        )
    )


def test_scholarship_awards_require_supported_status_and_reconciled_slips():
    unknown = ScholarshipInput(reviewed=None, awards=None)
    unsupported_award = ScholarshipAwardInput(
        award_id="award-a",
        issuer_id="school-a",
        amount=Decimal("1000"),
        category="research_grant",
        qualifying_student=True,
        attendance="full_time",
        intended_enrolment_support=Decimal("1000"),
        part_time_program_id=None,
    )

    assert "missing_scholarship_answers" in _codes(_input(scholarships=unknown))
    assert "unsupported_scholarship_category" in _codes(
        _input(
            scholarships=ScholarshipInput(
                reviewed=True, awards=[unsupported_award], part_time_programs=[]
            )
        )
    )


def test_resp_eap_requires_review_and_reconciled_supported_beneficiary_payments():
    base = _input()
    payment = RespEapPaymentInput(
        payment_id="resp-a", issuer_id="promoter-a", amount=Decimal("3000")
    )
    unknown = base.resp_eap.model_copy(update={"reviewed": None})
    qesi_excess = base.resp_eap.model_copy(
        update={"qesi_cumulative_amount_over_3600": True}
    )
    other_payment = base.resp_eap.model_copy(update={"has_other_resp_payments": True})
    mismatched = base.resp_eap.model_copy(update={"payments": [payment]})

    assert "missing_resp_eap_answers" in _codes(_input(resp_eap=unknown))
    assert "unsupported_resp_qesi_special_tax" in _codes(_input(resp_eap=qesi_excess))
    assert "unsupported_resp_payment_type" in _codes(_input(resp_eap=other_payment))
    assert "resp_eap_receipt_mismatch" in _codes(_input(resp_eap=mismatched))


def test_additional_return_situations_require_explicit_negative_screens():
    base = _input().additional_return_screens

    assert "missing_additional_return_screens" in _codes(
        _input(
            additional_return_screens=base.model_copy(
                update={"quebec_trust_return": None}
            )
        )
    )
    assert "unsupported_immigrated_or_emigrated_2025" in _codes(
        _input(
            additional_return_screens=base.model_copy(
                update={"immigrated_or_emigrated_2025": True}
            )
        )
    )
    assert "unsupported_quebec_enterprise_registration_or_annual_fee" in _codes(
        _input(
            additional_return_screens=base.model_copy(
                update={"quebec_enterprise_registration_or_annual_fee": True}
            )
        )
    )


def test_t4a_accumulated_income_payment_and_unknown_rl1_o_code_are_blocked():
    t4a_aip = SlipInput(
        slip_type="T4A",
        document_id="t4a-aip",
        issuer_id="promoter-a",
        tax_year=2025,
        confirmed=True,
        fields={"040": Decimal("1000")},
    )
    rl1_unknown = SlipInput(
        slip_type="RL1",
        document_id="rl1-other",
        issuer_id="other-a",
        tax_year=2025,
        confirmed=True,
        fields={"O": Decimal("1000")},
        rl1_box_o_allocations={"RZ-OTHER": Decimal("1000")},
    )

    assert "unsupported_resp_accumulated_income_payment" in _codes(
        _input(slips=[t4a_aip])
    )
    assert "unsupported_rl1_box_o_code" in _codes(_input(slips=[rl1_unknown]))


def test_zero_t4a_accumulated_income_box_does_not_trigger_special_tax_blocker():
    zero_aip = SlipInput(
        slip_type="T4A",
        document_id="t4a-zero-aip",
        issuer_id="promoter-a",
        tax_year=2025,
        confirmed=True,
        fields={"040": Decimal("0")},
    )

    assert "unsupported_resp_accumulated_income_payment" not in _codes(
        _input(slips=[zero_aip])
    )


def test_unknown_coverage_answer_blocks_instead_of_becoming_false():
    data = _input(taxpayer=_facts(has_capital_gains=None))

    assert "missing_coverage_answer" in _codes(data)


def test_year_province_and_persona_boundaries_are_blockers():
    assert "unsupported_tax_year" in _codes(_input(tax_year=2024))
    assert "unsupported_province" in _codes(_input(province_dec31="ON"))
    assert "unsupported_residency" in _codes(
        _input(taxpayer=_facts(full_year_canada_resident=False))
    )
    assert "unsupported_family_status" in _codes(
        _input(taxpayer=_facts(marital_status="married"))
    )


def test_turning_18_and_nonstandard_qpp_periods_block_full_year_schedule8():
    assert "unsupported_qpp_contributory_period" in _codes(
        _input(taxpayer=_facts(age_dec31=18))
    )
    assert "unsupported_qpp_contributory_period" in _codes(
        _input(taxpayer=_facts(received_qpp_disability_pension=True))
    )
    assert "unsupported_qpp_contributory_period" in _codes(
        _input(taxpayer=_facts(made_qpp_cpt30_election=True))
    )


def test_amt_threshold_is_a_fail_closed_coverage_boundary():
    t4 = SlipInput(
        slip_type="T4",
        document_id="t4-high",
        issuer_id="employer-a",
        tax_year=2025,
        province_of_employment="QC",
        confirmed=True,
        fields={
            "14": Decimal("177882.01"), "17": Decimal("0"), "17A": Decimal("0"),
            "18": Decimal("0"), "20": Decimal("0"), "22": Decimal("0"),
            "24": Decimal("0"), "26": Decimal("0"), "44": Decimal("0"),
            "52": Decimal("0"), "55": Decimal("0"),
        },
    )
    rl1 = SlipInput(
        slip_type="RL1",
        document_id="rl1-high",
        issuer_id="employer-a",
        tax_year=2025,
        confirmed=True,
        fields={box: Decimal("0") for box in ("A", "B.A", "B.B", "C", "D", "E", "F", "G", "H", "I", "211")},
    )
    data = _input(
        slips=[t4, rl1],
        inventory=_input().inventory.model_copy(update={"no_income_sources": False}),
    )

    blocker = next(b for b in preflight(data) if b.code == "alternative_minimum_tax_screen")
    assert blocker.source_ids == ["cra_2025_t691"]


def test_supported_slip_must_be_confirmed_and_for_2025():
    slip = SlipInput(
        slip_type="T4",
        document_id="t4-a",
        issuer_id="employer-a",
        tax_year=2024,
        province_of_employment="QC",
        confirmed=None,
        fields={"14": Decimal("10000.00")},
    )
    data = _input(
        slips=[slip],
        inventory=_input().inventory.model_copy(update={"no_income_sources": False}),
    )

    assert {"wrong_slip_year", "unconfirmed_slip"} <= _codes(data)


def test_unknown_slip_and_outside_quebec_employment_block_calculation():
    unknown = SlipInput(
        slip_type="T3",
        document_id="t3-a",
        issuer_id="payer-a",
        tax_year=2025,
        confirmed=True,
    )
    outside_qc = SlipInput(
        slip_type="T4",
        document_id="t4-b",
        issuer_id="employer-b",
        tax_year=2025,
        province_of_employment="ON",
        confirmed=True,
    )
    data = _input(
        slips=[unknown, outside_qc],
        inventory=_input().inventory.model_copy(update={"no_income_sources": False}),
    )

    assert {"unsupported_slip", "outside_quebec_employment"} <= _codes(data)


def test_t4_and_rl1_are_reconciled_by_issuer():
    t4 = SlipInput(
        slip_type="T4",
        document_id="t4-a",
        issuer_id="employer-a",
        tax_year=2025,
        province_of_employment="QC",
        confirmed=True,
    )
    data = _input(
        slips=[t4],
        inventory=_input().inventory.model_copy(update={"no_income_sources": False}),
    )

    assert "missing_slip_counterpart" in _codes(data)


def test_simple_interest_requires_t5_and_rl3_counterparts():
    t5 = SlipInput(
        slip_type="T5",
        document_id="t5-a",
        issuer_id="bank-a",
        tax_year=2025,
        confirmed=True,
        fields={"13": Decimal("125.40")},
    )
    data = _input(
        slips=[t5],
        inventory=_input().inventory.model_copy(update={"no_income_sources": False}),
    )

    assert "missing_slip_counterpart" in _codes(data)


def test_t5_recipient_identifier_box_is_rejected_from_money_fields():
    t5 = SlipInput(
        slip_type="T5",
        document_id="t5-a",
        issuer_id="bank-a",
        tax_year=2025,
        confirmed=True,
        fields={"13": Decimal("125.40"), "22": "123456789"},
    )
    data = _input(
        slips=[t5],
        inventory=_input().inventory.model_copy(update={"no_income_sources": False}),
    )

    assert "unsupported_slip_box" in _codes(data)


def test_t2202_accepts_only_official_total_boxes():
    slip = SlipInput(
        slip_type="T2202",
        document_id="tuition-a",
        issuer_id="school-a",
        tax_year=2025,
        confirmed=True,
        fields={"24": Decimal("0"), "25": Decimal("8"), "26": Decimal("4200")},
    )
    data = _input(
        slips=[slip],
        inventory=_input().inventory.model_copy(update={"no_income_sources": True}),
    )

    assert "missing_slip_box" not in _codes(data)
    assert "unsupported_slip_box" not in _codes(data)


def test_t2202_box26_must_reconcile_to_federal_tuition_input():
    slip = SlipInput(
        slip_type="T2202",
        document_id="tuition-a",
        issuer_id="school-a",
        tax_year=2025,
        confirmed=True,
        fields={"24": Decimal("0"), "25": Decimal("8"), "26": Decimal("4200")},
    )
    data = _input(
        slips=[slip],
        federal_tuition=FederalTuitionInput(
            has_current_tuition=True,
            t2202_eligible_fees=Decimal("4000"),
            has_prior_unused=False,
            wants_transfer=False,
            wants_canada_training_credit=False,
        ),
        inventory=_input().inventory.model_copy(update={"no_income_sources": True}),
    )

    assert "t2202_fee_mismatch" in _codes(data)


def test_t2202_more_than_100_threshold_excludes_low_fee_institutions():
    slips = [
        SlipInput(
            slip_type="T2202",
            document_id=f"tuition-{issuer}",
            issuer_id=issuer,
            tax_year=2025,
            confirmed=True,
            fields={"24": Decimal("0"), "25": Decimal("1"), "26": Decimal("60")},
        )
        for issuer in ("school-a", "school-b")
    ]
    data = _input(
        slips=slips,
        federal_tuition=FederalTuitionInput(
            has_current_tuition=True,
            t2202_eligible_fees=Decimal("0"),
            has_prior_unused=False,
            wants_transfer=False,
            wants_canada_training_credit=False,
        ),
        inventory=_input().inventory.model_copy(update={"no_income_sources": True}),
    )

    assert "t2202_fee_mismatch" not in _codes(data)

    wrong_aggregate = data.model_copy(
        update={
            "federal_tuition": data.federal_tuition.model_copy(
                update={"t2202_eligible_fees": Decimal("120")}
            )
        }
    )
    assert "t2202_fee_mismatch" in _codes(wrong_aggregate)


def test_rrsp_contribution_requires_amount_limit_and_no_hbp_llp():
    data = _input(
        rrsp=RrspInput(
            has_contributions=True,
            contribution_receipts=Decimal("2000.00"),
            deduction_limit=None,
            deduction_requested=Decimal("2000.00"),
            has_hbp_or_llp_activity=True,
        )
    )

    assert {"missing_rrsp_limit", "unsupported_hbp_llp"} <= _codes(data)


def test_rrsp_receipts_reconcile_aggregate_and_schedule7_periods():
    receipt = SlipInput(
        slip_type="RRSP_RECEIPT",
        document_id="rrsp-a",
        issuer_id="issuer-a",
        tax_year=2025,
        confirmed=True,
        rrsp_period="march_to_december_2025",
        fields={"amount": Decimal("100")},
    )
    data = _input(
        slips=[receipt],
        rrsp=RrspInput(
            has_contributions=True,
            has_prior_unused_contributions=False,
            contribution_receipts=Decimal("2000"),
            march_to_december_contributions=Decimal("2000"),
            first_60_days_contributions=Decimal("0"),
            deduction_limit=Decimal("3000"),
            deduction_requested=Decimal("2000"),
            has_hbp_or_llp_activity=False,
        ),
    )

    assert {"rrsp_receipt_mismatch", "rrsp_receipt_period_mismatch"} <= _codes(data)


def test_current_tuition_requires_distinct_federal_and_quebec_evidence():
    data = _input(
        federal_tuition=FederalTuitionInput(
            has_current_tuition=True,
            t2202_eligible_fees=None,
            has_prior_unused=False,
            wants_transfer=False,
            wants_canada_training_credit=False,
        ),
        quebec_tuition=QuebecTuitionInput(
            has_current_tuition=True,
            eligible_tuition_or_exam_receipts=None,
            has_prior_unused=False,
            wants_transfer=False,
        ),
    )

    assert {
        "missing_t2202_fees",
        "missing_t2202_slip",
        "missing_quebec_tuition_receipts",
        "missing_quebec_tuition_location",
    } <= _codes(data)


def test_blank_optional_t4_boxes_require_exemption_answers_not_fake_zeroes():
    t4 = SlipInput(
        slip_type="T4",
        document_id="t4-a",
        issuer_id="employer-a",
        tax_year=2025,
        province_of_employment="QC",
        cpp_qpp_exempt=False,
        ei_exempt=False,
        ppip_exempt=False,
        confirmed=True,
        fields={"14": Decimal("10000.00")},
    )
    rl1 = SlipInput(
        slip_type="RL1",
        document_id="rl1-a",
        issuer_id="employer-a",
        tax_year=2025,
        confirmed=True,
        fields={"A": Decimal("10000.00")},
    )
    data = _input(
        slips=[t4, rl1],
        inventory=_input().inventory.model_copy(update={"no_income_sources": False}),
    )

    assert "missing_slip_box" not in _codes(data)
    assert "missing_t4_exemption_answer" not in _codes(data)
