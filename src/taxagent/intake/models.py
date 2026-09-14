"""Public PDF intake result contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt


class IntakeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ExtractionMethod = Literal["digital_text", "acroform", "ocr_rapidocr", "user_correction"]
ExtractedValueState = Literal["present", "blank", "off"]
DocumentStatus = Literal[
    "processed",
    "duplicate",
    "encrypted",
    "malformed",
    "too_large",
    "too_many_pages",
    "too_many_files",
    "resource_limited",
    "unsupported",
]
CandidateDecision = Literal["accepted_auto", "needs_review", "rejected", "duplicate"]
AmendedStatus = Literal["original", "amended", "unknown"]


class ExtractedField(IntakeModel):
    value: str | StrictBool
    method: ExtractionMethod
    confidence: StrictFloat = Field(ge=0.0, le=1.0)
    review_required: StrictBool
    page: StrictInt = Field(ge=1)
    bbox: tuple[float, float, float, float] | None = None
    raw_text: str
    value_state: ExtractedValueState = "present"


class ImportedDocument(IntakeModel):
    document_id: str
    filename: str
    sha256: str
    status: DocumentStatus
    page_count: StrictInt = Field(ge=0)
    message: str | None = None


class ImportedSlipCandidate(IntakeModel):
    candidate_id: str
    document_id: str
    slip_type: str | None
    tax_year: StrictInt | None
    issuer_id: str | None
    contribution_period: str | None = None
    amended_status: AmendedStatus = "unknown"
    decision: CandidateDecision
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    metadata: dict[str, ExtractedField] = Field(default_factory=dict)
    review_reasons: list[str] = Field(default_factory=list)


class PdfImportBatchResult(IntakeModel):
    documents: list[ImportedDocument] = Field(default_factory=list)
    candidates: list[ImportedSlipCandidate] = Field(default_factory=list)
