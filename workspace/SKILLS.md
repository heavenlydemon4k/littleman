# SKILLS — Available Capabilities

This file documents all skills available to the agent. It is included in the system prompt during strategy planning and task execution so the agent knows what it can do.

---

## Research

### `web_search(query, source_filters=None, max_results=10)`
Search the web and return structured results (title, url, excerpt, date, source). Use for finding news, official statements, and data relevant to a market. `source_filters` accepts a list of domain strings to restrict results.

### `browse_url(url)`
Fetch and parse the text content of a specific URL. Use when you have a specific page to read (official announcement, filing, data release). Returns structured text, not raw HTML.

### `aggregate_research(topic, depth="standard")`
Run multiple searches on a topic and return a deduplicated, structured summary. `depth` controls number of queries and sources consulted: "quick" (2-3 sources), "standard" (5-8 sources), "deep" (10+ sources). Use "deep" only for high-stakes decisions.

---

## Polymarket

### `scan_markets(category=None, min_volume=None, closes_within_hours=None, max_results=20)`
List open markets matching optional filters. Returns market IDs, titles, current YES/NO prices, volume, and close times. Use at the start of a full-cycle session to find opportunities.

### `get_market(market_id)`
Get full detail on a specific market: description, resolution criteria, resolution source, current order book summary, volume, close time.

### `get_orderbook(market_id)`
Get current order book depth (bid/ask at each price level). Use before placing a bet to check liquidity.

### `get_position(position_id)`
Get current state of an open position: current price, unrealised P&L, whether the market has resolved.

### `check_resolution(market_id)`
Check whether a market has resolved and retrieve the outcome if so. Use in resolution-check sessions.

### `place_bet(market_id, direction, size_usdc, max_price=None)`
Place a bet. `direction` is "YES" or "NO". `size_usdc` is the amount to commit. `max_price` sets a limit (default: market order). Passes through the risk governor before execution — may be vetoed.

---

## Knowledge Base

### `write_to_kb(topic, content, source_urls=None, confidence="MEDIUM", expires_hours=None)`
Write research findings to the knowledge base. Always write to KB after completing research so findings persist across sessions.

### `read_from_kb(topic)`
Retrieve stored knowledge on a topic. Returns all non-expired entries, sorted by recency. Check KB before doing new research — the information may already be there.

### `search_kb(query)`
Full-text search across all KB entries. Use when you're not sure what topic key was used to store relevant information.

---

## World Model and State

### `update_world_model(fields)`
Persist updates to the world model. Call after any significant state change (position placed, balance updated, research completed). Fields is a dict of world model keys to new values.

### `read_world_model()`
Returns the current world model. Called automatically at session start; use this if you need to re-read it mid-session.

---

## Scheduling

### `create_heartbeat(fire_at, reason, session_type, context)`
Schedule a future session. `fire_at` is an ISO 8601 datetime. `reason` is a short human-readable explanation. `session_type` is one of: RESOLVE, RESEARCH, MONITOR, FULL_CYCLE. `context` is a dict with the information this future session needs.

### `amend_heartbeat(heartbeat_id, fire_at=None, reason=None, context=None)`
Modify a scheduled heartbeat. Use when new information changes when a session should run or what context it needs.

### `cancel_heartbeat(heartbeat_id, reason)`
Cancel a scheduled heartbeat. Use when the trigger condition is no longer relevant.

### `list_scheduled_heartbeats()`
Returns all heartbeats with status SCHEDULED, sorted by fire_at. Use at end of session to review what's already scheduled before creating new ones.

---

## Estimation

### `estimate_probability(market_id, evidence_summary, comparable_base_rates=None)`
Structured probability estimation. Given a market and a summary of evidence, returns a probability estimate with confidence level and a brief rationale. This is an LLM call — the output is the agent's own reasoning, not a lookup.
