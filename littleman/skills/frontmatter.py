"""Shared frontmatter parser for skill documentation and OpenClaw manifests."""

from __future__ import annotations

import re
from typing import Any


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)

_TRUE_VALUES = {"true", "True", "TRUE", "yes", "YES", "1"}
_FALSE_VALUES = {"false", "False", "FALSE", "no", "NO", "0"}


def _normalize_scalar(value: str) -> Any:
    """Normalize a scalar string value, coercing common booleans."""
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return value


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from markdown body.

    Returns a metadata dictionary and the markdown body. Scalar values are kept
    as strings except for common boolean representations ("true", "false",
    "yes", "no", "1", "0"), which are normalized to Python booleans. List
    items (lines starting with "-") are collected as strings under their key.
    """
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
            meta[key] = _normalize_scalar(value)
        elif key is not None and line.strip().startswith("-"):
            item = line.strip()[1:].strip().strip('"').strip("'")
            if key not in meta or not isinstance(meta[key], list):
                meta[key] = []
            meta[key].append(_normalize_scalar(item))
    return meta, body
