import json
from decimal import Decimal
from pathlib import Path

from taxagent.returns.coverage_2025 import _federal_printed_rows, complete_main_form_coverage
from taxagent.returns.models import LineValue
from taxagent.returns.engine import calculate_return
from taxagent.returns.federal_2025_qc import calculate_federal, calculate_qpp_schedule8
from taxagent.returns.quebec_2025 import calculate_quebec
from taxagent.returns.sources import SOURCES

from test_federal_return import _input


MANIFEST = json.loads(
    (Path(__file__).parent / "fixtures" / "main_form_2025_manifest.json").read_text()
)


def _covered(data):
    raw = [
        *calculate_qpp_schedule8(data).lines.values(),
        *calculate_federal(data).lines.values(),
        *calculate_quebec(data).lines.values(),
    ]
    return complete_main_form_coverage(data, raw)


def _by_form(lines, form_id):
    return {line.line_id: line for line in lines if line.form_id == form_id}


def test_main_form_membership_matches_independent_frozen_manifest():
    result = calculate_return(_input(employed=True))
    federal = _by_form(result.lines, "T1")
    quebec = _by_form(result.lines, "TP1")

    assert set(federal) == set(MANIFEST["T1"]["named_lines"]) | set(
        MANIFEST["T1"]["printed_rows"]
    )
    assert set(quebec) == set(MANIFEST["TP1"]["named_lines"])
    assert result.status == "complete"
    assert result.blockers == []
    assert all(line.status != "blocked" for line in [*federal.values(), *quebec.values()])
    assert any("QPIP overpayment" in warning and "assessment" in warning for warning in result.warnings)


def test_printed_rows_follow_official_subtotals_and_carries():
    lines, _ = _covered(_input(employed=True))
    rows = _by_form(lines, "T1")
    amount = lambda row: rows[str(row)].value

    assert amount(77) == amount(75) + amount(76)
    assert amount(85) == sum((amount(row) for row in range(78, 85)), start=Decimal("0"))
    assert amount(100) == sum((amount(row) for row in range(87, 100)), start=Decimal("0"))
    assert amount(102) == amount(86) + amount(100) + amount(101)
    assert amount(105) == amount(102) + amount(103) + amount(104)
    assert amount(110) == sum((amount(row) for row in range(105, 110)), start=Decimal("0"))
    assert amount(117) == amount(110) + amount(116)
    assert amount(122) == amount(119) + amount(120) + amount(121)
    assert amount(122) == rows["35000"].value
    assert amount(125) == amount(123) + amount(124)
    assert amount(129) == amount(126) + amount(127) + amount(128)
    assert amount(142) == amount(139) + amount(140) + amount(141)
    assert amount(146) == amount(143) + amount(144) + amount(145)
    assert amount(146) == rows["42000"].value
    assert amount(151) == sum((amount(row) for row in range(147, 151)), start=Decimal("0"))
    assert amount(171) == amount(155) + amount(156) + sum(
        (amount(row) for row in range(159, 171)), start=Decimal("0")
    )
    assert amount(171) == rows["48200"].value
    assert amount(172) == amount(152) - amount(171)


def test_printed_rate_rows_preserve_exact_decimal_rates():
    lines, _ = _covered(_input(employed=True))
    rows = _by_form(lines, "T1")

    assert rows["74"].value == Decimal("0.145")
    assert rows["118"].value == Decimal("0.145")


def test_printed_bracket_rate_row_preserves_each_official_rate():
    for taxable, expected in (
        ("60000", "0.205"),
        ("120000", "0.26"),
        ("180000", "0.29"),
        ("260000", "0.33"),
    ):
        rows = _federal_printed_rows(
            {
                ("T1", "26000"): LineValue(
                    form_id="T1",
                    line_id="26000",
                    value=Decimal(taxable),
                    status="calculated",
                    source_ids=["cra_2025_5005_r"],
                )
            }
        )

        assert rows[("T1", "74")].value == Decimal(expected)


def test_screened_out_line_is_na_while_its_printed_row_is_formula_zero():
    lines, _ = _covered(_input(employed=True))
    federal = _by_form(lines, "T1")

    assert federal["30100"].status == "not_applicable"
    assert federal["30100"].value is None
    assert federal["79"].status == "zero"
    assert federal["79"].value == Decimal("0.00")


