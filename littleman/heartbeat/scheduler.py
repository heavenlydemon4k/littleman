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
from datetime import datetime, timezone

from littleman.config import settings
from littleman.db.connection import AsyncSessionLocal, init_db
from littleman.heartbeat import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scheduler")


async def _cleanup_stale(timeout_minutes: int) -> None:
    """Detect heartbeats stuck in RUNNING and mark them FAILED so they can be retried.

    This handles the case where a session crashed without cleaning up after itself (process
    killed, OOM, machine reboot). Without this check, those heartbeats stay RUNNING forever
    and the agent goes silent. Adopted from OpenClaw's stale-run detection pattern.
    """
    async with AsyncSessionLocal() as db:
        stale = await store.get_stale_running_heartbeats(db, timeout_minutes)
        for hb in stale:
            elapsed = (datetime.now(timezone.utc) - hb.started_at).total_seconds() / 60
            log.warning(
                "heartbeat %s has been RUNNING for %.0f min — marking FAILED and scheduling retry",
                hb.id[:8], elapsed,
            )
            reason = f"session timed out after {elapsed:.0f} min (stale — process likely crashed)"
            await store.mark_failed(db, hb.id, reason)
            retry = await store.schedule_retry(db, hb, reason)
            if retry:
                log.info("retry scheduled at %s", retry.fire_at.isoformat())
            else:
                log.error("heartbeat %s: max retries exhausted after stale cleanup", hb.id[:8])


async def _tick(force: bool = False) -> int:
    """Fire due heartbeats. The background loop passes force=False so it only fires when
    autonomous mode is on; manual triggers (UI 'Fire due') pass force=True."""
    from littleman.llm import runtime

    if not force and not runtime.is_autonomous():
        return 0

    # Recover any heartbeats whose sessions crashed without marking themselves done.
    if settings.stale_session_timeout_minutes > 0:
        await _cleanup_stale(settings.stale_session_timeout_minutes)

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
    from littleman.llm import runtime

    await init_db()
    log.info(
        "scheduler started; poll %ss; autonomous=%s (heartbeats fire only when autonomous=on)",
        settings.heartbeat_poll_interval_seconds,
        runtime.is_autonomous(),
    )

    # Catch up any heartbeats that fired while the process was down.
    # force=True bypasses the autonomous check — if a heartbeat was scheduled it must fire.
    missed = await _tick(force=True)
    if missed:
        log.info("startup catchup: executed %d missed heartbeat(s)", missed)

    while True:
        try:
            await _tick()
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")
        await asyncio.sleep(settings.heartbeat_poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_forever())
