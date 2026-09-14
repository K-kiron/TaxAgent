from decimal import Decimal

import pytest

from taxagent.returns import SlipInput, calculate_return
from test_annual_returns import annual_input, by_form
from test_federal_return import _with_scholarship, _with_resp_eap


def scholarship_input(year):
    data = annual_input(year)
    data.slips = []
    data = _with_scholarship(data, amount="10000", qualifying_student=False,
                             attendance="nonqualifying")
    for slip in data.slips:
        slip.tax_year = year
    return data


@pytest.mark.parametrize("year", range(2020, 2025))
@pytest.mark.parametrize("field", ["category", "qualifying_student", "attendance", "intended_enrolment_support"])
def test_unknown_award_classification_blocks(year, field):
    data = scholarship_input(year)
    setattr(data.scholarships.awards[0], field, None)
    result = calculate_return(data)
    assert result.status == "blocked"
    assert "missing_scholarship_award_facts" in {b.code for b in result.blockers}
    assert all("2025" not in source for b in result.blockers for source in b.source_ids)


@pytest.mark.parametrize("year", range(2020, 2025))
def test_unsupported_award_category_blocks(year):
    data = scholarship_input(year)
    data.scholarships.awards[0].category = "research_grant"
    assert "unsupported_scholarship_category" in {b.code for b in calculate_return(data).blockers}


@pytest.mark.parametrize("year", range(2020, 2025))
@pytest.mark.parametrize("field", ["has_other_resp_payments", "qesi_cumulative_amount_over_3600"])
@pytest.mark.parametrize("value", [None, True])
def test_unsupported_or_unknown_resp_screen_blocks(year, field, value):
    data = _with_resp_eap(annual_input(year), amount="1000")
    for slip in data.slips:
        slip.tax_year = year
    setattr(data.resp_eap, field, value)
    assert calculate_return(data).status == "blocked"


@pytest.mark.parametrize("year", range(2020, 2025))
@pytest.mark.parametrize("field", ["federal_reviewed", "federal_paid", "quebec_reviewed", "quebec_paid"])
def test_unknown_instalments_block(year, field):
    data = annual_input(year)
    setattr(data.instalments, field, None)
    assert "missing_instalment_answers" in {b.code for b in calculate_return(data).blockers}


@pytest.mark.parametrize("year", range(2020, 2025))
@pytest.mark.parametrize("age", [None, 18, 19])
def test_scholarship_only_cwb_age_boundary(year, age):
    data = scholarship_input(year)
    data.taxpayer.age_dec31 = age
    result = calculate_return(data)
    if age is None:
        assert result.status == "blocked"
        assert "missing_cwb_eligibility" in {b.code for b in result.blockers}
    else:
        assert result.status == "complete"
        cwb = by_form(result, "T1")["45300"].value
        assert (cwb > 0) == (age >= 19)


@pytest.mark.parametrize("year", [2023, 2024])
def test_rc210_must_reconcile_before_calculation(year):
    data = scholarship_input(year)
    data.slips.append(SlipInput(slip_type="RC210", document_id="rc210", issuer_id="cra",
                               tax_year=year, confirmed=True,
                               fields={"10": Decimal("100"), "11": Decimal("0")}))
    data.refundable_credits.advanced_cwb_paid = None
    assert "rc210_amount_mismatch" in {b.code for b in calculate_return(data).blockers}
    data.refundable_credits.advanced_cwb_paid = Decimal("100")
    result = calculate_return(data)
    assert result.status == "complete"
    assert by_form(result, "T1")["41500"].value == Decimal("100")


@pytest.mark.parametrize("year", range(2020, 2025))
def test_rl19_supported_and_reconciled(year):
    data = annual_input(year)
    baseline = calculate_return(data)
    data.slips.append(SlipInput(slip_type="RL19", document_id="rl19", issuer_id="rq",
                               tax_year=year, confirmed=True,
                               fields={"A": Decimal("100"), "B": Decimal("50")}))
    data.refundable_credits.rl19_box_a = Decimal("100")
    data.refundable_credits.rl19_box_b = Decimal("50")
    result = calculate_return(data)
    assert result.status == "complete"
    assert result.quebec_refund_or_balance == baseline.quebec_refund_or_balance - Decimal("150")
    data.refundable_credits.rl19_box_a = Decimal("0")
    assert "rl19_amount_mismatch" in {b.code for b in calculate_return(data).blockers}


@pytest.mark.parametrize("year", range(2020, 2025))
def test_part_time_scholarship_requires_cost_evidence(year):
    data = _with_scholarship(annual_input(year), amount="4000", qualifying_student=True,
                             attendance="part_time", intended_support="4000", part_time_costs="2000")
    for slip in data.slips:
        slip.tax_year = year
    assert calculate_return(data).status == "complete"
    data.scholarships.part_time_programs[0].eligible_tuition_and_required_materials = None
    assert "missing_scholarship_part_time_program_cost" in {b.code for b in calculate_return(data).blockers}


@pytest.mark.parametrize("slip_type,fields", [
    ("RC210", {"10": "unknown", "11": Decimal("0")}),
    ("RL19", {"A": "unknown", "B": Decimal("0")}),
])
def test_invalid_advance_box_blocks_without_crashing(slip_type, fields):
    data = annual_input(2024)
    data.slips.append(SlipInput(slip_type=slip_type, document_id="advance", issuer_id="gov",
                               tax_year=2024, confirmed=True, fields=fields))
    assert "invalid_slip_box_type" in {b.code for b in calculate_return(data).blockers}
