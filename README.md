# littleman

An **LLM-native autonomous agent platform**. The LLM is the director — it forms its own intent,
schedules its own future work, and maintains explicit models of itself and its situation, so it
can run continuously without a human deciding the next step. The human provides identity and
limits; the agent provides the direction.

In the spirit of [OpenClaw](https://github.com/openclaw/openclaw), but where OpenClaw's
heartbeat is a static human-written checklist, littleman's heartbeats are **dynamic and
self-authored** — the agent writes, amends, and chains its own future activations.

**Polymarket trading is the first application, not the product.** An application is just a
`SOUL.md` (prime directive + domain knowledge), a skill pack, and optional domain config —
swap those three and the same platform becomes a research assistant, an ops monitor, or a
content pipeline. See [ADR 0002](docs/adr/0002-littleman-is-a-platform.md) and
[`docs/META.md`](docs/META.md).

---

## What the platform gives you

- **Self-prompting cognition** — a meta layer reads the agent's own workspace, synthesises the
  situation, and generates the directive that drives the turn. This replaces the human
  meta-cognition that normally writes each prompt.
- **Self-scheduling** — the agent authors its own heartbeats (when to wake, why, with what
  context) and chains them across time. No fixed cron cadence.
- **Mental Construct** — self-authored, inspectable markdown documents (`PRIORITIES`,
  `MACRO_PLAN`, `SELF`, `DIRECTIVE`, `REFLECTION`) that are the agent's runtime cognition.
- **Skill registry** — typed, gated capabilities the agent discovers via its self-model;
  unavailable skills (missing keys) are hidden from the model automatically.
- **Main session** — every autonomous or manual run narrates itself into the agent's own chat
  context, visible alongside ordinary user↔LLM chats.
- **Safe by default** — runs are manual from the UI unless an explicit **autonomous** toggle is
  on; hard limits (for trading: position/exposure/drawdown) are enforced in code, not prompts.
- **Model-agnostic** — Kimi/Moonshot, Anthropic, OpenAI, OpenRouter, or local Ollama via
  LiteLLM; the active model is editable live in the UI.

The flagship application — Polymarket trading — adds market scanning, calibrated probability
estimation, Kelly sizing, a deterministic risk governor, and a closed observation loop.

---

## Stack

- **Python 3.12+** (runs on 3.11), venv-isolated
- **LiteLLM** for LLM provider abstraction (Kimi/Anthropic/OpenAI/OpenRouter/Ollama)
- **SQLite** + aiosqlite (WAL) for all persistence
- **FastAPI** backend + **React/TypeScript** frontend (chat, agent dashboard, workspace editor, settings)
- **httpx** for HTTP, **playwright** (optional) for JS-heavy web research

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

- [`docs/META.md`](docs/META.md) — the canonical architectural meta: identity, mental workspace, primitives, turn cycle (tracks built vs planned)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full system design: all layers, the heartbeat cascade, data model, risk management
- [`docs/OPENCLAW_COMPARISON.md`](docs/OPENCLAW_COMPARISON.md) — measured against OpenClaw, with what was adopted
- [`docs/applications/polymarket.md`](docs/applications/polymarket.md) — the Polymarket application + live-trading integration plan
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — project structure, stack rationale, workflow, testing
- [`docs/adr/`](docs/adr/) — architecture decision records (serial execution; platform vs application)
- [`docs/GITHUB_PUSH_PLAN.md`](docs/GITHUB_PUSH_PLAN.md) — secret-hygiene checklist before pushing

---

## Cognitive layer (Mental Construct)

Beyond the static `SOUL.md`, the agent maintains a set of self-authored markdown documents in
`workspace/construct/` that form its runtime cognition — created from templates at **First
Light** and owned by the agent thereafter:

- `PRIORITIES.md` — ranked priority stack, rewritten each session
- `MACRO_PLAN.md` — strategic campaigns and horizons
- `SELF.md` — runtime self-model: capabilities, calibration, learned patterns
- `DIRECTIVE.md` — the current session's intent (written by the directive engine)
- `REFLECTION.md` — append-only learning log

These are loaded into the system prompt each session and editable from the workspace UI. See
[`docs/adr/0001-mental-construct-not-generational-state.md`](docs/adr/0001-mental-construct-not-generational-state.md)
for the decision to adopt this cognitive layer while keeping execution serial (not the
generational/parallel-context model some designs propose) — capital operations must evaluate
against one consistent view.

## Status

The platform runs end-to-end against a live LLM (verified on Kimi/Moonshot): First Light →
situation → directive → strategy/task planning → risk-gated execution → world-model update →
self-scheduled heartbeats, all visible in the UI. **51 tests passing.**

The flagship Polymarket application does live market **reads** today; live order **signing** is
the remaining piece — bets are sized, risk-checked, recorded, and logged, but not yet posted
on-chain. The integration plan is in [`docs/applications/polymarket.md`](docs/applications/polymarket.md).

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e .   # or: make install
.venv/Scripts/python -m uvicorn littleman.api.app:app --port 8000  # serves UI + API
# open http://localhost:8000 → Agent tab. Autonomous is OFF by default; click Run to drive a turn.
```
