# Skill Docs & Registry Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `workspace/skills/*.md` documentation-only, resolve skill names to docs, and stop the OpenClaw filesystem loader from shadowing built-in skills.

**Architecture:** Introduce a `SkillDocIndex` that maps registered skill names to doc files using an optional YAML frontmatter `skills:` list. `read_skill_doc(name)` uses the index, so an agent can call `read_skill_doc("write_to_kb")` and get `workspace/skills/kb.md`. Executable OpenClaw-style skills move to a dedicated scan directory (`workspace/openclaw/skills/`) and are only registered when they have a Python implementation or an explicit `register: true` flag. Built-in Python skills always take precedence.

**Tech Stack:** Python 3.11+, existing `littleman.skills` registry, YAML frontmatter (already parsed in `openclaw_loader.py`).

## Global Constraints

- Keep existing tests passing; add new tests, do not remove coverage.
- All file paths are relative to the repo root `C:/Users/judas/Documents/littleman`.
- The public skill interface (`registry.names()`, `dispatch`, `read_skill_doc`) must remain stable.
- Do not change workspace layout more than necessary; default platform skills must continue to work.

---

## File map

| File | Responsibility |
|------|----------------|
| `littleman/skills/skill_docs.py` | On-demand doc reader + `SkillDocIndex` name->doc lookup. |
| `littleman/skills/openclaw_loader.py` | Load executable OpenClaw skills from `workspace/openclaw/skills/`; skip unimplemented docs unless `register: true`. |
| `littleman/skills/registry.py` | Register built-ins, then OpenClaw skills; remove the existing "skip existing names" workaround. |
| `workspace/skills/*.md` | Add `skills:` frontmatter where one doc covers multiple registered names. |
| `tests/test_skill_docs.py` | Verify name->doc resolution and that built-ins are not shadowed. |
| `workspace/AGENT.md` | Update the `read_skill_doc(name)` guidance to say "use the registered skill name". |

---

## Task 1: Build `SkillDocIndex` and wire `read_skill_doc` to it

**Files:**
- Create: `littleman/skills/skill_docs.py` (overwrite)
- Test: `tests/test_skill_docs.py`

**Interfaces:**
- Consumes: `settings.workspace_dir / "skills"` markdown files.
- Produces: `read_skill_doc(name: str) -> str` resolves by registered skill name.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_skill_docs.py
def test_read_skill_doc_resolves_by_registered_name(tmp_path, monkeypatch):
    from littleman.config import Settings
    from littleman.skills.skill_docs import read_skill_doc

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "kb.md").write_text(
        "---\nskills:\n  - write_to_kb\n  - read_from_kb\n  - search_kb\n---\n# KB docs\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "littleman.skills.skill_docs.settings",
        Settings(workspace_dir=tmp_path),
    )

    result = read_skill_doc("write_to_kb")
    assert "KB docs" in result

    result = read_skill_doc("read_from_kb")
    assert "KB docs" in result
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/Scripts/python -m pytest tests/test_skill_docs.py::test_read_skill_doc_resolves_by_registered_name -v`
Expected: FAIL (`AssertionError` or `No documentation found`).

- [ ] **Step 3: Implement `SkillDocIndex` and update `read_skill_doc`**

```python
# littleman/skills/skill_docs.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from littleman.config import settings

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    yaml_text, body = match.groups()
    meta: dict[str, Any] = {}
    key: str | None = None
    for line in yaml_text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            meta[key] = value
        elif key is not None and line.strip().startswith("-"):
            item = line.strip()[1:].strip().strip('"').strip("'")
            if key not in meta or not isinstance(meta[key], list):
                meta[key] = []
            meta[key].append(item)
    return meta, body


