"""Golden scenario schema — the machine-checked source of truth for evals."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..models import Confidence


class SafetyExpectations(BaseModel):
    must_not_overclaim: bool = True
    must_not_advise_misreport: bool = True
    must_recommend_evidence_check: bool = False


class GoldenScenario(BaseModel):
    scenario_id: str
    tax_year: int
    kind: Literal["advisory", "adversarial"] = "advisory"
    user_message: str
    maps_to_rule_cards: list[str] = Field(default_factory=list)
    expected_concepts: list[str] = Field(default_factory=list)
    expected_confidence: list[Confidence] = Field(default_factory=list)
    safety: SafetyExpectations = Field(default_factory=SafetyExpectations)
    # smoke-test strings: a fast pre-filter, never the score; matched negation-aware
    smoke_include: list[str] = Field(default_factory=list)
    smoke_exclude_negation_aware: list[str] = Field(default_factory=list)
