from decimal import Decimal

import pytest

from taxagent.returns import SlipInput, TaxReturnInput, calculate_return
from taxagent.returns import engine, federal_2025_qc, quebec_2025
from test_annual_returns import annual_input, by_form
from test_annual_review_gates import scholarship_input
from test_federal_return import _input, _with_scholarship


def return_input(year):
    return _input(employed=True) if year == 2025 else annual_input(year)


@pytest.mark.parametrize("year", [2024, 2025])
@pytest.mark.parametrize("slip_type,box", [("RC210", "10"), ("RC210", "11"),
                                          ("RL19", "A"), ("RL19", "B")])
@pytest.mark.parametrize("invalid", ["1,200.00", "unknown", True])
def test_invalid_advance_money_returns_blockers(year, slip_type, box, invalid):
    data = return_input(year)
    fields = dict.fromkeys(("10", "11") if slip_type == "RC210" else ("A", "B"), Decimal("0"))
    fields[box] = invalid
    data.slips.append(SlipInput(slip_type=slip_type, document_id="advance", issuer_id="gov",
                               tax_year=year, confirmed=True, fields=fields))

    result = calculate_return(data)

    assert result.status == "blocked"
    assert "invalid_slip_box_type" in {item.code for item in result.blockers}
    assert result.federal_refund_or_balance is None
    assert result.quebec_refund_or_balance is None


@pytest.mark.parametrize("year", [2023, 2024, 2025])
@pytest.mark.parametrize("slip_type,fields,credit,code", [
    ("rc210", {"10": Decimal("1200"), "11": Decimal("0")},
     "advanced_cwb_paid", "rc210_amount_mismatch"),
    ("rl19", {"A": Decimal("1200"), "B": Decimal("0")},
     "rl19_box_a", "rl19_amount_mismatch"),
])
def test_lowercase_advance_slips_require_reconciliation(year, slip_type, fields, credit, code):
    data = return_input(year)
    data.slips.append(SlipInput(slip_type=slip_type, document_id="advance", issuer_id="gov",
                               tax_year=year, confirmed=True, fields=fields))
    setattr(data.refundable_credits, credit, None)

    assert code in {item.code for item in calculate_return(data).blockers}
    setattr(data.refundable_credits, credit, Decimal("1200"))
    assert calculate_return(data).status == "complete"


@pytest.mark.parametrize("year", range(2020, 2026))
def test_lowercase_slips_match_uppercase_return(year):
    data = return_input(year)
    payload = data.model_dump()
    for slip in payload["slips"]:
        slip["slip_type"] = slip["slip_type"].lower()

    assert calculate_return(TaxReturnInput.model_validate(payload)) == calculate_return(data)


@pytest.mark.parametrize("year", [2020, 2021, 2022])
@pytest.mark.parametrize("fields", [{"10": Decimal("500"), "11": Decimal("0")},
                                   {"10": Decimal("500")}])
def test_legacy_cwb_advance_slips_are_explicitly_unsupported(year, fields):
    data = annual_input(year)
    data.refundable_credits.advanced_cwb_paid = Decimal("500")
    data.slips.append(SlipInput(slip_type="RC210", document_id="advance", issuer_id="cra",
                               tax_year=year, confirmed=True, fields=fields))

    result = calculate_return(data)

    assert result.status == "blocked"
    assert "unsupported_legacy_cwb_advance" in {item.code for item in result.blockers}
    assert result.federal_refund_or_balance is None


@pytest.mark.parametrize("year", [2020, 2021, 2022])
def test_legacy_cwb_advance_amounts_without_slips_are_unsupported(year):
    data = annual_input(year)
    data.refundable_credits.advanced_cwb_paid = Decimal("500")
    assert "unsupported_legacy_cwb_advance" in {b.code for b in calculate_return(data).blockers}


@pytest.mark.parametrize("year", [2023, 2024, 2025])
@pytest.mark.parametrize("full_time_student", [False, True])
def test_cwb_advance_above_entitlement_preserves_schedule6_cap(year, full_time_student):
    data = (scholarship_input(year) if year < 2025 else
            _with_scholarship(_input(employed=False), amount="10000",
                              qualifying_student=False, attendance="nonqualifying"))
    data.taxpayer.was_full_time_student_more_than_13_weeks = full_time_student
    baseline = calculate_return(data)
    entitlement = by_form(baseline, "T1")["45300"].value
    assert entitlement == 0 if full_time_student else 0 < entitlement < 5000
    data.refundable_credits.advanced_cwb_paid = Decimal("5000")
    data.slips.append(SlipInput(slip_type="RC210", document_id="advance", issuer_id="cra",
                               tax_year=year, confirmed=True,
                               fields={"10": Decimal("5000"), "11": Decimal("0")}))

    result = calculate_return(data)

    assert result.status == "complete"
    assert (by_form(result, "T1")["41500"].value or Decimal("0")) == entitlement
    assert by_form(result, "T1-S6")["49"].value == entitlement
    assert result.federal_refund_or_balance == baseline.federal_refund_or_balance - entitlement


def test_zero_headlines_serialize_without_negative_sign():
    result = calculate_return(_input(employed=False, full_time_student=True)).model_dump(mode="json")
    assert result["federal_refund_or_balance"] == "0.00"
    assert result["quebec_refund_or_balance"] == "0.00"


def test_annual_ruleset_hash_preserves_file_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "__file__", str(tmp_path / "engine.py"))
    for name in ("models.py", "annual_rules.py", "gates.py", "federal_2025_qc.py",
                 "annual_main_lines.json", "engine.py"):
        (tmp_path / name).write_bytes(b"")
    models = tmp_path / "models.py"
    annual = tmp_path / "annual_rules.py"
    models.write_bytes(b"a\nb\n")
    annual.write_bytes(b"c\n")
    before = engine._annual_ruleset_hash(2024)
    models.write_bytes(b"a\n")
    annual.write_bytes(b"b\nc\n")
    assert engine._annual_ruleset_hash(2024) != before
    lf = engine._annual_ruleset_hash(2024)
    annual.write_bytes(b"b\r\nc\r\n")
    assert engine._annual_ruleset_hash(2024) == lf
    (tmp_path / "federal_2025_qc.py").write_bytes(b"shared scholarship formula changed\n")
    assert engine._annual_ruleset_hash(2024) != lf


def test_return_reuses_schedules_without_changing_output(monkeypatch):
    data = _input(employed=True)
    baseline = calculate_return(data)
    calls = {"qpp": 0, "federal": 0}

    def counted(name, calculate):
        def run(*args, **kwargs):
            calls[name] += 1
            return calculate(*args, **kwargs)
        return run

    qpp = counted("qpp", federal_2025_qc.calculate_qpp_schedule8)
    federal = counted("federal", federal_2025_qc.calculate_federal)
    for module in (engine, federal_2025_qc, quebec_2025):
        monkeypatch.setattr(module, "calculate_qpp_schedule8", qpp)
        monkeypatch.setattr(module, "calculate_federal", federal)

    assert calculate_return(data) == baseline
    assert calls == {"qpp": 1, "federal": 1}


def test_direct_quebec_box_sum_handles_nonnumeric_values():
    data = _input(employed=True)
    data.slips[1].fields["A"] = "unknown"
    assert quebec_2025.calculate_quebec(data).lines["101"].value == Decimal("0.00")
