# Littleman — Architectural Meta

The canonical, repo-resident statement of what littleman *is*. Platform-first. Where a concept
is built vs planned, this says so, so the doc tracks reality rather than aspiration.

---

## 1. Identity

Littleman is a **general-purpose, LLM-native autonomous agent platform** — an OpenClaw-class
system for building agents that direct themselves. It is **not** a Polymarket bot, not a
chatbot with tools, not a task executor waiting for prompts, and not a traditional agent with a
human in the meta-cognitive loop. The LLM is the **director, orchestrator, and cognitive
engine**, operating through self-generated intent, self-authored scheduling, and explicit
self-referential models.

**The platform is domain-agnostic.** What an instance of littleman *does* is defined entirely by
its **application**: a `SOUL.md` (prime directive, identity, domain knowledge), a **skill pack**
(the capabilities it can call), and optional domain config (limits, budgets, credentials). Swap
those three and the same engine becomes a research assistant, an operations monitor, a content
pipeline, a personal-ops agent — or a prediction-market trader. Nothing in the meta/macro/task
core, the heartbeat system, the mental construct, or the runtime is trading-specific.

**Polymarket trading is a reference application, not the product** — the first concrete proof
that the platform works end-to-end, and the source of the example skills in `docs/applications/`.
Treat every trading-shaped concept below (risk governor, budget, positions) as belonging to
*that application*, not the platform; another application simply would not register them. See
[ADR 0002](adr/0002-littleman-is-a-platform.md).

**The human role is constraint and identity, not direction.** The human provides the prime
directive, hard limits, and capability registry — typically through onboarding (§8). The agent
handles situational awareness, intent formation, planning, scheduling, execution, calibration,
and self-modification of its own internal models.

