from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from littleman.config import settings

router = APIRouter(prefix="/workspace", tags=["workspace"])

ALLOWED_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml"}


def _workspace_path() -> Path:
    return settings.workspace_dir.resolve()


def _resolve_safe(relative: str) -> Path:
    base = _workspace_path()
    target = (base / relative).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    if target.suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Extension {target.suffix} not editable")
    return target


@router.get("/files")
async def list_files():
    base = _workspace_path()
    files = []
    for p in sorted(base.rglob("*")):
        if p.is_file() and p.suffix in ALLOWED_EXTENSIONS:
            files.append({
                "path": p.relative_to(base).as_posix(),
                "name": p.name,
                "size": p.stat().st_size,
            })
    return files


@router.get("/files/{path:path}")
async def read_file(path: str):
    target = _resolve_safe(path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": target.read_text(encoding="utf-8")}


class FileWrite(BaseModel):
    content: str


@router.put("/files/{path:path}")
async def write_file(path: str, body: FileWrite):
    target = _resolve_safe(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")
    return {"ok": True, "path": path, "size": target.stat().st_size}
