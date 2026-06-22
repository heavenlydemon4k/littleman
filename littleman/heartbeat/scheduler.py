"""Heartbeat scheduler — the dumb runtime that fires due heartbeats.

It polls the heartbeat table and spawns a session for each due heartbeat. It carries no
intelligence: it does not decide when to run (the fire_at field does) or what to do (the
session's meta layer derives that from the heartbeat context). Per ADR 0001 the system is
serial by default — the scheduler awaits each session before firing the next, so capital is
always evaluated against a consistent view.
"""

from __future__ import annotations

import asyncio
import logging

from littleman.config import settings
from littleman.db.connection import AsyncSessionLocal, init_db
from littleman.heartbeat import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scheduler")


async def _tick() -> int:
    async with AsyncSessionLocal() as db:
        due = await store.get_due_heartbeats(db)

    if not due:
        return 0

    # Import here to avoid a circular import at module load.
    from littleman.agent.session import run_session

    from littleman.agent.lock import SessionLockBusy

    fired = 0
    for hb in due:
        log.info("firing heartbeat %s (%s): %s", hb.id[:8], hb.session_type, hb.reason)
        try:
            # Wait briefly for any manual/overlapping session to finish rather than failing.
            result = await run_session(heartbeat_id=hb.id, lock_timeout=60.0)
            log.info("session done: %s", result.get("summary"))
            fired += 1
        except SessionLockBusy:
            log.warning("heartbeat %s deferred — session lock busy; will retry next tick", hb.id[:8])
        except Exception:  # noqa: BLE001 — one bad session must not stop the scheduler
            log.exception("session for heartbeat %s failed", hb.id[:8])
    return fired


async def run_forever() -> None:
    await init_db()
    log.info("scheduler started; poll interval %ss", settings.heartbeat_poll_interval_seconds)
    while True:
        try:
            await _tick()
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")
        await asyncio.sleep(settings.heartbeat_poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_forever())
