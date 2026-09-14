"""Core data models — the single source of truth for the harness.

Every tax-relevant answer is a `Recommendation` object; the markdown the user
sees is *rendered from* it (see agent/render.py), and the harness validates the
object, never free-form prose (see README_HARNESS.md).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["low", "medium", "high"]


class UserFact(BaseModel):
    """A single fact extracted from the user. `evidence_status` says how well the
    *fact* is backed — distinct from `EvidenceItem.status` (a document's lifecycle)."""

    key: str
    value: str | int | float | bool | None = None
    source: str = "user_statement"
    confidence: Confidence = "low"
    evidence_status: Literal[
        "missing", "user_reported", "document_supported", "official_record"
    ] = "user_reported"
    notes: str | None = None


class EvidenceItem(BaseModel):
    """A document/record the user should check. `status` is the request lifecycle."""

    type: Literal[
        "tax_slip",
        "pay_stub",
        "insurance_card",
        "benefits_booklet",
        "government_notice",
        "software_screenshot",
        "user_statement",
        "other",
    ]
    description: str
    status: Literal["not_requested", "requested", "provided", "insufficient"] = "not_requested"


class RuleCard(BaseModel):
    """Source-grounded tax rule. `jurisdiction` = the tax authority;
    `source_type` = where the card's authority comes from (software is a
    source_type, not a jurisdiction)."""

    id: str
    jurisdiction: Literal["canada_federal", "quebec", "ramq"]
    source_type: Literal["government", "official_guide", "tax_software", "professional"]
    topic: str
    tax_year: int | None = None
    rule_summary: str
    source_urls: list[str] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    last_verified: date | None = None


class Recommendation(BaseModel):
    """The eight-part answer contract, as structured data. Fields map 1:1 to the
    rendered markdown sections in agent/render.py."""

    answer: str  # 1. Direct answer
    rationale: str  # 2. Explanation of the tax concept
    # advisory contract: always name the facts relied on and the evidence to check;
    # min_length=1 becomes minItems in the JSON schema so guided decoding enforces it.
    facts_used: list[UserFact] = Field(min_length=1)  # 3.
    required_evidence: list[EvidenceItem] = Field(min_length=1)  # 4.
    assumptions: list[str] = Field(default_factory=list)  # 5. (answer + assumptions)
    confidence: Confidence  # 6.
    risks: list[str] = Field(default_factory=list)  # 7.
    next_step: str  # 8. Suggested next step
    source_card_ids: list[str] = Field(default_factory=list)  # grounding
    professional_help_recommended: bool = False
