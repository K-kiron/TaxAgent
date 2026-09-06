from decimal import Decimal

from taxagent.returns import (
    FederalTuitionInput,
    QuebecTuitionInput,
    RrspInput,
    SlipInput,
    calculate_return,
)
from taxagent.returns.engine import _ruleset_hash

from test_federal_return import _input, _with_resp_eap, _with_scholarship


def test_no_income_student_is_a_complete_line_by_line_return():
    result = calculate_return(_input(employed=False, full_time_student=True))

    assert result.status == "complete"
    assert result.federal_refund_or_balance == Decimal("0.00")
    assert result.quebec_refund_or_balance == Decimal("0.00")
    assert result.ruleset_hash and len(result.ruleset_hash) == 64
    assert result.input_digest and len(result.input_digest) == 64
    form_ids = {line.form_id for line in result.lines}
    assert form_ids >= {"T1", "TP1", "TP1-K", "TP1-P", "TP1-T"}
    assert "T1-S11" not in form_ids
    assert all(line.explanation.strip() for line in result.lines)


def test_blocked_return_never_exposes_partial_headline_amounts():
    data = _input(employed=False).model_copy(
        update={
            "taxpayer": _input(employed=False).taxpayer.model_copy(
                update={"has_capital_gains": None}
            )
        }
    )

    result = calculate_return(data)

    assert result.status == "blocked"
    assert result.federal_refund_or_balance is None
    assert result.quebec_refund_or_balance is None
    assert "missing_coverage_answer" in {blocker.code for blocker in result.blockers}


def test_complete_headlines_use_positive_refund_negative_balance_convention():
    result = calculate_return(_input(employed=True))

    assert result.status == "complete"
    assert result.federal_refund_or_balance == Decimal("2546.70")
    assert result.quebec_refund_or_balance == Decimal("863.84")
    assert result.benefit_estimates["canada_workers_benefit"] == Decimal("0.00")
    assert result.benefit_estimates["quebec_work_premium"] == Decimal("0.00")


def test_final_return_preserves_quebec_other_income_source_codes():
    scholarship = _with_scholarship(
        _input(employed=False, full_time_student=True),
        amount="3000",
        qualifying_student=True,
        attendance="full_time",
        intended_support="3000",
    )
    resp = _with_resp_eap(_input(employed=False), amount="3000")
    mixed = _with_resp_eap(scholarship, amount="3000")

    for data, expected in ((scholarship, "01"), (resp, "03"), (mixed, "66")):
        result = calculate_return(data)
        line_153 = next(
            line for line in result.lines if line.form_id == "TP1" and line.line_id == "153"
        )

        assert result.status == "complete"
        assert line_153.value == expected


def test_ruleset_hash_normalizes_source_line_endings(tmp_path):
    lf = tmp_path / "lf.py"
    crlf = tmp_path / "crlf.py"
    lf.write_bytes(b"RATE = 1\nVALUE = 2\n")
    crlf.write_bytes(b"RATE = 1\r\nVALUE = 2\r\n")

    assert _ruleset_hash([lf]) == _ruleset_hash([crlf])


def test_ruleset_hash_changes_when_executed_formula_changes(tmp_path):
    formula = tmp_path / "formula.py"
    formula.write_text("RATE = 1\n", encoding="utf-8")
    before = _ruleset_hash([formula])
    formula.write_text("RATE = 2\n", encoding="utf-8")

    assert _ruleset_hash([formula]) != before


def test_simple_interest_uses_only_t5_box13_and_rl3_box_d():
    base = _input(employed=True)
    interest_slips = [
        SlipInput(
            slip_type="T5",
            document_id="t5-bank",
            issuer_id="bank-a",
            tax_year=2025,
            confirmed=True,
            fields={"13": Decimal("125.40")},
        ),
        SlipInput(
            slip_type="RL3",
            document_id="rl3-bank",
            issuer_id="bank-a",
            tax_year=2025,
            confirmed=True,
            fields={"D": Decimal("125.40")},
        ),
    ]

    result = calculate_return(base.model_copy(update={"slips": [*base.slips, *interest_slips]}))

    assert result.status == "complete"
    assert next(line for line in result.lines if line.form_id == "T1" and line.line_id == "12100").value == Decimal("125.40")
    assert next(line for line in result.lines if line.form_id == "TP1" and line.line_id == "130").value == Decimal("125.40")


def test_rrsp_claim_is_limited_by_evidenced_receipts_and_noa_limit():
    data = _input(employed=True).model_copy(
        update={
            "rrsp": RrspInput(
                has_contributions=True,
                has_prior_unused_contributions=False,
                contribution_receipts=Decimal("2000"),
                march_to_december_contributions=Decimal("2000"),
                first_60_days_contributions=Decimal("0"),
                deduction_limit=Decimal("3000"),
                deduction_requested=Decimal("2000"),
                has_hbp_or_llp_activity=False,
            ),
            "slips": [
                *_input(employed=True).slips,
                SlipInput(
                    slip_type="RRSP_RECEIPT",
                    document_id="rrsp-receipt-a",
                    issuer_id="rrsp-issuer-a",
                    tax_year=2025,
                    confirmed=True,
                    rrsp_period="march_to_december_2025",
                    fields={"amount": Decimal("2000")},
                ),
            ],
        }
    )

    result = calculate_return(data)

    assert result.status == "complete"
    assert next(line for line in result.lines if line.form_id == "T1" and line.line_id == "20800").value == Decimal("2000.00")
    assert next(line for line in result.lines if line.form_id == "TP1" and line.line_id == "214").value == Decimal("2000.00")


