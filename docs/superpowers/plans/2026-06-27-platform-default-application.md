# Platform Default Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `littleman.platform` a usable general-purpose autonomous assistant by adding a `PlatformApplication` class, generic platform skills, application-specific First Light context, lazy Polymarket loading, and updating the agent workspace files.

**Architecture:** Extend the existing `Application` protocol with a `first_light_context()` hook so each application provides its own bootstrap context. Add a new built-in `PlatformApplication` that registers only generic skills and returns domain-agnostic context. Convert the unconditional Polymarket import in `build_registry()` into lazy registration. Update `SOUL.md`, `AGENT.md`, and `SKILLS.md` to read as platform-first rather than trading-first.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), React/TypeScript frontend, pytest.

## Global Constraints

- All new code must be type-annotated where the surrounding code is typed.
- All new public functions/classes must have docstrings.
- Every task that changes behavior must include or update a test.
- Default config must remain `active_application = "littleman.platform"`.
- Polymarket modules must not be imported when the platform default is active.
- Frontend changes must leave `npm run build` clean.
- Follow existing code style: black-compatible formatting, `from __future__ import annotations`, explicit imports.

---

## Task 1: Extend Application protocol with `first_light_context()`

**Files:**
- Modify: `littleman/applications/__init__.py`
- Test: `tests/test_applications.py` (create if missing)

**Interfaces:**
- Consumes: nothing new.
- Produces: `Application.first_light_context(self) -> dict[str, Any]` (async) with default `{}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_applications.py`:

```python
import pytest

from littleman.applications import Application, get_active_application


class StubApp(Application):
    name = "stub"

    def is_configured(self):
        return True

    def register_skills(self, registry, db_session_factory=None):
        pass

    async def reconcile(self, db):
        return {}

    async def execute(self, ctx, node):
        return {}

    def dashboard_status(self):
        return {}

    def root_goal(self):
        return {"title": "stub", "rationale": "stub"}


@pytest.mark.asyncio
async def test_application_first_light_context_defaults_to_empty():
    app = StubApp()
    assert await app.first_light_context() == {}


def test_load_application_returns_platform_by_default():
    app = get_active_application()
    assert app is not None
    assert app.name == "littleman.platform"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_applications.py -v`

Expected: FAIL — `first_light_context` not on protocol / `PlatformApplication` not registered.

- [ ] **Step 3: Add protocol method with default implementation**

Modify `littleman/applications/__init__.py`:

```python
async def first_light_context(self) -> dict[str, Any]:
    """Return application-specific context injected into First Light.

    The platform default returns generic context; domain applications (e.g. Polymarket)
    return their own external-state snapshot.
    """
    return {}
```

Add it to the `Application` protocol.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_applications.py -v`

Expected: PASS for `test_application_first_light_context_defaults_to_empty`; `test_load_application_returns_platform_by_default` may still fail until Task 2.

- [ ] **Step 5: Commit**

```bash
git add littleman/applications/__init__.py tests/test_applications.py
git commit -m "feat(applications): add first_light_context hook to Application protocol"
```

---

## Task 2: Create and register `PlatformApplication`

**Files:**
- Create: `littleman/applications/platform/__init__.py`
- Create: `littleman/applications/platform/app.py`
- Modify: `littleman/applications/__init__.py`
- Test: `tests/test_applications.py`

**Interfaces:**
- Consumes: `Application` protocol, `register_builtin`.
- Produces: `PlatformApplication` class with `name = "littleman.platform"` and all protocol methods.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_applications.py`:

```python
def test_platform_application_loads_by_default():
    app = get_active_application()
    assert app is not None
    assert app.name == "littleman.platform"
    assert app.is_configured() is True


@pytest.mark.asyncio
async def test_platform_application_first_light_context_is_generic():
    app = get_active_application()
    ctx = await app.first_light_context()
    assert "wallet_balance_usdc" not in ctx
    assert "open_positions" not in ctx
    assert "active_application" in ctx


- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_applications.py::test_platform_application_loads_by_default -v`

Expected: FAIL — no builtin registered for `littleman.platform`.

- [ ] **Step 3: Implement PlatformApplication**

Create `littleman/applications/platform/__init__.py`:

```python
from littleman.applications.platform.app import PlatformApplication

__all__ = ["PlatformApplication"]
```

