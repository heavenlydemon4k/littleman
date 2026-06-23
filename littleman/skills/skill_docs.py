"""On-demand skill documentation reader.

The agent calls read_skill_doc before using a complex skill so it gets precise guidance
without bloating the base system prompt. Mirrors OpenClaw's on-demand doc pattern.
"""

from pathlib import Path


async def read_skill_doc(name: str) -> str:
    from littleman.config import settings

    doc_dir = Path(settings.workspace_dir) / "skills"
    for ext in (".md", ".txt"):
        p = doc_dir / f"{name}{ext}"
        if p.exists():
            return p.read_text(encoding="utf-8")
    available = [f.stem for f in doc_dir.glob("*.md")] if doc_dir.exists() else []
    hint = f" Available: {', '.join(sorted(available))}" if available else ""
    return f"No documentation found for skill '{name}'.{hint}"
