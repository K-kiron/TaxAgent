"""Public fail-closed entry point for the 2025 Quebec return ruleset."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping

from .annual_rules import ANNUAL_RULES, annual_preflight, calculate_annual_federal, calculate_annual_quebec, complete_annual_main_lines
from .coverage_2025 import complete_main_form_coverage
from .federal_2025_qc import calculate_federal, calculate_qpp_schedule8
from .gates import preflight
from .line_labels_2025 import official_applicability, official_line_label
from .models import CarryforwardAmount, LineValue, TaxReturnInput, TaxReturnResult
from .quebec_2025 import calculate_quebec
from .sources import ALL_SOURCES, SOURCES


COVERAGE_PROFILE_ID = "2025-qc-single-salaried-student-v1"

_FORMULA_FILES = (
    Path(__file__).with_name("models.py"),
    Path(__file__).with_name("gates.py"),
    Path(__file__).with_name("federal_2025_qc.py"),
    Path(__file__).with_name("quebec_2025.py"),
    Path(__file__).with_name("quebec_schedule_f.py"),
    Path(__file__).with_name("quebec_schedules.py"),
    Path(__file__).with_name("coverage_2025.py"),
    Path(__file__).with_name("line_labels_2025.py"),
    Path(__file__).with_name("engine.py"),
)


def _ruleset_hash(formula_paths: Iterable[Path] | None = None) -> str:
    """Hash executed code and frozen source metadata, independent of checkout EOLs."""

    digest = hashlib.sha256()
    for path in formula_paths or _FORMULA_FILES:
        normalized = Path(path).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        digest.update(len(normalized).to_bytes(8, "big"))
        digest.update(normalized)
    source_manifest = {
        source_id: source.model_dump(mode="json")
        for source_id, source in sorted(SOURCES.items())
    }
    digest.update(
        json.dumps(source_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return digest.hexdigest()


def _input_digest(data: TaxReturnInput) -> str:
    canonical = json.dumps(
        data.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _annual_ruleset_hash(year: int) -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__).with_name("models.py"), Path(__file__).with_name("annual_rules.py"), Path(__file__).with_name("gates.py"), Path(__file__).with_name("annual_main_lines.json"), Path(__file__).with_name("engine.py")):
        digest.update(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    manifest = {
        source_id: source.model_dump(mode="json")
        for source_id, source in sorted(ALL_SOURCES.items())
        if source.tax_year == year
    }
    digest.update(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    return digest.hexdigest()


def _sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    return text if text.endswith(('.', '!', '?')) else f"{text}."


def _explain(line: LineValue) -> LineValue:
    label = official_line_label(line.form_id, line.line_id)
    applicability = official_applicability(line.form_id, line.line_id)
    existing = line.explanation.strip()

    if label is None:
        if existing:
            return line
        if line.formula_id:
            label = line.formula_id.replace("_", " ").capitalize()
        else:
            label = "Entered amount" if line.status == "input" else "Calculated amount"
        inputs = f" Based on {', '.join(line.inputs)}." if line.inputs else ""
        return line.model_copy(
            update={"explanation": f"{line.form_id} line {line.line_id}: {label}.{inputs}"}
        )

    prefix = f"{line.form_id} line {line.line_id}: {label}."
    details: list[str] = [prefix]
    if line.status == "not_applicable":
        reason = existing or "No supported fact made this line applicable."
        details.append(f"Not applicable: {_sentence(reason)}")
    elif line.status == "blocked":
        reason = existing or "Applicability must be resolved before this line can be completed."
        details.append(f"Blocked: {_sentence(reason)}")
    elif existing and label not in existing:
        details.append(f"Calculation note: {_sentence(existing)}")
    if line.inputs:
        details.append(f"Based on {', '.join(line.inputs)}.")
    if applicability:
        details.append(f"Applicability condition: {_sentence(applicability)}")
    return line.model_copy(update={"explanation": " ".join(details)})


def _amount(lines: Mapping[str, LineValue], line_id: str) -> Decimal:
    value = lines[line_id].value
    if not isinstance(value, Decimal):
        raise TypeError(f"Expected a monetary amount at line {line_id}")
    return value


def _signed_refund_or_balance(
    lines: Mapping[str, LineValue], refund_line: str, balance_line: str
) -> Decimal:
    refund = _amount(lines, refund_line)
    balance = _amount(lines, balance_line)
    return refund if refund else -balance


def _carryforward_outputs(data: TaxReturnInput, lines: Iterable[LineValue]) -> dict[str, CarryforwardAmount]:
    """Expose proposed closing balances without altering assessed opening inputs."""

    indexed = {(item.form_id, item.line_id): item for item in lines}
    output: dict[str, CarryforwardAmount] = {}

    def add(name: str, form: str, line_id: str, explanation: str) -> None:
        item = indexed.get((form, line_id))
        if item is not None and isinstance(item.value, Decimal) and item.value >= 0:
            output[name] = CarryforwardAmount(
                amount=item.value,
                source_line_ids=[f"{form}:{line_id}"],
                explanation=explanation,
            )

    add("federal_tuition_unused_fees", "T1-S11", "24" if data.tax_year == 2020 else "25", "Proposed federal tuition fees available to carry forward after this return.")
    add("quebec_tuition_unused_fees_20_percent", "TP1-T", "40", "Proposed Quebec legacy 20% tuition fee pool after this return.")
    add("quebec_tuition_unused_fees_8_percent", "TP1-T", "48", "Proposed Quebec 8% tuition fee pool after this return.")
    add("rrsp_unused_contributions", "T1-S7", "23", "Proposed unused RRSP contributions after the elected deduction.")
    add("quebec_student_loan_interest_unused", "TP1-M", "62", "Proposed unused Quebec student-loan interest after the elected claim.")

    loan = data.student_loan_interest
    origins = loan.federal_unused_by_origin_year
    if origins is None and data.tax_year == 2025:
        origins = {
            year: value
            for year in range(2020, 2025)
            if (value := getattr(loan, f"federal_unused_{year}")) is not None
        }
    available = (loan.federal_current_year_paid or Decimal("0")) + sum((origins or {}).values(), start=Decimal("0"))
    remaining = max(available - (loan.federal_claim_amount or Decimal("0")), Decimal("0"))
    output["federal_student_loan_interest_unallocated_unused"] = CarryforwardAmount(
        amount=remaining,
        source_line_ids=["T1:31900"],
        explanation="Proposed total federal student-loan interest remaining; a positive claim needs taxpayer allocation before origin-year balances can be stated.",
    )
    if not (loan.federal_claim_amount or Decimal("0")):
        for origin_year, amount in sorted((origins or {}).items()):
            output[f"federal_student_loan_interest_unused_{origin_year}"] = CarryforwardAmount(
                amount=amount,
                source_line_ids=["T1:31900"],
                explanation=f"Proposed unclaimed federal student-loan interest originating in {origin_year}.",
            )
        if loan.federal_current_year_paid is not None:
            output[f"federal_student_loan_interest_unused_{data.tax_year}"] = CarryforwardAmount(
                amount=loan.federal_current_year_paid,
                source_line_ids=["T1:31900"],
                explanation=f"Proposed unclaimed federal student-loan interest originating in {data.tax_year}.",
            )
    return output


def calculate_return(data: TaxReturnInput) -> TaxReturnResult:
    """Calculate both returns or return explicit blockers without headline amounts."""

    if data.tax_year in ANNUAL_RULES:
        rules = ANNUAL_RULES[data.tax_year]
        ruleset_hash = _annual_ruleset_hash(data.tax_year)
        input_digest = _input_digest(data)
        blockers = annual_preflight(data)
        profile = f"{data.tax_year}-qc-single-salaried-student-v2"
        if blockers:
            return TaxReturnResult(
                status="blocked",
                coverage_profile_id=profile,
                ruleset_hash=ruleset_hash,
                input_digest=input_digest,
                blockers=blockers,
            )
        federal = calculate_annual_federal(data, rules)
        if federal.blockers:
            return TaxReturnResult(
                status="blocked",
                coverage_profile_id=profile,
                ruleset_hash=ruleset_hash,
                input_digest=input_digest,
                blockers=federal.blockers,
            )
        quebec = calculate_annual_quebec(data, rules, federal)
        if quebec.blockers:
            return TaxReturnResult(
                status="blocked",
                coverage_profile_id=profile,
                ruleset_hash=ruleset_hash,
                input_digest=input_digest,
                blockers=quebec.blockers,
            )
        lines = complete_annual_main_lines(data.tax_year, [*federal.lines.values(), *quebec.lines.values()])
        return TaxReturnResult(
            status="complete",
            coverage_profile_id=profile,
            ruleset_hash=ruleset_hash,
            input_digest=input_digest,
            warnings=[
                "Positive headline amounts are refunds; negative amounts are balances owing.",
                "This ruleset covers the declared single Quebec salary/student profile; special return branches remain fail-closed.",
            ],
            lines=lines,
            federal_refund_or_balance=_signed_refund_or_balance(federal.lines, "48400", "48500"),
            quebec_refund_or_balance=_signed_refund_or_balance(quebec.lines, "478", "479"),
            benefit_estimates={
                "canada_workers_benefit": _amount(federal.lines, "45300"),
                "quebec_work_premium": _amount(quebec.lines, "456"),
            },
            carryforwards=_carryforward_outputs(data, lines),
        )

    ruleset_hash = _ruleset_hash()
    input_digest = _input_digest(data)
    blockers = preflight(data)
    if blockers:
        return TaxReturnResult(
            status="blocked",
            coverage_profile_id=COVERAGE_PROFILE_ID,
            ruleset_hash=ruleset_hash,
            input_digest=input_digest,
            blockers=blockers,
            missing_documents=sorted(
                {
                    path
                    for blocker in blockers
                    if blocker.code.startswith("missing_")
                    for path in blocker.input_paths
                }
            ),
        )

    qpp = calculate_qpp_schedule8(data)
    federal = calculate_federal(data)
    if qpp.blockers or federal.blockers:
        return TaxReturnResult(
            status="blocked",
            coverage_profile_id=COVERAGE_PROFILE_ID,
            ruleset_hash=ruleset_hash,
            input_digest=input_digest,
            blockers=[*qpp.blockers, *federal.blockers],
        )
    quebec = calculate_quebec(data)
    if quebec.blockers:
        return TaxReturnResult(
            status="blocked",
            coverage_profile_id=COVERAGE_PROFILE_ID,
            ruleset_hash=ruleset_hash,
            input_digest=input_digest,
            blockers=quebec.blockers,
            lines=[_explain(line) for line in quebec.lines.values()],
        )

    lines = [
        *qpp.lines.values(),
        *federal.lines.values(),
        *quebec.lines.values(),
    ]
    lines, coverage_blockers = complete_main_form_coverage(data, lines)
    if coverage_blockers:
        return TaxReturnResult(
            status="blocked",
            coverage_profile_id=COVERAGE_PROFILE_ID,
            ruleset_hash=ruleset_hash,
            input_digest=input_digest,
            blockers=coverage_blockers,
            lines=[_explain(line) for line in lines],
        )
    return TaxReturnResult(
        status="complete",
        coverage_profile_id=COVERAGE_PROFILE_ID,
        ruleset_hash=ruleset_hash,
        input_digest=input_digest,
        warnings=[
            "Positive headline amounts are refunds; negative amounts are balances owing.",
            "The Quebec headline is the prepared-return amount before any additional below-maximum QPIP overpayment that Revenu Quebec may calculate on assessment.",
        ],
        lines=[_explain(line) for line in lines],
        federal_refund_or_balance=_signed_refund_or_balance(federal.lines, "48400", "48500"),
        quebec_refund_or_balance=_signed_refund_or_balance(quebec.lines, "478", "479"),
        benefit_estimates={
            "canada_workers_benefit": _amount(federal.lines, "45300"),
            "quebec_work_premium": _amount(quebec.lines, "456"),
        },
        carryforwards=_carryforward_outputs(data, lines),
    )