Create `littleman/applications/platform/app.py`:

```python
"""Default platform application — a general-purpose autonomous assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from littleman.applications import Application, register_builtin
from littleman.config import settings


class PlatformApplication(Application):
    """A domain-agnostic assistant application. It is always configured and registers only
    generic platform skills."""

    name = "littleman.platform"

    def is_configured(self) -> bool:
        return True

    def register_skills(
        self,
        registry: Any,
        db_session_factory: Any | None = None,
    ) -> None:
        from littleman.skills.platform import make_platform_skills

        for skill in make_platform_skills(db_session_factory):
            registry.register(**skill)

    async def reconcile(self, db: Any) -> dict[str, Any]:
        return {}

    async def execute(self, ctx: Any, node: Any) -> dict[str, Any]:
        return {"status": "NOOP", "reason": "Platform default has no EXECUTE semantics"}

    def dashboard_status(self) -> dict[str, Any]:
        return {
            "name": "platform",
            "ok": True,
            "detail": f"Running littleman.platform (provider: {settings.llm_primary_model})",
        }

    def root_goal(self) -> dict[str, str]:
        return {
            "title": "Be a helpful, autonomous assistant to the operator",
            "rationale": (
                "Persist what matters, schedule follow-ups, research when useful, and stay "
                "within the operator's guidance."
            ),
        }

    async def first_light_context(self) -> dict[str, Any]:
        return {
            "active_application": self.name,
            "provider": settings.llm_primary_model,
            "utc_now": datetime.now(timezone.utc).isoformat(),
        }


register_builtin("littleman.platform", lambda: PlatformApplication())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_applications.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add littleman/applications/platform/ littleman/applications/__init__.py tests/test_applications.py
git commit -m "feat(applications): add PlatformApplication as default built-in"
```

---

## Task 3: Add generic platform skills

**Files:**
- Create: `littleman/skills/platform.py`
- Test: `tests/test_platform_skills.py`

**Interfaces:**
- Consumes: `littleman.heartbeat.store.create_heartbeat`, KB read/write functions.
- Produces: `make_platform_skills(db_session_factory) -> list[dict[str, Any]]` returning skill definitions for `set_reminder`, `take_note`, `read_notes`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_platform_skills.py`:

```python
import pytest

from littleman.skills.platform import make_platform_skills


def test_platform_skill_names():
    skills = {s["name"] for s in make_platform_skills(lambda: None)}
    assert "set_reminder" in skills
    assert "take_note" in skills
    assert "read_notes" in skills


