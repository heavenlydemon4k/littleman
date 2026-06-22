"""Cross-process session lock.

OpenClaw serializes agent runs per session and backs the in-process queue with a
process-aware, file-based write lock that "catches writers that bypass the in-process queue".
Littleman's scheduler is already serial, but the operator can run `python -m littleman once`
or `boot` while the scheduler is running, and the API could trigger work too. Without a
cross-process lock those could execute sessions concurrently and evaluate bets against the
same wallet balance — the exact double-spend ADR 0001 exists to prevent.

This lock makes the "one consistent view of capital" guarantee hold across processes. It is a
lock-file with atomic O_EXCL creation holding the owner PID and acquisition time. A stale lock
(owner process gone, or older than max_age) is taken over.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from littleman.config import settings

_LOCK_NAME = "session.lock"
_DEFAULT_MAX_AGE_SECONDS = 1800  # a session should never legitimately run this long


def _lock_path() -> Path:
    state_dir = settings.workspace_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / _LOCK_NAME


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we cannot signal it — treat as alive.
        return True
    except OSError:
        # Windows: os.kill(pid, 0) raises OSError for a dead pid in some cases.
        return False
    return True


def _read_lock(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _is_stale(info: dict, max_age: float) -> bool:
    age = time.time() - info.get("acquired_at", 0)
    if age > max_age:
        return True
    return not _pid_alive(int(info.get("pid", -1)))


def _try_acquire(path: Path, max_age: float) -> bool:
    payload = json.dumps({"pid": os.getpid(), "acquired_at": time.time()})
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            f.write(payload)
        return True
    except FileExistsError:
        info = _read_lock(path)
        if info is None or _is_stale(info, max_age):
            # Take over a stale/abandoned lock.
            try:
                path.unlink()
            except OSError:
                return False
            return _try_acquire(path, max_age)
        return False


class SessionLock:
    """Async context manager guarding session execution across processes."""

    def __init__(
        self,
        timeout: float = 0.0,
        poll_interval: float = 0.5,
        max_age: float = _DEFAULT_MAX_AGE_SECONDS,
    ):
        # timeout=0 means do not wait — fail immediately if held by a live owner.
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_age = max_age
        self.path = _lock_path()
        self._held = False

    async def __aenter__(self) -> "SessionLock":
        deadline = time.time() + self.timeout
        while True:
            if _try_acquire(self.path, self.max_age):
                self._held = True
                return self
            if time.time() >= deadline:
                raise SessionLockBusy(
                    f"another session holds {self.path}; not running concurrently"
                )
            await asyncio.sleep(self.poll_interval)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._held:
            try:
                info = _read_lock(self.path)
                if info and int(info.get("pid", -1)) == os.getpid():
                    self.path.unlink(missing_ok=True)
            except OSError:
                pass
            self._held = False


class SessionLockBusy(RuntimeError):
    """Raised when the session lock is held by another live process and timeout elapsed."""
