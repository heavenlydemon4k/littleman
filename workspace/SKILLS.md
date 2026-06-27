# SKILLS — Available Capabilities

This file documents skills available to the agent. Platform skills are always available when running the default `littleman.platform` application. Application skills are available only when a domain-specific application (e.g. Polymarket trading) is active.

---

## Platform skills (always available)

### Research

#### `web_search(query, source_filters=None, max_results=10)`
Search the web and return structured results (title, url, excerpt, date, source).

#### `browse_url(url)`
Fetch and parse the text content of a specific URL.

#### `browse_urls(urls)`
Fetch and parse several URLs in parallel.

### Knowledge Base

#### `write_to_kb(topic, content, source_urls=None, confidence="MEDIUM", expires_hours=None)`
Persist research findings or notes to the knowledge base.

#### `read_from_kb(topic)`
Retrieve stored knowledge on a topic.

#### `search_kb(query)`
Full-text search across KB entries.

### Notes and Reminders

#### `take_note(topic, content, source_urls=None)`
Save a general note under a topic.

#### `read_notes(topic=None, query=None)`
Read notes by topic or full-text query.

#### `set_reminder(title, fire_at, reason=None)`
Schedule a future heartbeat reminder. `fire_at` is an ISO 8601 datetime.

### Mental Construct

#### `read_construct(name)` / `write_construct(name, content)`
Read or write a construct document.

#### `append_reflection(entry)`
Append an entry to the append-only REFLECTION.md.

### Scheduling

#### `create_heartbeat(fire_at, reason, session_type, context)`
Schedule a future session.

#### `amend_heartbeat(heartbeat_id, ...)`
Modify a scheduled heartbeat.

#### `cancel_heartbeat(heartbeat_id, reason)`
Cancel a scheduled heartbeat.

#### `list_scheduled_heartbeats()`
List scheduled heartbeats.

### Estimation and Reflection

#### `estimate_probability(market_id, evidence_summary, ...)`
Structured probability estimation.

#### `record_prediction_outcome(...)` / `get_calibration_summary()`
Record resolved predictions and view calibration stats.

---

## Application skills (Polymarket trading only)

The following skills are available only when `active_application = "Polymarket trading"`:

### `scan_markets(...)`
### `get_market(market_id)`
### `get_orderbook(market_id)`
### `get_position(position_id)`
### `check_resolution(market_id)`
### `place_bet(market_id, direction, size_usdc, max_price=None)`

See the Polymarket application documentation for details.
