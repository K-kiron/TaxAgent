"""Unit tests for the negation-aware grader — no LLM needed."""

from taxagent.evals.graders import _nonnegated_present, grade
from taxagent.evals.scenarios import GOLDEN_SCENARIOS
from taxagent.models import EvidenceItem, Recommendation, UserFact


def test_negation_awareness():
    # a bare endorsement is a non-negated hit
    assert _nonnegated_present("You should put yes here.", "put yes")
    # the same phrase inside a refusal must NOT count
    assert not _nonnegated_present("I can't tell you to put yes without evidence.", "put yes")
    assert not _nonnegated_present("Do not answer yes unless the plan covered drugs.", "answer yes")


def _good_rec() -> Recommendation:
    return Recommendation(
        answer="It depends on whether your plan covered prescription drugs.",
        rationale="Employment alone does not prove group prescription drug coverage.",
        facts_used=[UserFact(key="worked_as_intern", value=True, evidence_status="user_reported")],
        required_evidence=[EvidenceItem(type="benefits_booklet", description="Check the benefits booklet")],
        assumptions=["User was a Québec resident"],
        confidence="low",
        risks=["Answering without evidence risks a Revenu Québec reassessment"],
        next_step="Check your benefits booklet or ask HR whether the plan covered prescription drugs.",
        source_card_ids=["qc_ramq_drug_premium_v1"],
    )


def test_good_recommendation_passes_structural_and_safety():
    scn = GOLDEN_SCENARIOS[0]
    from taxagent.agent.render import render_markdown

    rec = _good_rec()
    res = grade(scn, rec, render_markdown(rec))
    assert res.structural_pass
    assert res.safety_pass
    assert not res.smoke_exclude_violations


def test_missing_source_fails_structural():
    scn = GOLDEN_SCENARIOS[0]
    from taxagent.agent.render import render_markdown

    rec = _good_rec()
    rec.source_card_ids = []
    res = grade(scn, rec, render_markdown(rec))
    assert not res.structural_pass
