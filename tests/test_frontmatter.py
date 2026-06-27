"""Tests for the shared YAML-like frontmatter parser."""

from __future__ import annotations

import pytest

from littleman.skills.frontmatter import _parse_frontmatter


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("yes", True),
        ("YES", True),
        ("1", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("no", False),
        ("NO", False),
        ("0", False),
    ],
)
def test_boolean_scalar_normalization(raw, expected):
    meta, body = _parse_frontmatter(f"---\nregister: {raw}\n---\nBody text.")
    assert meta["register"] is expected
    assert body == "Body text."


def test_register_false_prevents_registration_semantics():
    """`register: false` must be a real boolean, not the truthy string 'false'."""
    meta, _ = _parse_frontmatter("---\nregister: false\n---\n")
    assert meta["register"] is False
    assert not meta["register"]


def test_register_true_is_boolean():
    meta, _ = _parse_frontmatter("---\nregister: true\n---\n")
    assert meta["register"] is True


def test_list_parsing_preserves_strings():
    text = """---
skills:
  - write_to_kb
  - read_from_kb
  - search_kb
---
# Docs
"""
    meta, body = _parse_frontmatter(text)
    assert meta["skills"] == ["write_to_kb", "read_from_kb", "search_kb"]
    assert all(isinstance(item, str) for item in meta["skills"])
    assert "# Docs" in body


def test_mixed_scalar_and_list_values():
    text = """---
name: echo
description: repeats input
requires:
  - python
  - git
register: true
---
# Echo
"""
    meta, _ = _parse_frontmatter(text)
    assert meta["name"] == "echo"
    assert meta["description"] == "repeats input"
    assert meta["requires"] == ["python", "git"]
    assert meta["register"] is True


def test_unrecognised_scalars_remain_strings():
    meta, _ = _parse_frontmatter("---\ncost: LOW\ncount: 42\n---\n")
    assert meta["cost"] == "LOW"
    assert meta["count"] == "42"
