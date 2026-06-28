# Roadmap & status

Where littleman is, where development paused, and where it is going. Kept current as a single
source of truth for "what's done vs next".

---

## ⚑ Recent handoff (live action feed + CALENDAR.md + SELF.md maintenance — DONE)

Built, tested (**84 green**), and **integrated onto `main`** (fast-forward; the feature
branches `feat/live-action-feed` and `feat/calendar-construct` were merged and removed). Frontend
tsc + production build clean.

### Live action feed (new)

Watch a wake act in real time. Because wakes run in a different process than the API/WS server
(`scheduler` vs `uvicorn`) and SQLite has no pub/sub, events are delivered **through the database**:

- `littleman/db/models.py` — new `AgentEvent` table (`seq`-ordered cursor; WAL lets a reader see
  another process's commits).
- `littleman/agent/events.py` — best-effort `emit()` bound to the active wake via a ContextVar
  (no-ops outside a wake / in chat / tests), plus `tail`/`recent` cursors and `prune` (keeps the
  last ~50 sessions).
- Emit points: `session.py` (`session_start`, coarse stage markers, `session_done` + prune,
  ContextVar cleared in `finally`); `skills/registry.py` `dispatch` (`tool_call`/`tool_result` —
  one chokepoint covers all tools/web search/file access); `agent/loop.py` (`reasoning`, the
  model's between-steps text).
- `api/routes/agent.py` — `GET /agent/activity` (backlog) + `WS /agent/activity/ws` (tails the
  table, fresh session per poll, ~0.75s latency).
- Frontend — `hooks/useActivity.ts` (WS + dedupe/reconnect), `components/activity/ActivityFeed.tsx`
  (minimized action rows that change as they run, expand arrow reveals reasoning + input + result,
  stage dividers, grouped per wake), rendered at the bottom of the **Main** session.
- Tests: `tests/test_events.py` (emit/tail/prune/dispatch + a full `run_session` integration
  asserting the event sequence and ContextVar cleanup).

### CALENDAR.md + SELF.md maintenance

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
- `84 tests passing` (65 baseline + the live-action-feed and CALENDAR/SELF passes).
- `construct.is_initialised()` checks `FIRST_LIGHT_DOCS` (PRIORITIES/MACRO_PLAN/SELF/DIRECTIVE) and
  intentionally **does not** require CALENDAR.md — so workspaces created before CALENDAR.md existed
  are not falsely treated as uninitialised and re-sent through First Light. CALENDAR.md is still an
  `OVERWRITE_DOCS` member (seeded, loaded, agent-writable); it just isn't part of the init gate.
- SELF.md is updated at most once per wake, only when there is genuine signal; idle wakes
  leave it untouched.
- The activity feed never fires the LLM: emission is best-effort DB writes, and the API/WS tail is
  read-only — consistent with the "idle = zero token spend" invariant.

---

## Current status (built and verified)

**Platform core**
- Wake/sleep model with self-authored **heartbeats**; dumb scheduler (poll + fire), gated by an
  **autonomous** toggle (off by default), with stale-session recovery + exponential-backoff retry.
- **Mental construct** (PRIORITIES / MACRO_PLAN / SELF / EXPOSURE / CALENDAR / DIRECTIVE /
  REFLECTION / HYPOTHESES / BLOCKERS / SKILL_NOTES) that is read at the start of every wake and
  **maintained at the end** — a living memory, not a snapshot: priorities re-ranked, exposure
  re-rendered from the world model, calendar refreshed, and self-model conditionally updated.
- **Construct storage modes**: file-backed by default; optional DB-backed (`ConstructDoc` rows are
  the source of truth, markdown files are rendered mirrors).
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

**Platform default application**
- Built-in default application `littleman.platform` with generic skills (`set_reminder`, `take_note`,
  `read_notes`) available in chat and wakes.
- Application protocol with `first_light_context()` hook so each application injects its own
  external-state snapshot into First Light (generic context for platform, financial snapshot for
  Polymarket).
- Lazy Polymarket loading: the Polymarket application and its skills are loaded only when
  `settings.active_application = "Polymarket trading"`; the default stack is trading-free.
- Tests: `tests/test_applications.py`, `tests/test_platform_skills.py`, `tests/test_registry.py`,
  `tests/test_first_light.py`.

**Polymarket reference application**
- Live market reads (scan/market/orderbook/resolution) and read-only wallet reconcile.

**Tests:** 156 passing.

---

## Where development paused

Paused after integrating the **platform default application** (`littleman.platform`) with its
generic skills, `first_light_context()` application hook, and lazy Polymarket loading — all now on
`main`. The stack is now application-agnostic by default; trading-specific code is loaded only when
the operator explicitly selects Polymarket trading.

Push still pending: `main` is ahead of `origin/main`. When ready:
```
git push origin main
```
Not yet done: a **live run** of the stack (uvicorn + scheduler + a real/fake wake) to watch the
dashboard and action feed render in the browser — verified by tests + build only so far.

---

## Next (forward plan)

Near-term, in rough priority:

0. **Chat app MVP + connector architecture** — new product direction captured in
   [`docs/CHAT_APP_MVP.md`](CHAT_APP_MVP.md). The target is a capable chat-first app where the
   assistant can explain and safely configure its own system, then connect to external apps
   through a connector registry with approval-gated side effects. This should happen before
   adding more one-off integrations.

1. **`EXPOSURE.md`** — ✅ DONE. A 7th construct doc: a readable risk map (capital, open exposure
   by category, drawdown from peak, circuit-breaker status, open positions). Resolved with
   operator as **deterministically rendered** (not LLM-authored) so figures can't drift, and
   written in `maintain_construct()` each wake (runs in fake mode too — no LLM).
   - `meta/exposure.py` `render_exposure(world_state)` — pure formatter, tolerant of partial
     snapshots; `meta/maintain.py` `_render_exposure()` writes it before the fake-mode gate.
   - New doc category `construct.RENDERED_DOCS` (agent-readable, never agent-written); threaded
     through `Construct.exposure`, `as_prompt_block`, `load()`, `write_doc` guard, `ALL_DOCS`
     (next to SELF.md), `WORKSPACE_CORE`, `construct_skills` read map, the dashboard route, and
     `AGENT.md`. Excluded from `FIRST_LIGHT_DOCS` (like CALENDAR.md) so old workspaces aren't
     re-onboarded. `session.py` enriches the world snapshot with balances/exposure/peak.
   - Frontend: an "Exposure" `AuthoredCard` on the Agent overview; the doc also lists generically.
   - Tests: `tests/test_exposure.py` (7 — figures, drawdown, breaker, empty/partial snapshot,
     fake-mode maintain integration, not-agent-writable). Suite **94 green**; frontend build clean.
2. **Custom-path self-config skill** (`update_self`) — so custom onboarding genuinely writes the
   operator's `SOUL.md` through conversation; gated to the custom onboarding path.
3. **Turn cycle PLAN.md → TURNS.md** — the N-turn execution window from the architecture meta;
   lets the agent track multi-turn task state explicitly.
4. **OpenClaw `SKILL.md` filesystem loader** — marketplace-compatible skills beyond the built-in
   Python registry; loads from `workspace/skills/*.md` + matching Python modules.
5. ✅ **Calibration loop** — see "Longer-term" note (promoted to built because it shipped).

**Chat-experience track** (operator-requested UX vision; piece #1 shipped above):

5. **Island aesthetic pass** — ✅ DONE. Extracted the repeated `rounded-xl border border-border
   bg-surface-*` look into a token-backed primitive:
   - `--island-radius` / `--island-shadow` tokens in `index.css`, exposed as Tailwind
     `rounded-island` / `shadow-island` (`tailwind.config.ts`).
   - `components/ui/Island.tsx` — a typed `<Island>` wrapper with `surface` (1/2), `floating`
     (drop shadow), and `interactive` (focus-within accent) variants.
   - Applied to the floating/tool surfaces only (deliberately not a reskin): the chat input bar +
     skills popover (`ChatInput.tsx`) and the activity feed groups + action rows
     (`ActivityFeed.tsx`).
   - Verified: tsc + production build clean; tokens resolve and utilities compile in a live preview
     (`rounded-island`→12px, `shadow-island`→defined). Full ChatInput/ActivityFeed visual render
     still wants the backend live-run reserved for operator go. Static page cards (settings/agent/
     onboarding) intentionally left for a later, wider pass.
6. **Elicitation surface** — ✅ DONE. LLM-asked questions are now first-class, and the composer
   morphs into the answer card. Forks resolved with operator: **input-morph** (not a separate
   card) and **LLM-generated** suggestions (not deterministic).
   - Structured ask: the model may end a chat reply with a fenced ` ```ask ` block
     (`CHAT_ELICITATION_GUIDE`, appended to the chat system prompt). `lib/elicitation.ts`
     `parseAsk()` splits prose (→ bubble) from the ask (→ composer); malformed blocks degrade to
     no-card. `ChatPage` derives the active (last, unanswered) elicitation; `ChatInput` morphs
     into a question header + option chips, free-text still allowed.
   - Suggestion bar: a 3rd **Suggest** toggle beside Thinking/Skills (off by default, persisted).
     When on, `POST /chat/sessions/{id}/suggestions` returns 3 LLM-predicted prompts (routed
     through the provider abstraction → testable on the scripted fake). Fetched only on operator
     activity (open / after a turn), never on idle — preserves the zero-token invariant. Chips
     prefill the input (editable), not auto-send.
   - Tests: `tests/test_chat_suggestions.py` (3 — returns three, empty-session safe, degrades to
     `[]` on bad model output). Suite now **87 green**; frontend tsc + build clean.
   - **DONE.** User chat now has a tool-executing ReAct loop that persists tool results and
     streams them to the frontend. Chat tools are filtered to `chat_safe=True` skills as a
     safety gate. Full live render still wants the operator-go backend run.

Longer-term / deliberately deferred:

- **Live Polymarket order signing** — needs a funded signing wallet + `py-clob-client-v2`;
  gated behind the risk governor and autonomous toggle.
- ✅ **Expanded construct docs** — `HYPOTHESES.md`, `BLOCKERS.md`, and `SKILL_NOTES.md` are now
  first-class construct documents: templates, `Construct` fields, prompt order, `OVERWRITE_DOCS`
  membership, and LLM maintenance prompts in `maintain_construct()`. Tests:
  `tests/test_construct_docs.py` (8).
- ✅ **Calibration loop** — `CalibrationEntry` table records resolved predictions; Brier scores,
  confidence-bucket accuracy, and per-category summaries are rendered deterministically into the
  `Calibration` section of `SELF.md` each wake. Skills `record_prediction_outcome` and
  `get_calibration_summary` are available to chat and wakes. Tests: `tests/test_calibration.py`
  (6).
- ✅ **DB-backed construct** — optional `ConstructDoc` source-of-truth with file mirrors.
  `db_backed_construct = true` switches reads/writes to SQLite while keeping markdown files as
  rendered, human-inspectable copies. Existing file workspaces are imported on first startup.
  Tests: `tests/test_db_construct.py` (7).

---

## Non-goals (for now)

- Generational/parallel-context state (ADR 0001) — serial execution protects a single wallet.
- Multi-instance coordination — single-operator until a real need exists.
