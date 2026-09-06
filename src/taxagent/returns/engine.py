"""Public fail-closed entry point for the 2025 Quebec return ruleset."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping

from .coverage_2025 import complete_main_form_coverage
from .federal_2025_qc import calculate_federal, calculate_qpp_schedule8
from .gates import preflight
from .line_labels_2025 import official_applicability, official_line_label
from .models import LineValue, TaxReturnInput, TaxReturnResult
from .quebec_2025 import calculate_quebec
from .sources import SOURCES


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


def calculate_return(data: TaxReturnInput) -> TaxReturnResult:
    """Calculate both returns or return explicit blockers without headline amounts."""

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
    )
