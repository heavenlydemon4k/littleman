"""Web research skills.

Real HTTP fetching via httpx. Search uses a configurable provider; if no search API key is
configured the search skill degrades to a clear error rather than fabricating results — the
agent must know when it cannot actually see the web.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from littleman.config import settings

_FETCH_TIMEOUT = 20.0
_MAX_BODY_CHARS = 12_000


async def _fetch_one(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        text = resp.text
        # Strip the worst of the markup for token economy. A real deployment swaps in
        # readability/trafilatura; this keeps the dependency surface minimal.
        stripped = _strip_html(text)
        truncated = stripped[:_MAX_BODY_CHARS]
        return {
            "url": url,
            "status": resp.status_code,
            "content": truncated,
            "truncated": len(stripped) > _MAX_BODY_CHARS,
        }
    except httpx.HTTPError as e:
        return {"url": url, "error": str(e)}


async def _duckduckgo_search(query: str, max_results: int) -> dict:
    """Keyless web search via DuckDuckGo's HTML endpoint (no API key needed)."""
    import re
    from urllib.parse import parse_qs, unquote, urlparse

    try:
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 littleman/0.1"}) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                timeout=_FETCH_TIMEOUT,
                follow_redirects=True,
            )
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPError as e:
        return {"query": query, "error": str(e), "results": [], "provider": "duckduckgo"}

    results: list[dict] = []
    # Each result: an anchor with class result__a (title + link) and a result__snippet.
    link_re = re.compile(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    snip_re = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.S)
    snippets = [_strip_html(s) for s in snip_re.findall(html)]
    for i, (href, title) in enumerate(link_re.findall(html)):
        # DDG wraps the real URL in a redirect with a uddg= param.
        real = href
        if "uddg=" in href:
            qs = parse_qs(urlparse(href).query)
            if qs.get("uddg"):
                real = unquote(qs["uddg"][0])
        results.append({
            "title": _strip_html(title),
            "url": real,
            "excerpt": snippets[i] if i < len(snippets) else "",
        })
        if len(results) >= max_results:
            break

    return {"query": query, "results": results, "count": len(results), "provider": "duckduckgo"}


def _strip_html(html: str) -> str:
    import re

    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_web_research_skills() -> list[dict]:
    async def browse_url(url: str) -> dict:
        async with httpx.AsyncClient(headers={"User-Agent": "littleman/0.1"}) as client:
            return await _fetch_one(client, url)

    async def browse_urls(urls: list[str]) -> dict:
        # Read-only parallelism is permitted (see ADR 0001) — fan out fetches within one
        # session via gather.
        async with httpx.AsyncClient(headers={"User-Agent": "littleman/0.1"}) as client:
            results = await asyncio.gather(*[_fetch_one(client, u) for u in urls])
        return {"results": list(results), "count": len(results)}

    async def web_search(
        query: str,
        source_filters: list[str] | None = None,
        max_results: int = 10,
    ) -> dict:
        api_key = getattr(settings, "search_api_key", "") or ""
        if not api_key:
            # Keyless fallback so the agent always has web search.
            return await _duckduckgo_search(query, max_results)
        # Tavily-compatible request shape; swap endpoint via settings if needed.
        endpoint = getattr(settings, "search_endpoint", "https://api.tavily.com/search")
        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "include_domains": source_filters or [],
        }
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(endpoint, json=payload, timeout=_FETCH_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                return {"query": query, "error": str(e), "results": []}
        results = [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "excerpt": r.get("content", "")[:500],
                "score": r.get("score"),
            }
            for r in data.get("results", [])
        ]
        return {"query": query, "results": results, "count": len(results)}

    return [
        {
            "name": "web_search",
            "fn": web_search,
            "description": "Search the web for information relevant to a topic (keyless DuckDuckGo by default; Tavily if a key is set).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "source_filters": {"type": "array", "items": {"type": "string"}},
                    "max_results": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
            "cost": "MEDIUM",
        },
        {
            "name": "browse_url",
            "fn": browse_url,
            "description": "Fetch and extract the readable text of a single URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            "cost": "MEDIUM",
        },
        {
            "name": "browse_urls",
            "fn": browse_urls,
            "description": "Fetch several URLs in parallel and return their extracted text.",
            "parameters": {
                "type": "object",
                "properties": {"urls": {"type": "array", "items": {"type": "string"}}},
                "required": ["urls"],
            },
            "cost": "MEDIUM",
        },
    ]
