# read_notes — Read Saved Notes

## Purpose
Retrieve notes previously saved with `take_note`, either by exact topic or by full-text query.

## Parameters
- `topic` (str, optional): read all notes under this topic.
- `query` (str, optional): full-text search across note topics and contents.

## Returns
A dict with matching entries.

## When to use
- Before a wake, to remind yourself of operator preferences or past notes.
- When the operator asks about something you previously discussed.

## Note
Provide either `topic` or `query`, not both. If neither is provided, returns an empty result.
