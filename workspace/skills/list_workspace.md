# list_workspace — List Readable/Writable Workspace Documents

## Purpose
Return the lists of documents you can read, write, or append to. Useful when you are unsure what files are available.

## Parameters
None.

## Returns
A dict with `readable`, `writable`, and `append_only` lists.

## When to use
- During First Light, to orient yourself to the workspace layout.
- Any time you need to confirm whether a document name is valid for `read_construct` or `write_construct`.
