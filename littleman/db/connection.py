from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from littleman.config import settings
from littleman.db.models import Base

_url = settings.database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
engine = create_async_engine(_url, connect_args={"check_same_thread": False})
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(__import__("sqlalchemy").text("PRAGMA journal_mode=WAL"))


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
