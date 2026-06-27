# read_template — Read a Construct Document Template

## Purpose
Read the template for a construct document. Templates contain the required format and instructions for what belongs in the doc.

## Parameters
- `doc` (str): the construct document name, e.g. `"PRIORITIES.md"`, `"MACRO_PLAN.md"`, `"SELF.md"`.

## Returns
A dict with `doc` and `template`.

## When to use
- During First Light, before writing each construct doc, to learn its expected structure.
- Any time you are unsure of the format for a construct doc.

## Tip
Read the template, then write the doc with `write_construct`. Do not copy the HTML comment markers literally — they are instructions, not content.
