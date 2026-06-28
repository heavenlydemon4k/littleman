import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from littleman.api.app import app
from littleman.db.models import Base


@pytest_asyncio.fixture
async def db(monkeypatch):
    """A fresh in-memory SQLite database per test.

    StaticPool keeps a single connection so the in-memory schema persists across the
    session's statements. The module-level ``AsyncSessionLocal`` is patched so code that
    creates sessions from ``littleman.db.connection`` (e.g. ``construct._get_db``) routes
    to the same in-memory database.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("littleman.db.connection.AsyncSessionLocal", session_factory)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    """An async HTTP client for the FastAPI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
