"""Tests for top-level app behavior."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_spa_fallback_serves_index_html(client):
    """Direct navigation to a frontend route returns the SPA shell, not a JSON 404."""
    r = await client.get("/chat/main", headers={"Accept": "text/html"})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "<div id=\"root\"></div>" in r.text or "<script" in r.text


@pytest.mark.asyncio
async def test_api_404_remains_json(client):
    """Unknown API routes still return JSON 404 responses."""
    r = await client.get("/api/no-such-route")
    assert r.status_code == 404
    assert r.json()["detail"] == "Not Found"
