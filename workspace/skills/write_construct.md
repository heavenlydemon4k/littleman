# write_construct — Write an Agent-Authored Construct Document

## Purpose
Overwrite one of the construct documents you own. This is how you persist your priorities, strategy, self-model, calendar, hypotheses, blockers, skill notes, and directive.

## Parameters
- `doc` (str): the document name. Must be one of the overwrite docs.
- `content` (str): the full markdown body to write.

## Returns
A dict with `doc`, `written`, and `chars`.

## Writable docs
`PRIORITIES.md`, `MACRO_PLAN.md`, `SELF.md`, `CALENDAR.md`, `DIRECTIVE.md`, `HYPOTHESES.md`, `BLOCKERS.md`, `SKILL_NOTES.md`, `EXPOSURE.md`, `TURNS.md`.

## When to use
- During First Light: write your initial `PRIORITIES.md`, `MACRO_PLAN.md`, and `SELF.md`.
- At the end of a wake: rewrite `PRIORITIES.md` to reflect new state.
- When strategy shifts: rewrite `MACRO_PLAN.md`.
- When you learn something about yourself: update `SELF.md`.

## Note
You cannot write `SOUL.md` or `AGENT.md` with this skill — those are operator/platform-owned. `REFLECTION.md` is append-only; use `append_reflection` instead.
