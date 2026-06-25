"""Chat-experience track: predictive prompt suggestions endpoint.

The suggestion bar is LLM-generated but routed through the provider abstraction, so it runs on
the deterministic scripted fake here — no network. Guards that the endpoint returns the model's
three predicted prompts and degrades to an empty list rather than erroring.
"""

import uuid

import pytest

from littleman.api.routes.chat import suggest_prompts
from littleman.db.models import ChatMessage, ChatSession
from littleman.llm.provider import ScriptedProvider, set_provider


@pytest.fixture
def scripted():
    set_provider(ScriptedProvider())
    yield
    set_provider(None)


async def _seed(db, with_messages=True):
    sid = str(uuid.uuid4())
    db.add(ChatSession(id=sid, title="t"))
    if with_messages:
        db.add(ChatMessage(id=str(uuid.uuid4()), session_id=sid, role="user",
                           content="what markets look interesting?"))
        db.add(ChatMessage(id=str(uuid.uuid4()), session_id=sid, role="assistant",
                           content="A few politics markets have a clear edge."))
    await db.commit()
    return sid


@pytest.mark.asyncio
async def test_suggestions_returns_three(db, scripted):
    sid = await _seed(db)
    out = await suggest_prompts(sid, db)
    assert len(out["suggestions"]) == 3
    assert all(isinstance(s, str) and s for s in out["suggestions"])


@pytest.mark.asyncio
async def test_suggestions_empty_session_still_ok(db, scripted):
    sid = await _seed(db, with_messages=False)
    out = await suggest_prompts(sid, db)
    # Scripted fake always returns three; the point is it does not raise on an empty transcript.
    assert isinstance(out["suggestions"], list)


@pytest.mark.asyncio
async def test_suggestions_degrade_to_empty_on_bad_output(db, scripted, monkeypatch):
    sid = await _seed(db)

    class Broken:
        async def complete(self, *a, **k):
            return "not json at all"

    set_provider(Broken())
    out = await suggest_prompts(sid, db)
    assert out["suggestions"] == []
