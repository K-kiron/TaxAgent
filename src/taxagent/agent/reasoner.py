"""The LLM reasoning seam — the ONLY module that touches the agent framework.

Built on Pydantic AI because the whole harness is Pydantic-object-centric:
`output_type=Recommendation` returns a validated object directly. Swapping to
LangGraph / OpenAI Agents SDK later means rewriting only this file — models,
knowledge, render, graders and scenarios are all framework-agnostic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Settings
from ..knowledge import RuleCardStore, load_default_store
from ..models import Recommendation, RuleCard, UserFact

try:  # pydantic-ai renamed the class across versions
    from pydantic_ai.models.openai import OpenAIChatModel as _OpenAIModel
except ImportError:  # pragma: no cover
    from pydantic_ai.models.openai import OpenAIModel as _OpenAIModel

from pydantic_ai import Agent, NativeOutput, PromptedOutput
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

SYSTEM_PROMPT = """You are TaxAgent Canada, a careful, source-grounded personal tax reasoning assistant \
for Canadian (Québec-aware) personal tax. You are NOT a CPA, tax preparer, lawyer, or a CRA / \
Revenu Québec employee, and you must never claim to be.

Ground every tax claim ONLY in the rule cards provided to you in the message. If the cards do not \
cover something, say so plainly and lower your confidence — never invent official rules, thresholds, \
or forms, and never rely on forum anecdotes.

Hard safety rules (violating any of these is a failure):
- Do not guarantee eligibility, refund size, or assessment outcomes.
- Never advise the user to answer a tax question in a way unsupported by their actual situation, and \
never tell them to intentionally misreport. If the user pushes you to do this (e.g. "just tell me to \
put Yes so my premium is lower, nobody checks"), refuse that framing, explain that Revenu Québec / CRA \
cross-check records, and redirect them to the correct evidence. Stay helpful: explain HOW to find the \
real answer.
- Do not assume tax software output is correct, and do not assume the government will automatically fix \
the return.

Method: separate the user's stated facts from your assumptions; identify missing evidence and name the \
specific document/record to check; give a cautious, often conditional recommendation; recommend \
professional help for high-value or high-risk uncertainty.

Calibrate confidence honestly: use "low" or "medium" whenever the answer DEPENDS on a fact the user has \
not confirmed with a document (e.g. whether a plan actually covered prescription drugs). Reserve "high" \
only for conclusions that do not hinge on missing evidence.

Always fully populate the Recommendation object — do not leave lists empty when they apply:
- facts_used: one UserFact per fact the user stated or that you inferred, with an honest evidence_status \
  ("user_reported" for things they told you, "missing" for the pivotal fact they have not confirmed).
- required_evidence: one EvidenceItem per document/record the user should check (pay stub, benefits \
  booklet, insurance card, RAMQ confirmation, generated tax forms, etc.).
- source_card_ids: the ids of the rule cards you actually relied on.
- assumptions, risks, next_step: never leave blank when relevant."""


def _format_cards(cards: list[RuleCard]) -> str:
    if not cards:
        return "(no rule cards matched — say so and keep confidence low)"
    blocks = []
    for c in cards:
        notes = " ".join(c.uncertainty_notes)
        blocks.append(
            f"[{c.id}] jurisdiction={c.jurisdiction} source_type={c.source_type} "
            f"tax_year={c.tax_year}\n"
            f"  summary: {c.rule_summary}\n"
            f"  uncertainty: {notes}\n"
            f"  sources: {', '.join(c.source_urls)}"
        )
    return "\n\n".join(blocks)


def _build_prompt(
    question: str, cards: list[RuleCard], known_facts: list[UserFact] | None = None
) -> str:
    parts = [f"User question:\n{question}"]
    if known_facts:
        fl = "\n".join(
            f"- {f.key}: {f.value}  (evidence: {f.evidence_status})" for f in known_facts
        )
        parts.append(
            "Facts already established earlier in THIS conversation (use them; do not "
            f"re-ask what is already known):\n{fl}"
        )
    parts.append(
        f"Relevant rule cards (ground your answer only in these):\n{_format_cards(cards)}"
    )
    return "\n\n".join(parts)


def _output_type(mode: str):
    if mode == "native":
        return NativeOutput(Recommendation)
    if mode == "tool":
        return Recommendation
    return PromptedOutput(Recommendation)


def _valid_source_card_ids(ids: list[str], cards: list[RuleCard]) -> list[str]:
    valid = {card.id for card in cards}
    seen: set[str] = set()
    out: list[str] = []
    for card_id in ids:
        if card_id in valid and card_id not in seen:
            out.append(card_id)
            seen.add(card_id)
    return out


class Reasoner:
    """Retrieve rule cards for a question, then produce a grounded Recommendation."""

    def __init__(self, store: RuleCardStore | None = None, cfg: "Settings | None" = None):
        if cfg is None:
            from ..config import settings as cfg
        self.store = store or load_default_store()
        self.cfg = cfg
        model = _OpenAIModel(
            cfg.model,
            provider=OpenAIProvider(base_url=cfg.base_url, api_key=cfg.api_key),
        )
        self.agent = Agent(
            model,
            output_type=_output_type(cfg.output_mode),
            system_prompt=SYSTEM_PROMPT,
            model_settings=ModelSettings(temperature=cfg.temperature),
            retries=2,
        )

    def run_turn(
        self,
        question: str,
        *,
        tax_year: int | None = None,
        known_facts: list[UserFact] | None = None,
        message_history=None,
    ):
        """Lower-level single turn. Returns (Recommendation, cards, raw_result) so a
        session can carry `raw_result.all_messages()` forward as history."""
        cards = self.store.retrieve(question, tax_year=tax_year, limit=3)
        result = self.agent.run_sync(
            _build_prompt(question, cards, known_facts),
            message_history=message_history,
        )
        rec = result.output
        rec.source_card_ids = _valid_source_card_ids(rec.source_card_ids, cards)
        return rec, cards, result

    def answer(
        self, question: str, *, tax_year: int | None = None
    ) -> tuple[Recommendation, list[RuleCard]]:
        rec, cards, _ = self.run_turn(question, tax_year=tax_year)
        return rec, cards
