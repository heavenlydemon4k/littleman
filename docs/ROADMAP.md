# Roadmap & status

Where littleman is, where development paused, and where it is going. Kept current as a single
source of truth for "what's done vs next".

---

## ⚑ Recent handoff (CALENDAR.md + SELF.md maintenance — DONE)

Built, tested (78 green), committed on `feat/live-action-feed`.

**What this pass changed:**

- `workspace/construct/CALENDAR.template.md` (new) — the agent's upcoming-events calendar;
  includes format instructions and maintenance rules (most imminent first, prune past entries).
- `littleman/meta/construct.py` — added `CALENDAR.md` to `OVERWRITE_DOCS` and the `Construct`
  dataclass (`calendar: str` field); `load()` and `as_prompt_block()` updated accordingly.
- `littleman/llm/prompts.py` — added `CALENDAR_MAINTAIN_SYSTEM` and `SELF_MAINTAIN_SYSTEM`
  prompts; updated `WORKSPACE_CORE` and `HEARTBEAT_PLAN_SYSTEM` to reference CALENDAR.md.
- `littleman/meta/maintain.py` — now maintains three docs per wake:
  - `PRIORITIES.md` (always, was already done)
  - `CALENDAR.md` (always — prune past events, add newly discovered ones)
  - `SELF.md` (conditionally — only when failures or bets placed, gated on `NO_UPDATE` signal)
- `littleman/meta/planner.py` — LLM refinement step now receives CALENDAR.md content so
  agent-discovered events can produce heartbeats beyond the deterministic cascade.
- `littleman/agent/session.py` — passes a world model snapshot to `maintain_construct()` so
  CALENDAR.md can track open positions and watched markets.
- `littleman/skills/construct_skills.py` — `read_construct` and `write_construct` now include
  `CALENDAR.md` in their doc mappings.
- `workspace/AGENT.md` §3 — added CALENDAR.md row to the workspace table; updated the "read
  at start of every wake" rule to include it.
- `tests/test_construct.py` — 4 new CALENDAR tests (is_overwrite_doc, write/load, in prompt
  block, excluded from selective block); 11 passing.
- `tests/test_hardening.py` — `_construct()` helper updated to include `calendar=""`.

**Verified facts:**
- `78 tests passing` (was 65 before the live-action-feed pass, now includes both passes).
- `construct.is_initialised()` now requires CALENDAR.md to exist (alongside the original 4).
- SELF.md is updated at most once per wake, only when there is genuine signal; idle wakes
  leave it untouched.

---

## Current status (built and verified)

**Platform core**
- Wake/sleep model with self-authored **heartbeats**; dumb scheduler (poll + fire), gated by an
  **autonomous** toggle (off by default), with stale-session recovery + exponential-backoff retry.
- **Mental construct** (PRIORITIES / MACRO_PLAN / SELF / CALENDAR / DIRECTIVE / REFLECTION) that
  is read at the start of every wake and **maintained at the end** — a living memory, not a
  snapshot: priorities re-ranked, calendar refreshed, and self-model conditionally updated.
- **Turn cycle**: reconcile → situate → directive → strategy/tasks → ReAct skill execution →
  reflect → maintain (PRIORITIES + CALENDAR + SELF) → self-schedule.
- **Skill registry** (22 skills) with requirement gating + on-demand `read_skill_doc`; the agent
  reads/writes its own files via construct skills (including CALENDAR.md).
- **LLM provider abstraction** (LiteLLM): real (Kimi/Anthropic/OpenAI/OpenRouter/Ollama) or a
  deterministic fake for tests; runtime model/mode editable live in the UI.
- **Cross-process session lock**; serial execution (ADR 0001).
- **Keyless web search** (DuckDuckGo; Tavily if keyed).

**Onboarding & First Light**
- Compulsory first-run onboarding: shared welcome (name → purpose → provider/model) → guided
  questionnaire or custom → answers richly compiled into `SOUL.md`.
- **Agentic First Light**: the agent reads `AGENT.md` + `SOUL.md` + onboarding answers and
  authors its own construct (incl. CALENDAR.md), then greets the operator in chat.

**Frontend**
- Onboarding flow, chat, agent dashboard, workspace editor, settings (LLM runtime + theme).
- Live action feed (`feat/live-action-feed` branch): DB-based pub/sub between scheduler and API;
  `ActivityFeed.tsx` + `useActivity.ts` consuming `/api/agent/activity/ws`.

**Polymarket reference application**
- Live market reads (scan/market/orderbook/resolution) and read-only wallet reconcile.

**Tests:** 78 passing.

---

## Where development paused

Paused after completing the CALENDAR.md + SELF.md maintenance additions (items 1 and 2 from the
forward plan). The construct is now a genuinely living workspace: priorities, calendar, and
self-model all update each wake; the self-scheduler reads CALENDAR.md for agent-discovered events.

Push still pending: local branch `feat/live-action-feed` is ahead of `origin/main`. Run:
```
git push -u origin feat/live-action-feed
git checkout main && git merge feat/live-action-feed --ff-only && git push origin main
```

---

## Next (forward plan)

Near-term, in rough priority:

1. **`EXPOSURE.md`** — a readable risk map mirroring the world model (open positions, exposure,
   drawdown) for the agent to reason over during the directive/strategy step.
2. **Custom-path self-config skill** (`update_self`) — so custom onboarding genuinely writes the
   operator's `SOUL.md` through conversation; gated to the custom onboarding path.
3. **Turn cycle PLAN.md → TURNS.md** — the N-turn execution window from the architecture meta;
   lets the agent track multi-turn task state explicitly.
4. **OpenClaw `SKILL.md` filesystem loader** — marketplace-compatible skills beyond the built-in
   Python registry; loads from `workspace/skills/*.md` + matching Python modules.

Longer-term / deliberately deferred:

- **Live Polymarket order signing** — needs a funded signing wallet + `py-clob-client-v2`;
  gated behind the risk governor and autonomous toggle.
- Remaining expanded docs (HYPOTHESES / BLOCKERS / SKILL_NOTES) when the agent's behaviour
  shows it needs them.
- Calibration loop writing measured accuracy back into SELF over many resolved outcomes.

---

## Non-goals (for now)

- Generational/parallel-context state (ADR 0001) — serial execution protects a single wallet.
- Multi-instance coordination — single-operator until a real need exists.
- A second application — the application contract is extracted only when a second concrete one
  is built (ADR 0002).
