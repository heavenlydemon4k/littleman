# polymarket_scan — Market Discovery & Filtering

## Purpose
Retrieve open Polymarket markets that match a category, keyword, or resolution window.
Use this at the start of a research cycle to discover what to bet on.

## When to use
- Beginning a FULL_CYCLE session to find active markets
- Focused research on a specific domain (politics, crypto, sports, science)
- Checking what resolves this week before a scheduled heartbeat fires

## Key parameters
- `query` (str): keyword or topic, e.g. "US election", "Bitcoin price", "Fed rate"
- `category` (str, optional): "politics" | "crypto" | "sports" | "science" | "entertainment"
- `min_volume_usdc` (float, optional): filter noise — use 5000+ for liquid markets
- `closes_before` (ISO date str, optional): only markets resolving before this date
- `limit` (int, optional): max results, default 20

## Return shape
List of market dicts: `{ market_id, title, category, end_date, yes_price, no_price, volume_usdc, resolution_criteria }`

## Workflow example
```
1. scan("Fed rate cut", min_volume_usdc=10000) → get market list
2. For promising markets: read_orderbook(market_id) for depth
3. run web_research on each → estimate_probability
4. Compare edge = estimated_prob - market_price
```

## Common mistakes
- Scanning too broadly wastes context — use category + min_volume filters
- Don't skip resolution_criteria from the result; it's what determines what "YES" means
- Low-volume markets (<$1k) are usually illiquid; avoid unless the edge is extreme
- Market price is already the consensus — your edge must come from new information
