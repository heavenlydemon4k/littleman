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
| Language | Python 3.12+ | LLM SDKs, web scraping, data handling. No good reason to use anything else for this domain. |
| LLM provider abstraction | [LiteLLM](https://github.com/BerriAI/litellm) | Single `completion()` call covers Anthropic, OpenAI, Ollama, and 100+ others. No lock-in. |
| Local LLM runtime | [Ollama](https://ollama.ai) | Standard, well-maintained, works offline. Pull a model, run a server, done. |
| Database | SQLite (via `sqlite3` stdlib + `aiosqlite` for async) | Single file, zero config, sufficient for one agent, trivially backed up. Upgrade to Postgres only if multiple processes need concurrent writes. |
| Migrations | [Alembic](https://alembic.sqlalchemy.org) | Standard, works with SQLite and Postgres, so switching databases later doesn't require changing the migration toolchain. |
| ORM | SQLAlchemy Core (not ORM) | Direct SQL with type-checked query construction. Avoids the magic of the full ORM while keeping queries composable. |
| HTTP client | [httpx](https://www.python-httpx.org) | Async-native, clean API, supports both sync and async use. Standard for modern Python. |
| Web scraping | [playwright](https://playwright.dev/python/) | Handles JS-heavy pages. Used only by the web researcher skill; not a core dependency. |
| Settings | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Reads from `.env` and environment variables with type validation. Single `Settings` object imported where needed. |
| Dependency management | [uv](https://github.com/astral-sh/uv) | Fast, replaces pip + virtualenv + pip-tools in one tool. `uv sync` sets up the environment. |
| Task runner | `Makefile` | Simple, universal, no dependencies. Wraps common commands so you don't need to remember flags. |
| Vector search (KB) | SQLite FTS5 | Built into SQLite. Adequate for full-text search over the knowledge base. Add a proper vector store (pgvector, Chroma) only if semantic similarity search proves necessary. |

### What is explicitly not included

- Docker / containerisation — unnecessary for a single-user local process
- A web UI — the agent reports via logs and the database; a UI is a separate concern if it ever becomes useful
- A task queue (Celery, RQ, etc.) — the heartbeat scheduler is a simple polling loop
- Redis — no need for a cache layer at this scale
- Cloud infrastructure — runs locally; cloud deployment is a future option, not a current requirement

---

## 3. Repository Layout

```
littleman/
│
├── littleman/                  # main Python package
│   ├── __init__.py
│   ├── main.py                 # entrypoint: `python -m littleman`
│   ├── config.py               # Settings (pydantic-settings), loaded once
│   │
│   ├── agent/                  # session orchestration
│   │   ├── __init__.py
│   │   ├── session.py          # runs one full heartbeat session end-to-end
│   │   └── loop.py             # ReAct reasoning loop (reason → act → observe → repeat)
│   │
│   ├── meta/                   # meta layer: world model, synthesis, directive, scheduler
│   │   ├── __init__.py
│   │   ├── world_model.py      # load/save world model from db
│   │   ├── synthesizer.py      # world model → situation report
│   │   ├── directive.py        # situation report → directive (LLM call)
│   │   └── planner.py          # end-of-session heartbeat planning
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
│   │   ├── registry.py         # skill registration, discovery, context serialisation
│   │   ├── web_research.py     # search and fetch
│   │   ├── polymarket.py       # Polymarket API read/write
│   │   ├── kb.py               # knowledge base read/write
│   │   ├── probability.py      # structured probability estimation (LLM call)
│   │   └── heartbeat.py        # create/modify/cancel heartbeat records
│   │
│   ├── heartbeat/              # heartbeat system
│   │   ├── __init__.py
│   │   ├── store.py            # heartbeat table CRUD
│   │   └── scheduler.py        # polling loop: finds due heartbeats, fires sessions
│   │
│   ├── db/                     # database layer
│   │   ├── __init__.py
│   │   ├── connection.py       # db connection and session management
│   │   └── models.py           # SQLAlchemy table definitions (Core, not ORM)
│   │
│   └── llm/                    # LLM provider abstraction
│       ├── __init__.py
│       ├── client.py           # thin wrapper around litellm.completion()
│       └── prompts.py          # prompt templates (not stored in agent workspace)
│
├── workspace/                  # agent workspace (read by the agent at runtime)
│   ├── SOUL.md                 # agent identity, domain knowledge, operating philosophy
│   ├── SKILLS.md               # human-readable skill reference (mirrors registry)
│   └── skills/                 # workspace-local skill overrides (optional)
│
├── migrations/                 # Alembic migration scripts
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
│
├── tests/
│   ├── test_heartbeat.py       # heartbeat store and scheduler logic
│   ├── test_risk.py            # risk governor limit enforcement
│   ├── test_world_model.py     # world model load/save round-trip
│   └── test_skills.py          # skill registry and dispatch
│
├── docs/
│   ├── ARCHITECTURE.md         # full system design specification
│   └── DEVELOPMENT.md          # this file
│
├── .env.example                # all required env vars with descriptions
├── .gitignore
├── pyproject.toml              # project metadata and dependencies (uv)
├── Makefile                    # dev task runner
└── README.md
```

### Naming and layout rules

- **One module per responsibility.** If a file is growing past ~300 lines, that is a signal that it is doing more than one thing.
- **No circular imports.** The dependency direction is strictly: `db` ← `skills` ← `tasks` ← `macro` ← `meta` ← `agent`. Lower layers never import from higher layers.
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

`SOUL.md` is read at the start of every session and included in full in the system prompt for the directive engine's LLM call. It is not a prompt in the conventional sense — it is the agent's durable self-description.

The agent may append to `SOUL.md` over time (e.g., calibration notes, updated category assessments), but it does not rewrite the core identity sections. Structural changes to `SOUL.md` are developer changes.

### `workspace/SKILLS.md`

A human-readable listing of all registered skills, their parameters, and when to use them. This is the narrative companion to the skill registry. It is included in the system prompt for strategy planning and task execution so the LLM knows what capabilities are available.

`SKILLS.md` is updated by the developer when skills are added or changed. The agent does not modify it.

---

## 5. Configuration and Environment

All runtime configuration lives in `.env`. Copy `.env.example` to `.env` to start.

```bash
# LLM provider (see docs/ARCHITECTURE.md §4 for full options)
LLM_PRIMARY_MODEL=anthropic/claude-sonnet-4-6
LLM_SECONDARY_MODEL=ollama/llama3.1:8b
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434

# Database
DATABASE_URL=sqlite:///./littleman.db

# Workspace
WORKSPACE_DIR=./workspace

# Polymarket
POLYMARKET_API_KEY=...
POLYMARKET_WALLET_ADDRESS=0x...
POLYMARKET_PRIVATE_KEY=...   # used only for transaction signing

# Budget and risk limits (all in USDC)
BUDGET_USDC=500.00
MAX_POSITION_PCT=0.20
MAX_EXPOSURE_PCT=0.80
MAX_SESSION_DRAWDOWN_PCT=0.15
MAX_TOTAL_DRAWDOWN_PCT=0.40
MAX_CATEGORY_EXPOSURE_PCT=0.40

# Scheduler
HEARTBEAT_POLL_INTERVAL_SECONDS=30
HEARTBEAT_MISSED_THRESHOLD_MINUTES=10
IDLE_HEARTBEAT_INTERVAL_HOURS=4
```

All values are loaded into a `Settings` instance via pydantic-settings and validated at startup. The agent will not start if required fields are missing.

`.env` is in `.gitignore`. `.env.example` is committed with empty or placeholder values and a comment on each line explaining what it does.

---

## 6. Database

SQLite in development. A single file (`littleman.db`) in the project root.

The Alembic migration in `migrations/versions/001_initial_schema.py` creates the full schema (see [ARCHITECTURE.md §14](ARCHITECTURE.md#14-data-model)). Run `make migrate` to apply.

The `db/connection.py` module manages a connection pool using `aiosqlite` for async access. All database access goes through this module — no module opens its own connection.

**Why SQLite and not Postgres?** This is a single-process application with one user. SQLite handles concurrent reads well and handles sequential writes (which is all the scheduler + one session require) without issue. The Alembic setup means switching to Postgres is a connection string change and a `make migrate` if the need arises.

**On WAL mode:** SQLite is configured in WAL (Write-Ahead Log) mode. This allows the scheduler process (reader) and an active session (writer) to operate concurrently without read-blocking.

---

## 7. Dependency Management

This project uses [uv](https://github.com/astral-sh/uv) for all dependency management.

```bash
# Install uv (once, globally)
pip install uv

# Set up the project environment
uv sync

# Add a dependency
uv add httpx

# Add a dev-only dependency
uv add --dev pytest

# Run a command in the project environment
uv run python -m littleman
```

Dependencies are declared in `pyproject.toml`. The `uv.lock` file is committed to the repository so installs are reproducible.

Core dependencies:

```toml
[project]
dependencies = [
    "litellm>=1.40.0",
    "pydantic-settings>=2.0.0",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.19.0",
    "alembic>=1.13.0",
    "httpx>=0.27.0",
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
make install     # uv sync — install all dependencies
make migrate     # alembic upgrade head — apply database migrations
make run         # start the full agent (scheduler + session loop)
make scheduler   # start only the heartbeat scheduler process
make session     # run a single session manually (for testing)
make test        # pytest tests/
make lint        # ruff check littleman/
make format      # ruff format littleman/
make clean       # remove __pycache__, .pyc, the db file
```

### Starting fresh

```bash
git clone ...
cd littleman
cp .env.example .env
# edit .env with your API keys and settings
make install
make migrate
make run
```

### Making a change

1. Edit the relevant module
2. If the change affects the database schema, create a new Alembic migration: `alembic revision --autogenerate -m "description"`
3. Run `make test` — tests must pass before committing
4. Run `make lint` — no lint errors
5. Commit

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

**Test the heartbeat store.** The cascade logic — create, amend, cancel, chain — must be correct. A bug here means the agent either never wakes up or wakes up at the wrong time with the wrong context.

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

### Two processes

The agent requires two processes running simultaneously:

**1. The scheduler** (`littleman/heartbeat/scheduler.py`): polls the heartbeat table every `HEARTBEAT_POLL_INTERVAL_SECONDS` seconds. When it finds a heartbeat with `status=SCHEDULED` and `fire_at <= now()`, it marks it `RUNNING` and starts a session.

**2. The session** (`littleman/agent/session.py`): the actual agent work. Started by the scheduler; runs one full planning cycle and exits. Creates new heartbeat records before exiting.

In development, you can run them in separate terminals:

```bash
# Terminal 1
make scheduler

# Terminal 2 (to manually trigger a session without waiting for a heartbeat)
make session
```

In practice (when leaving the agent to run autonomously), a process supervisor handles both. A `Procfile` or a simple systemd unit file covers this. Details in `docs/DEPLOYMENT.md` (not yet written — deploy when you need to deploy).

### Initial boot

The very first heartbeat does not come from the scheduler — there are no heartbeat records yet. The initial boot session is triggered manually:

```bash
make session -- --boot
```

The `--boot` flag tells the session to skip the heartbeat lookup and run as an initial full-cycle session. At the end of this session, the self-scheduler creates the first real heartbeat records. From that point, the scheduler takes over.

### Logs

All session activity is written to stdout in structured JSON lines format (one JSON object per log entry, with `level`, `timestamp`, `session_id`, and `message` fields). In development, pipe through `jq` for readability:

```bash
make run | jq .
```

The session audit log in the database (`sessions` table) contains the structured summary of each session. Query it to review what the agent has been doing:

```sql
SELECT started_at, ended_at, bets_placed, heartbeats_created, outcome_summary
FROM sessions
ORDER BY started_at DESC
LIMIT 10;
```
