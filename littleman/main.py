"""Littleman entrypoint.

`python -m littleman` runs the heartbeat scheduler (the autonomous agent runtime). The chat
UI / API is run separately via `uvicorn littleman.api.app:app` (or `make api`).

Subcommands:
    python -m littleman scheduler   # run the autonomous scheduler (default)
    python -m littleman boot        # force First Light, schedule the first heartbeat, exit
    python -m littleman once        # run a single session immediately (no heartbeat)
"""

from __future__ import annotations

import asyncio
import sys

from littleman.db.connection import init_db


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scheduler"

    if cmd == "scheduler":
        from littleman.heartbeat.scheduler import run_forever

        asyncio.run(run_forever())

    elif cmd == "boot":
        from littleman.agent.session import run_session

        async def _boot() -> None:
            await init_db()
            print(await run_session(boot=True))

        asyncio.run(_boot())

    elif cmd == "once":
        from littleman.agent.session import run_session

        async def _once() -> None:
            await init_db()
            print(await run_session())

        asyncio.run(_once())

    else:
        print(f"Unknown command: {cmd!r}. Use scheduler | boot | once.")
        sys.exit(1)


if __name__ == "__main__":
    main()
