---
skills:
  - write_to_kb
  - read_from_kb
  - search_kb
---
# Knowledge Base (Read & Write)

## Purpose
The KB stores durable research findings and notes across sessions. Write to it when you learn something that will still be useful next session. Read from it before doing web research to avoid redundant work.

## Skills
- `write_to_kb(topic, content, source_urls=None, confidence="MEDIUM", expires_hours=None)`
- `read_from_kb(topic)` — fuzzy-matched retrieval by topic string
- `search_kb(query, limit=10)` — full-text search across all KB entries

## When to WRITE
- You've researched a topic with ≥ MEDIUM confidence and it will age well (>6h).
- You've identified a base rate, reference class, or structural fact.
- You want to persist a durable note for future wakes.

## When to READ
- Before starting `web_search` on any topic — check if a recent entry exists.
- When you need background on a topic you previously researched.

## Topic naming conventions
Use lowercase, underscore-separated, specific:
- `fed_rate_cut_june_2026` (specific, dated)
- `btc_price_trend_may_2026` (asset + timeframe)
- `us_election_2026_polling` (event + type)
- `polymarket_fee_structure` (structural/durable facts)

NOT: `research`, `notes`, `markets`, `info` (too generic — hard to retrieve)

## Key parameters for write_to_kb
- `topic` (str): follows naming convention above
- `content` (str): your synthesized finding, 50–500 words
- `source_urls` (list[str], optional): URLs you researched from
- `confidence` (str, default "MEDIUM"): "HIGH" | "MEDIUM" | "LOW"
- `expires_hours` (number, optional): omit for durable facts; set for fast-moving data
  - Breaking news → expires in 4–8h
  - Weekly data (polls, prices) → expires in 24–48h
  - Structural/institutional facts → no expiry

## Common mistakes
- Writing to KB without source_urls (makes it unverifiable later)
- Topic too generic → read_from_kb won't find it next session
- Not expiring fast-moving data → stale KB entries cause anchoring
- Skipping read_from_kb before web_research → wastes tokens re-discovering known facts
