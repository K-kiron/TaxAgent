"""Render a `Recommendation` object into the eight-part markdown contract.

The assistant never hand-writes this markdown — it is produced here from the
structured object, so the two can never drift (README_HARNESS.md → Agent
Response Contract).
"""

from __future__ import annotations

from ..models import Recommendation


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items) if items else "- (none)"


def render_markdown(rec: Recommendation) -> str:
    facts = (
        "\n".join(
            f"- **{f.key}**: {f.value}  _(evidence: {f.evidence_status}, confidence: {f.confidence})_"
            for f in rec.facts_used
        )
        or "- (none recorded)"
    )
    evidence = (
        "\n".join(f"- {e.description}  _({e.type}, {e.status})_" for e in rec.required_evidence)
        or "- (none)"
    )
    sources = ", ".join(rec.source_card_ids) if rec.source_card_ids else "(none)"
    prof = "\n\n> ⚠️ Consider consulting a tax professional." if rec.professional_help_recommended else ""

    return f"""## Direct Answer

{rec.answer}

## Reasoning

{rec.rationale}

## Facts I Used

{facts}

## Evidence to Check

{evidence}

## Recommendation

{rec.answer}

Assumptions:
{_bullets(rec.assumptions)}

## Confidence

**{rec.confidence}**

## Risks

{_bullets(rec.risks)}

## Suggested Next Step

{rec.next_step}

---
_Sources: {sources}. This is educational information, not certified tax advice._{prof}
"""
