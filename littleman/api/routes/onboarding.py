"""Onboarding — the compulsory first-run flow.

Slice 0 backend contract:
- GET  /onboarding/status   → is this instance onboarded? plus profile basics.
- POST /onboarding/welcome  → persist name + purpose; set the runtime LLM (provider/model/key).
- POST /onboarding/complete → compile a seed SOUL.md from the chosen path, mark onboarded, and
                              return the First-Light chat session to land on.

Onboarding is domain-agnostic: the *purpose* the user writes is what gives the agent its domain
(see docs/design/onboarding-and-ui.md). First Light itself (the compulsory waking run) is
triggered separately from the chat (a later slice).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.config import settings
from littleman.db.connection import get_db
from littleman.db.models import Profile

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


async def _get_profile(db: AsyncSession) -> Profile | None:
    result = await db.execute(select(Profile).where(Profile.id == 1))
    return result.scalar_one_or_none()


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    p = await _get_profile(db)
    onboarded = bool(p and p.onboarded_at)
    return {
        "onboarded": onboarded,
        "display_name": p.display_name if p else None,
        "purpose": p.purpose if p else None,
        "path": p.onboarding_path if p else None,
    }


class WelcomeBody(BaseModel):
    display_name: str
    purpose: str
    provider: str | None = None          # informational; model string carries the route
    model: str                            # full litellm model string, e.g. openai/moonshot-v1-128k
    secondary_model: str | None = None
    api_base: str | None = None
    api_key: str | None = None


@router.post("/welcome")
async def welcome(body: WelcomeBody, db: AsyncSession = Depends(get_db)):
    """Persist the shared-welcome answers and point the runtime at the chosen model."""
    p = await _get_profile(db)
    if p is None:
        p = Profile(id=1)
        db.add(p)
    p.display_name = body.display_name.strip()
    p.purpose = body.purpose.strip()
    await db.commit()

    # Point the live runtime at the selected model (UI-editable later in Settings).
    from littleman.llm import runtime

    override: dict = {"mode": "real", "primary_model": body.model}
    if body.secondary_model:
        override["secondary_model"] = body.secondary_model
    if body.api_base is not None:
        override["api_base"] = body.api_base
    if body.api_key:
        override["api_key"] = body.api_key
    runtime.set_override(override)

    return {"ok": True}


class CompleteBody(BaseModel):
    path: str                             # "guided" | "custom"
    answers: dict | None = None           # guided questionnaire answers


@router.post("/complete")
async def complete(body: CompleteBody, db: AsyncSession = Depends(get_db)):
    """Compile a seed SOUL.md, mark onboarded, and return the First-Light chat session."""
    p = await _get_profile(db)
    if p is None or not p.purpose:
        return {"ok": False, "error": "run /onboarding/welcome first"}

    p.onboarding_path = body.path
    p.answers = body.answers or {}
    p.onboarded_at = datetime.now(timezone.utc)
    await db.commit()

    soul = await _compile_soul(
        p.display_name or "the operator", p.purpose, body.path, body.answers or {}
    )
    soul_path = settings.workspace_dir / "SOUL.md"
    soul_path.parent.mkdir(parents=True, exist_ok=True)
    soul_path.write_text(soul, encoding="utf-8")

    # Designate a First-Light chat session for the agent's first activation.
    from littleman.agent.mainlog import MAIN_SESSION_ID, ensure_main

    await ensure_main(db)

    return {"ok": True, "path": body.path, "first_light_session_id": MAIN_SESSION_ID}


async def _compile_soul(name: str, purpose: str, path: str, answers: dict) -> str:
    """Compile SOUL.md from onboarding answers.

    Real mode: an LLM richly synthesizes a coherent identity from the answers. Fake mode or any
    failure: a deterministic template. The custom path skips the questionnaire, so its SOUL is a
    minimal stub the agent fleshes out conversationally via its self-config skill.
    """
    import json

    from littleman.llm import runtime

    if path == "custom" or runtime.active().get("mode") == "fake":
        return _compile_soul_template(name, purpose, path, answers)

    from littleman.llm.complete import complete_text
    from littleman.llm.prompts import SOUL_COMPILE_SYSTEM

    user = (
        f"Operator name: {name}\n"
        f"Stated purpose: {purpose}\n"
        f"Guided answers (JSON): {json.dumps(answers)}\n\n"
        "Write the SOUL.md now."
    )
    try:
        soul = await complete_text(SOUL_COMPILE_SYSTEM, user, tier="primary")
        soul = soul.strip()
        if soul.startswith("```"):
            soul = "\n".join(soul.splitlines()[1:])
            if soul.rstrip().endswith("```"):
                soul = soul.rstrip()[:-3]
        return soul.strip() or _compile_soul_template(name, purpose, path, answers)
    except Exception:  # noqa: BLE001 — never block onboarding on the LLM; fall back to template
        return _compile_soul_template(name, purpose, path, answers)


def _compile_soul_template(name: str, purpose: str, path: str, answers: dict) -> str:
    """Deterministic seed SOUL.md (fallback / fake mode / custom stub)."""
    lines = [
        "# SOUL — Agent Identity",
        "",
        "## Mission",
        "",
        purpose.strip(),
        "",
        f"Operator: {name}.",
        "",
    ]

    if path == "guided" and answers:
        objective = answers.get("objective")
        constraints = answers.get("constraints") or answers.get("red_lines")
        autonomy = answers.get("autonomy")
        focus = answers.get("focus")
        if objective:
            lines += ["## Objective & success", "", str(objective), ""]
        if focus:
            lines += ["## Focus", "", str(focus), ""]
        if constraints:
            lines += ["## Constraints / red lines", "", str(constraints), ""]
        if autonomy:
            lines += ["## Autonomy & check-in", "", str(autonomy), ""]
    elif path == "custom":
        lines += [
            "## Configuration",
            "",
            "This agent is configured conversationally. Refine identity, objectives, and "
            "constraints by talking to it in chat; it maintains this document over time.",
            "",
        ]

    lines += [
        "## Operating principles",
        "",
        "- Form your own intent from your situation; do not wait to be told the next step.",
        "- Respect the operator's constraints as hard limits.",
        "- Persist what you learn; reflect on outcomes.",
        "",
    ]
    return "\n".join(lines)
