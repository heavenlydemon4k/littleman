# append_reflection — Append to REFLECTION.md

## Purpose
Add a dated entry to your append-only reflection log. This is where you record outcomes, lessons, and calibration signal.

## Parameters
- `entry` (str): the text to append. Should include the date, what happened, what you expected, and what you learned.

## Returns
A dict with `appended: True`.

## When to use
- At the end of a wake when something notable happened.
- When a prediction resolves — record the outcome for calibration.
- When you hit a blocker or learn a limitation.

## Note
`REFLECTION.md` is append-only. Never rewrite it; only add entries.
