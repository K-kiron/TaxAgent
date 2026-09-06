"""Rule card store: load JSON cards from the packaged knowledge base and retrieve them.

MVP retrieval is deliberately simple (keyword + jurisdiction + tax_year filter).
The point of the abstraction is that the reasoner asks for cards *by id or topic*
and never carries unsupported tax facts in its own head — grounding is checked
against these cards (see README_HARNESS.md → Harness Evaluation).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from ..models import RuleCard

PACKAGE_KB_DIR = resources.files("taxagent").joinpath("data", "knowledge_base")


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


def _sort_key(path: Any) -> str:
    return str(path).replace("\\", "/")


def _iter_package_json_files(root) -> list:
    found = []

    def visit(node) -> None:
        if node.is_file() and node.name.endswith(".json"):
            found.append(node)
            return
        if node.is_dir():
            for child in node.iterdir():
                visit(child)

    if root.is_dir():
        visit(root)
    return sorted(found, key=_sort_key)


def _iter_card_paths(kb_dir) -> list:
    if isinstance(kb_dir, str):
        kb_dir = Path(kb_dir)
    if isinstance(kb_dir, Path):
        return sorted(kb_dir.rglob("*.json"))
    return _iter_package_json_files(kb_dir)


def _read_card_text(path) -> str:
    return path.read_text(encoding="utf-8")


def load_default_store(kb_dir=None) -> RuleCardStore:
    kb_root = PACKAGE_KB_DIR if kb_dir is None else kb_dir
    cards: list[RuleCard] = []
    for path in _iter_card_paths(kb_root):
        cards.append(RuleCard.model_validate_json(_read_card_text(path)))
    if not cards:
        raise FileNotFoundError(f"no rule cards found under {kb_root}")
    return RuleCardStore(cards)
