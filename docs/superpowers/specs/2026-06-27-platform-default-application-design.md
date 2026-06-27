# Design — Platform Default Application

**Date:** 2026-06-27  
**Status:** Draft — pending operator review  
**Goal:** Make `littleman.platform` a usable general-purpose autonomous assistant so the platform works out-of-the-box without Polymarket. Polymarket becomes opt-in via `active_application = "Polymarket trading"`.

---

## Background

Littleman's architecture (ADR 0002) already separates the domain-agnostic **platform** from domain-specific **applications**. The Polymarket application was decoupled into `littleman/applications/polymarket/`, the OpenClaw-style filesystem skill loader exists, and `active_application` defaults to `littleman.platform`. However, the default platform application is effectively a no-op: there is no `PlatformApplication` class, the workspace `SOUL.md` still describes a Polymarket trading agent, and `AGENT.md` / `SKILLS.md` carry trading-specific examples. This makes the platform look like a trading product even when no trading application is active.

This design makes the default platform a real, useful application and cleans up the agent-facing workspace files.

---

## Non-goals

- **Application marketplace / installer UI.** Installing or switching applications remains a config change (`active_application` + `SOUL.md`). A marketplace is a later milestone.
- **Per-application workspace isolation.** All applications continue to share `workspace/construct/` and `workspace/SOUL.md`. Isolation is deferred until a second real application justifies it.
- **Multi-channel Gateway or sandboxing.** Out of scope per ADR 0002 and the OpenClaw comparison.
- **Generational/parallel state.** Serial execution and single-operator focus remain unchanged.

---

## Changes

### 1. Workspace identity — `workspace/SOUL.md`

Replace the Polymarket trading identity with a domain-agnostic autonomous assistant identity.

- **Mission:** Help the operator pursue their goals autonomously through research, memory, scheduling, and action within the operator's stated limits.
- **Operating principles:**
  - Form your own intent each wake.
  - Be economical with tokens and skill calls.
  - Persist what matters across wakes.
  - Calibrate your estimates when outcomes arrive.
  - Schedule your own future work.
- **Application note:** The operator may activate a domain-specific application (e.g. Polymarket trading) that adds concrete goals and hard limits. When active, that application's constraints take precedence for its domain.

Remove all Polymarket domain knowledge, market mechanics, category assessment, and financial risk constraints.

### 2. Operating manual — `workspace/AGENT.md`

`AGENT.md` is already largely platform-agnostic. Minor edits:

- Replace trading-flavored examples ("a position to check", "a market closing") with generic examples ("a deadline the operator mentioned", "a research thread to follow up").
- In §7, state that concrete hard limits are enforced by the active application, if any. The platform default only has operator guidance and the autonomous toggle.
- No structural changes to the wake/sleep model, construct lifecycle, turn cycle, or scheduling rules.

### 3. Capability inventory — `workspace/SKILLS.md`

Restructure into two sections so the agent's self-model matches what is actually registered:

- **Platform skills** (always available when running the platform default): web research, KB read/write, scheduling, construct read/write, workspace file discovery, calibration, probability estimation, skill docs.
- **Application skills** (only when `Polymarket trading` is active): Polymarket scan/orderbook/account/bet skills.

In code, skill registration is already conditional via the active application. The doc change makes this explicit to the agent.

### 4. `PlatformApplication` class

Create `littleman/applications/platform/app.py` implementing the existing `Application` protocol:

| Method | Behavior |
|---|---|
| `name` | `"littleman.platform"` |
| `is_configured()` | Always returns `True`. |
| `register_skills(registry, db_session_factory)` | Registers generic platform skills from `littleman.skills.platform`. Does not register Polymarket or risk-governed skills. |
| `reconcile(db)` | No-op (returns `{}`). |
| `execute(ctx, node)` | Generic EXECUTE handler: records an observation/intent in the DB without financial gating. Returns a dict describing what was attempted. |
| `dashboard_status()` | Returns platform health: active application name, model provider status, autonomous toggle state. |
| `root_goal()` | Returns a general assistant goal: "Be a helpful, autonomous assistant to the operator." |
| `first_light_context()` *(new protocol method)* | Returns generic context: current UTC time, active application, model provider, operator purpose from profile. |

Register the platform builtin in `littleman/applications/__init__.py`:

```python
from littleman.applications.platform.app import PlatformApplication
register_builtin("littleman.platform", lambda: PlatformApplication())
```

### 5. Generic platform skill pack — `littleman/skills/platform.py`

Lightweight skills that make the default platform useful:

- **`set_reminder(title, fire_at, reason=None)`** — wraps `create_heartbeat` for operator-requested reminders.
- **`take_note(topic, content, source_urls=None)`** — KB wrapper for general note-taking.
- **`read_notes(topic=None, query=None)`** — reads from KB by topic or full-text query.
- **`reflect_and_prioritize()`** *(optional)* — asks the agent to re-read PRIORITIES and append a reflection entry; useful when the platform has no app forcing a maintenance cycle.

These skills are chat-safe and gated only by the KB/scheduling infrastructure that already exists.

### 6. Application protocol extension — `first_light_context()`

Add a new optional method to the `Application` protocol:

```python
def first_light_context(self) -> dict[str, Any]: ...
```

Default implementation returns `{}`. `PlatformApplication` returns generic context. `PolymarketApplication` returns the financial snapshot currently hard-coded in `first_light.py` (`wallet_balance_usdc`, `available_balance_usdc`, `open_positions`, `budget_usdc`).

Update `littleman/meta/first_light.py` to call `app.first_light_context()` instead of hard-coding trading fields.

### 7. Lazy Polymarket import

Currently `build_registry()` does `import littleman.applications.polymarket` unconditionally. Change this so Polymarket code is loaded only when selected:

- Move the import into `load_application("Polymarket trading")` or an explicit registration hook inside `littleman/applications/polymarket/__init__.py`.
- Ensure the platform default never imports Polymarket modules.

### 8. Frontend / dashboard

Minimal changes:

- Show the active application name in the dashboard header/status area.
- When running the platform default, do not render the Polymarket wallet connection card; instead show a generic platform status card (model provider, autonomous toggle).
- If Polymarket is active, keep the existing wallet/exposure cards.

### 9. Tests

Create `tests/test_platform_default.py`:

- `test_platform_app_loads_by_default` — `get_active_application()` returns `PlatformApplication` with default config.
- `test_polymarket_skills_not_loaded_in_platform_mode` — registry built with platform active does not contain `polymarket_scan`, `place_bet`, etc.
- `test_platform_skills_present` — `set_reminder`, `take_note`, `read_notes` are present and available.
- `test_platform_first_light_context_is_generic` — no wallet/position/budget fields; contains `active_application` and `provider`.
- `test_polymarket_first_light_context_has_finance` — when Polymarket is active, context contains the financial snapshot.
- `test_dashboard_status_platform` — returns platform status, not wallet detail.

Update any existing tests that assume `active_application = "Polymarket trading"` or trading-specific First Light output.

---

## Verification

- Full test suite passes (target: baseline + new platform tests).
- Frontend `tsc` and production build clean.
- Running with default config does not import Polymarket modules.
- First Light succeeds in platform mode and produces a non-trading greeting.

---

## Open questions (none blocking)

- Should `PlatformApplication.execute` do anything beyond recording an observation? For now, no — the platform default delegates execution to skills; `execute` is a hook for future app-specific orchestration.
- Should we expose an application switcher in the UI? Not in this milestone; keep it config-driven.
