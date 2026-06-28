---
skills:
  - inspect_system_config
  - propose_soul_update
  - apply_soul_update
  - set_runtime_config
---

# system_config — Inspect and Configure Littleman

## Purpose

Use these skills when the operator asks what Littleman is configured to do, asks
to change the assistant identity, or asks to change model/runtime settings.

## Skills

### `inspect_system_config(include_soul=false)`

Reads the current runtime, active application, construct status, SOUL.md status,
and registered skills. API keys are redacted.

Set `include_soul=true` when the operator is asking about the assistant identity
or wants to edit it.

### `propose_soul_update(content, mode="replace", rationale=None)`

Previews a SOUL.md update without writing it. Use this before changing identity,
purpose, operating principles, constraints, or other durable assistant behavior.

Modes:

- `replace` — proposed content becomes the whole file.
- `append` — proposed content is added to the end.
- `prepend` — proposed content is added to the start.

### `apply_soul_update(content, mode="replace", confirm=false)`

Writes SOUL.md only when `confirm=true`. Do not call this until the operator has
approved the proposed content.

### `set_runtime_config(values, confirm=false)`

Updates runtime settings only when `confirm=true`.

Allowed keys:

- `mode`
- `primary_model`
- `secondary_model`
- `api_base`
- `api_key`
- `autonomous`

## Common Mistakes

- Do not expose raw API keys back to the user.
- Do not silently change autonomy.
- Do not rewrite SOUL.md without first showing the proposed content.
- Do not use workspace file tools for runtime config. Use `set_runtime_config`.
