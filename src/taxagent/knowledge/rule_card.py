"""Rule card store: load JSON cards from the knowledge base and retrieve them.

MVP retrieval is deliberately simple (keyword + jurisdiction + tax_year filter).
The point of the abstraction is that the reasoner asks for cards *by id or topic*
and never carries unsupported tax facts in its own head — grounding is checked
against these cards (see README_HARNESS.md → Harness Evaluation).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import RuleCard

# repo_root/knowledge_base  (src/taxagent/knowledge/rule_card.py -> up 4)
DEFAULT_KB_DIR = Path(__file__).resolve().parents[3] / "knowledge_base"


class RuleCardStore:
    def __init__(self, cards: list[RuleCard]):
        self._by_id: dict[str, RuleCard] = {c.id: c for c in cards}

    @property
    def cards(self) -> list[RuleCard]:
        return list(self._by_id.values())

    def get(self, card_id: str) -> RuleCard | None:
        return self._by_id.get(card_id)

    def get_many(self, ids: list[str]) -> list[RuleCard]:
        return [c for cid in ids if (c := self._by_id.get(cid)) is not None]

    def retrieve(
        self,
        query: str,
        *,
        jurisdiction: str | None = None,
        tax_year: int | None = None,
        limit: int = 3,
    ) -> list[RuleCard]:
        """Naive keyword overlap over topic + rule_summary, with optional filters."""
        terms = {t for t in _tokenize(query) if len(t) > 2}
        scored: list[tuple[int, RuleCard]] = []
        for card in self._by_id.values():
            if jurisdiction and card.jurisdiction != jurisdiction:
                continue
            if tax_year and card.tax_year and card.tax_year != tax_year:
                continue
            hay = _tokenize(f"{card.topic} {card.rule_summary} {' '.join(card.required_facts)}")
            score = sum(1 for t in terms if t in hay)
            if score:
                scored.append((score, card))
        scored.sort(key=lambda s: s[0], reverse=True)
        return [c for _, c in scored[:limit]]


def _tokenize(text: str) -> set[str]:
    return {w.strip(".,:;()") for w in text.lower().split()}


def load_default_store(kb_dir: Path | str = DEFAULT_KB_DIR) -> RuleCardStore:
    kb_dir = Path(kb_dir)
    cards: list[RuleCard] = []
    for path in sorted(kb_dir.rglob("*.json")):
        cards.append(RuleCard.model_validate_json(path.read_text()))
    if not cards:
        raise FileNotFoundError(f"no rule cards found under {kb_dir}")
    return RuleCardStore(cards)