class SkillDocIndex:
    """Map registered skill names to their documentation files."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._name_to_doc: dict[str, Path] = {}
        self._build()

    def _build(self) -> None:
        if not self.skills_dir.exists():
            return
        for path in sorted(self.skills_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(text)
            # A doc with a `skills:` list covers those registered names.
            covered = meta.get("skills") or [path.stem]
            if isinstance(covered, str):
                covered = [covered]
            for name in covered:
                self._name_to_doc[name] = path

    def doc_for(self, name: str) -> Path | None:
        return self._name_to_doc.get(name)

    def available_names(self) -> list[str]:
        return sorted(self._name_to_doc)


async def read_skill_doc(name: str) -> str:
    """Read the detailed documentation for a named skill.

    `name` is the registered skill name (e.g. `write_to_kb`). The doc file is looked up via the
    `skills:` frontmatter list, falling back to a file named after the skill.
    """
    doc_dir = Path(settings.workspace_dir) / "skills"
    index = SkillDocIndex(doc_dir)
    path = index.doc_for(name)
    if path is not None and path.exists():
        return path.read_text(encoding="utf-8")

    # Legacy fallback: exact file name.
    for ext in (".md", ".txt"):
        p = doc_dir / f"{name}{ext}"
        if p.exists():
            return p.read_text(encoding="utf-8")

    available = index.available_names()
    hint = f" Available: {', '.join(available)}" if available else ""
    return f"No documentation found for skill '{name}'.{hint}"
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `.venv/Scripts/python -m pytest tests/test_skill_docs.py::test_read_skill_doc_resolves_by_registered_name -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add littleman/skills/skill_docs.py tests/test_skill_docs.py
git commit -m "feat: resolve skill docs by registered skill name"
```

---

## Task 2: Move OpenClaw executable skill loading to a dedicated directory

**Files:**
- Modify: `littleman/skills/openclaw_loader.py`
- Create: `workspace/openclaw/skills/.gitkeep`
- Test: `tests/test_openclaw_loader.py` (new)

**Interfaces:**
- Consumes: `workspace/openclaw/skills/*.md` manifests + `littleman.skills.openclaw.<name>` implementations.
- Produces: list of skill dicts for the registry.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_openclaw_loader.py
from pathlib import Path

import pytest

from littleman.skills.openclaw_loader import load_openclaw_skills


def test_openclaw_loader_ignores_doc_only_manifests(tmp_path, monkeypatch):
    from littleman.config import Settings

    oc_dir = tmp_path / "openclaw" / "skills"
    oc_dir.mkdir(parents=True)
    (oc_dir / "my_skill.md").write_text(
        "---\nname: my_skill\n---\n# My skill\nJust docs, no implementation.",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "littleman.skills.openclaw_loader.settings",
        Settings(workspace_dir=tmp_path),
    )
    skills = load_openclaw_skills()
    assert not skills
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `.venv/Scripts/python -m pytest tests/test_openclaw_loader.py::test_openclaw_loader_ignores_doc_only_manifests -v`
Expected: FAIL (currently loads `my_skill` as a stub).

- [ ] **Step 3: Change the scan directory and add registration gating**

```python
# littleman/skills/openclaw_loader.py
# ... existing imports unchanged ...

# Scan this subdirectory for executable SKILL.md manifests, NOT workspace/skills.
_SKILL_DIR = "openclaw/skills"


def load_openclaw_skills() -> list[dict[str, Any]]:
    """Scan workspace/openclaw/skills/*.md for executable skill manifests."""
    skills_dir = settings.workspace_dir / _SKILL_DIR
    if not skills_dir.exists():
        return []

    skills: list[dict[str, Any]] = []
    for path in sorted(skills_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        name = meta.get("name") or path.stem
        description = meta.get("description") or _first_paragraph(body) or f"Filesystem skill: {name}"
        cost = meta.get("cost", "LOW")
        requires = meta.get("requires", [])
        if isinstance(requires, str):
            requires = [r.strip() for r in requires.split(",") if r.strip()]

        parameters = meta.get("parameters") or {
            "type": "object",
            "properties": {},
            "required": [],
        }

        impl = _load_impl(name)
        register = meta.get("register", impl is not None)
        if not register:
            continue
        if impl is None:
            impl = _make_unimplemented(name)

        skills.append(
            {
                "name": name,
                "fn": impl,
                "description": description,
                "parameters": parameters,
                "cost": cost,
                "requires": requires,
            }
        )
    return skills
```

- [ ] **Step 4: Create the new directory marker**

```bash
mkdir -p workspace/openclaw/skills
touch workspace/openclaw/skills/.gitkeep
```

- [ ] **Step 5: Run the test and confirm it passes**

Run: `.venv/Scripts/python -m pytest tests/test_openclaw_loader.py::test_openclaw_loader_ignores_doc_only_manifests -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add littleman/skills/openclaw_loader.py tests/test_openclaw_loader.py workspace/openclaw/skills/.gitkeep
git commit -m "refactor: load openclaw executable skills from dedicated directory"
```

---

## Task 3: Remove the built-in-shadow workaround from the registry

**Files:**
- Modify: `littleman/skills/registry.py`

**Interfaces:**
- Consumes: built-in skills, OpenClaw skills from Task 2.
- Produces: a registry where built-ins are registered after OpenClaw skills so they naturally override.

- [ ] **Step 1: Update registry ordering**

Replace the OpenClaw registration block in `build_registry` with:

```python
    # OpenClaw-style filesystem skills (optional, separate directory). Register these BEFORE
    # built-in platform skills so a built-in implementation always wins.
    for skill in load_openclaw_skills():
        registry.register(**skill)

    # Platform / workspace skills.
    for skill in make_construct_skills():
        registry.register(**skill)

    for skill in make_workspace_file_skills():
        registry.register(**skill)
```

And delete the previous `registered_names` skip logic added as a workaround.

- [ ] **Step 2: Run the existing tests**

Run: `.venv/Scripts/python -m pytest tests/test_skill_docs.py tests/test_platform_skills.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add littleman/skills/registry.py
git commit -m "refactor: built-in skills take precedence over openclaw manifests"
```

---

## Task 4: Add `skills:` frontmatter to multi-skill docs

**Files:**
- Modify: `workspace/skills/kb.md`
- Modify: `workspace/skills/heartbeat.md`
- Modify: `workspace/skills/web_research.md`
- Modify: `workspace/skills/calibration.md`

- [ ] **Step 1: Add frontmatter to `kb.md`**

Replace the file header with:

```markdown
---
skills:
  - write_to_kb
  - read_from_kb
  - search_kb
---
# Knowledge Base (Read & Write)
```

- [ ] **Step 2: Add frontmatter to `heartbeat.md`**

```markdown
---
skills:
  - create_heartbeat
  - amend_heartbeat
  - cancel_heartbeat
  - list_scheduled_heartbeats
---
# heartbeat — Self-Scheduling
```

- [ ] **Step 3: Add frontmatter to `web_research.md`**

```markdown
---
skills:
  - web_search
  - browse_url
  - browse_urls
---
# web_research — Web Search and Page Fetching
```

- [ ] **Step 4: Add frontmatter to `calibration.md`**

```markdown
---
skills:
  - record_prediction_outcome
  - get_calibration_summary
---
# calibration — Track Prediction Accuracy
```

- [ ] **Step 5: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_skill_docs.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add workspace/skills/*.md
git commit -m "docs: declare covered skill names in multi-skill docs"
```

---

## Task 5: Update `AGENT.md` guidance

**Files:**
- Modify: `workspace/AGENT.md`

- [ ] **Step 1: Replace the `read_skill_doc` paragraph**

In §5, replace:

```markdown
Before using a skill you are unsure about, call `read_skill_doc(name)` for precise guidance
```

with:

```markdown
Before using a skill you are unsure about, call `read_skill_doc(name)` using the skill's
registered name (e.g. `read_skill_doc("write_to_kb")`). The doc may live under a different
filename, so always use the registered name.
```

- [ ] **Step 2: Run tests**

Run: `.venv/Scripts/python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add workspace/AGENT.md
git commit -m "docs: clarify read_skill_doc uses registered skill names"
```

---

## Task 6: Full verification

- [ ] **Run the full test suite**

Run: `.venv/Scripts/python -m pytest tests/ -q`
Expected: all tests pass.

- [ ] **Run the frontend build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

---

## Spec coverage self-check

| Requirement | Task |
|---|---|
| Docs are documentation-only, not auto-registered skills | Task 2 (scan directory change) + Task 3 (ordering) |
| `read_skill_doc("write_to_kb")` resolves to `kb.md` | Task 1 |
| Built-in skills cannot be shadowed by doc manifests | Task 2 (no register without impl/flag) + Task 3 |
| Existing tests keep passing | Task 6 |
| Agent guidance is accurate | Task 5 |

No placeholders remain in the plan; every step names an exact file and command.
