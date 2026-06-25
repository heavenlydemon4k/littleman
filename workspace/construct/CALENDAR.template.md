<!-- TEMPLATE: CALENDAR.md
     Upcoming events the agent tracks for self-scheduling. Updated every wake: add newly
     discovered events, remove past ones. The self-scheduler reads this when planning heartbeats
     so it can fire at the right moment for each event — not just for open positions/markets.

     Covers anything time-bound and requiring future agent action:
       - Market closes (from watched_markets or discovered during research)
       - Position resolution windows (known outcome dates)
       - External events with predictable timing (earnings, political votes, data releases)
       - Self-scheduled follow-ups the agent decided on mid-session

     Format for each entry (most imminent first):
       ## {ISO date or datetime UTC} — {short label}
       **Type:** market_close | position_resolution | external_event | self_scheduled
       **Lead:** {how far ahead to act, e.g. "1 h before", "10 min after"}
       **Action:** {what the future wake should do — 1 sentence}
       **Context:** {key identifiers and facts the future wake needs, e.g. market id, current price}

     Maintenance rules:
       - Keep most imminent first.
       - Drop entries whose datetime is in the past.
       - Merge duplicates (one entry per unique event).
       - Keep a Current Summary at the top (1-2 sentences: earliest event, total count).
       - If nothing is upcoming, write "No upcoming events." as the only body content.
-->

## Current Summary
<!-- Empty at first light — filled by the agent once it has reviewed the calendar horizon. -->

<!-- Upcoming event entries go here, most imminent first. -->
