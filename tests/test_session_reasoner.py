from __future__ import annotations

import pytest

from taxagent.agent.reasoner import Reasoner
from taxagent.agent.session import TaxSession
from taxagent.models import EvidenceItem, Recommendation, RuleCard, UserFact
from taxagent.persistence import AsyncProfileWriter, ProfileStore, UserProfile


def _rec(*, source_card_ids: list[str] | None = None) -> Recommendation:
    return Recommendation(
        answer="Answer",
        rationale="Rationale",
        facts_used=[UserFact(key="province", value="Quebec", evidence_status="user_reported")],
        required_evidence=[EvidenceItem(type="user_statement", description="Confirm province")],
        assumptions=[],
        confidence="low",
        risks=[],
        next_step="Check the facts.",
        source_card_ids=source_card_ids or [],
    )


class FakeResult:
    def __init__(self, output: Recommendation):
        self.output = output

    def all_messages(self):
        return ["history"]


class FakeReasoner:
    def __init__(self):
        self.calls = []

    def run_turn(self, question, *, tax_year=None, known_facts=None, message_history=None):
        self.calls.append((question, tax_year, known_facts, message_history))
        return _rec(), [], FakeResult(_rec())


def test_session_uses_custom_store_for_implicit_writer(tmp_path):
    store = ProfileStore(tmp_path)
    reasoner = FakeReasoner()
    session = TaxSession(reasoner=reasoner, default_tax_year=2025, user_id="same/store", store=store)
    try:
        session.ask("remember my province")
        session.flush()
    finally:
        session.close()

    assert store.path("same/store", 2025).exists()
    assert store.load("same/store", tax_year=2025).facts["province"].value == "Quebec"


def test_session_does_not_load_facts_from_another_tax_year(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(
        UserProfile(
            user_id="u-year",
            tax_year=2024,
            facts={
                "province": UserFact(key="province", value="Quebec", evidence_status="user_reported")
            },
        )
    )
    writer = AsyncProfileWriter(store)
    try:
        session = TaxSession(
            reasoner=FakeReasoner(),
            default_tax_year=2025,
            user_id="u-year",
            store=store,
            writer=writer,
        )
        assert session.known_facts == []
    finally:
        writer.close()


def test_session_does_not_load_unknown_year_profile_into_explicit_year(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(
        UserProfile(
            user_id="u-unknown-year",
            tax_year=None,
            facts={
                "province": UserFact(key="province", value="Quebec", evidence_status="user_reported")
            },
        )
    )
    writer = AsyncProfileWriter(store)
    try:
        session = TaxSession(
            reasoner=FakeReasoner(),
            default_tax_year=2025,
            user_id="u-unknown-year",
            store=store,
            writer=writer,
        )
        assert session.known_facts == []
    finally:
        writer.close()


def test_session_does_not_carry_unknown_year_profile_into_first_explicit_year(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(
        UserProfile(
            user_id="u-later-year",
            tax_year=None,
            facts={
                "province": UserFact(key="province", value="Quebec", evidence_status="user_reported")
            },
        )
    )
    writer = AsyncProfileWriter(store)
    try:
        reasoner = FakeReasoner()
        session = TaxSession(
            reasoner=reasoner,
            user_id="u-later-year",
            store=store,
            writer=writer,
        )
        assert session.known_facts == []

        session.ask("now use 2025", tax_year=2025)

        assert reasoner.calls[0][2] is None
    finally:
        writer.close()


def test_session_closes_writer_it_created_for_custom_store(tmp_path):
    store = ProfileStore(tmp_path)
    session = TaxSession(
        reasoner=FakeReasoner(),
        default_tax_year=2025,
        user_id="owned-writer",
        store=store,
    )
    writer = session._writer

    session.close()

    assert writer is not None
    with pytest.raises(RuntimeError, match="closed"):
        writer.submit(UserProfile(user_id="owned-writer", tax_year=2025))


def test_session_ask_after_close_fails_before_reasoner_call(tmp_path):
    store = ProfileStore(tmp_path)
    reasoner = FakeReasoner()
    session = TaxSession(
        reasoner=reasoner,
        default_tax_year=2025,
        user_id="closed-session",
        store=store,
    )
    session.close()

    with pytest.raises(RuntimeError, match="closed"):
        session.ask("do not call reasoner", tax_year=2025)

    assert reasoner.calls == []


def test_session_saves_new_tax_year_without_overwriting_existing_year(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(
        UserProfile(
            user_id="session-year",
            tax_year=2025,
            facts={"province": UserFact(key="province", value="Quebec")},
        )
    )
    old_path = store.path("session-year", 2025)
    old_text = old_path.read_text(encoding="utf-8")

    session = TaxSession(
        reasoner=FakeReasoner(),
        default_tax_year=2024,
        user_id="session-year",
        store=store,
    )
    try:
        session.ask("remember 2024")
        session.flush()
    finally:
        session.close()

    assert old_path.read_text(encoding="utf-8") == old_text
    assert store.load("session-year", tax_year=2025).facts["province"].value == "Quebec"
    assert store.load("session-year", tax_year=2024).facts["province"].value == "Quebec"


def test_session_rejects_tax_year_switch_to_avoid_history_leakage():
    session = TaxSession(reasoner=FakeReasoner(), default_tax_year=2025)
    session.ask("first", tax_year=2025)

    with pytest.raises(ValueError, match="start a new TaxSession"):
        session.ask("different year", tax_year=2024)


class FakeStore:
    def retrieve(self, question, *, tax_year=None, limit=3):
        return [
            RuleCard(
                id="valid_card",
                jurisdiction="quebec",
                source_type="government",
                topic="topic",
                tax_year=2025,
                rule_summary="summary",
            )
        ]


class FakeAgent:
    def __init__(self, output: Recommendation):
        self._output = output

    def run_sync(self, prompt, *, message_history=None):
        return FakeResult(self._output)


def _reasoner_with_output(output: Recommendation) -> Reasoner:
    reasoner = Reasoner.__new__(Reasoner)
    reasoner.store = FakeStore()
    reasoner.agent = FakeAgent(output)
    return reasoner


def test_reasoner_does_not_auto_promote_missing_citations():
    rec, cards, _ = _reasoner_with_output(_rec(source_card_ids=[])).run_turn("question", tax_year=2025)

    assert [card.id for card in cards] == ["valid_card"]
    assert rec.source_card_ids == []


def test_reasoner_drops_citation_ids_that_were_not_retrieved():
    rec, _cards, _ = _reasoner_with_output(
        _rec(source_card_ids=["made_up", "valid_card", "valid_card"])
    ).run_turn("question", tax_year=2025)

    assert rec.source_card_ids == ["valid_card"]
