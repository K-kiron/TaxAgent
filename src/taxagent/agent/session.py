"""Multi-turn tax conversation.

A real filing is a sequence of related questions: the user establishes context
once ("Québec resident, interned Jan–June, has tuition carryforward…") and then
asks a string of follow-ups. `TaxSession` gives continuity two ways:

1. `message_history` threaded through Pydantic AI so the model resolves references
   ("that question", "it") naturally across turns.
2. an accumulating, deduped **fact store** (`UserFact`s) — the spec's Fact Store /
   Evidence Tracker — injected into every turn. This keeps the salient facts
   explicit and auditable (supports the filing-rationale / audit-trail goal) even
   as raw history grows.
"""

from __future__ import annotations

from ..models import Recommendation, UserFact
from ..persistence import AsyncProfileWriter, ProfileStore, UserProfile, default_writer
from .reasoner import Reasoner

# how well-backed a fact is; a later turn should not downgrade an established fact
_EVIDENCE_RANK = {
    "missing": 0,
    "user_reported": 1,
    "document_supported": 2,
    "official_record": 3,
}


class TaxSession:
    def __init__(
        self,
        reasoner: Reasoner | None = None,
        *,
        default_tax_year: int | None = None,
        user_id: str | None = None,
        store: ProfileStore | None = None,
        writer: AsyncProfileWriter | None = None,
    ):
        self.reasoner = reasoner or Reasoner()
        self.default_tax_year = default_tax_year
        self.user_id = user_id
        self._store = store
        self._writer = writer
        self._owns_writer = False
        self._closed = False
        self.history = None  # Pydantic AI message list carried across turns
        self._facts: dict[str, UserFact] = {}
        self.transcript: list[tuple[str, Recommendation]] = []

        # Returning user: load their persistent profile so prior facts are already known.
        if user_id:
            self._store = self._store or ProfileStore()
            if self._writer is None:
                if store is not None:
                    self._writer = AsyncProfileWriter(self._store)
                    self._owns_writer = True
                else:
                    self._writer = default_writer()
            profile = self._store.load(user_id, tax_year=self.default_tax_year)
            if self.default_tax_year is None and profile.tax_year is not None:
                self.default_tax_year = profile.tax_year
            if self.default_tax_year is not None and profile.tax_year == self.default_tax_year:
                self._facts = dict(profile.facts)

    @property
    def known_facts(self) -> list[UserFact]:
        return list(self._facts.values())

    def ask(self, question: str, *, tax_year: int | None = None) -> Recommendation:
        if self._closed:
            raise RuntimeError("tax session is closed")
        effective_tax_year = tax_year or self.default_tax_year
        if self.default_tax_year is None and effective_tax_year is not None:
            self.default_tax_year = effective_tax_year
        elif tax_year is not None and self.default_tax_year is not None and tax_year != self.default_tax_year:
            raise ValueError("tax_year cannot change within one TaxSession; start a new TaxSession")

        rec, _cards, result = self.reasoner.run_turn(
            question,
            tax_year=effective_tax_year,
            known_facts=self.known_facts or None,
            message_history=self.history,
        )
        self.history = result.all_messages()
        self._merge_facts(rec.facts_used)
        self.transcript.append((question, rec))
        self._persist_async()  # non-blocking snapshot of the updated profile
        return rec

    def _merge_facts(self, facts: list[UserFact]) -> None:
        for f in facts:
            cur = self._facts.get(f.key)
            # keep the best-evidenced version of each fact key
            if cur is None or _EVIDENCE_RANK[f.evidence_status] >= _EVIDENCE_RANK[cur.evidence_status]:
                self._facts[f.key] = f

    def _persist_async(self) -> None:
        if not self.user_id or self._writer is None:
            return
        self._writer.submit(
            UserProfile(user_id=self.user_id, tax_year=self.default_tax_year, facts=self._facts)
        )

    def flush(self) -> None:
        """Block until the profile is durably written (call before exit)."""
        if self._writer is not None:
            self._writer.flush()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._writer is None:
            return
        if self._owns_writer:
            self._writer.close()
        else:
            self._writer.flush()
