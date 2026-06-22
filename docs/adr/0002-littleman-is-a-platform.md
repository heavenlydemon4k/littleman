# ADR 0002 — Littleman is an agent platform; Polymarket is the first application

Status: Accepted
Date: 2026-06-22

## Context

Littleman was bootstrapped around a single goal — autonomous Polymarket trading — but the
architecture (mental construct, self-authored heartbeats, meta/macro/task layers, skill
registry, LLM-provider abstraction) is domain-agnostic. The owning intent is now explicit:
**littleman is an LLM-native autonomous agent platform, in the spirit of OpenClaw**, and
Polymarket trading is the first *application* that runs on it — not the product itself.

This ADR fixes the platform/application boundary so future work does not re-entangle them.

## Decision

### The platform (domain-agnostic core)

These are general and must not contain trading-specific logic:

- **Cognition**: the Mental Construct (`meta/construct.py`), First Light (`meta/first_light.py`),
  the meta layer (situation → directive), macro layer (strategy → tasks), task layer.
- **Autonomy**: the heartbeat store + dumb scheduler, the self-scheduler, the session
  orchestration and cross-process lock, the autonomous toggle.
- **Capabilities**: the skill registry + gating, the LLM provider/runtime, the ReAct loop.
- **Surfaces**: the chat + Main session, the workspace editor, the agent dashboard, settings.

### An application

An application is defined by three things the operator provides — no platform code changes:

1. **`SOUL.md`** — the prime directive, domain knowledge, values, and constraints.
2. **A skill pack** — the registered skills that give the agent its hands (for Polymarket:
   `skills/polymarket*.py`, `web_research.py`, `probability.py`).
3. **Optional domain config** — e.g. the risk governor's limits and budget for a trading app.

Swapping these three turns littleman into a different agent (research assistant, ops monitor,
content pipeline) without touching the platform. See ARCHITECTURE.md §"Domain Agnosticism".

### What stays trading-shaped, and why that's fine

The **risk governor**, **budget**, **positions/exposure**, and **world-model balance** are
currently financial. They remain because Polymarket is the live application; they are part of
the *trading application*, surfaced as the active app's view. A non-trading application simply
would not register them. We do NOT prematurely abstract them into a generic "resource governor"
— that is speculative until a second application needs it (boring-tools principle).

## Consequences

- Documentation leads with the platform; Polymarket lives under `docs/applications/`.
- The frontend frames Polymarket as the **active application**, not the whole product.
- New domain work goes into a skill pack + `SOUL.md`, never into the meta/macro/task core.
- The financial layer stays concrete until a second application justifies generalising it.

## Revisit if

- A second real application is built — at that point, extract the application contract
  (SOUL + skills + config) into an explicit `applications/<name>/` layout and generalise the
  resource/risk layer only as far as the two concrete cases require.
