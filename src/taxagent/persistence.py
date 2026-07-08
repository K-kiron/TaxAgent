"""Persistent user profile + asynchronous, non-blocking disk writes.

A `UserProfile` is the durable tax picture of one user (their accumulated
`UserFact`s + tax year), keyed by `user_id`, one JSON file each. Writes go through
`AsyncProfileWriter`: a single background thread that COALESCES bursts (only the
latest snapshot per user is written), writes ATOMICALLY (temp file + os.replace),
and offers a `flush()` that guarantees every submitted snapshot has reached disk —
so the conversation path never blocks on I/O and the last update is never lost.
"""

from __future__ import annotations

import atexit
import os
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .config import settings as default_settings
from .models import UserFact


class UserProfile(BaseModel):
    user_id: str
    tax_year: int | None = None
    facts: dict[str, UserFact] = Field(default_factory=dict)
    updated_at: str | None = None
    version: int = 1


def _safe_id(user_id: str) -> str:
    cleaned = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in user_id)
    return cleaned or "anon"


class ProfileStore:
    """Synchronous load/atomic-save of profiles to a directory."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or default_settings.profile_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path(self, user_id: str) -> Path:
        return self.base_dir / f"{_safe_id(user_id)}.json"

    def load(self, user_id: str) -> UserProfile:
        p = self.path(user_id)
        if p.exists():
            return UserProfile.model_validate_json(p.read_text())
        return UserProfile(user_id=user_id)

    def save(self, profile: UserProfile) -> None:
        self.save_json(profile.user_id, profile.model_dump_json(indent=2))

    def save_json(self, user_id: str, data: str) -> None:
        p = self.path(user_id)
        tmp = p.with_name(f"{p.name}.tmp.{os.getpid()}.{threading.get_ident()}")
        tmp.write_text(data)
        os.replace(tmp, p)  # atomic on POSIX — readers never see a half-written file


_SENTINEL = object()


class AsyncProfileWriter:
    """Background single-writer. Non-blocking `submit`, coalescing, atomic, with a
    `flush()` that blocks until all submitted snapshots are durably written."""

    def __init__(self, store: ProfileStore | None = None):
        self.store = store or ProfileStore()
        self._pending: dict[str, str] = {}
        self._lock = threading.Lock()
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(
            target=self._run, name="taxagent-profile-writer", daemon=True
        )
        self._thread.start()

    def submit(self, profile: UserProfile) -> None:
        """Hand off a snapshot for writing and return immediately (off the hot path)."""
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        data = profile.model_dump_json(indent=2)  # serialize on caller thread -> writer sees an immutable snapshot
        with self._lock:
            self._pending[profile.user_id] = data
        self._q.put(profile.user_id)

    def _run(self) -> None:
        while True:
            item = self._q.get()
            try:
                if item is _SENTINEL:
                    return
                with self._lock:
                    data = self._pending.pop(item, None)  # take latest; may be None if already coalesced
                if data is not None:
                    self.store.save_json(item, data)
            finally:
                self._q.task_done()

    def flush(self) -> None:
        """Block until every submitted write has completed."""
        self._q.join()

    def close(self) -> None:
        self.flush()
        self._q.put(_SENTINEL)
        self._thread.join(timeout=5)


_default_writer: AsyncProfileWriter | None = None
_default_lock = threading.Lock()


def default_writer() -> AsyncProfileWriter:
    """Process-wide writer, flushed on interpreter exit so nothing is lost."""
    global _default_writer
    with _default_lock:
        if _default_writer is None:
            _default_writer = AsyncProfileWriter()
            atexit.register(_default_writer.close)
    return _default_writer
