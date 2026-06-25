<!-- TEMPLATE: CALENDAR.md
     Your forward calendar: time-bound events you are tracking — market closes, resolution
     windows, deadlines, anything that should pull you awake at a specific time.

     This file is READ BY YOUR SELF-SCHEDULER at the end of every wake. Each future entry
     under "## Upcoming" that it can parse is turned into a heartbeat automatically, so you
     do not have to call create_heartbeat by hand for things you record here. Keep it current:
     this is how you tie what you are tracking to when you next wake.

     Put each event on its own line under "## Upcoming", in exactly this shape:
       - <ISO 8601 datetime UTC> | <SESSION_TYPE> | <reason>
     for example:
       - 2026-06-25T14:00:00Z | RESEARCH | BTC > $80k market closes in 1h — refresh estimate
       - 2026-06-26T09:30:00Z | RESOLVE  | Election market resolves; check the position

     SESSION_TYPE is one of: RESOLVE | RESEARCH | MONITOR | FULL_CYCLE.
     Use UTC (a trailing Z) so times are unambiguous. Lines that do not match the shape, or
     whose time is in the past, are ignored. Remove entries once they have fired or no longer
     matter so the calendar stays an accurate picture of what is ahead.
-->

## Current Summary
<!-- The agent writes a 1-2 sentence summary of the calendar horizon at first light. -->

## Upcoming
<!-- one event per line in the format: - <ISO datetime Z> | <SESSION_TYPE> | <reason> -->
