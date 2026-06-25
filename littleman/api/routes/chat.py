import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import litellm
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from littleman.config import settings
from littleman.db.connection import get_db
from littleman.db.models import ChatMessage, ChatSession, LLMConfig
from littleman.llm.client import build_tool_definitions, load_soul

router = APIRouter(prefix="/chat", tags=["chat"])
log = logging.getLogger("littleman.chat")


# ── REST: session management ──────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession).order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sessions
    ]


@router.post("/sessions")
async def create_session(db: AsyncSession = Depends(get_db)):
    session = ChatSession(id=str(uuid.uuid4()), title="New conversation")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "title": session.title}


@router.patch("/sessions/{session_id}")
async def rename_session(session_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if "title" in body:
        session.title = body["title"]
    await db.commit()
    return {"ok": True}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    from littleman.agent.mainlog import MAIN_SESSION_ID

    if session_id == MAIN_SESSION_ID:
        return {"ok": False, "error": "the Main agent session cannot be deleted"}
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    await db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    await db.commit()
    return {"ok": True}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


@router.post("/sessions/{session_id}/suggestions")
async def suggest_prompts(session_id: str, db: AsyncSession = Depends(get_db)):
    """LLM-generated predictive prompts the operator is likely considering next.

    Opt-in (the frontend's suggestion toggle is off by default) and only ever invoked on
    explicit operator activity — never on idle — so it does not breach the zero-token-when-idle
    invariant. Routed through the provider abstraction so it runs on the scripted fake in tests.
    """
    from littleman.llm.prompts import CHAT_SUGGESTIONS_SYSTEM, CHAT_SUGGESTIONS_USER
    from littleman.llm.provider import get_provider

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    # Compact transcript of the recent exchange (most recent dozen turns is plenty of context).
    lines = []
    for m in messages[-12:]:
        if m.role in ("user", "assistant") and m.content:
            lines.append(f"{m.role}: {m.content[:300]}")
    transcript = "\n".join(lines) or "(no messages yet)"

    model = await _resolve_model(db)
    try:
        raw = await get_provider().complete(
            model,
            [
                {"role": "system", "content": CHAT_SUGGESTIONS_SYSTEM},
                {"role": "user", "content": CHAT_SUGGESTIONS_USER.format(transcript=transcript)},
            ],
        )
        parsed = json.loads(_strip_code_fence(raw))
        suggestions = [str(s) for s in parsed if isinstance(s, (str, int, float))][:3]
    except Exception:
        suggestions = []
    return {"suggestions": suggestions}


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return [_serialise_message(m) for m in messages]


# ── WebSocket: streaming chat ─────────────────────────────────────────────────

@router.websocket("/sessions/{session_id}/ws")
async def chat_ws(session_id: str, ws: WebSocket, db: AsyncSession = Depends(get_db)):
    await ws.accept()

    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    chat_session = result.scalar_one_or_none()
    if not chat_session:
        await ws.send_json({"type": "error", "message": "Session not found"})
        await ws.close()
        return

    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") != "user_message":
                continue

            user_text: str = data["content"]
            thinking_on: bool = bool(data.get("thinking"))
            skills_on: bool = data.get("skills", True)

            user_msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="user",
                content=user_text,
            )
            db.add(user_msg)

            if chat_session.title == "New conversation" and len(user_text) > 0:
                chat_session.title = user_text[:60]

            await db.commit()

            await ws.send_json({"type": "user_message", "message": _serialise_message(user_msg)})

            history = await _load_history(session_id, db)
            model = await _resolve_model(db)
            soul = load_soul()
            tools = _chat_tools() if skills_on else []

            assistant_id = str(uuid.uuid4())
            await ws.send_json({"type": "assistant_start", "id": assistant_id})

            accumulated_content = ""
            accumulated_thinking = ""
            pending_tool_calls: list[dict] = []

            # Never let an LLM/provider failure die silently: surface it to the client as an
            # `error` frame (the model config is wrong, the key is bad, the host is down, …) and
            # still close out the turn so the UI resolves instead of hanging on the placeholder.
            try:
                async for event in _stream_llm(model, soul, history, tools, thinking_on):
                    await ws.send_json(event)

                    if event["type"] == "token":
                        accumulated_content += event["content"]
                    elif event["type"] == "thinking":
                        accumulated_thinking += event["content"]
                    elif event["type"] == "tool_call":
                        pending_tool_calls.append(event["call"])
            except Exception as e:  # noqa: BLE001 — any provider error must reach the operator
                log.exception("chat stream failed for session %s", session_id)
                detail = f"{type(e).__name__}: {e}"
                await ws.send_json({"type": "error", "message": detail})
                # Persist the failure as the assistant turn so it survives reload, not a blank.
                db.add(ChatMessage(
                    id=assistant_id, session_id=session_id, role="assistant",
                    content=f"⚠️ Generation failed — {detail}",
                ))
                await db.commit()
                await ws.send_json({"type": "assistant_done", "id": assistant_id})
                continue

            assistant_msg = ChatMessage(
                id=assistant_id,
                session_id=session_id,
                role="assistant",
                content=accumulated_content or None,
                thinking=accumulated_thinking or None,
                tool_calls=pending_tool_calls or None,
            )
            db.add(assistant_msg)
            await db.commit()

            await ws.send_json({"type": "assistant_done", "id": assistant_id})

    except WebSocketDisconnect:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_code_fence(text: str) -> str:
    """Tolerate models that wrap JSON in a ```json fence."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -3]
        if t.startswith("json"):
            t = t[4:]
    return t.strip()


def _serialise_message(m: ChatMessage) -> dict:
    return {
        "id": m.id,
        "session_id": m.session_id,
        "role": m.role,
        "content": m.content,
        "thinking": m.thinking,
        "tool_calls": m.tool_calls,
        "tool_call_id": m.tool_call_id,
        "tool_name": m.tool_name,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


async def _load_history(session_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    out = []
    for m in messages:
        if m.role == "user":
            out.append({"role": "user", "content": m.content or ""})
        elif m.role == "assistant":
            content_parts = []
            if m.thinking:
                content_parts.append({"type": "thinking", "thinking": m.thinking})
            if m.content:
                content_parts.append({"type": "text", "text": m.content})
            if m.tool_calls:
                for tc in m.tool_calls:
                    content_parts.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc.get("args", {}),
                    })
            out.append({"role": "assistant", "content": content_parts or m.content or ""})
        elif m.role == "tool":
            out.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content or ""}],
            })
    return out


async def _resolve_model(db: AsyncSession) -> str:
    result = await db.execute(select(LLMConfig).where(LLMConfig.is_primary == True))
    cfg = result.scalar_one_or_none()
    if cfg:
        return cfg.model
    from littleman.llm import runtime

    return runtime.model_for("primary")


def _chat_tools() -> list[dict]:
    """Real skill definitions for the chat, from the live registry (built at app startup)."""
    from littleman.skills.registry import get_registry

    try:
        return get_registry().get_definitions()
    except RuntimeError:
        return build_tool_definitions()


async def _stream_llm(
    model: str, soul: str, history: list[dict], tools: list[dict], thinking: bool = False
) -> AsyncIterator[dict]:
    from littleman.llm.prompts import CHAT_ELICITATION_GUIDE

    messages = [{"role": "system", "content": soul + CHAT_ELICITATION_GUIDE}] + history

    from littleman.llm.provider import completion_kwargs

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        # Pick up OpenAI-compatible endpoint/credentials (Kimi/Moonshot, OpenRouter, …).
        **completion_kwargs(),
    }
    if tools:
        kwargs["tools"] = tools

    # Thinking mode: enable the model's native reasoning where supported.
    if thinking:
        if model.startswith("anthropic/"):
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 5000}
        else:
            # OpenAI-compatible reasoning models (Kimi k2.x, o-series, …).
            kwargs["reasoning_effort"] = "medium"

    response = await litellm.acompletion(**kwargs)

    current_tool: dict | None = None
    current_tool_args = ""

    async for chunk in response:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is None:
            continue

        # Thinking blocks (Anthropic extended thinking)
        if hasattr(delta, "thinking") and delta.thinking:
            yield {"type": "thinking", "content": delta.thinking}
            continue

        # Regular text token
        if delta.content:
            yield {"type": "token", "content": delta.content}

        # Tool call streaming
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                if tc_delta.id:
                    if current_tool:
                        current_tool["args"] = json.loads(current_tool_args or "{}")
                        yield {"type": "tool_call", "call": current_tool}
                    current_tool = {
                        "id": tc_delta.id,
                        "name": tc_delta.function.name if tc_delta.function else "",
                        "args": {},
                    }
                    current_tool_args = ""
                elif tc_delta.function and tc_delta.function.arguments:
                    current_tool_args += tc_delta.function.arguments

    if current_tool:
        try:
            current_tool["args"] = json.loads(current_tool_args or "{}")
        except json.JSONDecodeError:
            current_tool["args"] = {"raw": current_tool_args}
        yield {"type": "tool_call", "call": current_tool}

    yield {"type": "done"}