@pytest.mark.asyncio
async def test_take_note_and_read_notes(db):
    from littleman.skills.registry import build_registry

    registry = build_registry(lambda: db)
    await registry.dispatch("take_note", {"topic": "ideas", "content": "build platform default"})
    result = await registry.dispatch("read_notes", {"topic": "ideas"})
    assert "build platform default" in str(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_platform_skills.py -v`

Expected: FAIL — `littleman.skills.platform` does not exist.

- [ ] **Step 3: Implement platform skills**

Create `littleman/skills/platform.py`:

```python
"""Generic platform skills available to the default littleman.platform application."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def make_platform_skills(
    db_session_factory: Callable[[], Any] | None = None,
) -> list[dict[str, Any]]:
    """Return skill definitions for the platform default application."""
    from littleman.heartbeat import store
    from littleman.skills.kb import make_kb_skills

    kb_factory = db_session_factory or (lambda: None)
    kb_skills = {s["name"]: s["fn"] for s in make_kb_skills(kb_factory)}
    write_to_kb = kb_skills["write_to_kb"]
    read_from_kb = kb_skills["read_from_kb"]
    search_kb = kb_skills["search_kb"]

    async def set_reminder(title: str, fire_at: str, reason: str | None = None) -> dict[str, Any]:
        """Schedule a future heartbeat reminder."""
        fire_dt = _parse_iso_datetime(fire_at)
        factory = db_session_factory or (lambda: None)
        async with factory() as db:
            hb = await store.create_heartbeat(
                db,
                fire_at=fire_dt,
                reason=reason or title,
                session_type="FULL_CYCLE",
                context={"reminder_title": title},
                spawned_by=None,
            )
            return {"heartbeat_id": hb.id, "fire_at": hb.fire_at.isoformat()}

    async def take_note(
        topic: str,
        content: str,
        source_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """Persist a general note to the knowledge base."""
        return await write_to_kb(
            topic=topic,
            content=content,
            source_urls=source_urls or [],
            confidence="HIGH",
        )

    async def read_notes(topic: str | None = None, query: str | None = None) -> dict[str, Any]:
        """Read notes by topic or full-text query."""
        if topic:
            return await read_from_kb(topic)
        if query:
            return await search_kb(query)
        return {"entries": []}

    return [
        {
            "name": "set_reminder",
            "fn": set_reminder,
            "description": "Schedule a future reminder. fire_at is an ISO 8601 datetime.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "fire_at": {"type": "string", "format": "date-time"},
                    "reason": {"type": "string"},
                },
                "required": ["title", "fire_at"],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
        {
            "name": "take_note",
            "fn": take_note,
            "description": "Save a note to the knowledge base under a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "content": {"type": "string"},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["topic", "content"],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
        {
            "name": "read_notes",
            "fn": read_notes,
            "description": "Read notes by topic or search query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": [],
            },
            "cost": "LOW",
            "chat_safe": True,
        },
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_platform_skills.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add littleman/skills/platform.py tests/test_platform_skills.py
git commit -m "feat(skills): add generic platform skills (reminder, notes)"
```

---

## Task 4: Make Polymarket import lazy and add its `first_light_context()`

**Files:**
- Modify: `littleman/applications/polymarket/__init__.py`
- Modify: `littleman/applications/polymarket/app.py`
- Modify: `littleman/skills/registry.py`
- Test: `tests/test_applications.py`, `tests/test_registry.py` (create if missing)

**Interfaces:**
- Consumes: `register_builtin` from `littleman.applications`.
- Produces: Polymarket self-registers when its module is first imported; `build_registry()` no longer imports it unconditionally.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_applications.py`:

```python
@pytest.mark.asyncio
async def test_polymarket_first_light_context_has_finance(monkeypatch):
    monkeypatch.setattr("littleman.config.settings.active_application", "Polymarket trading")
    app = get_active_application()
    assert app is not None
    assert app.name == "Polymarket trading"
    ctx = await app.first_light_context()
    assert "wallet_balance_usdc" in ctx
    assert "budget_usdc" in ctx
```

Create `tests/test_registry.py`:

```python
def test_platform_mode_does_not_import_polymarket(monkeypatch):
    import sys

    # Ensure Polymarket modules are not loaded after building the registry in platform mode.
    monkeypatch.setattr("littleman.config.settings.active_application", "littleman.platform")
    from littleman.skills.registry import build_registry
    from littleman.db.connection import AsyncSessionLocal

    build_registry(AsyncSessionLocal)
    assert "littleman.applications.polymarket" not in sys.modules
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_applications.py::test_polymarket_first_light_context_has_finance tests/test_registry.py -v`

Expected: FAIL — Polymarket not registered / `first_light_context` not implemented.

- [ ] **Step 3: Move Polymarket registration into the application module**

Modify `littleman/applications/polymarket/__init__.py`:

```python
"""Polymarket prediction-market trading application for the littleman platform."""

from littleman.applications import register_builtin
from littleman.applications.polymarket.app import PolymarketApplication

register_builtin("Polymarket trading", lambda: PolymarketApplication())

__all__ = ["PolymarketApplication"]
```

Modify `littleman/applications/polymarket/app.py`:

Add `first_light_context()` to `PolymarketApplication`:

```python
async def first_light_context(self) -> dict[str, Any]:
    from littleman.db.connection import AsyncSessionLocal
    from littleman.meta.world_model import WorldModelManager

    async with AsyncSessionLocal() as db:
        state = await WorldModelManager(db).load()
        return {
            "wallet_balance_usdc": state.wallet_balance_usdc,
            "available_balance_usdc": state.available_balance_usdc,
            "open_positions": len(state.open_positions),
            "budget_usdc": settings.budget_usdc,
        }
```

Modify `littleman/skills/registry.py`:

Remove the unconditional `import littleman.applications.polymarket` and rely on lazy loading:

```python
# Import built-in applications so they register themselves.
import littleman.applications.platform  # noqa: F401
```

Keep only the platform import; Polymarket self-registers when `load_application("Polymarket trading")` imports its module.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_applications.py tests/test_registry.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add littleman/applications/ littleman/skills/registry.py tests/test_applications.py tests/test_registry.py
git commit -m "feat(applications): lazy Polymarket loading and app-specific First Light context"
```

---

## Task 5: Wire `first_light_context()` into First Light

**Files:**
- Modify: `littleman/meta/first_light.py`
- Test: `tests/test_first_light.py` (update or create)

**Interfaces:**
- Consumes: `Application.first_light_context()`.
- Produces: First Light uses `external_state = await app.first_light_context()` if an app is active.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_first_light.py` (create if it doesn't exist):

```python
import pytest


@pytest.mark.asyncio
async def test_first_light_uses_application_context(db, monkeypatch):
    monkeypatch.setattr("littleman.config.settings.active_application", "littleman.platform")
    monkeypatch.setattr("littleman.llm.runtime.active", lambda: {"mode": "fake"})
    from littleman.meta.first_light import run

    result = await run(db)
    assert result["first_light"] == "complete"
    assert result["mode"] == "fake"
    # The bootstrap directive should not contain financial context in platform mode.
    assert "USDC" not in result["bootstrap_directive"].get("financial_context", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_first_light.py::test_first_light_uses_application_context -v`

Expected: FAIL — `first_light.py` hard-codes trading context.

- [ ] **Step 3: Update First Light to use application context**

Modify `littleman/meta/first_light.py` around the `external_state` construction:

```python
from littleman.applications import get_active_application

wm = WorldModelManager(db)
state = await wm.load()

app = get_active_application()
if app is not None:
    external_state = await app.first_light_context()
else:
    external_state = {}
```

Remove the hard-coded trading fields.

Also update the bootstrap directive to remove the financial context string when in platform mode. Replace:

```python
"financial_context": f"Budget {settings.budget_usdc:.2f} USDC.",
```

with:

```python
"financial_context": (
    f"Budget {settings.budget_usdc:.2f} USDC."
    if settings.active_application == "Polymarket trading"
    else "No application-specific financial context."
),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_first_light.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add littleman/meta/first_light.py tests/test_first_light.py
git commit -m "feat(first_light): use active application's first_light_context"
```

---

## Task 6: Update workspace `SOUL.md`

**Files:**
- Modify: `workspace/SOUL.md`

**Interfaces:**
- No code interfaces; this is a content change read by the agent.

- [ ] **Step 1: Replace SOUL.md content**

Modify `workspace/SOUL.md` to the domain-agnostic identity from the design spec:

```markdown
# SOUL — Littleman Agent Identity

## Mission

You are Littleman, an autonomous agent running on the littleman platform. Your goal is to help the operator pursue their goals autonomously: research what matters, remember what you learn, schedule your own follow-ups, and act within the operator's stated limits.

You operate without ongoing human direction. You plan your own work, your own schedule, and your own next actions. When you finish a session, you leave behind a schedule of future sessions that the runtime will fire at the right times.

---

## Operating Principles

**Form your own intent.** Each wake, derive what you should do from your construct, your operator's guidance, and any heartbeat context. Do not wait to be told the next step.

**Be economical.** A wake costs tokens; sleep costs nothing. Do the work this wake is for, not everything imaginable. If work belongs later, schedule a heartbeat for it.

**Persist what matters.** Knowledge, priorities, plans, and lessons learned should be written to your construct or knowledge base. What you do not write down is lost when you sleep.

**Calibrate yourself.** When you make a prediction or judgment and later learn the outcome, record it. Honest records of what you believed before an outcome are what make you calibrated over time.

**Schedule your own continuity.** At the end of every session, schedule the sessions you need in the future. If you committed to a deadline, schedule a check-in. If you found something worth following up, schedule research. If there is nothing time-bound, schedule an idle maintenance wake. Do not rely on external triggers.

---

## Application Note

The operator may activate a domain-specific application (for example, Polymarket trading) that adds concrete goals and hard limits. When such an application is active, its constraints and objectives take precedence for its domain. In platform default mode, your role is the general-purpose assistant described above.

---

## Calibration Notes

*This section is updated by the agent over time. Initially empty.*

---

## Operator-Provided Constraints

The operator provides your identity, your skills, and any hard limits during onboarding. Respect those limits as final. If a limit is enforced in code, a veto is final — adjust your plan rather than reasoning around it.
```

- [ ] **Step 2: Verify no Polymarket references remain**

Run: `grep -i "polymarket\|usdc\|bet\|position\|wallet" workspace/SOUL.md`

Expected: No matches.

- [ ] **Step 3: Commit**

```bash
git add workspace/SOUL.md
git commit -m "docs(workspace): rewrite SOUL.md as platform-default assistant identity"
```

---

## Task 7: Update workspace `AGENT.md`

**Files:**
- Modify: `workspace/AGENT.md`

**Interfaces:**
- No code interfaces; content change read by the agent.

- [ ] **Step 1: Replace trading examples and hard-limit framing**

In `workspace/AGENT.md`:

- §3: change examples from "a position to check" / "a market closing" to "a deadline the operator mentioned" / "a research thread to follow up on".
- §6: change scheduling examples similarly.
- §7: update the hard-limits paragraph to:

```markdown
**Hard limits are enforced in code, not by these instructions.** The active application, if any, provides concrete hard limits (for example, budget or exposure caps). Those limits are checked deterministically before any action that would violate them, and such actions are vetoed regardless of your reasoning. The platform default has no application-specific hard limits beyond the operator's guidance and the autonomous toggle.
```

- [ ] **Step 2: Verify examples are domain-agnostic**

Run: `grep -i "market\|bet\|position\|wallet\|usdc" workspace/AGENT.md`

Expected: No matches except possibly in historical references; clean if any are found.

- [ ] **Step 3: Commit**

```bash
git add workspace/AGENT.md
git commit -m "docs(workspace): make AGENT.md examples domain-agnostic"
```

---

## Task 8: Update workspace `SKILLS.md`

**Files:**
- Modify: `workspace/SKILLS.md`

**Interfaces:**
- No code interfaces; content change read by the agent.

- [ ] **Step 1: Restructure into Platform vs Application sections**

Rewrite `workspace/SKILLS.md`:

```markdown
# SKILLS — Available Capabilities

This file documents skills available to the agent. Platform skills are always available when running the default `littleman.platform` application. Application skills are available only when a domain-specific application (e.g. Polymarket trading) is active.

---

## Platform skills (always available)

### Research

#### `web_search(query, source_filters=None, max_results=10)`
Search the web and return structured results (title, url, excerpt, date, source).

#### `browse_url(url)`
Fetch and parse the text content of a specific URL.

#### `aggregate_research(topic, depth="standard")`
Run multiple searches on a topic and return a deduplicated summary.

### Knowledge Base

#### `write_to_kb(topic, content, source_urls=None, confidence="MEDIUM", expires_hours=None)`
Persist research findings or notes to the knowledge base.

#### `read_from_kb(topic)`
Retrieve stored knowledge on a topic.

#### `search_kb(query)`
Full-text search across KB entries.

### Notes and Reminders

#### `take_note(topic, content, source_urls=None)`
Save a general note under a topic.

#### `read_notes(topic=None, query=None)`
Read notes by topic or full-text query.

#### `set_reminder(title, fire_at, reason=None)`
Schedule a future heartbeat reminder. `fire_at` is an ISO 8601 datetime.

### Mental Construct

#### `read_construct(name)` / `write_construct(name, content)`
Read or write a construct document.

#### `append_reflection(entry)`
Append an entry to the append-only REFLECTION.md.

### Scheduling

#### `create_heartbeat(fire_at, reason, session_type, context)`
Schedule a future session.

#### `amend_heartbeat(heartbeat_id, ...)`
Modify a scheduled heartbeat.

#### `cancel_heartbeat(heartbeat_id, reason)`
Cancel a scheduled heartbeat.

#### `list_scheduled_heartbeats()`
List scheduled heartbeats.

### Estimation and Reflection

#### `estimate_probability(market_id, evidence_summary, ...)`
Structured probability estimation.

#### `record_prediction_outcome(...)` / `get_calibration_summary()`
Record resolved predictions and view calibration stats.

---

## Application skills (Polymarket trading only)

The following skills are available only when `active_application = "Polymarket trading"`:

### `scan_markets(...)`
### `get_market(market_id)`
### `get_orderbook(market_id)`
### `get_position(position_id)`
### `check_resolution(market_id)`
### `place_bet(market_id, direction, size_usdc, max_price=None)`

See the Polymarket application documentation for details.
```

- [ ] **Step 2: Commit**

```bash
git add workspace/SKILLS.md
git commit -m "docs(workspace): restructure SKILLS.md into platform vs application skills"
```

---

## Task 9: Frontend dashboard active application display

**Files:**
- Modify: `frontend/src/pages/AgentPage.tsx`
- Modify: `frontend/src/lib/api.ts` if agent status shape changed.

**Interfaces:**
- Consumes: `/api/agent/status` response, which already includes `application` per `littleman/api/routes/agent.py`.
- Produces: UI renders active application name and a platform status card when not Polymarket.

- [ ] **Step 1: Locate dashboard component**

Find the agent dashboard overview component using the existing UI structure. Read it to understand the current wallet/exposure cards.

- [ ] **Step 2: Add active application badge**

Add a small badge near the dashboard header showing `status.application`. No new API call needed.

- [ ] **Step 3: Conditionally render platform status card**

When `status.application !== "Polymarket trading"`, render a generic card:

```tsx
<Island>
  <h3>Platform</h3>
  <p>Active application: {status.application}</p>
  <p>Provider: {settings.llm_primary_model}</p>
</Island>
```

Hide or simplify the Polymarket wallet card in platform mode.

- [ ] **Step 4: Run frontend build**

Run: `cd frontend && npm run build`

Expected: Clean build.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AgentPage.tsx
git commit -m "feat(frontend): show active application and platform status card"
```

---

## Task 10: Update documentation and worklog

**Files:**
- Modify: `docs/META.md`
- Modify: `docs/ROADMAP.md`
- Modify: `worklog/2026-06-28.md`

**Interfaces:**
- None; documentation only.

- [ ] **Step 1: Update META.md**

In `docs/META.md` §2, ensure the mental workspace table reflects all current construct docs. Add a note that the default application is `littleman.platform` and Polymarket is opt-in.

- [ ] **Step 2: Update ROADMAP.md**

Add to "Built / current status":
- Platform default application with generic skills.
- Application protocol with `first_light_context()` hook.
- Lazy Polymarket loading.

Update test count if it changed.

- [ ] **Step 3: Update worklog**

Append to `worklog/2026-06-28.md`:

```markdown
## Platform default application

Made `littleman.platform` a real general-purpose autonomous assistant.

- Added `PlatformApplication` (`littleman/applications/platform/app.py`) as a built-in default.
- Added `Application.first_light_context()` hook; Polymarket provides financial snapshot, platform provides generic context.
- Converted unconditional Polymarket import in `build_registry()` to lazy loading.
- Added generic platform skills in `littleman/skills/platform.py`: `set_reminder`, `take_note`, `read_notes`.
- Updated `workspace/SOUL.md`, `workspace/AGENT.md`, and `workspace/SKILLS.md` to be platform-first.
- Updated dashboard to show active application and a platform status card.
- Tests: `tests/test_applications.py`, `tests/test_platform_skills.py`, `tests/test_registry.py`, `tests/test_first_light.py`.
```

- [ ] **Step 4: Commit**

```bash
git add docs/META.md docs/ROADMAP.md worklog/2026-06-28.md
git commit -m "docs: update platform status in META, ROADMAP, and worklog"
```

---

## Task 11: Final verification

**Files:**
- All of the above.

- [ ] **Step 1: Run full test suite**

Run: `.venv/Scripts/python -m pytest tests/ -q --tb=short`

Expected: All tests pass.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

Expected: Clean build.

- [ ] **Step 3: Verify lazy loading**

Run a quick check that `littleman.applications.polymarket` is not in `sys.modules` after building the registry in platform mode (already covered by `tests/test_registry.py`).

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final verification for platform default application"
```

---

## Self-Review Checklist

- [ ] Spec coverage: every design section has a corresponding task.
- [ ] No placeholders: all code blocks contain real implementation.
- [ ] Type consistency: `first_light_context` is async in protocol, platform app, and Polymarket app.
- [ ] Test coverage: platform app, skills, lazy loading, First Light context, registry behavior.
- [ ] Documentation: SOUL.md, AGENT.md, SKILLS.md, META.md, ROADMAP.md, worklog updated.
