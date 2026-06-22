from pathlib import Path

from littleman.config import settings


def load_soul() -> str:
    soul_path = settings.workspace_dir / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text(encoding="utf-8")
    return "You are Littleman, an autonomous prediction market trading agent."


def build_tool_definitions() -> list[dict]:
    skills_path = settings.workspace_dir / "SKILLS.md"
    if not skills_path.exists():
        return []

    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for information relevant to a market or topic.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "source_filters": {"type": "array", "items": {"type": "string"}},
                        "max_results": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "scan_markets",
                "description": "List open Polymarket markets matching optional filters.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "min_volume": {"type": "number"},
                        "closes_within_hours": {"type": "number"},
                        "max_results": {"type": "integer", "default": 20},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_market",
                "description": "Get full details on a specific Polymarket market including resolution criteria.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "market_id": {"type": "string"},
                    },
                    "required": ["market_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "estimate_probability",
                "description": "Produce a structured probability estimate for a market given evidence.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "market_id": {"type": "string"},
                        "evidence_summary": {"type": "string"},
                        "comparable_base_rates": {"type": "string"},
                    },
                    "required": ["market_id", "evidence_summary"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_to_kb",
                "description": "Write research findings to the knowledge base for future sessions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "content": {"type": "string"},
                        "source_urls": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "expires_hours": {"type": "number"},
                    },
                    "required": ["topic", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_heartbeat",
                "description": "Schedule a future agent session at a specific time with context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fire_at": {"type": "string", "description": "ISO 8601 datetime"},
                        "reason": {"type": "string"},
                        "session_type": {
                            "type": "string",
                            "enum": ["RESOLVE", "RESEARCH", "MONITOR", "FULL_CYCLE"],
                        },
                        "context": {"type": "object"},
                    },
                    "required": ["fire_at", "reason", "session_type", "context"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "place_bet",
                "description": "Place a bet on a Polymarket market. Passes through the risk governor.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "market_id": {"type": "string"},
                        "direction": {"type": "string", "enum": ["YES", "NO"]},
                        "size_usdc": {"type": "number"},
                        "max_price": {"type": "number"},
                    },
                    "required": ["market_id", "direction", "size_usdc"],
                },
            },
        },
    ]