It is inspired by [OpenClaw](https://github.com/openclaw/openclaw) and diverges where it
matters — most of all by making the heartbeat **dynamic and self-authored** rather than a
static checklist (see [OPENCLAW_COMPARISON.md](OPENCLAW_COMPARISON.md)).

---

## 2. The Mental Workspace (internal construct)

The agent maintains self-authored documents that are its explicit cognitive scaffolding —
inspectable, editable, and version-controllable. They beat opaque vector memory for a system
that must be auditable.

### Persistent documents (survive across turns)

| Document | Function | Status |
|---|---|---|
| `PRIORITIES.md` | ranked stack of what matters across turns | **built** |
| `MACRO_PLAN.md` | strategic agenda, campaigns, horizons | **built** |
| `SELF.md` | self-model: capabilities, limits, calibration | **built** |
| `REFLECTION.md` | post-outcome analysis, calibration drift (append-only) | **built** |
| `HYPOTHESES.md` | open predictions/questions being tested | planned |
| `BLOCKERS.md` | known failures, skill bugs, API issues | planned |
| `CALENDAR.md` | upcoming events, deadlines, resolution times | **built** |
| `EXPOSURE.md` | risk map: positions, correlations, locked capital | **built** |
| `SKILL_NOTES.md` | dynamic per-skill assessment | planned |

### Turn-cycle documents (regenerated each turn)

| Document | Function | Status |
|---|---|---|
| `DIRECTIVE.md` | current intent: what this turn is for and why | **built** |
| `PLAN.md` | research → gather bearings → form approach | planned |
| `TURNS.md` | execution queue: N planned turns + error handling | planned |

### Static documents (human-provided)

`SOUL.md` (prime directive, identity, domain knowledge) and `SKILLS.md` (capability reference).

### Lifecycle rules

- **Read at turn start:** PRIORITIES, SELF, MACRO_PLAN, DIRECTIVE.
- **Append-only:** REFLECTION (and the planned HYPOTHESES/BLOCKERS/CALENDAR).
- **Overwrite each turn:** DIRECTIVE (and planned PLAN/TURNS).
- **Context budget:** each doc is capped on injection; REFLECTION is truncated to its tail so
  it cannot overflow the window (**built** — `meta/construct.py`).

The construct is currently **file-backed** (markdown is the source of truth, editable in the
UI). A DB-backed source-of-truth with rendered files is a future option; it is intentionally
deferred (boring-tools principle).

---

## 3. Core primitives

- **Self-Model** — runtime, agent-updated representation of capabilities/knowledge/state/
  identity. Distinct from the static `SOUL.md`. (`SELF.md`, **built**.)
- **First Light** — re-invokable bootstrap: read config, inventory skills, query external
  state, populate the construct, write the first heartbeat. Not one-time init. (**built**.)
- **Heartbeat** — a self-authored activation record (`fire_at`, `reason`, `session_type`,
  `context`, `spawned_by`). The store is the agent's own schedule; the scheduler is dumb.
  (**built**.)
- **Session/Context** — a bounded run that wakes from a heartbeat, carries its intent, executes,
  persists, and ends. Runs are **serial** (one consistent capital view — ADR 0001), guarded by
  a cross-process lock. (**built**.)
- **Directive** — the meta layer's self-generated statement of intent. Not a task list.
  (**built**.)
- **Skill** — a registered, gated capability the agent discovers via its self-model. (**built**.)

---

## 4. Layer model

```
META   — reads construct, synthesises situation, generates DIRECTIVE, self-schedules
MACRO  — reads DIRECTIVE + goal tree, plans strategy + tasks, risk governor vets
TASK   — sequences RESEARCH/ANALYSIS/DECISION/EXECUTE/MONITOR/RESOLVE  (PLAN/TURNS planned)
EXEC   — skills: research, Polymarket, KB, probability; writes observations
WORKSPACE — the mental construct (file-backed, UI-editable)
HEARTBEAT — append-only store + dumb poll-and-fire scheduler + spawned_by lineage
```

### Concurrency

**Serial by default**, not parallel. OpenClaw itself serialises per session and backs it with a
file lock; littleman does the same (cross-process `SessionLock`) because the agent manages a
single shared wallet and parallel contexts could double-spend. Read-only research may fan out
within a session. The generational/parallel-context model from earlier drafts is **rejected**
for a single-operator agent (ADR 0001).

---

## 5. The turn cycle (as built)

```
WAKE      scheduler fires a due heartbeat → session starts with its context
SITUATE   load construct + world model → situation report
DIRECT    generate DIRECTIVE.md (the self-prompt that replaces human meta-cognition)
PLAN      strategy planner → goal-tree mutations + task specs   [PLAN.md/TURNS.md: planned]
EXECUTE   task tree runs serially; EXECUTE tasks are Kelly-sized and risk-governor-gated
REFLECT   append REFLECTION.md, update world model + SELF (calibration: planned)
SCHEDULE  self-scheduler writes the next heartbeat(s); cascade via spawned_by
END       mark heartbeat DONE, write the session row, narrate into the Main session
```

Every run — autonomous or manual — narrates itself into the **Main session**, the agent's own
chat context (OpenClaw-style), visible alongside ordinary user↔LLM chats.

---

## 6. Human / agent boundary

**Human provides:** `SOUL.md`, `SKILLS.md`, skill implementations, hard limits (risk/budget/
circuit breakers), construct templates, and the autonomous on/off decision.

**Agent owns:** PRIORITIES, MACRO_PLAN, SELF, DIRECTIVE, REFLECTION (+ planned docs), the
heartbeat schedule, the goal tree, and the knowledge base.

**Human does not provide:** the next task, the schedule, the research agenda, the
prioritisation, or the self-assessment.

**Hard limits are code, not prompts.** The risk governor returns ALLOW/VETO deterministically;
the LLM cannot reason around it.

---

## 7. Stack

Python 3.12+ · LiteLLM (provider-agnostic; Kimi/Anthropic/OpenAI/Ollama) · SQLite + aiosqlite
(WAL) · SQLAlchemy · httpx · FastAPI + React/TS frontend · pydantic-settings · uv. The
complexity lives in the cognition; the infrastructure stays boring.

---

## 8. Applications & onboarding

An **application** = `SOUL.md` (prime directive + domain knowledge) + a **skill pack** + optional
domain config. The same platform can run a research pipeline, an operations/triage monitor, a
content operation, a personal-ops agent, or a prediction-market trader — anywhere work is
ongoing and irregular and the agent must form its own view of what matters. **Polymarket trading
is the reference application** (`docs/applications/polymarket.md`), not the product.

### Onboarding (how an application is created)

A new instance is configured through onboarding, which produces the application artifacts. Two
paths, sharing a common first step:

1. **Shared welcome** (domain-agnostic): *what should we call you* (display name) → *what should
   we do* (the purpose/prime directive, free text) → *LLM provider → model*.
2. **Branch on details & constraints:**
   - **Guided** — a short questionnaire (objective & success criteria; operating constraints /
     red lines; autonomy & check-in cadence; and any domain config the purpose implies — e.g. a
     budget/wallet only if the purpose involves money). An LLM compiles the answers into a
     `SOUL.md` + initial limits, then runs **First Light**.
   - **Custom** — drops the power user straight into editing `SOUL.md` and config directly.

Onboarding is **not** Polymarket-specific: the purpose the user types determines what kind of
agent it is, and domain-specific questions (wallet, budget, risk) appear only when the purpose
warrants them. First Light (§3) then turns the resulting `SOUL.md` into the live mental
construct.

---

## 9. Open questions

- DB-backed construct + generational history (deferred; files suffice for one operator).
- Live order signing for Polymarket (planned — see the application doc).
- Calibration loop writing measured accuracy back into SELF (planned).
- Multi-instance coordination (out of scope until a real need exists).
