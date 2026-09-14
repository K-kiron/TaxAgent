"""Bridge imported PDF candidates into a year-keyed return workspace."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from taxagent.intake.models import ExtractedField, ImportedSlipCandidate, PdfImportBatchResult
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
    RrspInput,
    ScholarshipInput,
    SlipInput,
    StudentLoanInterestInput,
    TaxReturnInput,
    TaxpayerFacts,
    calculate_return,
)
from taxagent.returns import calculate_return as _calculate_return_for_missing_facts
from taxagent.returns.annual_rules import annual_preflight

SUPPORTED_YEARS = range(2020, 2026)
ENGINE_SLIP_TYPES = {"T4", "T4A", "T4E", "RL1", "T5", "RL3", "T2202", "RRSP_RECEIPT", "RC210", "RL19"}
BRIDGE_SLIP_TYPES = ENGINE_SLIP_TYPES | {"RL8"}
CorrectionValue = Decimal | StrictBool | str
CORRECTABLE_FIELDS = {
    "T2202": {"24", "25", "26"},
}
CORRECTABLE_METADATA = {
    "T4": {"province_of_employment", "cpp_qpp_exempt", "ei_exempt", "ppip_exempt"},
}


class BridgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkspaceYear(BridgeModel):
    tax_year: int
    input: dict[str, Any]
    evidence: dict[str, Any] = Field(default_factory=dict)
    unresolved_candidates: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_candidates: list[dict[str, Any]] = Field(default_factory=list)
    missing_facts: list[dict[str, str]] = Field(default_factory=list)
    carryforwards: dict[str, Any] = Field(default_factory=dict)
    ready_to_calculate: bool = False


class BatchWorkspace(BridgeModel):
    schema_version: str = "batch-workspace-v1"
    years: dict[str, WorkspaceYear]
    unassigned_candidates: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_candidates: list[dict[str, Any]] = Field(default_factory=list)
    excluded_candidates: list[dict[str, Any]] = Field(default_factory=list)
    source_candidates: dict[str, ImportedSlipCandidate] = Field(default_factory=dict)
    file_errors: list[dict[str, Any]] = Field(default_factory=list)
    active_years: list[StrictInt] = Field(default_factory=list)
    corrections: list["CandidateCorrection"] = Field(default_factory=list)
    decisions: list["CandidateReviewDecision"] = Field(default_factory=list)
    carryforward_choices: list["CarryforwardChoice"] = Field(default_factory=list)
    correction_audit: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_year_keys(self) -> "BatchWorkspace":
        mismatches = [
            key
            for key, value in self.years.items()
            if key != str(value.tax_year) or value.input.get("tax_year") != value.tax_year
        ]
        if mismatches:
            raise ValueError(f"workspace year key does not match tax_year: {mismatches}")
        if len(self.active_years) != len(set(self.active_years)):
            raise ValueError("active_years must not contain duplicates")
        invalid_active = [year for year in self.active_years if year not in SUPPORTED_YEARS or str(year) not in self.years]
        if invalid_active:
            raise ValueError(f"active_years must identify supported workspace years: {invalid_active}")
        registry_mismatches = [key for key, candidate in self.source_candidates.items() if key != candidate.candidate_id]
        if registry_mismatches:
            raise ValueError(f"source candidate key does not match candidate_id: {registry_mismatches}")
        return self


class CandidateCorrection(BridgeModel):
    candidate_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    slip_type: str | None = Field(default=None, min_length=1, max_length=40)
    tax_year: StrictInt | None = None
    issuer_id: str | None = Field(default=None, min_length=1, max_length=300)
    fields: dict[str, CorrectionValue] | None = Field(default=None, max_length=100)
    metadata: dict[str, CorrectionValue] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_correction(self) -> "CandidateCorrection":
        if self.tax_year is not None and self.tax_year not in SUPPORTED_YEARS:
            raise ValueError("corrected tax_year must be between 2020 and 2025")
        if (
            self.slip_type is None
            and self.tax_year is None
            and self.issuer_id is None
            and self.fields is None
            and self.metadata is None
        ):
            raise ValueError("correction must change type, year, issuer, or at least one box")
        for label, values in (("fields", self.fields), ("metadata", self.metadata)):
            if values is None:
                continue
            if not values:
                raise ValueError(f"corrected {label} must not be empty")
            invalid = [
                key for key, value in values.items()
                if not key or len(key) > 40 or not _valid_correction_value(value)
            ]
            if invalid:
                raise ValueError(f"corrected {label} values must be finite, nonnegative, or typed source facts: {invalid}")
        return self


class CandidateReviewDecision(BridgeModel):
    candidate_id: str = Field(min_length=1, max_length=200)
    action: Literal["accept", "exclude", "select_amendment"]
    reason: str = Field(min_length=1, max_length=500)
    selected_candidate_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_selection(self) -> "CandidateReviewDecision":
        if self.action != "select_amendment" and self.selected_candidate_id is not None:
            raise ValueError("selected_candidate_id is only valid for select_amendment")
        return self


class CarryforwardChoice(BridgeModel):
    tax_year: StrictInt
    key: str = Field(min_length=1, max_length=100)
    selection: Literal["assessed", "proposed"]
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_year(self) -> "CarryforwardChoice":
        if self.tax_year not in SUPPORTED_YEARS:
            raise ValueError("carryforward choice tax_year must be between 2020 and 2025")
        return self


class ReconcileRequest(BridgeModel):
    workspace: BatchWorkspace
    active_years: list[StrictInt]
    corrections: list[CandidateCorrection] = Field(default_factory=list, max_length=500)
    decisions: list[CandidateReviewDecision] = Field(default_factory=list, max_length=500)
    carryforward_choices: list[CarryforwardChoice] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_active_years(self) -> "ReconcileRequest":
        if len(self.active_years) != len(set(self.active_years)):
            raise ValueError("active_years must not contain duplicates")
        invalid = [year for year in self.active_years if year not in SUPPORTED_YEARS or str(year) not in self.workspace.years]
        if invalid:
            raise ValueError(f"active_years must identify supported workspace years: {invalid}")
        return self


BatchWorkspace.model_rebuild()


def workspace_from_import(import_result: PdfImportBatchResult) -> BatchWorkspace:
    years = {
        str(year): WorkspaceYear(
            tax_year=year,
            input=_blank_year_input(year).model_dump(mode="json"),
            missing_facts=[],
            carryforwards={
                "assessed_opening_balances": {},
                "proposed_closing_balances": {},
                "conflicts": [],
                "downstream_invalidated": False,
            },
        )
        for year in SUPPORTED_YEARS
    }

    unassigned_candidates: list[dict[str, Any]] = []
    duplicate_candidates: list[dict[str, Any]] = []
    active_years: set[int] = set()

    for candidate in import_result.candidates:
        if candidate.decision == "duplicate":
            duplicate = _candidate_review(candidate, "duplicate_candidate")
            if candidate.tax_year in SUPPORTED_YEARS:
                years[str(candidate.tax_year)].duplicate_candidates.append(duplicate)
            else:
                duplicate_candidates.append(duplicate)
            continue
        if candidate.tax_year not in SUPPORTED_YEARS:
            unassigned_candidates.append(_candidate_review(candidate, "unsupported_or_missing_year"))
            continue
        active_years.add(candidate.tax_year)
        year_state = years[str(candidate.tax_year)]
        if candidate.decision != "accepted_auto":
            year_state.unresolved_candidates.append(_candidate_review(candidate, "candidate_requires_review"))
            continue
        if _engine_slip_type(candidate) not in BRIDGE_SLIP_TYPES:
            year_state.unresolved_candidates.append(_candidate_review(candidate, "unsupported_slip_type"))
            continue
        if _engine_slip_type(candidate) in ENGINE_SLIP_TYPES:
            slip = _slip_from_candidate(candidate)
            year_state.input["slips"].append(slip.model_dump(mode="json"))
        year_state.evidence[candidate.candidate_id] = _candidate_evidence(candidate, candidate)
        _map_candidate_to_year_inputs(candidate, year_state.input)

    candidates = {candidate.candidate_id: candidate for candidate in import_result.candidates}
    for year_state in years.values():
        _rebuild_imported_quebec_tuition(year_state, candidates)
        _refresh_year_status(year_state)
    return BatchWorkspace(
        years=years,
        unassigned_candidates=unassigned_candidates,
        duplicate_candidates=duplicate_candidates,
        source_candidates=candidates,
        file_errors=[
            document.model_dump(mode="json")
            for document in import_result.documents
            if document.status not in {"processed", "duplicate"}
        ],
        active_years=sorted(active_years),
    )


def reconcile_workspace(request: ReconcileRequest | dict[str, Any]) -> BatchWorkspace:
    """Apply reviewed corrections and rebuild all derived workspace state."""

    parsed = request if isinstance(request, ReconcileRequest) else ReconcileRequest.model_validate(request)
    workspace = parsed.workspace.model_copy(deep=True)
    workspace.active_years = sorted(parsed.active_years)
    workspace.corrections = _merge_by_key(
        workspace.corrections,
        parsed.corrections,
        lambda item: item.candidate_id,
        merge_correction=True,
    )
    workspace.decisions = _merge_by_key(
        workspace.decisions,
        parsed.decisions,
        lambda item: item.candidate_id,
    )
    workspace.carryforward_choices = _merge_by_key(
        workspace.carryforward_choices,
        parsed.carryforward_choices,
        lambda item: (item.tax_year, item.key),
    )
    for kind, items in (
        ("correction", parsed.corrections),
        ("decision", parsed.decisions),
        ("carryforward_choice", parsed.carryforward_choices),
    ):
        for item in items:
            audit = {"kind": kind, **item.model_dump(mode="json", exclude_none=True)}
            if audit not in workspace.correction_audit:
                workspace.correction_audit.append(audit)

    candidates = _corrected_candidates(workspace)
    decisions = {item.candidate_id: item for item in workspace.decisions}
    _validate_review_targets(workspace, candidates, decisions)
    selected, amendment_exclusions = _selected_amendments(candidates, decisions)

    orphaned_unassigned = [
        item for item in workspace.unassigned_candidates
        if item.get("candidate_id") not in workspace.source_candidates
    ]
    orphaned_duplicates = [
        item for item in workspace.duplicate_candidates
        if item.get("candidate_id") not in workspace.source_candidates
    ]
    for year_state in workspace.years.values():
        _remove_imported_derivations(year_state, workspace.source_candidates)
        year_state.unresolved_candidates = []
        year_state.duplicate_candidates = []
    workspace.unassigned_candidates = orphaned_unassigned
    workspace.duplicate_candidates = orphaned_duplicates
    workspace.excluded_candidates = []

    for candidate_id, candidate in candidates.items():
        action = decisions.get(candidate_id)
        if candidate_id in amendment_exclusions or (action and action.action == "exclude"):
            workspace.excluded_candidates.append(_candidate_review(candidate, "excluded_by_user"))
            continue
        explicitly_accepted = bool(action and action.action == "accept") or candidate_id in selected
        if candidate.tax_year not in SUPPORTED_YEARS:
            workspace.unassigned_candidates.append(_candidate_review(candidate, "unsupported_or_missing_year"))
            continue
        year_state = workspace.years[str(candidate.tax_year)]
        if candidate.decision == "duplicate" and not explicitly_accepted:
            duplicate = _candidate_review(candidate, "duplicate_candidate")
            year_state.duplicate_candidates.append(duplicate)
            continue
        slip_type = _engine_slip_type(candidate)
        if slip_type not in BRIDGE_SLIP_TYPES:
            year_state.unresolved_candidates.append(_candidate_review(candidate, "unsupported_slip_type"))
            continue
        if candidate.decision != "accepted_auto" and not explicitly_accepted:
            year_state.unresolved_candidates.append(_candidate_review(candidate, "candidate_requires_review"))
            continue
        if slip_type in ENGINE_SLIP_TYPES:
            year_state.input["slips"].append(_slip_from_candidate(candidate).model_dump(mode="json"))
        original = workspace.source_candidates[candidate_id]
        year_state.evidence[candidate_id] = _candidate_evidence(candidate, original)
        _map_candidate_to_year_inputs(candidate, year_state.input)

    for year_state in workspace.years.values():
        _rebuild_imported_quebec_tuition(year_state, candidates)
    _invalidate_stale_dependencies(workspace)
    for year_state in workspace.years.values():
        _capture_assessed_openings(year_state, workspace)
        _refresh_year_status(year_state)
    return BatchWorkspace.model_validate(workspace.model_dump(mode="json"))


def _merge_by_key(existing, incoming, key, *, merge_correction: bool = False):
    merged = {key(item): item for item in existing}
    order = [key(item) for item in existing]
    for item in incoming:
        item_key = key(item)
        if merge_correction and item_key in merged:
            prior = merged[item_key]
            update = item.model_dump(exclude_none=True)
            if item.fields is not None:
                update["fields"] = {**(prior.fields or {}), **item.fields}
            if item.metadata is not None:
                update["metadata"] = {**(prior.metadata or {}), **item.metadata}
            merged[item_key] = prior.model_copy(update=update)
        else:
            merged[item_key] = item
        if item_key not in order:
            order.append(item_key)
    return [merged[item_key] for item_key in order]


def _corrected_candidates(workspace: BatchWorkspace) -> dict[str, ImportedSlipCandidate]:
    corrections = {item.candidate_id: item for item in workspace.corrections}
    candidates: dict[str, ImportedSlipCandidate] = {}
    for candidate_id, original in workspace.source_candidates.items():
        correction = corrections.get(candidate_id)
        if correction is None:
            candidates[candidate_id] = original.model_copy(deep=True)
            continue
        slip_type = correction.slip_type if correction.slip_type is not None else original.slip_type
        fields = {box: field.model_copy(deep=True) for box, field in original.fields.items()}
        for box, value in (correction.fields or {}).items():
            if box not in fields and box not in CORRECTABLE_FIELDS.get((slip_type or "").replace("-", ""), set()):
                raise ValueError(f"corrected box {box!r} is not supported on candidate {candidate_id!r}")
            current = fields.get(box)
            if current is None:
                fields[box] = _correction_field(box, value)
            else:
                fields[box] = current.model_copy(update={"value": _field_value(value), "review_required": False})
        metadata = {key: field.model_copy(deep=True) for key, field in original.metadata.items()}
        for key, value in (correction.metadata or {}).items():
            if key not in metadata and key not in CORRECTABLE_METADATA.get((slip_type or "").replace("-", ""), set()):
                raise ValueError(f"corrected metadata {key!r} is not supported on candidate {candidate_id!r}")
            current = metadata.get(key)
            if current is None:
                metadata[key] = _correction_field(key, value)
            else:
                metadata[key] = current.model_copy(update={
                    "value": _field_value(value),
                    "review_required": False,
                    "value_state": _value_state(value),
                })
        candidates[candidate_id] = original.model_copy(update={
            "slip_type": slip_type,
            "tax_year": correction.tax_year if correction.tax_year is not None else original.tax_year,
            "issuer_id": correction.issuer_id if correction.issuer_id is not None else original.issuer_id,
            "fields": fields,
            "metadata": metadata,
        })
    return candidates


def _validate_review_targets(
    workspace: BatchWorkspace,
    candidates: dict[str, ImportedSlipCandidate],
    decisions: dict[str, CandidateReviewDecision],
) -> None:
    unknown_corrections = [item.candidate_id for item in workspace.corrections if item.candidate_id not in candidates]
    unknown_decisions = [item.candidate_id for item in workspace.decisions if item.candidate_id not in candidates]
    unknown_selected = [
        item.selected_candidate_id
        for item in decisions.values()
        if item.selected_candidate_id is not None and item.selected_candidate_id not in candidates
    ]
    unknown = [*unknown_corrections, *unknown_decisions, *unknown_selected]
    if unknown:
        raise ValueError(f"review action references an unknown candidate: {unknown}")


def _selected_amendments(
    candidates: dict[str, ImportedSlipCandidate],
    decisions: dict[str, CandidateReviewDecision],
) -> tuple[set[str], set[str]]:
    selected: set[str] = set()
    excluded: set[str] = set()
    for decision in decisions.values():
        if decision.action != "select_amendment":
            continue
        selected_id = decision.selected_candidate_id or decision.candidate_id
        chosen = candidates[selected_id]
        key = (_engine_slip_type(chosen), chosen.tax_year, (chosen.issuer_id or "").strip().casefold())
        group = {
            candidate_id
            for candidate_id, candidate in candidates.items()
            if (_engine_slip_type(candidate), candidate.tax_year, (candidate.issuer_id or "").strip().casefold()) == key
        }
        if decision.candidate_id not in group:
            raise ValueError("selected amendment must belong to the same type, year, and issuer group")
        selected.add(selected_id)
        excluded.update(group - {selected_id})
    return selected, excluded


def _remove_imported_derivations(
    year_state: WorkspaceYear,
    registry: dict[str, ImportedSlipCandidate],
) -> None:
    imported_ids = set(registry)
    evidence_types = {
        str(item.get("slip_type") or "").replace("-", "")
        for key, item in year_state.evidence.items()
        if key in imported_ids
    }
    year_state.input["slips"] = [
        slip for slip in year_state.input.get("slips", [])
        if slip.get("document_id") not in imported_ids
    ]
    year_state.evidence = {key: value for key, value in year_state.evidence.items() if key not in imported_ids}
    if "T2202" in evidence_types:
        year_state.input["federal_tuition"]["has_current_tuition"] = None
        year_state.input["federal_tuition"]["t2202_eligible_fees"] = None
    if evidence_types & {"T2202", "RL8"}:
        year_state.input["quebec_tuition"]["has_current_tuition"] = None
        year_state.input["quebec_tuition"]["eligible_tuition_or_exam_receipts"] = None
    if "RRSP_RECEIPT" in evidence_types:
        rrsp = year_state.input["rrsp"]
        rrsp["has_contributions"] = None
        for name in ("contribution_receipts", "march_to_december_contributions", "first_60_days_contributions"):
            rrsp[name] = None
    if "RL19" in evidence_types:
        credits = year_state.input["refundable_credits"]
        credits["rl19_advance_payments_reviewed"] = None
        credits["rl19_box_a"] = None
        credits["rl19_box_b"] = None


def _derived_active_years(workspace: BatchWorkspace) -> list[int]:
    active = []
    for key, state in workspace.years.items():
        if (
            state.input.get("slips")
            or state.unresolved_candidates
            or state.input.get("inventory", {}).get("no_income_sources") is True
            or state.evidence
        ):
            active.append(int(key))
    return sorted(active)


def _year_input_digest(data: dict[str, Any]) -> str:
    normalized = TaxReturnInput.model_validate(data).model_dump(mode="json")
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


_CARRY_INPUTS = {
    "federal_tuition_unused_fees": ("federal_tuition", "prior_unused_amount", "has_prior_unused"),
    "quebec_tuition_unused_fees_20_percent": ("quebec_tuition", "prior_unused_at_20_percent", "has_prior_unused"),
    "quebec_tuition_unused_fees_8_percent": ("quebec_tuition", "prior_unused_at_8_percent", "has_prior_unused"),
    "rrsp_unused_contributions": ("rrsp", "prior_unused_contributions", "has_prior_unused_contributions"),
    "quebec_student_loan_interest_unused": ("student_loan_interest", "quebec_prior_unused", None),
}


def _same_money(left: Any, right: Any) -> bool:
    return Decimal(str(left)) == Decimal(str(right))


def _opening_balance_snapshot(
    data: dict[str, Any],
    tracked_keys: set[str] | None = None,
) -> tuple[dict[str, str], set[str]]:
    tracked_keys = tracked_keys or set()
    balances: dict[str, str] = {}
    cleared: set[str] = set()
    for key, (section, amount_name, flag_name) in _CARRY_INPUTS.items():
        values = data[section]
        value = values.get(amount_name)
        if flag_name is None:
            if value is not None:
                balances[key] = str(value)
            elif key in tracked_keys:
                cleared.add(key)
            continue
        flag = values.get(flag_name)
        if flag is True and value is not None:
            balances[key] = str(value)
        elif flag is False:
            balances[key] = "0"
        elif flag is None and value is not None:
            balances[key] = str(value)
        elif key in tracked_keys:
            cleared.add(key)
    origins = data["student_loan_interest"].get("federal_unused_by_origin_year")
    if origins is not None:
        for origin, value in origins.items():
            key = f"federal_student_loan_interest_unused_{origin}"
            if value is None:
                cleared.add(key)
            else:
                balances[key] = str(value)
    return balances, cleared


def _explicit_opening_balances(data: dict[str, Any]) -> dict[str, str]:
    balances, _ = _opening_balance_snapshot(data)
    return balances


def _capture_assessed_openings(year_state: WorkspaceYear, workspace: BatchWorkspace | None = None) -> None:
    carry = year_state.carryforwards
    assessed = carry.setdefault("assessed_opening_balances", {})
    applied = carry.setdefault("applied_proposed_balances", {})
    origin_prefix = "federal_student_loan_interest_unused_"
    origins = year_state.input["student_loan_interest"].get("federal_unused_by_origin_year")
    tracked_keys = set(assessed) | set(applied)
    explicit, cleared = _opening_balance_snapshot(year_state.input, tracked_keys)
    if origins is None:
        cleared.update(key for key in tracked_keys if key.startswith(origin_prefix))
    else:
        present_origins = {f"{origin_prefix}{origin}" for origin in origins}
        cleared.update(
            key
            for key in tracked_keys
            if key.startswith(origin_prefix) and key not in present_origins
        )
    for key in sorted(cleared - set(explicit)):
        previous = assessed.pop(key, None)
        stale_applied = applied.pop(key, None) is not None
        if previous is None and not stale_applied:
            continue
        _refresh_assessed_conflicts(carry, key, None)
        if workspace is None:
            continue
        invalidated = _remove_carryforward_choice(workspace, year_state.tax_year, key)
        if previous is None:
            continue
        audit = {
            "kind": "assessed_opening_clear",
            "tax_year": year_state.tax_year,
            "key": key,
            "previous_assessed_amount": str(previous),
            "new_assessed_amount": None,
            "invalidated_prior_choice": invalidated,
        }
        if audit not in workspace.correction_audit:
            workspace.correction_audit.append(audit)
    for key, value in explicit.items():
        stale_applied = False
        if key in applied:
            if _same_money(applied[key], value):
                continue
            applied.pop(key, None)
            stale_applied = True
        previous = assessed.get(key)
        if previous is not None and _same_money(previous, value) and not stale_applied:
            continue
        assessed[key] = value
        _refresh_assessed_conflicts(carry, key, value)
        if workspace is None or (previous is None and not stale_applied):
            continue
        invalidated = _remove_carryforward_choice(workspace, year_state.tax_year, key)
        audit = {
            "kind": "assessed_opening_update",
            "tax_year": year_state.tax_year,
            "key": key,
            "previous_assessed_amount": str(previous) if previous is not None else None,
            "new_assessed_amount": value,
            "invalidated_prior_choice": invalidated,
        }
        if audit not in workspace.correction_audit:
            workspace.correction_audit.append(audit)


def _remove_carryforward_choice(workspace: BatchWorkspace, tax_year: int, key: str) -> bool:
    before = len(workspace.carryforward_choices)
    workspace.carryforward_choices = [
        choice
        for choice in workspace.carryforward_choices
        if not (choice.tax_year == tax_year and choice.key == key)
    ]
    return before != len(workspace.carryforward_choices)


def _refresh_assessed_conflicts(
    carry: dict[str, Any],
    key: str,
    assessed_amount: str | None,
) -> None:
    conflicts = carry.get("conflicts")
    if not isinstance(conflicts, list):
        return
    refreshed: list[dict[str, Any]] = []
    for conflict in conflicts:
        if not isinstance(conflict, dict) or conflict.get("key") != key:
            refreshed.append(conflict)
            continue
        if assessed_amount is None:
            continue
        updated = dict(conflict)
        updated["assessed_amount"] = str(assessed_amount)
        updated["resolved_selection"] = None
        proposed = updated.get("proposed_amount")
        if proposed is not None and _same_money(proposed, assessed_amount):
            continue
        refreshed.append(updated)
    carry["conflicts"] = refreshed


def _invalidate_stale_dependencies(workspace: BatchWorkspace) -> None:
    for year_state in workspace.years.values():
        dependency = year_state.carryforwards.get("depends_on")
        if not dependency:
            continue
        upstream = workspace.years.get(str(dependency.get("tax_year")))
        if upstream is None:
            year_state.carryforwards["downstream_invalidated"] = True
            continue
        current_digest = _year_input_digest(upstream.input)
        stored_rules = upstream.carryforwards.get("calculation_ruleset_hash")
        stale = dependency.get("input_digest") != current_digest
        if stored_rules and dependency.get("ruleset_hash") != stored_rules:
            stale = True
        if stale:
            year_state.carryforwards["downstream_invalidated"] = True
            year_state.carryforwards["proposed_opening_balances"] = {}
            year_state.carryforwards["proposed_closing_balances"] = {}


def _apply_prior_carryforwards(
    workspace: BatchWorkspace,
    year_state: WorkspaceYear,
    prior_year: int,
    prior_result: dict[str, Any],
) -> list[dict[str, Any]]:
    proposed = prior_result.get("carryforwards", {})
    assessed = year_state.carryforwards.setdefault("assessed_opening_balances", {})
    choices = {
        item.key: item.selection
        for item in workspace.carryforward_choices
        if item.tax_year == year_state.tax_year
    }
    applicable = {
        key: value for key, value in proposed.items()
        if key in _CARRY_INPUTS or key.startswith("federal_student_loan_interest_unused_")
    }
    applicable.pop("federal_student_loan_interest_unallocated_unused", None)
    applicable = {
        key: value for key, value in applicable.items()
        if not key.startswith("federal_student_loan_interest_unused_")
        or Decimal(str(value.get("amount") if isinstance(value, dict) else value)) > 0
    }
    proposed_opening = {key: value for key, value in applicable.items()}
    conflicts: list[dict[str, Any]] = []
    applied: dict[str, Any] = {}
    for key, value in applicable.items():
        amount = str(value.get("amount") if isinstance(value, dict) else value)
        assessed_amount = assessed.get(key)
        selection = choices.get(key)
        if assessed_amount is not None and Decimal(str(assessed_amount)) != Decimal(amount):
            conflict = {
                "key": key,
                "assessed_amount": str(assessed_amount),
                "proposed_amount": amount,
                "resolved_selection": selection,
            }
            conflicts.append(conflict)
            if selection is None:
                continue
            chosen_amount = str(assessed_amount) if selection == "assessed" else amount
        else:
            chosen_amount = str(assessed_amount) if assessed_amount is not None else amount
        _set_opening_balance(year_state.input, key, chosen_amount)
        if selection == "proposed" or assessed_amount is None:
            applied[key] = chosen_amount
    year_state.carryforwards.update({
        "proposed_opening_balances": proposed_opening,
        "applied_proposed_balances": applied,
        "conflicts": conflicts,
        "depends_on": {
            "tax_year": prior_year,
            "input_digest": prior_result.get("input_digest"),
            "ruleset_hash": prior_result.get("ruleset_hash"),
        },
        "downstream_invalidated": False,
    })
    return conflicts


def _set_opening_balance(data: dict[str, Any], key: str, amount: str) -> None:
    if key in _CARRY_INPUTS:
        section, amount_name, flag_name = _CARRY_INPUTS[key]
        data[section][amount_name] = amount
        if flag_name:
            data[section][flag_name] = True
        return
    prefix = "federal_student_loan_interest_unused_"
    if key.startswith(prefix):
        origin = int(key.removeprefix(prefix))
        origins = dict(data["student_loan_interest"].get("federal_unused_by_origin_year") or {})
        origins[origin] = amount
        data["student_loan_interest"]["federal_unused_by_origin_year"] = origins


def _has_income_evidence_or_no_income_confirmation(year_state: WorkspaceYear) -> bool:
    if year_state.input.get("inventory", {}).get("no_income_sources") is True:
        return True
    income_types = {"T4", "T4A", "T4E", "RL1", "T5", "RL3"}
    return any(slip.get("slip_type") in income_types for slip in year_state.input.get("slips", []))


def calculate_ready_years(workspace: BatchWorkspace | dict[str, Any]) -> dict[str, Any]:
    parsed = workspace if isinstance(workspace, BatchWorkspace) else BatchWorkspace.model_validate(workspace)
    parsed = reconcile_workspace({
        "workspace": parsed,
        "active_years": parsed.active_years or _derived_active_years(parsed),
    })
    active_keys = [str(year) for year in sorted(parsed.active_years)]
    if parsed.unassigned_candidates:
        return {
            "schema_version": "batch-calculation-v1",
            "status": "blocked",
            "reason": "unassigned_candidates_require_review",
            "unassigned_candidates": parsed.unassigned_candidates,
            "duplicate_candidates": parsed.duplicate_candidates,
            "results": {
                year_key: {
                    "status": "blocked",
                    "reason": "unassigned_candidates_require_review",
                    "unresolved_candidates": year_state.unresolved_candidates,
                    "duplicate_candidates": year_state.duplicate_candidates,
                    "missing_facts": year_state.missing_facts,
                }
                for year_key, year_state in parsed.years.items()
                if year_key in active_keys
            },
            "workspace": parsed.model_dump(mode="json"),
        }
    results: dict[str, Any] = {}
    previous_year: int | None = None
    previous_result: dict[str, Any] | None = None
    for year_key in active_keys:
        year_state = parsed.years[year_key]
        if previous_year == year_state.tax_year - 1:
            if previous_result and previous_result.get("status") == "complete":
                conflicts = _apply_prior_carryforwards(parsed, year_state, previous_year, previous_result)
                if any(item.get("resolved_selection") is None for item in conflicts):
                    year_state.ready_to_calculate = False
                    year_state.missing_facts = [{
                        "path": f"carryforwards.conflicts.{item['key']}",
                        "code": "carryforward_conflict",
                        "label": "Choose the assessed opening balance or the preceding year's proposed closing balance.",
                    } for item in conflicts if item.get("resolved_selection") is None]
                    results[year_key] = {
                        "status": "blocked",
                        "reason": "carryforward_conflict",
                        "unresolved_candidates": year_state.unresolved_candidates,
                        "duplicate_candidates": year_state.duplicate_candidates,
                        "missing_facts": year_state.missing_facts,
                    }
                    previous_year = year_state.tax_year
                    previous_result = results[year_key]
                    continue
            else:
                year_state.carryforwards["downstream_invalidated"] = True
                results[year_key] = {
                    "status": "blocked",
                    "reason": "upstream_year_not_complete",
                    "unresolved_candidates": year_state.unresolved_candidates,
                    "duplicate_candidates": year_state.duplicate_candidates,
                    "missing_facts": [{
                        "path": f"years.{previous_year}",
                        "code": "upstream_year_not_complete",
                        "label": f"Complete {previous_year} before calculating dependent year {year_state.tax_year}.",
                    }],
                }
                previous_year = year_state.tax_year
                previous_result = results[year_key]
                continue
        _refresh_year_status(year_state)
        blockers = list(year_state.unresolved_candidates)
        if not _has_income_evidence_or_no_income_confirmation(year_state):
            missing_facts = _no_imported_slips_fact(year_state.tax_year)
            year_state.missing_facts = missing_facts
            year_state.ready_to_calculate = False
            results[year_key] = {
                "status": "blocked",
                "reason": "workspace_year_not_ready",
                "unresolved_candidates": year_state.unresolved_candidates,
                "duplicate_candidates": year_state.duplicate_candidates,
                "missing_facts": missing_facts,
            }
            previous_year = year_state.tax_year
            previous_result = results[year_key]
            continue
        if blockers:
            missing_facts = _missing_facts_from_input(year_state.input)
            year_state.missing_facts = missing_facts
            year_state.ready_to_calculate = False
            results[year_key] = {
                "status": "blocked",
                "reason": "workspace_year_not_ready",
                "unresolved_candidates": year_state.unresolved_candidates,
                "duplicate_candidates": year_state.duplicate_candidates,
                "missing_facts": missing_facts,
            }
            previous_year = year_state.tax_year
            previous_result = results[year_key]
            continue
        data = _decimalize_slip_fields(TaxReturnInput.model_validate(year_state.input))
        result = calculate_return(data)
        missing_facts = _missing_facts_from_result(result)
        if missing_facts:
            year_state.missing_facts = missing_facts
            year_state.ready_to_calculate = False
            results[year_key] = {
                "status": "blocked",
                "reason": "workspace_year_not_ready",
                "unresolved_candidates": year_state.unresolved_candidates,
                "duplicate_candidates": year_state.duplicate_candidates,
                "missing_facts": missing_facts,
            }
            previous_year = year_state.tax_year
            previous_result = results[year_key]
            continue
        result_data = result.model_dump(mode="json")
        results[year_key] = result_data
        year_state.carryforwards.update({
            "proposed_closing_balances": result_data.get("carryforwards", {}),
            "calculation_input_digest": result_data.get("input_digest") or _year_input_digest(year_state.input),
            "calculation_ruleset_hash": result_data.get("ruleset_hash"),
            "downstream_invalidated": False,
        })
        previous_year = year_state.tax_year
        previous_result = result_data
    return {
        "schema_version": "batch-calculation-v1",
        "status": "complete",
        "duplicate_candidates": parsed.duplicate_candidates,
        "results": results,
        "workspace": parsed.model_dump(mode="json"),
    }


def _blank_year_input(year: int) -> TaxReturnInput:
    return TaxReturnInput(
        schema_version="qc-return-v2",
        tax_year=year,
        province_dec31="QC",
        taxpayer=TaxpayerFacts(),
        slips=[],
        inventory=DocumentInventory(),
        federal_tuition=FederalTuitionInput(),
        quebec_tuition=QuebecTuitionInput(),
        rrsp=RrspInput(),
        instalments=InstalmentInput(),
        quebec_schedule_b=QuebecScheduleBInput(),
        student_loan_interest=StudentLoanInterestInput(),
        scholarships=ScholarshipInput(),
        resp_eap=RespEapInput(),
        additional_return_screens=AdditionalReturnScreenInput(),
        drug_insurance=DrugInsuranceInput(),
        refundable_credits=RefundableCreditInput(),
    )


def _slip_from_candidate(candidate: ImportedSlipCandidate) -> SlipInput:
    metadata = candidate.metadata
    return SlipInput(
        slip_type=_engine_slip_type(candidate),
        document_id=candidate.candidate_id,
        issuer_id=candidate.issuer_id or "unknown",
        tax_year=candidate.tax_year or 0,
        province_of_employment=_metadata_str(metadata, "province_of_employment"),
        cpp_qpp_exempt=_metadata_bool(metadata, "cpp_qpp_exempt"),
        ei_exempt=_metadata_bool(metadata, "ei_exempt"),
        ppip_exempt=_metadata_bool(metadata, "ppip_exempt"),
        rrsp_period=_rrsp_period(candidate),
        confirmed=True,
        fields=_slip_fields(candidate),
    )


def _engine_slip_type(candidate: ImportedSlipCandidate) -> str:
    return (candidate.slip_type or "").replace("-", "")


def _engine_box(candidate: ImportedSlipCandidate, box: str) -> str:
    if candidate.slip_type == "RRSP_RECEIPT" and box == "contribution_amount":
        return "amount"
    if _engine_slip_type(candidate) == "T4A" and box in {"40", "42"}:
        return box.zfill(3)
    return box


def _slip_fields(candidate: ImportedSlipCandidate) -> dict[str, Decimal]:
    fields: dict[str, Decimal] = {}
    for box, field in candidate.fields.items():
        engine_box = _engine_box(candidate, box)
        fields[engine_box] = Decimal(str(field.value))
    return fields


def _metadata_str(metadata: dict[str, ExtractedField], key: str) -> str | None:
    field = metadata.get(key)
    return str(field.value).strip() if field is not None and field.value_state != "blank" else None


def _metadata_bool(metadata: dict[str, ExtractedField], key: str) -> bool | None:
    field = metadata.get(key)
    return field.value if field is not None and isinstance(field.value, bool) else None


def _normalized_issuer(candidate: ImportedSlipCandidate) -> str:
    return " ".join((candidate.issuer_id or "").split()).casefold()


def _append_candidate_review(year_state: WorkspaceYear, candidate: ImportedSlipCandidate, reason: str) -> None:
    review = _candidate_review(candidate, reason)
    if all(item.get("candidate_id") != candidate.candidate_id or item.get("reason") != reason for item in year_state.unresolved_candidates):
        year_state.unresolved_candidates.append(review)


def _rebuild_imported_quebec_tuition(
    year_state: WorkspaceYear,
    candidates: dict[str, ImportedSlipCandidate],
) -> None:
    groups: dict[str, dict[str, Any]] = {}
    has_imported_tuition = False
    tuition_conflict = False
    for candidate_id in year_state.evidence:
        candidate = candidates.get(candidate_id)
        if candidate is None or candidate.tax_year != year_state.tax_year:
            continue
        slip_type = _engine_slip_type(candidate)
        group = groups.setdefault(_normalized_issuer(candidate), {"t2202": [], "rl8": []})
        if slip_type == "T2202" and "26" in candidate.fields:
            has_imported_tuition = True
            group["t2202"].append((candidate, Decimal(candidate.fields["26"].value)))
        elif slip_type == "RL8":
            if "B" in candidate.fields:
                has_imported_tuition = True
                group["rl8"].append((candidate, Decimal(candidate.fields["B"].value)))
            box_c = candidate.fields.get("C")
            if box_c is not None and Decimal(box_c.value) > 0:
                _append_candidate_review(year_state, candidate, "unsupported_rl8_donation")
    if not has_imported_tuition:
        return

    total = Decimal("0")
    for group in groups.values():
        t2202_total = sum((amount for _, amount in group["t2202"]), start=Decimal("0"))
        rl8_total = sum((amount for _, amount in group["rl8"]), start=Decimal("0"))
        if t2202_total and rl8_total:
            if t2202_total == rl8_total:
                total += t2202_total
                continue
            tuition_conflict = True
            for candidate, _ in [*group["t2202"], *group["rl8"]]:
                _append_candidate_review(year_state, candidate, "conflicting_tuition_evidence")
            continue
        total += t2202_total + rl8_total

    if tuition_conflict:
        year_state.input["quebec_tuition"]["has_current_tuition"] = None
        year_state.input["quebec_tuition"]["eligible_tuition_or_exam_receipts"] = None
        return
    year_state.input["quebec_tuition"]["has_current_tuition"] = True
    year_state.input["quebec_tuition"]["eligible_tuition_or_exam_receipts"] = str(total)


def _map_candidate_to_year_inputs(candidate: ImportedSlipCandidate, data: dict[str, Any]) -> None:
    fields = candidate.fields
    slip_type = _engine_slip_type(candidate)
    if slip_type == "T2202" and "26" in fields:
        data["federal_tuition"]["has_current_tuition"] = True
        _add_money(data["federal_tuition"], "t2202_eligible_fees", fields["26"].value)
    if slip_type == "RRSP_RECEIPT" and "contribution_amount" in fields:
        period = _rrsp_period(candidate)
        data["rrsp"]["has_contributions"] = True
        _add_money(data["rrsp"], "contribution_receipts", fields["contribution_amount"].value)
        if period == "march_to_december":
            _add_money(data["rrsp"], "march_to_december_contributions", fields["contribution_amount"].value)
        elif period == "first_60_days":
            _add_money(data["rrsp"], "first_60_days_contributions", fields["contribution_amount"].value)
    if slip_type == "RL19":
        data["refundable_credits"]["rl19_advance_payments_reviewed"] = True
        if "A" in fields:
            _add_money(data["refundable_credits"], "rl19_box_a", fields["A"].value)
        if "B" in fields:
            _add_money(data["refundable_credits"], "rl19_box_b", fields["B"].value)


def _rrsp_period(candidate: ImportedSlipCandidate) -> str | None:
    if candidate.slip_type != "RRSP_RECEIPT":
        return None
    if candidate.contribution_period in {"march_to_december", "march_to_december_2025"}:
        return "march_to_december"
    if candidate.contribution_period in {"first_60_days", "first_60_days_2026"}:
        return "first_60_days"
    return None


def _add_money(section: dict[str, Any], key: str, value: str) -> None:
    current = Decimal(str(section[key])) if section.get(key) is not None else Decimal("0")
    section[key] = str(current + Decimal(value))


def _refresh_year_status(year_state: WorkspaceYear) -> None:
    if not _has_income_evidence_or_no_income_confirmation(year_state):
        year_state.missing_facts = _no_imported_slips_fact(year_state.tax_year)
        year_state.ready_to_calculate = False
        return
    if year_state.unresolved_candidates:
        year_state.missing_facts = _missing_facts_from_input(year_state.input)
        year_state.ready_to_calculate = False
        return
    missing_facts = _missing_facts_from_input(year_state.input)
    year_state.missing_facts = missing_facts
    year_state.ready_to_calculate = not missing_facts


def _no_imported_slips_fact(year: int) -> list[dict[str, str]]:
    return [
        {
            "path": "slips",
            "code": "missing_imported_slips",
            "label": f"Import or enter income slips for {year}, or explicitly confirm there are none.",
        }
    ]


def _missing_facts_from_input(data: dict[str, Any]) -> list[dict[str, str]]:
    parsed = _decimalize_slip_fields(TaxReturnInput.model_validate(data))
    if parsed.schema_version == "qc-return-v2" and parsed.tax_year in range(2020, 2025):
        missing: list[dict[str, str]] = []
        for blocker in annual_preflight(parsed):
            for path in blocker.input_paths or [""]:
                missing.append({"path": path, "code": blocker.code, "label": blocker.message})
        return missing
    return _missing_facts_from_result(_calculate_return_for_missing_facts(parsed))


def _decimalize_slip_fields(data: TaxReturnInput) -> TaxReturnInput:
    slips = []
    for slip in data.slips:
        fields = {
            box: Decimal(value) if isinstance(value, str) else value
            for box, value in slip.fields.items()
        }
        slips.append(slip.model_copy(update={"fields": fields}))
    return data.model_copy(update={"slips": slips})


def _missing_facts_from_result(result: Any) -> list[dict[str, str]]:
    if getattr(result, "status", None) != "blocked":
        return []
    missing: list[dict[str, str]] = []
    for blocker in getattr(result, "blockers", []):
        paths = blocker.input_paths or [""]
        for path in paths:
            missing.append({"path": path, "code": blocker.code, "label": blocker.message})
    return missing


def _candidate_review(candidate: ImportedSlipCandidate, reason: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "document_id": candidate.document_id,
        "slip_type": candidate.slip_type,
        "tax_year": candidate.tax_year,
        "issuer_id": candidate.issuer_id,
        "decision": candidate.decision,
        "reason": reason,
        "review_reasons": candidate.review_reasons,
        "candidate": candidate.model_dump(mode="json"),
    }


def _candidate_evidence(candidate: ImportedSlipCandidate, original: ImportedSlipCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "document_id": candidate.document_id,
        "slip_type": candidate.slip_type,
        "tax_year": candidate.tax_year,
        "issuer_id": candidate.issuer_id,
        "fields": {
            box: _evidence_field(field, original.fields.get(box))
            for box, field in candidate.fields.items()
        },
        "metadata": {
            key: _evidence_field(field, original.metadata.get(key))
            for key, field in candidate.metadata.items()
        },
    }


def _evidence_field(field: ExtractedField, original: ExtractedField | None) -> dict[str, Any]:
    if original is None:
        return {
            "value": None,
            "accepted_value": field.value,
            "method": field.method,
            "confidence": field.confidence,
            "review_required": field.review_required,
            "page": field.page,
            "bbox": field.bbox,
            "raw_text": "",
            "value_state": field.value_state,
            "correction_only": True,
        }
    return {
        **original.model_dump(mode="json"),
        "accepted_value": field.value,
        "correction_only": False,
    }


def _valid_correction_value(value: CorrectionValue) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, Decimal):
        return value.is_finite() and value >= 0
    return bool(str(value).strip())


def _field_value(value: CorrectionValue) -> str | bool:
    return value if isinstance(value, bool) else str(value)


def _value_state(value: CorrectionValue) -> str:
    return "off" if value is False else "present"


def _correction_field(key: str, value: CorrectionValue) -> ExtractedField:
    return ExtractedField(
        value=_field_value(value),
        method="user_correction",
        confidence=1.0,
        review_required=False,
        page=1,
        bbox=None,
        raw_text=f"User correction for {key}",
        value_state=_value_state(value),
    )
