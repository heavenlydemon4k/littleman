import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.db.connection import get_db
from littleman.db.models import LLMConfig

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMConfigCreate(BaseModel):
    name: str
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    is_primary: bool = False
    is_secondary: bool = False
    extra_params: dict = {}


class LLMConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    is_primary: bool | None = None
    is_secondary: bool | None = None
    extra_params: dict | None = None


@router.get("/llm")
async def list_llm_configs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LLMConfig).order_by(LLMConfig.created_at))
    configs = result.scalars().all()
    return [_serialise(c) for c in configs]


@router.post("/llm")
async def create_llm_config(body: LLMConfigCreate, db: AsyncSession = Depends(get_db)):
    if body.is_primary:
        await db.execute(update(LLMConfig).values(is_primary=False))
    if body.is_secondary:
        await db.execute(update(LLMConfig).values(is_secondary=False))

    cfg = LLMConfig(
        id=str(uuid.uuid4()),
        name=body.name,
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        is_primary=body.is_primary,
        is_secondary=body.is_secondary,
        extra_params=body.extra_params,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return _serialise(cfg)


@router.patch("/llm/{config_id}")
async def update_llm_config(config_id: str, body: LLMConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LLMConfig).where(LLMConfig.id == config_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")

    if body.is_primary is True:
        await db.execute(update(LLMConfig).where(LLMConfig.id != config_id).values(is_primary=False))
    if body.is_secondary is True:
        await db.execute(update(LLMConfig).where(LLMConfig.id != config_id).values(is_secondary=False))

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cfg, field, value)

    await db.commit()
    await db.refresh(cfg)
    return _serialise(cfg)


@router.delete("/llm/{config_id}")
async def delete_llm_config(config_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LLMConfig).where(LLMConfig.id == config_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    await db.delete(cfg)
    await db.commit()
    return {"ok": True}


def _serialise(c: LLMConfig) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "provider": c.provider,
        "model": c.model,
        "api_key": "***" if c.api_key else None,
        "base_url": c.base_url,
        "is_primary": c.is_primary,
        "is_secondary": c.is_secondary,
        "extra_params": c.extra_params,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
