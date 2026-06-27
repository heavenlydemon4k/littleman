# read_construct — Read a Workspace or Construct Document

## Purpose
Read the content of a document in your workspace. Use this to inspect your mental construct, your identity (`SOUL.md`), your operating manual (`AGENT.md`), your capability list (`SKILLS.md`), or any other document you are allowed to read.

## Parameters
- `doc` (str): the document name, e.g. `"PRIORITIES.md"`, `"SOUL.md"`, `"AGENT.md"`, `"SKILLS.md"`.

## Returns
A dict with `doc`, `content`, and `exists`.

## When to use
- At the start of every wake to load your construct.
- During First Light to read `SOUL.md`, `AGENT.md`, and construct templates.
- Before writing a construct doc to see what's already there.

## Note
`SOUL.md` and `AGENT.md` are read-only through this skill. Use `write_construct` for agent-authored construct docs.
