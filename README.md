# littleman

An autonomous agent for systematic prediction market trading on Polymarket. Designed to operate continuously without ongoing human direction — the user sets a budget and a goal, and the agent plans, researches, bets, monitors, and compounds results on its own schedule.

---

## What this is

Littleman is a self-directing AI agent with a specific domain: Polymarket prediction markets. It does not require a human to decide what to research, when to act, or when to check results. It determines those things itself through a planning loop that runs at the start of every active session and produces a concrete schedule of future work.

The agent's output is not text or summaries. Its output is placed bets, updated positions, a maintained portfolio, and a continuous heartbeat schedule that keeps the cycle running.

Inspired by [OpenClaw](https://github.com/openclaw/openclaw), adopting its workspace-first configuration pattern, model-agnostic provider layer, and skills architecture — and extending its static heartbeat concept into a dynamic, agent-authored scheduling system.

---

## Core properties

- **Self-scheduling** — the agent writes its own future activation times (heartbeats) based on market close times, research windows, and result availability. No fixed cron cadence.
- **Context-carrying wakeups** — each heartbeat stores the specific context that triggered it. The agent re-hydrates from this context on wake, not from scratch.
- **Hierarchical task decomposition** — goals decompose into strategies, strategies into concrete tasks, tasks into subtasks. The agent maintains and modifies this tree throughout operation.
- **Baked-in domain model** — knowledge of Polymarket mechanics, topic categories, resolution criteria, and edge theory is embedded in `workspace/SOUL.md`, not retrieved at runtime.
- **Closed observation loop** — every bet is logged with the agent's stated probability estimate. Resolved bets feed back into calibration statistics by category.
- **Hard budget controls** — user-set limits on position size, total exposure, and drawdown are enforced in code, not prompt instructions.
- **Model-agnostic** — runs on local models (Ollama) or cloud (Anthropic, OpenAI) via LiteLLM. Switch providers by changing a `.env` variable.

---

## Stack

- **Python 3.12+** with [uv](https://github.com/astral-sh/uv) for dependency management
- **LiteLLM** for LLM provider abstraction (local Ollama or cloud Claude/GPT)
- **SQLite** for all persistence (heartbeats, positions, world model, knowledge base)
- **Alembic** for schema migrations
- **httpx** for HTTP, **playwright** for JS-heavy web research

---

## Quick start

```bash
git clone ...
cd littleman
cp .env.example .env
# edit .env: add API keys, set budget, choose LLM provider
make install
make migrate
make session -- --boot   # first run; agent creates its own future heartbeats
make scheduler           # leave running; fires sessions when heartbeats are due
```

---

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full system design: all layers, the heartbeat cascade, data model, risk management, design decisions
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — project structure, stack rationale, workflow, testing conventions

---

## Status

Pre-implementation. Documentation and workspace scaffold in place. Implementation begins with the database schema and heartbeat store.
