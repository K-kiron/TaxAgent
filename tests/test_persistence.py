"""Unit tests for async profile persistence — no LLM needed."""

from contextlib import suppress
import json
import threading

import pytest

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
    loaded = store.load("u1", tax_year=2025)
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
        assert store.path("u2", 2025).exists()
        reloaded = store.load("u2", tax_year=2025)
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
        assert store.load("u3", tax_year=2025).facts["counter"].value == "19"
        # no temp files left behind (atomic replace cleaned up)
        assert not list(tmp_path.glob("*.tmp*"))
    finally:
        writer.close()


class FailingStore(ProfileStore):
    def save_json(self, user_id: str, data: str, tax_year: int | None = None) -> None:
        raise OSError("disk is unavailable")


def test_safe_profile_paths_do_not_collide(tmp_path):
    store = ProfileStore(tmp_path)
    first = _profile("a/b", province="Quebec")
    second = _profile("a?b", province="Ontario")

    store.save(first)
    store.save(second)

    assert store.path(first.user_id) != store.path(second.user_id)
    assert store.load(first.user_id, tax_year=2025).facts["province"].value == "Quebec"
    assert store.load(second.user_id, tax_year=2025).facts["province"].value == "Ontario"


def test_legacy_sanitized_profile_path_still_loads(tmp_path):
    legacy = tmp_path / "a_b.json"
    legacy.write_text(_profile("a/b", province="Quebec").model_dump_json(indent=2), encoding="utf-8")

    loaded = ProfileStore(tmp_path).load("a/b")

    assert loaded.user_id == "a/b"
    assert loaded.facts["province"].value == "Quebec"


def test_legacy_sanitized_profile_path_rejects_mismatched_user_id(tmp_path):
    legacy = tmp_path / "a_b.json"
    legacy.write_text(_profile("a/b", province="Quebec").model_dump_json(indent=2), encoding="utf-8")

    loaded = ProfileStore(tmp_path).load("a_b")

    assert loaded.user_id == "a_b"
    assert loaded.facts == {}
    assert legacy.exists()


def test_no_year_profile_api_uses_unsuffixed_path(tmp_path):
    store = ProfileStore(tmp_path)
    profile = UserProfile(
        user_id="no-year",
        tax_year=None,
        facts={"province": UserFact(key="province", value="Quebec")},
    )

    store.save(profile)

    assert store.path("no-year").exists()
    assert store.load("no-year").facts["province"].value == "Quebec"
    assert store.load("no-year", tax_year=2025).facts == {}


def test_same_user_profiles_are_isolated_by_tax_year(tmp_path):
    store = ProfileStore(tmp_path)
    store.save(_profile("same-user", province="Quebec"))
    store.save(
        UserProfile(
            user_id="same-user",
            tax_year=2024,
            facts={"province": UserFact(key="province", value="Ontario")},
        )
    )

    assert store.path("same-user", 2025) != store.path("same-user", 2024)
    assert store.load("same-user", tax_year=2025).facts["province"].value == "Quebec"
    assert store.load("same-user", tax_year=2024).facts["province"].value == "Ontario"


def test_async_same_user_different_years_do_not_coalesce_each_other(tmp_path):
    store = ProfileStore(tmp_path)
    writer = AsyncProfileWriter(store)
    try:
        writer.submit(_profile("multi-year", province="Quebec"))
        writer.submit(
            UserProfile(
                user_id="multi-year",
                tax_year=2024,
                facts={"province": UserFact(key="province", value="Ontario")},
            )
        )
        writer.flush()
    finally:
        writer.close()

    assert store.load("multi-year", tax_year=2025).facts["province"].value == "Quebec"
    assert store.load("multi-year", tax_year=2024).facts["province"].value == "Ontario"


def test_new_year_save_does_not_overwrite_legacy_hashed_profile(tmp_path):
    store = ProfileStore(tmp_path)
    legacy = store.path("legacy-user")
    before = _profile("legacy-user", province="Quebec").model_dump_json(indent=2)
    legacy.write_text(before, encoding="utf-8")

    assert store.load("legacy-user", tax_year=2025).facts["province"].value == "Quebec"
    store.save(
        UserProfile(
            user_id="legacy-user",
            tax_year=2024,
            facts={"province": UserFact(key="province", value="Ontario")},
        )
    )

    assert legacy.read_text(encoding="utf-8") == before
    assert store.load("legacy-user", tax_year=2025).facts["province"].value == "Quebec"
    assert store.load("legacy-user", tax_year=2024).facts["province"].value == "Ontario"


