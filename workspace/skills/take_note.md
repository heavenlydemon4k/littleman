# take_note — Save a General Note

## Purpose
Persist a short note to the knowledge base under a topic. Use this for durable information that is not a formal research finding.

## Parameters
- `topic` (str): the topic key. Use lowercase, underscore-separated names (e.g. `operator_preferences`, `project_goals`).
- `content` (str): the note text.
- `source_urls` (list[str], optional): URLs or references supporting the note.

## Returns
A dict with the written entry id, topic, and `written: True`.

## When to use
- The operator tells you something you should remember across wakes.
- You learn a preference, constraint, or fact worth preserving.
- During First Light, to capture anything the operator emphasized.

## See also
- `read_notes` — read notes back by topic or query.
- `write_to_kb` — for formal research findings with confidence and expiry.
