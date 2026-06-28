# Littleman — Development Guide

This document covers the project's structure, tooling choices, conventions, and development workflow. It is the reference for how this project is built and maintained.

---

## Table of Contents

1. [Project Philosophy](#1-project-philosophy)
2. [Stack Choices](#2-stack-choices)
3. [Repository Layout](#3-repository-layout)
4. [Workspace Files](#4-workspace-files)
5. [Configuration and Environment](#5-configuration-and-environment)
6. [Database](#6-database)
7. [Dependency Management](#7-dependency-management)
8. [Development Workflow](#8-development-workflow)
9. [Testing](#9-testing)
10. [Running the Agent](#10-running-the-agent)

---

## 1. Project Philosophy

This is a solo project. The decisions below are calibrated for that reality.

**Don't add structure before it earns its place.** A flat package layout, a single database file, and a Makefile cover the needs of this project in its early phases. Microservices, message queues, containerisation, and deployment pipelines are options available later when the code actually requires them — not defaults imposed at the start.

**Prefer boring tools.** Python, SQLite, LiteLLM, a shell script, a `.env` file. These are well-understood, well-documented, and survivable by a single developer. Novelty has a maintenance cost; pay that cost only when the boring alternative genuinely can't do the job.

**The agent is the complex part.** The infrastructure that runs it should be as simple as possible. A scheduler that polls a table every 30 seconds is simpler, more debuggable, and more maintainable than a distributed job queue, and it is fully adequate for one agent running on one machine.

**Defer decisions that don't need to be made yet.** The stack choices below are correct for a single user. If the scope changes, revisit them. Don't engineer for a scale that may never arrive.

---

## 2. Stack Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Language | Python 3.11+ | LLM SDKs, web scraping, data handling. No good reason to use anything else for this domain. |
| LLM provider abstraction | [LiteLLM](https://github.com/BerriAI/litellm) | Single `completion()` call covers Anthropic, OpenAI, Ollama, and 100+ others. No lock-in. |
| Local LLM runtime | [Ollama](https://ollama.ai) | Standard, well-maintained, works offline. Pull a model, run a server, done. |
| Database | SQLite (via `aiosqlite` + SQLAlchemy ORM) | Single file, zero config, sufficient for one agent, trivially backed up. WAL mode for concurrent reader/writer access. |
| Migrations | None yet (schema created on startup) | The SQLite schema is created by `init_db()` from SQLAlchemy models. Alembic can be introduced when the schema stabilises and production upgrades are needed. |
| HTTP client | [httpx](https://www.python-httpx.org) | Async-native, clean API, supports both sync and async use. Standard for modern Python. |
| API server | [FastAPI](https://fastapi.tiangolo.com) | Async-native, WebSocket support, automatic OpenAPI docs. Serves both the REST API and the WebSocket chat endpoint. |
| Frontend | React + TypeScript + Vite + Tailwind CSS | Local dashboard for chat, agent observability, workspace file editing, and settings. Served via FastAPI in production, Vite dev server during development. |
| Web scraping | [playwright](https://playwright.dev/python/) | Handles JS-heavy pages. Used only by the web researcher skill; not a core dependency. |
| Settings | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Reads from `.env` and environment variables with type validation. Single `Settings` object imported where needed. |
| Dependency management | [uv](https://github.com/astral-sh/uv) | Fast, replaces pip + virtualenv + pip-tools in one tool. `uv sync` sets up the environment. |
| Task runner | `Makefile` | Simple, universal, no dependencies. Wraps common commands so you don't need to remember flags. |
| Vector search (KB) | SQLite FTS5 | Built into SQLite. Adequate for full-text search over the knowledge base. Add a proper vector store (pgvector, Chroma) only if semantic similarity search proves necessary. |

---

## 3. Repository Layout

```
littleman/
│
├── littleman/                  # main Python package
│   ├── __init__.py
│   ├── main.py                 # entrypoint: starts FastAPI + scheduler together
│   ├── __main__.py             # `python -m littleman` shim
│   ├── config.py               # Settings (pydantic-settings), loaded once
│   │
│   ├── agent/                  # session orchestration
│   │   ├── __init__.py
│   │   ├── lock.py             # cross-process SessionLock (O_EXCL file lock; ADR 0001)
│   │   ├── mainlog.py          # narrates agent sessions into the Main chat session
│   │   ├── session.py          # runs one full heartbeat session end-to-end
│   │   └── loop.py             # ReAct reasoning loop (reason → act → observe → repeat)
│   │
│   ├── api/                    # FastAPI application
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI app, CORS, static file serving
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── agent.py        # /api/agent/* — status, sessions, construct, controls
│   │       ├── chat.py         # /api/chat/* — sessions, messages, WebSocket streaming
│   │       ├── settings.py     # /api/settings/* — LLM config, runtime overrides
│   │       └── workspace.py    # /api/workspace/* — construct file CRUD
│   │
│   ├── meta/                   # meta layer: world model, synthesis, directive, scheduler
│   │   ├── __init__.py
│   │   ├── construct.py        # mental construct: load/save/inject PRIORITIES, SELF, etc.
│   │   ├── first_light.py      # bootstrap protocol: inventory skills, write first heartbeat
│   │   ├── world_model.py      # load/save world model from db
│   │   ├── synthesizer.py      # world model → situation report
│   │   ├── directive.py        # situation report → directive (LLM call; writes DIRECTIVE.md)
│   │   └── planner.py          # end-of-session heartbeat planning (self-scheduler)
│   │
│   ├── macro/                  # macro layer: goal tree, strategy, risk
│   │   ├── __init__.py
│   │   ├── goal_tree.py        # goal tree CRUD
│   │   ├── strategy.py         # directive → strategy modifications + task creation (LLM call)
│   │   └── risk.py             # risk governor: deterministic limit enforcement
│   │
│   ├── tasks/                  # task layer: task tree execution
│   │   ├── __init__.py
│   │   ├── tree.py             # task tree: create, sequence, track
│   │   └── executor.py         # processes task tree in dependency order
│   │
│   ├── skills/                 # skill registry and implementations
│   │   ├── __init__.py
│   │   ├── registry.py         # skill registration, discovery, gating, context serialisation
│   │   ├── skill_docs.py       # reads workspace/skills/{name}.md for on-demand skill docs
│   │   ├── web_research.py     # search and fetch
│   │   ├── polymarket.py       # Polymarket skill (calls polymarket_client)
│   │   ├── polymarket_client.py # low-level Polymarket API + wallet reconciliation
│   │   ├── kb.py               # knowledge base read/write
│   │   ├── probability.py      # structured probability estimation (LLM call)
│   │   └── heartbeat.py        # create/modify/cancel heartbeat records
│   │
│   ├── heartbeat/              # heartbeat system
│   │   ├── __init__.py
│   │   ├── store.py            # heartbeat table CRUD + retry scheduling + stale detection
│   │   └── scheduler.py        # polling loop: fires due heartbeats, cleans stale runs
│   │
│   ├── db/                     # database layer
│   │   ├── __init__.py
│   │   ├── connection.py       # db connection and session management
│   │   └── models.py           # SQLAlchemy ORM models
│   │
│   └── llm/                    # LLM provider abstraction
│       ├── __init__.py
│       ├── client.py           # thin wrapper around litellm.completion()
│       ├── complete.py         # streaming completion helpers for WebSocket chat
│       ├── provider.py         # provider config resolution (real vs fake)
│       ├── runtime.py          # runtime LLM config (autonomous mode toggle, live overrides)
│       └── prompts.py          # prompt templates (not stored in agent workspace)
│
├── frontend/                   # React/TS frontend (Vite + Tailwind)
│   ├── src/
│   │   ├── App.tsx             # router: /agent, /chat/:id, /workspace, /settings
│   │   ├── main.tsx
│   │   ├── types/index.ts      # shared TypeScript types
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts # auto-reconnect WS hook (exponential backoff)
│   │   │   └── useChat.ts      # chat state: messages, streaming, stopStreaming
│   │   ├── pages/
│   │   │   ├── AgentPage.tsx   # agent dashboard: overview, activity, construct, skills, positions
│   │   │   ├── ChatPage.tsx    # chat UI: session title, scroll-to-bottom, WS status
│   │   │   ├── WorkspacePage.tsx # construct file editor
│   │   │   └── SettingsPage.tsx  # LLM config and runtime settings
│   │   └── components/
│   │       ├── sidebar/Sidebar.tsx
│   │       └── chat/
│   │           ├── ChatInput.tsx    # textarea + thinking/skills toggles + stop button
│   │           ├── MessageItem.tsx  # markdown render + copy button + timestamp
│   │           ├── ThinkingBlock.tsx
│   │           └── ToolCallBlock.tsx
│   ├── package.json
│   ├── vite.config.ts          # proxies /api/* to FastAPI in dev
│   └── tailwind.config.js
│
├── workspace/                  # agent workspace (read by the agent at runtime)
│   ├── SOUL.md                 # agent identity, domain knowledge, operating philosophy
│   ├── SKILLS.md               # human-readable skill reference (mirrors registry)
│   ├── skills/                 # per-skill on-demand documentation (read via skill_docs.py)
│   └── construct/              # mental construct files (PRIORITIES, SELF, MACRO_PLAN, etc.)
│
├── migrations/                 # reserved for future Alembic migration scripts
│   ├── env.py
│   ├── script.py.mako
│   └── versions/               # empty today; schema is created on startup
│
├── tests/
│   ├── test_heartbeat.py       # heartbeat store and scheduler logic
│   ├── test_risk.py            # risk governor limit enforcement
│   ├── test_world_model.py     # world model load/save round-trip
│   └── test_skills.py          # skill registry and dispatch
│
├── docs/
│   ├── META.md                 # platform identity, layer model, primitives (authoritative)
│   ├── ARCHITECTURE.md         # full system design specification
│   ├── DEVELOPMENT.md          # this file
│   ├── OPENCLAW_COMPARISON.md  # what was adopted from OpenClaw and why
│   ├── GITHUB_PUSH_PLAN.md     # pre-push secret hygiene checklist
│   ├── adr/                    # architecture decision records
│   └── applications/           # per-application docs (Polymarket, etc.)
│
├── .env.example                # all required env vars with descriptions
├── .gitignore
├── pyproject.toml              # project metadata and dependencies (uv)
├── Makefile                    # dev task runner
└── README.md
```

### Naming and layout rules

- **One module per responsibility.** If a file is growing past ~300 lines, that is a signal that it is doing more than one thing.
- **No circular imports.** The dependency direction is strictly: `db` ← `skills` ← `tasks` ← `macro` ← `meta` ← `agent`. Lower layers never import from higher layers. The `api` package imports from all layers but nothing imports from `api`.
- **`config.py` is the single source of settings.** No module reads `os.environ` directly. All config comes from the `Settings` object in `config.py`.
- **LLM calls only in designated modules.** `meta/directive.py`, `meta/synthesizer.py`, `macro/strategy.py`, `skills/probability.py`, and `llm/client.py` are the only places that call the LLM. This makes the LLM surface auditable and testable.

---

## 4. Workspace Files

The `workspace/` directory follows the OpenClaw workspace-first pattern. These files are read by the agent at the start of every session. They are not code — they are the agent's configuration and identity, expressed in plain text.

### `workspace/SOUL.md`

The most important file in the workspace. Defines:

- The agent's mission and operating goal (Polymarket profit generation)
- Its embedded domain knowledge (Polymarket mechanics, topic categories, edge theory)
- Its risk philosophy (what it will and won't do, regardless of apparent edge)
- Its calibration self-assessment (updated periodically by the agent itself)
- The format of the situation report it produces
- The format of the directive it generates

`SOUL.md` is read at the start of every session and included in the system prompt. It is subject to the context budget cap (`soul_excerpt_max_chars`) so a large `SOUL.md` is truncated rather than overflowing the context window.

### `workspace/SKILLS.md`

A human-readable listing of all registered skills, their parameters, and when to use them. This is the narrative companion to the skill registry and is included in session context so the LLM knows what capabilities are available.

`SKILLS.md` is updated by the developer when skills are added or changed. The agent does not modify it.

### `workspace/construct/`

The mental construct files: `PRIORITIES.md`, `MACRO_PLAN.md`, `SELF.md`, `DIRECTIVE.md`, `REFLECTION.md`. These are agent-authored and updated every session. They are editable via the Workspace tab in the frontend. See [META.md](META.md) for their roles and lifecycle.

### `workspace/skills/`

Optional per-skill documentation files (`{name}.md`). When the agent calls the `read_skill_doc` skill, it reads from here. Useful for detailed usage notes, parameter examples, and caveats that would be too verbose to include in the main skill context block.

---

## 5. Configuration and Environment

All runtime configuration lives in `.env`. Copy `.env.example` to `.env` to start.

```bash
# LLM provider (see docs/ARCHITECTURE.md §4 for full options)
LLM_PRIMARY_MODEL=anthropic/claude-sonnet-4-6
LLM_SECONDARY_MODEL=anthropic/claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434

# Generic OpenAI-compatible endpoint (Kimi/Moonshot, OpenRouter, vLLM, etc.)
LLM_API_BASE=
LLM_API_KEY=

# Database
DATABASE_URL=sqlite:///./littleman.db

# Workspace
WORKSPACE_DIR=./workspace

# Polymarket
POLYMARKET_API_KEY=...
POLYMARKET_WALLET_ADDRESS=0x...
POLYMARKET_PRIVATE_KEY=...   # used only for transaction signing

# Web search (Tavily-compatible; optional — search skill degrades gracefully if unset)
SEARCH_API_KEY=...

# Budget and risk limits (all in USDC)
BUDGET_USDC=500.00
MAX_POSITION_PCT=0.20
MAX_EXPOSURE_PCT=0.80
MAX_SESSION_DRAWDOWN_PCT=0.15
MAX_TOTAL_DRAWDOWN_PCT=0.40
MAX_CATEGORY_EXPOSURE_PCT=0.40
KELLY_FRACTION=0.25

# Scheduler
HEARTBEAT_POLL_INTERVAL_SECONDS=30
IDLE_HEARTBEAT_INTERVAL_HOURS=4
STALE_SESSION_TIMEOUT_MINUTES=30   # heartbeats RUNNING longer than this are marked FAILED

# Context budget (mirrors OpenClaw bootstrapMaxChars/TotalMaxChars)
BOOTSTRAP_MAX_CHARS=20000
BOOTSTRAP_TOTAL_MAX_CHARS=60000
SOUL_EXCERPT_MAX_CHARS=6000
```

All values are loaded into a `Settings` instance via pydantic-settings and validated at startup. The agent will not start if required fields are missing.

`.env` is in `.gitignore`. `.env.example` is committed with empty or placeholder values and a comment on each line explaining what it does.

Some settings (LLM provider, autonomous mode on/off) can also be changed live via the Settings page in the frontend without restarting the process. These overrides live in `workspace/state/runtime.json`, which is also `.gitignore`d.

---

## 6. Database

SQLite in development. A single file (`littleman.db`) in the project root.

The schema is created automatically on first API startup by `littleman/db/connection.py::init_db()` from `Base.metadata.create_all`. There are no Alembic migrations yet (the `migrations/` directory is reserved for when the schema stabilises and production upgrades are needed).

The `db/connection.py` module manages a connection pool using `aiosqlite` for async access. All database access goes through this module — no module opens its own connection.

**Why SQLite and not Postgres?** This is a single-process application with one user. SQLite handles concurrent reads well and handles sequential writes (which is all the scheduler + one session require) without issue. Switching to Postgres later is a connection string change; Alembic can be introduced when upgrades require it.

**On WAL mode:** SQLite is configured in WAL (Write-Ahead Log) mode. This allows the scheduler process (reader) and an active session (writer) to operate concurrently without read-blocking.

---

## 7. Dependency Management

This project uses [uv](https://github.com/astral-sh/uv) for all Python dependency management. Frontend dependencies are managed with npm.

```bash
# Install uv (once, globally)
pip install uv

# Set up the Python environment
uv sync

# Add a Python dependency
uv add httpx

# Add a dev-only Python dependency
uv add --dev pytest

# Run a command in the project environment
uv run python -m littleman

# Frontend dependencies
cd frontend && npm install
```

Python dependencies are declared in `pyproject.toml`. The `uv.lock` file is committed so installs are reproducible.

Core Python dependencies:

```toml
[project]
dependencies = [
    "litellm>=1.40.0",
    "pydantic-settings>=2.0.0",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.19.0",
    "alembic>=1.13.0",
    "httpx>=0.27.0",
    "fastapi>=0.111.0",
    "uvicorn>=0.30.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
]
browser = [
    "playwright>=1.44.0",  # only needed if web research uses JS-heavy pages
]
```

---

## 8. Development Workflow

### Makefile targets

```makefile
make install     # uv sync + npm install in frontend/
make setup       # install + build-ui (first-time setup)
make start       # start FastAPI + scheduler (production-like runtime)
make run         # start FastAPI reload + Vite dev server (development)
make fresh       # wipe runtime state and start from scratch (testing)
make build-ui    # npm run build — build frontend to frontend/dist/
make boot        # run First Light once and exit
make once        # run a single heartbeat session and exit
make test        # pytest tests/
make lint        # ruff check littleman/
make format      # ruff format littleman/
make clean       # remove __pycache__, .pyc, the db file, frontend/dist
```

### Starting fresh

```bash
git clone ...
cd littleman
cp .env.example .env
# edit .env with your API keys and settings
python start.py          # one-command setup + runtime start
```

or, if you prefer Make:

```bash
make setup
make start
```

To wipe all runtime state and retest onboarding from a blank slate:

```bash
python start.py --fresh
# or
make fresh
```

The frontend dev server runs on port 5173 and proxies `/api/*` to FastAPI on port 8000. In production (`make start`), FastAPI serves the built frontend from `frontend/dist/`. See [`docs/GETTING_STARTED.md`](GETTING_STARTED.md) for the full onboarding walkthrough.

There are no Alembic migrations today; `littleman/db/connection.py::init_db` creates the SQLite schema on first API startup.

### Making a change

1. Edit the relevant module
2. Run `make test` — tests must pass before committing
3. Run `make lint` — no lint errors
4. Commit

If you change the SQLAlchemy models, remember that the schema is created from `Base.metadata` on startup. There is no migration system yet, so existing `littleman.db` files will need to be deleted (or migrated manually) until Alembic is introduced.

### Commit conventions

Keep commits small and focused. The commit message first line should complete the sentence "this commit will...":

```
add probability estimation skill
fix risk governor to reject positions at exactly the limit
update SOUL.md with initial Polymarket domain knowledge
add heartbeat cascade test for multi-session chain
```

No ticket numbers, no emoji, no "WIP". If a commit needs a body, write one. If it doesn't, don't.

---

## 9. Testing

Tests live in `tests/`. The guiding principle is: test the components where bugs cause real harm, and test them against real behaviour, not mocked internals.

### What to test

**Test the risk governor thoroughly.** It is the only hard protection against the agent losing money due to a bug. Every limit type, every boundary condition, every veto case should have a test.

**Test the heartbeat store.** The cascade logic — create, amend, cancel, chain — must be correct. A bug here means the agent either never wakes up or wakes up at the wrong time with the wrong context. Include tests for the stale-session detection and the retry scheduling.

**Test the world model round-trip.** Load from database, modify fields, save, reload. The world model is the agent's persistent state; corruption here means the agent starts each session with wrong information.

**Test skill dispatch.** The skill registry must correctly resolve skill names to implementations and validate parameters. A wrong dispatch means the agent calls the wrong function.

### What not to test with automated tests

LLM calls. The outputs of the directive engine, strategy planner, and probability estimator are not deterministic. Test that the LLM is called with the correct inputs (messages, system prompt structure) but do not assert on the content of its outputs in automated tests. Evaluate LLM output quality manually and through calibration data.

The Polymarket client's write operations. Do not place test orders. Use a Polymarket testnet environment for manual testing of bet placement.

### Test style

```python
# tests/test_risk.py
import pytest
from littleman.macro.risk import RiskGovernor
from littleman.db.models import RiskState

def test_veto_when_position_exceeds_max_pct():
    state = RiskState(wallet_balance_usdc=1000, open_exposure_usdc=150)
    governor = RiskGovernor(max_position_pct=0.20, max_exposure_pct=0.80)
    result = governor.check_bet(size_usdc=250, current_state=state)
    assert result.allowed is False
    assert "max_position_pct" in result.reason

def test_allow_bet_within_limits():
    state = RiskState(wallet_balance_usdc=1000, open_exposure_usdc=100)
    governor = RiskGovernor(max_position_pct=0.20, max_exposure_pct=0.80)
    result = governor.check_bet(size_usdc=150, current_state=state)
    assert result.allowed is True
```

Plain assertions, no class-based test organisation unless there is a genuine grouping reason. Fixtures in `conftest.py` for shared setup (a test database, a default settings object). No mocking of the database in tests that exercise database logic — use an in-memory SQLite database instead.

---

## 10. Running the Agent

### Processes

A full environment runs one of two combos:

- **Runtime (`make start` or `python start.py`)**: FastAPI backend + heartbeat scheduler in parallel. FastAPI serves the built frontend from `frontend/dist/`.
- **Development (`make run`)**: FastAPI backend with hot reload + Vite dev server (port 5173). The dev server proxies `/api/*` to FastAPI.

There is also a **manual session runner** (`python -m littleman once`) for running a single heartbeat session immediately without waiting for the scheduler.

### `make run` (recommended for development)

```bash
make run
# FastAPI on http://localhost:8000
# Frontend on http://localhost:5173 (proxy to FastAPI)
```

### `make start` (production-like runtime)

```bash
make start
# FastAPI + scheduler on http://localhost:8000
```

The frontend dashboard at `http://localhost:5173` shows the Agent, Chat, Workspace, and Settings pages.

### Initial boot

The very first agent session is triggered via the frontend. Navigate to the Agent tab — if the agent is not yet bootstrapped, an amber card prompts you to run First Light. Clicking it calls `POST /api/agent/boot`, which runs the bootstrap protocol: reads `SOUL.md`, inventories skills, populates the mental construct, and schedules the first heartbeat.

Alternatively, trigger it from the command line:

```bash
make boot
# or
python -m littleman boot
```

After First Light, the scheduler process (started by `make start` or `python start.py`) polls for due heartbeats every `HEARTBEAT_POLL_INTERVAL_SECONDS` seconds.

### Logs

All session activity is written to stdout in structured JSON lines format (one JSON object per log entry, with `level`, `timestamp`, `session_id`, and `message` fields). In development, pipe through `jq` for readability:

```bash
make dev 2>&1 | jq .
```

The session audit log in the database (`agent_sessions` table) contains the structured summary of each session. Query it to review what the agent has been doing:

```sql
SELECT started_at, ended_at, bets_placed, heartbeats_created, outcome_summary
FROM agent_sessions
ORDER BY started_at DESC
LIMIT 10;
```

Every agent session also narrates itself into the **Main chat session** — a pinned session in the chat sidebar that shows the agent's autonomous activity as a readable stream of entries alongside ordinary user↔LLM conversations.