def test_new_year_save_does_not_overwrite_legacy_sanitized_profile(tmp_path):
    store = ProfileStore(tmp_path)
    legacy = tmp_path / "legacy_user.json"
    before = _profile("legacy/user", province="Quebec").model_dump_json(indent=2)
    legacy.write_text(before, encoding="utf-8")

    assert store.load("legacy/user", tax_year=2025).facts["province"].value == "Quebec"
    store.save(
        UserProfile(
            user_id="legacy/user",
            tax_year=2024,
            facts={"province": UserFact(key="province", value="Ontario")},
        )
    )

    assert legacy.read_text(encoding="utf-8") == before
    assert store.load("legacy/user", tax_year=2025).facts["province"].value == "Quebec"
    assert store.load("legacy/user", tax_year=2024).facts["province"].value == "Ontario"


def test_legacy_load_rejects_mismatched_tax_year(tmp_path):
    legacy = tmp_path / "year_user.json"
    legacy.write_text(_profile("year/user", province="Quebec").model_dump_json(indent=2), encoding="utf-8")

    loaded = ProfileStore(tmp_path).load("year/user", tax_year=2024)

    assert loaded.user_id == "year/user"
    assert loaded.tax_year == 2024
    assert loaded.facts == {}
    assert legacy.exists()


def test_writer_flush_reports_save_failure_without_hanging(tmp_path):
    writer = AsyncProfileWriter(FailingStore(tmp_path))
    try:
        writer.submit(_profile("u4", province="Quebec"))

        with pytest.raises(RuntimeError, match="profile writer failed"):
            writer.flush()

        with pytest.raises(RuntimeError, match="profile writer failed"):
            writer.submit(_profile("u4", province="Ontario"))
    finally:
        with suppress(RuntimeError):
            writer.close()


def test_writer_close_is_idempotent_and_rejects_late_submit(tmp_path):
    writer = AsyncProfileWriter(ProfileStore(tmp_path))

    writer.close()
    writer.close()

    with pytest.raises(RuntimeError, match="closed"):
        writer.submit(_profile("late", province="Quebec"))
    writer.flush()


def test_writer_close_does_not_lose_in_flight_submit(tmp_path):
    store = ProfileStore(tmp_path)
    writer = AsyncProfileWriter(store)
    original_put = writer._q.put
    enqueue_started = threading.Event()
    release_enqueue = threading.Event()
    submit_errors: list[BaseException] = []
    close_errors: list[BaseException] = []

    def gated_put(item):
        if item == ("race", 2025):
            enqueue_started.set()
            assert release_enqueue.wait(timeout=2)
        return original_put(item)

    def submit_profile():
        try:
            writer.submit(_profile("race", province="Quebec"))
        except BaseException as exc:  # pragma: no cover - reported below
            submit_errors.append(exc)

    def close_writer():
        try:
            writer.close()
        except BaseException as exc:  # pragma: no cover - reported below
            close_errors.append(exc)

    writer._q.put = gated_put
    submit_thread = threading.Thread(target=submit_profile)
    submit_thread.start()
    assert enqueue_started.wait(timeout=2)

    close_thread = threading.Thread(target=close_writer)
    close_thread.start()
    release_enqueue.set()

    submit_thread.join(timeout=2)
    close_thread.join(timeout=2)
    writer._q.put = original_put

    assert not submit_thread.is_alive()
    assert not close_thread.is_alive()
    assert submit_errors == []
    assert close_errors == []
    assert store.load("race", tax_year=2025).facts["province"].value == "Quebec"


def test_writer_close_surfaces_save_failure_and_stops_thread(tmp_path):
    writer = AsyncProfileWriter(FailingStore(tmp_path))
    writer.submit(_profile("u5", province="Quebec"))

    with pytest.raises(RuntimeError, match="profile writer failed"):
        writer.close()

    assert not writer._thread.is_alive()
