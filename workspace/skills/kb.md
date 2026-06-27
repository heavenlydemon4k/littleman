---
skills:
  - write_to_kb
  - read_from_kb
  - search_kb
---
# Knowledge Base (Read & Write)

## Purpose
The KB stores durable research findings across sessions. Write to it when you
learn something that will still be useful next session. Read from it before
doing web research to avoid redundant work.

## Skills
- `kb_write(topic, content, source_urls, confidence, expires_at, linked_market_ids)`
- `kb_read(topic)` — fuzzy-matched retrieval by topic string
- `kb_search(query)` — full-text search across all KB entries

## When to WRITE
- You've researched a topic with ≥ MEDIUM confidence and it will age well (>6h)
- You've identified a base rate, reference class, or structural fact
- You've profiled a market's resolution source (e.g. "this resolves via CME FedWatch")

## When to READ
- Before starting web_research on any topic — check if a recent entry exists
- When about to estimate probability — KB evidence = cheaper than re-searching

## Topic naming conventions
Use lowercase, underscore-separated, specific:
- `fed_rate_cut_june_2026` (specific, dated)
- `btc_price_trend_may_2026` (asset + timeframe)
- `us_election_2026_polling` (event + type)
- `polymarket_fee_structure` (structural/durable facts)

NOT: `research`, `notes`, `markets`, `info` (too generic — hard to retrieve)

## Key parameters for kb_write
- `topic` (str): follows naming convention above
- `content` (str): your synthesized finding, 50–500 words
- `source_urls` (list[str]): URLs you researched from
- `confidence` (str): "HIGH" | "MEDIUM" | "LOW"
- `expires_at` (ISO str, optional): omit for durable facts; set for fast-moving data
  - Breaking news → expires in 4–8h
  - Weekly data (polls, prices) → expires in 24–48h
  - Structural/institutional facts → no expiry
- `linked_market_ids` (list[str]): market IDs this research applies to

## Common mistakes
- Writing to KB without source_urls (makes it unverifiable later)
- Topic too generic → kb_read won't find it next session
- Not expiring fast-moving data → stale KB entries cause anchoring
- Skipping kb_read before web_research → wastes tokens re-discovering known facts
