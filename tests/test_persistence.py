"""Unit tests for async profile persistence — no LLM needed."""

from taxagent.models import UserFact
from taxagent.persistence import AsyncProfileWriter, ProfileStore, UserProfile


def _profile(uid: str, **facts: str) -> UserProfile:
    return UserProfile(
        user_id=uid,
        tax_year=2025,
        facts={k: UserFact(key=k, value=v, evidence_status="user_reported") for k, v in facts.items()},
    )


def test_store_roundtrip(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(_profile("u1", province="Quebec"))
    loaded = store.load("u1")
    assert loaded.user_id == "u1"
    assert loaded.facts["province"].value == "Quebec"


def test_load_missing_returns_empty(tmp_path):
    prof = ProfileStore(tmp_path).load("nobody")
    assert prof.user_id == "nobody" and prof.facts == {}


def test_async_write_is_durable_after_flush(tmp_path):
    store = ProfileStore(tmp_path)
    writer = AsyncProfileWriter(store)
    try:
        writer.submit(_profile("u2", province="Quebec", intern="Jan-Jun"))
        writer.flush()  # must guarantee it hit disk
        assert store.path("u2").exists()
        reloaded = store.load("u2")
        assert set(reloaded.facts) == {"province", "intern"}
        assert reloaded.updated_at is not None
    finally:
        writer.close()


def test_burst_coalesces_to_last_write(tmp_path):
    store = ProfileStore(tmp_path)
    writer = AsyncProfileWriter(store)
    try:
        # rapid-fire updates for the same user; the LAST one must win, none lost
        for i in range(20):
            writer.submit(_profile("u3", counter=str(i)))
        writer.flush()
        assert store.load("u3").facts["counter"].value == "19"
        # no temp files left behind (atomic replace cleaned up)
        assert not list(tmp_path.glob("*.tmp*"))
    finally:
        writer.close()