def test_current_tuition_requires_and_uses_t2202_total_box26():
    base = _input(employed=True)
    t2202 = SlipInput(
        slip_type="T2202",
        document_id="t2202-school",
        issuer_id="school-a",
        tax_year=2025,
        confirmed=True,
        fields={"24": Decimal("0"), "25": Decimal("8"), "26": Decimal("4200")},
    )
    data = base.model_copy(
        update={
            "slips": [*base.slips, t2202],
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

    result = calculate_return(data)

    assert result.status == "complete"
    assert next(line for line in result.lines if line.form_id == "T1" and line.line_id == "32300").value == Decimal("4200.00")
    assert next(line for line in result.lines if line.form_id == "TP1" and line.line_id == "398").value == Decimal("336.00")


def test_no_income_student_preserves_current_tuition_as_carryforward():
    base = _input(employed=False, full_time_student=True)
    t2202 = SlipInput(
        slip_type="T2202",
        document_id="t2202-school",
        issuer_id="school-a",
        tax_year=2025,
        confirmed=True,
        fields={"24": Decimal("0"), "25": Decimal("8"), "26": Decimal("4200")},
    )
    data = base.model_copy(
        update={
            "slips": [t2202],
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

    result = calculate_return(data)

    assert result.status == "complete"
    assert result.federal_refund_or_balance == Decimal("0.00")
    assert result.quebec_refund_or_balance == Decimal("0.00")
    assert next(line for line in result.lines if line.form_id == "T1-S11" and line.line_id == "25").value == Decimal("4200.00")
    assert next(line for line in result.lines if line.form_id == "TP1-T" and line.line_id == "48").value == Decimal("4200.00")


def test_low_income_worker_gets_both_mandatory_work_credits():
    base = _input(employed=True)
    t4 = base.slips[0].model_copy(
        update={
            "fields": {
                "14": Decimal("10000"), "17": Decimal("416"), "17A": Decimal("0"),
                "18": Decimal("131"), "20": Decimal("0"), "22": Decimal("0"),
                "24": Decimal("10000"), "26": Decimal("10000"), "44": Decimal("0"),
                "52": Decimal("0"), "55": Decimal("49.40"),
            }
        }
    )
    rl1 = base.slips[1].model_copy(
        update={
            "fields": {
                "A": Decimal("10000"), "B.A": Decimal("416"), "B.B": Decimal("0"),
                "C": Decimal("131"), "D": Decimal("0"), "E": Decimal("0"),
                "F": Decimal("0"), "G": Decimal("10000"), "H": Decimal("49.40"),
                "I": Decimal("10000"), "211": Decimal("0"),
            }
        }
    )

    result = calculate_return(base.model_copy(update={"slips": [t4, rl1]}))

    assert result.status == "complete"
    assert result.benefit_estimates["canada_workers_benefit"] == Decimal("2834.80")
    assert result.benefit_estimates["quebec_work_premium"] == Decimal("881.60")

    qc_student_credits = base.refundable_credits.model_copy(
        update={"quebec_work_premium_full_time_student": True}
    )
    qc_student_result = calculate_return(
        base.model_copy(
            update={"slips": [t4, rl1], "refundable_credits": qc_student_credits}
        )
    )
    assert qc_student_result.benefit_estimates["canada_workers_benefit"] == Decimal("2834.80")
    assert qc_student_result.benefit_estimates["quebec_work_premium"] == Decimal("0.00")


def test_advance_work_credits_are_repaid_without_double_counting_benefits():
    base = _input(employed=True)
    t4 = base.slips[0].model_copy(
        update={
            "fields": {
                "14": Decimal("10000"), "17": Decimal("416"), "17A": Decimal("0"),
                "18": Decimal("131"), "20": Decimal("0"), "22": Decimal("0"),
                "24": Decimal("10000"), "26": Decimal("10000"), "44": Decimal("0"),
                "52": Decimal("0"), "55": Decimal("49.40"),
            }
        }
    )
    rl1 = base.slips[1].model_copy(
        update={
            "fields": {
                "A": Decimal("10000"), "B.A": Decimal("416"), "B.B": Decimal("0"),
                "C": Decimal("131"), "D": Decimal("0"), "E": Decimal("0"),
                "F": Decimal("0"), "G": Decimal("10000"), "H": Decimal("49.40"),
                "I": Decimal("10000"), "211": Decimal("0"),
            }
        }
    )
    credits = base.refundable_credits.model_copy(
        update={
            "advanced_cwb_paid": Decimal("500"),
            "rl19_box_a": Decimal("500"),
        }
    )

    result = calculate_return(
        base.model_copy(
            update={
                "slips": [
                    t4,
                    rl1,
                    SlipInput(
                        slip_type="RC210",
                        document_id="rc210-a",
                        issuer_id="cra",
                        tax_year=2025,
                        confirmed=True,
                        fields={"10": Decimal("500")},
                    ),
                    SlipInput(
                        slip_type="RL19",
                        document_id="rl19-a",
                        issuer_id="rq",
                        tax_year=2025,
                        confirmed=True,
                        fields={"A": Decimal("500")},
                    ),
                ],
                "refundable_credits": credits,
            }
        )
    )

    assert result.status == "complete"
    assert next(line for line in result.lines if line.form_id == "T1" and line.line_id == "41500").value == Decimal("500.00")
    assert next(line for line in result.lines if line.form_id == "TP1" and line.line_id == "441").value == Decimal("500.00")
    assert result.federal_refund_or_balance == Decimal("2334.80")
    assert result.quebec_refund_or_balance == Decimal("381.60")
