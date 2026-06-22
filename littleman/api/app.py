import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from littleman.api.routes import agent, chat, settings, workspace
from littleman.db.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Build the skill registry once so /agent/skills and chat share the real capability list.
    from littleman.db.connection import AsyncSessionLocal
    from littleman.skills.registry import build_registry

    build_registry(db_session_factory=AsyncSessionLocal)
    yield


app = FastAPI(title="Littleman", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(workspace.router, prefix="/api")
app.include_router(agent.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}

dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="static")
