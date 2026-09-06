"""Persistent user profile + asynchronous, non-blocking disk writes.

A `UserProfile` is the durable tax picture of one user (their accumulated
`UserFact`s + tax year), keyed by `user_id` plus `tax_year` when a year is known.
No-year callers still use the unsuffixed user profile path. Writes go through
`AsyncProfileWriter`: a single background thread that COALESCES bursts (only the
latest snapshot per user/year is written), writes ATOMICALLY (temp file + os.replace),
and offers a `flush()` that guarantees every submitted snapshot has reached disk —
so the conversation path never blocks on I/O and the last update is never lost.
"""

from __future__ import annotations

import atexit
import hashlib
import os
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .models import UserFact


class UserProfile(BaseModel):
    user_id: str
    tax_year: int | None = None
    facts: dict[str, UserFact] = Field(default_factory=dict)
    updated_at: str | None = None
    version: int = 1


def _default_profile_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else None
    if base:
        return Path(base) / "TaxAgent" / "profiles"
    return Path.home() / ".taxagent" / "profiles"


def _legacy_safe_id(user_id: str) -> str:
    cleaned = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in user_id)
    return cleaned or "anon"


def _safe_id(user_id: str) -> str:
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
    return f"{_legacy_safe_id(user_id)}-{digest}"


class ProfileStore:
    """Synchronous load/atomic-save of profiles to a directory."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or os.environ.get("TAXAGENT_PROFILE_DIR") or _default_profile_dir())
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path(self, user_id: str, tax_year: int | None = None) -> Path:
        suffix = f"-ty{tax_year}" if tax_year is not None else ""
        return self.base_dir / f"{_safe_id(user_id)}{suffix}.json"

    def _legacy_path(self, user_id: str, tax_year: int | None = None) -> Path:
        suffix = f"-ty{tax_year}" if tax_year is not None else ""
        return self.base_dir / f"{_legacy_safe_id(user_id)}{suffix}.json"

    def _candidate_paths(self, user_id: str, tax_year: int | None) -> list[Path]:
        candidates = [self.path(user_id, tax_year), self._legacy_path(user_id, tax_year)]
        if tax_year is not None:
            candidates.extend([self.path(user_id), self._legacy_path(user_id)])
        return candidates

    def _matches(self, profile: UserProfile, user_id: str, tax_year: int | None) -> bool:
        if profile.user_id != user_id:
            return False
        return tax_year is None or profile.tax_year == tax_year

    def load(self, user_id: str, tax_year: int | None = None) -> UserProfile:
        for p in self._candidate_paths(user_id, tax_year):
            if not p.exists():
                continue
            profile = UserProfile.model_validate_json(p.read_text(encoding="utf-8"))
            if self._matches(profile, user_id, tax_year):
                return profile
        return UserProfile(user_id=user_id, tax_year=tax_year)

    def save(self, profile: UserProfile) -> None:
        self.save_json(profile.user_id, profile.model_dump_json(indent=2), tax_year=profile.tax_year)

    def save_json(self, user_id: str, data: str, tax_year: int | None = None) -> None:
        p = self.path(user_id, tax_year)
        tmp = p.with_name(f"{p.name}.tmp.{os.getpid()}.{threading.get_ident()}")
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, p)


_SENTINEL = object()


class AsyncProfileWriter:
    """Background single-writer. Non-blocking `submit`, coalescing, atomic, with a
    `flush()` that blocks until all submitted snapshots are durably written."""

    def __init__(self, store: ProfileStore | None = None):
        self.store = store or ProfileStore()
        self._pending: dict[tuple[str, int | None], str] = {}
        self._lock = threading.Lock()
        self._q: queue.Queue = queue.Queue()
        self._error: BaseException | None = None
        self._closed = False
        self._thread = threading.Thread(
            target=self._run, name="taxagent-profile-writer", daemon=True
        )
        self._thread.start()

    def _raise_if_failed(self) -> None:
        if self._error is not None:
            raise RuntimeError("profile writer failed; the latest profile snapshot was not saved") from self._error

    def submit(self, profile: UserProfile) -> None:
        """Hand off a snapshot for writing and return immediately (off the hot path)."""
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        data = profile.model_dump_json(indent=2)  # serialize on caller thread -> writer sees an immutable snapshot
        with self._lock:
            if self._closed:
                raise RuntimeError("profile writer is closed")
            self._raise_if_failed()
            key = (profile.user_id, profile.tax_year)
            self._pending[key] = data
            self._q.put(key)

    def _run(self) -> None:
        while True:
            item = self._q.get()
            try:
                if item is _SENTINEL:
                    return
                with self._lock:
                    data = self._pending.pop(item, None)  # take latest; may be None if already coalesced
                if data is not None:
                    user_id, tax_year = item
                    try:
                        self.store.save_json(user_id, data, tax_year=tax_year)
                    except Exception as exc:  # writer must not die and leave later flushes hanging
                        self._error = exc
            finally:
                self._q.task_done()

    def flush(self) -> None:
        """Block until every submitted write has completed, then report writer failures."""
        self._q.join()
        self._raise_if_failed()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        flush_error: RuntimeError | None = None
        try:
            self.flush()
        except RuntimeError as exc:
            flush_error = exc
        self._q.put(_SENTINEL)
        self._thread.join(timeout=5)
        if flush_error is not None:
            raise flush_error


_default_writer: AsyncProfileWriter | None = None
_default_lock = threading.Lock()


def _close_default_writer(writer: AsyncProfileWriter) -> None:
    try:
        writer.close()
    except RuntimeError:
        pass


def default_writer() -> AsyncProfileWriter:
    """Process-wide writer, flushed on interpreter exit so nothing is lost."""
    global _default_writer
    with _default_lock:
        if _default_writer is None:
            _default_writer = AsyncProfileWriter()
            atexit.register(_close_default_writer, _default_writer)
    return _default_writer
