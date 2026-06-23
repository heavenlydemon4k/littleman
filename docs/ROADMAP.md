# Roadmap & status

Where littleman is, where development paused, and where it is going. Kept current as a single
source of truth for "what's done vs next".

---

## Current status (built and verified)

**Platform core**
- Wake/sleep model with self-authored **heartbeats**; dumb scheduler (poll + fire), gated by an
  **autonomous** toggle (off by default), with stale-session recovery + exponential-backoff retry.
- **Mental construct** (PRIORITIES / MACRO_PLAN / SELF / DIRECTIVE / REFLECTION) that is read at
  the start of every wake and **maintained at the end** (priorities re-ranked) — a living memory,
  not a snapshot.
- **Turn cycle**: reconcile → situate → directive → strategy/tasks → ReAct skill execution →
  reflect → maintain → self-schedule.
- **Skill registry** (22 skills) with requirement gating + on-demand `read_skill_doc`; the agent
  reads/writes its own files via construct skills.
- **LLM provider abstraction** (LiteLLM): real (Kimi/Anthropic/OpenAI/OpenRouter/Ollama) or a
  deterministic fake for tests; runtime model/mode editable live in the UI.
- **Cross-process session lock**; serial execution (ADR 0001).
- **Keyless web search** (DuckDuckGo; Tavily if keyed).

**Onboarding & First Light**
- Compulsory first-run onboarding: shared welcome (name → purpose → provider/model) → guided
  questionnaire or custom → answers richly compiled into `SOUL.md`.
- **Agentic First Light**: the agent reads `AGENT.md` (operating manual) + `SOUL.md` + onboarding
  answers and authors its own construct, then greets the operator in chat (a button, not a field,
  with live status). Deterministic safety net guarantees a usable construct.

**Frontend**
- Onboarding flow, chat (Main agent session + user chats, thinking/skills toggles, stop/rename),
  agent dashboard (status, connections, heartbeats, sessions, construct, controls), workspace
  editor, settings (LLM runtime + monochrome-default customizable theme).

**Polymarket reference application**
- Live market reads (scan/market/orderbook/resolution) and **read-only** wallet reconcile (real
  pUSD balance + positions, no spend).

**Tests:** 65 passing. Verified live against Kimi where noted.

---

## Where development paused

Paused after making the mental workspace *living* (the MAINTAIN step + continuous onboarding via
`WORKSPACE_CORE`). The immediate next item under discussion was extending the construct with
`CALENDAR.md` (which feeds self-scheduling) and having MAINTAIN also update `SELF.md` from
calibration. See `docs/design/mental-workspace-lifecycle.md` §4 for the agreed expansion order.

---

## Next (forward plan)

Near-term, in rough priority:

1. **`CALENDAR.md`** in the construct lifecycle — the agent records upcoming events/closes and
   the self-scheduler reads it, tying the workspace directly to heartbeat scheduling.
2. **MAINTAIN → SELF.md** — conditionally update the self-model/calibration each wake, not just
   priorities.
3. **`EXPOSURE.md`** — a readable risk map mirroring the world model for the agent to reason over.
4. **Custom-path self-config skill** (`update_self`) — so custom onboarding genuinely writes the
   operator's `SOUL.md` through conversation.
5. **Turn cycle PLAN.md → TURNS.md** — the N-turn execution window from the architecture meta.
6. **OpenClaw `SKILL.md` filesystem loader** — marketplace-compatible skills beyond the built-in
   Python registry.

Longer-term / deliberately deferred:

- **Live Polymarket order signing** (the one money-moving stub) — needs a funded signing wallet +
  `py-clob-client-v2`; gated behind the risk governor and autonomous toggle. Plan in
  `docs/applications/polymarket.md`.
- Remaining expanded docs (HYPOTHESES / BLOCKERS / SKILL_NOTES) when the agent's behaviour shows
  it needs them.
- Calibration loop writing measured accuracy back into SELF over many resolved outcomes.

---

## Non-goals (for now)

- Generational/parallel-context state (ADR 0001) — serial execution protects a single wallet.
- Multi-instance coordination — single-operator until a real need exists.
- A second application — the application contract is extracted only when a second concrete one
  is built (ADR 0002).