def test_main_form_lines_include_official_label_and_applicability_reason():
    result = calculate_return(_input(employed=True))
    federal = _by_form(result.lines, "T1")
    quebec = _by_form(result.lines, "TP1")

    assert "T1 line 30100: Age amount." in federal["30100"].explanation
    assert "Born in 1960 or earlier" in federal["30100"].explanation
    assert "TP1 line 406: Non-refundable tax credits carried from line 399." in quebec["406"].explanation
    assert "Always: copy line 399" in quebec["406"].explanation


def test_federal_printed_rows_include_readable_official_labels():
    result = calculate_return(_input(employed=True))
    federal = _by_form(result.lines, "T1")

    assert "T1 line 74: Federal tax bracket percentage." in federal["74"].explanation
    assert "applicable taxable-income column" in federal["74"].explanation
    assert "T1 line 105: Add lines 102 to 104." in federal["105"].explanation
    assert "subtotal of printed rows 102 through 104" in federal["105"].explanation
    assert "T1 line 171: Total credits." in federal["171"].explanation
    assert "add lines 155, 156, and 159 to 170" in federal["171"].explanation


def test_unknown_inventory_blocks_instead_of_becoming_na():
    data = _input(employed=True)
    data.inventory = data.inventory.model_copy(update={"credits_reviewed": None})
    lines, blockers = _covered(data)
    federal = _by_form(lines, "T1")

    assert federal["30100"].status == "blocked"
    assert "unknown_credit_applicability" in {blocker.code for blocker in blockers}


def test_moving_expense_lines_require_their_own_explicit_screen():
    unknown = _input(employed=True)
    unknown.taxpayer = unknown.taxpayer.model_copy(update={"has_moving_expenses": None})
    unknown_lines, unknown_blockers = _covered(unknown)
    unknown_federal = _by_form(unknown_lines, "T1")
    unknown_quebec = _by_form(unknown_lines, "TP1")

    assert unknown_federal["21900"].status == "blocked"
    assert unknown_quebec["228"].status == "blocked"
    assert "unknown_moving-expense_applicability" in {
        blocker.code for blocker in unknown_blockers
    }
    assert any(
        "taxpayer.has_moving_expenses" in blocker.input_paths
        for blocker in unknown_blockers
    )

    false_lines, _ = _covered(_input(employed=True))
    assert _by_form(false_lines, "T1")["21900"].status == "not_applicable"
    assert _by_form(false_lines, "TP1")["228"].status == "not_applicable"


def test_positive_moving_expense_screen_blocks_until_schedule_is_supported():
    data = _input(employed=True)
    data.taxpayer = data.taxpayer.model_copy(update={"has_moving_expenses": True})

    assert "unsupported_situation" in {
        blocker.code for blocker in calculate_return(data).blockers
    }


def test_tips_and_other_employment_income_lines_require_their_own_screen():
    unknown = _input(employed=True)
    unknown.taxpayer = unknown.taxpayer.model_copy(
        update={"has_tips_or_other_employment_income": None}
    )
    unknown_lines, unknown_blockers = _covered(unknown)

    assert _by_form(unknown_lines, "T1")["10400"].status == "blocked"
    assert _by_form(unknown_lines, "TP1")["106"].status == "blocked"
    assert _by_form(unknown_lines, "TP1")["107"].status == "blocked"
    assert "unknown_tips-or-other-employment-income_applicability" in {
        blocker.code for blocker in unknown_blockers
    }
    assert any(
        "taxpayer.has_tips_or_other_employment_income" in blocker.input_paths
        for blocker in unknown_blockers
    )

    positive = _input(employed=True)
    positive.taxpayer = positive.taxpayer.model_copy(
        update={"has_tips_or_other_employment_income": True}
    )
    assert "unsupported_situation" in {
        blocker.code for blocker in calculate_return(positive).blockers
    }


def test_quebec_line_406_is_the_line_399_nonrefundable_credit_carry():
    result = calculate_return(_input(employed=True))
    quebec = _by_form(result.lines, "TP1")

    assert quebec["406"].value == quebec["399"].value
    assert quebec["406"].status == "calculated"


def test_every_completion_source_id_resolves():
    lines, _ = _covered(_input(employed=True))

    assert all(line.source_ids for line in lines)
    assert {source_id for line in lines for source_id in line.source_ids} <= SOURCES.keys()
