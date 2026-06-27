---
skills:
  - create_heartbeat
  - amend_heartbeat
  - cancel_heartbeat
  - list_scheduled_heartbeats
---
# heartbeat — Self-Scheduling

## Purpose
Schedule future autonomous sessions by creating heartbeat records. This is how the agent plans its own wake-up schedule without human intervention.

## Skills
- `create_heartbeat(fire_at, reason, session_type, context=None)` — create a new heartbeat.
- `amend_heartbeat(heartbeat_id, fire_at=None, reason=None, context=None)` — reschedule an existing heartbeat.
- `cancel_heartbeat(heartbeat_id, reason)` — cancel a scheduled heartbeat.
- `list_scheduled_heartbeats()` — list all scheduled heartbeats.

## Session types
- `FULL_CYCLE` — full session: situate, plan, execute, reflect, maintain, schedule.
- `RESEARCH` — deep-dive on a specific topic; no actions.
- `MONITOR` — check state and market/data movements.
- `RESOLVE` — check whether a tracked event has resolved.

## When to schedule heartbeats

### End of every session
Always schedule the next wake-up. If uncertain, default to `FULL_CYCLE` in 4h.

### Event-driven timing examples
- Major data release (NFP, CPI, FOMC): schedule `FULL_CYCLE` 30min after expected release.
- Tracked event resolution: schedule `MONITOR` 1h before resolution to check final state.
- Breaking news detected: schedule `RESEARCH` in 2h to gather more evidence.

## `fire_at` format
ISO 8601 with timezone: `"2026-06-24T14:00:00+00:00"`
Always use UTC. Never schedule in the past.

## Context blob
The context dict is injected into the next session's situation synthesis:
```json
{
  "intent": "What this session should accomplish",
  "focus": ["topic_1", "topic_2"],
  "carry_forward": "Key finding from this session the next one must know",
  "urgency": "routine | elevated | urgent"
}
```
Use `carry_forward` to pass time-sensitive context that may not be in the KB yet.

## Deduplication rule
Before scheduling, check: is there already a SCHEDULED heartbeat of the same type within ±30 minutes of your intended `fire_at`? If yes, amend it rather than creating a duplicate.

## Common mistakes
- Not scheduling the next heartbeat → agent goes dark after current session.
- Scheduling too many heartbeats (>3 per session) → redundant computation.
- Setting `fire_at` in the past → heartbeat fires immediately on next scheduler tick.
- Empty context blob → next session has no carry-forward intent.
