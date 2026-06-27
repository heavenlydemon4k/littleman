# set_reminder — Schedule a Reminder Heartbeat

## Purpose
Create a future heartbeat that reminds you to handle something at a specific time. This is a convenience wrapper around `create_heartbeat` with `session_type="FULL_CYCLE"`.

## Parameters
- `title` (str): short title for the reminder.
- `fire_at` (str): ISO 8601 datetime in UTC, e.g. `"2026-06-24T14:00:00+00:00"`.
- `reason` (str, optional): longer explanation of why the reminder exists.

## Returns
A dict with `heartbeat_id` and `fire_at`.

## When to use
- The operator asks you to follow up at a specific time.
- You want to be woken to check on a deadline, event, or task.

## Common mistakes
- Passing a datetime without timezone — always use UTC.
- Scheduling in the past — the reminder will fire immediately.
