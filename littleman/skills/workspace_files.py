"""Generic workspace file skills.

The agent can create, list, read, and update arbitrary markdown/text files in its workspace.
This makes the workspace a true self-editing surface: plans, notes, scratchpads, application-
specific docs, etc. can be generated and referred to across turns.

Paths are sandboxed to `settings.workspace_dir`; directory-traversal attempts are rejected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from littleman.config import settings


class WorkspacePathError(ValueError):
    """Raised when a requested path escapes the workspace sandbox."""


_ALLOWED_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".ts", ".tsx"}


def _resolve(path: str) -> Path:
    """Resolve a workspace-relative path and ensure it stays inside the workspace."""
    base = settings.workspace_dir.resolve()
    target = (base / path).resolve()
    # On Windows, Path.resolve() can fail for non-existent parents; use absolute instead.
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise WorkspacePathError(f"path escapes workspace: {path}") from exc
    return target


def _assert_text_file(path: Path) -> None:
    if path.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise WorkspacePathError(
            f"only text file types are allowed: {', '.join(sorted(_ALLOWED_SUFFIXES))}"
        )


def make_workspace_file_skills() -> list[dict[str, Any]]:
    async def list_workspace_files(directory: str = "") -> dict[str, Any]:
        """List files and directories directly inside a workspace-relative path."""
        base = _resolve(directory)
        if not base.exists():
            return {"path": directory, "exists": False, "entries": []}
        entries = []
        for p in sorted(base.iterdir()):
            entries.append({"name": p.name, "type": "dir" if p.is_dir() else "file"})
        return {"path": directory, "exists": True, "entries": entries}

    async def read_workspace_file(path: str) -> dict[str, Any]:
        """Read a workspace file as text."""
        target = _resolve(path)
        if not target.exists():
            return {"path": path, "exists": False, "content": ""}
        if target.is_dir():
            return {"path": path, "exists": True, "error": "path is a directory"}
        return {"path": path, "exists": True, "content": target.read_text(encoding="utf-8")}

    async def write_workspace_file(path: str, content: str) -> dict[str, Any]:
        """Create or overwrite a workspace text file. Parent directories are created as needed."""
        target = _resolve(path)
        _assert_text_file(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": path, "written": True, "bytes": len(content.encode("utf-8"))}

    async def update_workspace_file(
        path: str,
        content: str,
        mode: str = "append",
    ) -> dict[str, Any]:
        """Update a workspace file by appending or prepending content."""
        target = _resolve(path)
        _assert_text_file(target)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = ""
        else:
            existing = target.read_text(encoding="utf-8")

        mode = (mode or "append").lower()
        if mode == "append":
            new = f"{existing}{content}"
        elif mode == "prepend":
            new = f"{content}{existing}"
        elif mode == "replace":
            new = content
        else:
            return {"path": path, "updated": False, "error": f"unknown mode: {mode}"}

        target.write_text(new, encoding="utf-8")
        return {"path": path, "updated": True, "bytes": len(new.encode("utf-8"))}

    return [
        {
            "name": "list_workspace_files",
            "fn": list_workspace_files,
            "description": (
                "List files and directories inside a workspace-relative path. "
                "Use this to discover notes, plans, or other files the agent has created."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Workspace-relative directory (default: workspace root).",
                    }
                },
                "required": [],
            },
            "cost": "LOW",
        },
        {
            "name": "read_workspace_file",
            "fn": read_workspace_file,
            "description": (
                "Read any text file in the workspace. Use this to refer to plans, notes, "
                "or application docs created by the agent or operator."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path, e.g. 'plans/mvp.md'.",
                    }
                },
                "required": ["path"],
            },
            "cost": "LOW",
        },
        {
            "name": "write_workspace_file",
            "fn": write_workspace_file,
            "description": (
                "Create or overwrite a workspace text file. Use this for plans, notes, "
                "design docs, or any durable thinking the agent wants to refer to later."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path, e.g. 'plans/mvp.md'.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content to write.",
                    },
                },
                "required": ["path", "content"],
            },
            "cost": "LOW",
        },
        {
            "name": "update_workspace_file",
            "fn": update_workspace_file,
            "description": (
                "Append, prepend, or replace content in a workspace text file. Use append "
                "for logs and prepend for priority lists."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["append", "prepend", "replace"],
                        "description": "How to combine new content with the existing file.",
                    },
                },
                "required": ["path", "content"],
            },
            "cost": "LOW",
        },
    ]
