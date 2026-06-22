# littleman

An autonomous agent for systematic prediction market trading on Polymarket. Designed to operate continuously without ongoing human direction — the user sets a budget and a goal, and the agent plans, researches, bets, monitors, and compounds results on its own schedule.

---

## What this is

Littleman is a self-directing AI agent with a specific domain: Polymarket prediction markets. It does not require a human to decide what to research, when to act, or when to check results. It determines those things itself through a planning loop that runs at the start of every active session and produces a concrete schedule of future work.

The agent's output is not text or summaries. Its output is placed bets, updated positions, a maintained portfolio, and a continuous heartbeat schedule that keeps the cycle running.

---

## Core properties

- **Self-scheduling** — the agent writes its own future activation times (heartbeats) based on market close times, research windows, and result availability. No fixed cron cadence.
- **Context-carrying wakeups** — each heartbeat stores the specific context that triggered it (which positions to check, which markets to research, what information was expected). The agent re-hydrates from this context on every wake, not from scratch.
- **Hierarchical task decomposition** — goals decompose into strategies, strategies into concrete tasks, tasks into subtasks. The agent maintains and modifies this tree throughout its operation.
- **Baked-in domain model** — knowledge of Polymarket mechanics, topic categories, resolution criteria, and edge theory is embedded in the agent's system context, not retrieved at runtime.
- **Closed observation loop** — every action is logged against its predicted outcome. Resolved bets are compared against the agent's stated probability estimate at time of bet. This data feeds back into the world model and calibrates future estimates.
- **Hard budget controls** — user-set limits on maximum position size, maximum drawdown, and total exposure are enforced by a risk governor that has veto power over all execution actions.

---

## Architecture overview

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full technical specification.

Five conceptual layers, each with distinct responsibilities:

| Layer | Responsibility |
|-------|---------------|
| Meta | World model maintenance, situation synthesis, directive generation, self-scheduling |
| Macro | Strategy planning, goal tree management, skill dispatch, risk governance |
| Task | Concrete task decomposition and sequencing |
| Execution | Web research, Polymarket API calls, knowledge base writes, observation logging |
| Domain | Embedded knowledge of Polymarket mechanics and topic ontology |

---

## Status

Pre-implementation. This repository contains architectural specification only.

Stack TBD.
