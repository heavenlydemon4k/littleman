# Getting Started with littleman

This guide is for someone who has just cloned the repository and wants to get the system running, then understand what they are looking at.

---

## What this project is

**littleman** is an LLM-native autonomous agent platform. The LLM is the director: it forms its own intent, schedules its own future work, and maintains explicit models of itself and its situation so it can run continuously without a human deciding the next step.

The flagship demo application is **Polymarket trading**, but the platform is intentionally generic. An application is just:

- a `SOUL.md` (prime directive + domain knowledge),
- a pack of skill docs in `workspace/skills/`,
- optional domain configuration.

Swap those three and the same runtime becomes a research assistant, an ops monitor, or a content pipeline. See [`docs/META.md`](META.md) and [`docs/adr/0002-littleman-is-a-platform.md`](../adr/0002-littleman-is-a-platform.md).

---

## Prerequisites

- Python 3.12+ (3.11 works)
- Node.js 20+ (for the frontend)
- `uv` is recommended but not required; the startup script falls back to `venv` + `pip`
- Git

---

## One-command start

From the repository root:

```bash
python start.py
```

This will, on first run:

1. Install Python dependencies (`uv sync --all-extras`, or `pip install -e .` if you don't have `uv`).
2. Install frontend dependencies (`npm install` in `frontend/`).
3. Run database migrations (`alembic upgrade head`).
4. Build the frontend (`npm run build`).

Then it starts both:

- **API server** — `uvicorn littleman.api.app:app --host 0.0.0.0 --port 8000`
- **Autonomous scheduler** — `python -m littleman`

Open `http://localhost:8000`.

### Other useful startup modes

| Command | What it does |
|---------|--------------|
| `python start.py --setup` | Force a fresh dependency install/migration/build |
| `python start.py --no-setup` | Skip setup checks and start immediately |
| `python start.py --dev` | Start API with hot reload + Vite dev UI (`http://localhost:5173`) |
| `python start.py --boot` | Run **First Light** immediately, then start the runtime |
| `make setup` | First-time setup only (uv + npm + migrate + build) |
| `make start` | Start API + scheduler (assumes setup already done) |
| `make run` | Start API reload + Vite dev UI |
| `make boot` | Run First Light once and exit |
| `make once` | Run a single heartbeat session and exit |

---

## The first run

1. Open `http://localhost:8000`.
2. The onboarding wizard asks for:
   - **Name** for the agent instance.
   - **Purpose** / prime directive.
   - **LLM provider and model** (Kimi, Anthropic, OpenAI, OpenRouter, Ollama, etc.).
   - **Guided or custom** configuration.
3. After onboarding you land in the **Main session** chat.
4. Click **Begin onboarding** (First Light).
   - The agent reads `workspace/SOUL.md`, `workspace/AGENT.md`, `workspace/SKILLS.md`, and every skill doc in `workspace/skills/`.
   - It authors its initial mental construct documents in `workspace/construct/`.
   - It writes an initial `EXPOSURE.md`.
   - It greets you.
5. The agent is now dormant until you message it or enable **Autonomous** mode.

---

## How to read and understand the system

The repository is organized around a few core ideas. Read them in this order:

### 1. Start with the identity and operating manual

| File | What it is |
|------|------------|
| `workspace/SOUL.md` | Prime directive, values, domain knowledge. This is the agent's identity. |
| `workspace/AGENT.md` | How the agent should behave: reasoning style, safety rules, user-relationship norms. |
| `workspace/SKILLS.md` | How skills are discovered, called, and documented. |
| `workspace/construct/EXPOSURE.template.md` | Template for the agent's risk / state snapshot. |

### 2. Understand the runtime loop

The agent's life is a repeating **wake cycle**:

```
situate → directive → strategy/tasks → ReAct skill execution → reflect → maintain → self-schedule
```

Read the code in this order:

| Layer | Entry file | Responsibility |
|-------|------------|----------------|
| Session orchestration | `littleman/agent/session.py` | Runs one full wake end-to-end. |
| Situation / directive | `littleman/meta/synthesizer.py`, `littleman/meta/directive.py` | Reads construct + world model, decides intent. |
| Strategy | `littleman/macro/strategy.py` | Turns intent into a task plan. |
| Task execution | `littleman/tasks/executor.py`, `littleman/agent/loop.py` | ReAct loop: reason → act → observe. |
| Maintenance | `littleman/meta/maintain.py` | Updates PRIORITIES, SELF, HYPOTHESES, BLOCKERS, SKILL_NOTES, CALENDAR. |
| Scheduler | `littleman/heartbeat/scheduler.py` | Polls for due heartbeats and fires them. |

### 3. Understand the mental workspace

After First Light, `workspace/construct/` contains the agent's runtime cognition:

| Document | Purpose |
|----------|---------|
| `PRIORITIES.md` | Ranked priority stack, rewritten each wake. |
| `MACRO_PLAN.md` | Strategic campaigns and horizons. |
| `SELF.md` | Runtime self-model: capabilities, calibration, learned patterns. |
| `DIRECTIVE.md` | The current wake's intent. |
| `REFLECTION.md` | Append-only learning log. |
| `EXPOSURE.md` | Risk / application-state snapshot. |
| `CALENDAR.md` | Self-scheduled future heartbeats. |
| `HYPOTHESES.md` | Open predictions to test. |
| `BLOCKERS.md` | Obstacles and how to resolve them. |
| `SKILL_NOTES.md` | Per-skill usage notes learned from experience. |

These files are loaded into the system prompt each wake and are editable from the workspace UI.

### 4. Understand the skill system

- Built-in skills are Python modules in `littleman/skills/`.
- OpenClaw-style skills are markdown docs in `workspace/skills/` with YAML frontmatter.
- The registry lives in `littleman/skills/registry.py`.
- On-demand skill docs are read by `littleman/skills/skill_docs.py`.
- Skills can be gated on availability (e.g. the Polymarket skills only appear when `active_application = "Polymarket trading"`).

### 5. Understand the data model

- `littleman/db/models.py` defines the SQLAlchemy tables.
- `littleman/db/connection.py` configures the async SQLite engine.
- Key tables: `Session`, `Message`, `Heartbeat`, `WorldModel`, `ConstructDoc`, `CalibrationEntry`.

---

## Key architecture docs

For a deeper read:

- [`docs/META.md`](META.md) — canonical architecture: identity, mental workspace, primitives, turn cycle.
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — full system design, heartbeat cascade, data model, risk management.
- [`docs/adr/0001-mental-construct-not-generational-state.md`](../adr/0001-mental-construct-not-generational-state.md) — why the agent uses a mental workspace instead of parallel contexts.
- [`docs/adr/0002-littleman-is-a-platform.md`](../adr/0002-littleman-is-a-platform.md) — why Polymarket is an application, not the product.
- [`docs/ROADMAP.md`](ROADMAP.md) — current status, what paused, and the forward plan.

---

## Common development commands

```bash
# Run the full test suite
make test

# Run just the backend tests
pytest -q

# Build the frontend
make build-ui

# Run the scheduler manually (autonomous mode must be enabled in the UI)
make scheduler

# Run a single heartbeat session
make once

# Force First Light
make boot

# Lint / format
make lint
make format
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `uv: command not found` | Install [`uv`](https://github.com/astral-sh/uv), or let `start.py` fall back to `venv` + `pip`. |
| Port 8000 in use | Change the port in `Makefile` or run `uvicorn littleman.api.app:app --port 8001`. |
| Frontend shows a blank page | Run `make build-ui`; FastAPI serves the built files from `frontend/dist/`. |
| Database errors | Run `make migrate` or `python start.py --setup`. |
| Agent never wakes autonomously | Turn **Autonomous** on in the dashboard; the scheduler only fires when enabled. |
