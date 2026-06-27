---
skills:
  - web_search
  - browse_url
  - browse_urls
---
# web_research — Web Search and Page Fetching

## Purpose
Gather current evidence from the web to inform probability estimates.
Combines `web_search` (retrieves URLs + snippets) and `browse_url` (reads full page content).

## Skills involved
- `web_search(query, source_filters=None, max_results=10)` → list of `{ url, title, snippet }`
- `browse_url(url)` → `{ content, title, truncated }` (up to ~12 000 chars)
- `browse_urls(urls)` → fetch several URLs in parallel and return `{ results, count }`

## When to use
- Forming evidence for `estimate_probability` — always research before estimating
- Checking recent news that could invalidate KB entries older than 24h
- Verifying resolution criteria for an unusual market

## Effective search patterns

### For event probability
```
web_search("<event> latest news site:reuters.com OR site:apnews.com OR site:bbc.com")
web_search("<event> prediction market analysis")
```

### For data-driven markets (prices, economic indicators)
```
web_search("current <metric> <source>")  # e.g. "current Fed funds rate Federal Reserve"
browse_url("<authoritative source URL>")  # e.g. Fed website, CME FedWatch
```

### For political/electoral markets
```
web_search("<candidate/party> polling <state/country> <month year>")
web_search("<election> forecast 538 OR Nate Silver OR prediction")
```

## Source quality ranking
1. Official sources (government, Fed, WHO, company IR pages)
2. Established news with bylines (Reuters, AP, BBC, FT, WSJ)
3. Reputable aggregators (FiveThirtyEight, RealClearPolitics, Polymarket blog)
4. Prediction market forums (Metaculus, Manifold) — useful for base rates
5. Social media / blogs — treat as weak signals only

## Token economy rules
- Search first, browse selectively — only browse the top 2-3 most relevant URLs
- Snippets often enough; full browse only if the snippet is ambiguous
- Don't browse paywalled pages — the truncated stub wastes a round-trip

## Common mistakes
- Searching without a date constraint → stale results dominate
- Anchoring on market price before forming your own view from evidence
- Over-relying on a single source; cross-validate across ≥2 independent sources
- Treating prediction market prices as evidence (circular reasoning)
