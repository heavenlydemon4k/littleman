<!-- TEMPLATE: TURNS.md
     Your rolling N-turn execution window. Read at the start of every wake and updated at the
     end. This is where you track multi-turn state explicitly: what this turn did, what the next
     turn(s) should do, and how to recover if something goes wrong.

     Structure:
       ## Current Turn
       - turn_n: integer starting at 1 for this session sequence
       - goal: one sentence describing what this turn is for
       - planned_skills: skills you expect to call
       - exit_condition: what would make this turn complete

       ## Upcoming Turns
       A short queue (1–4 turns) in dependency order. Each entry:
       - turn_n: integer
       - goal: one sentence
       - depends_on: turn number(s) this cannot start before
       - fallback: what to do if the predecessor fails or returns no useful result

       ## Completed Turns
       Append each finished turn here (keep the last ~10). Each entry:
       - turn_n: integer
       - summary: what happened
       - result: COMPLETE | PARTIAL | FAILED

     Rules:
     - Rewrite Current Turn and Upcoming Turns every wake.
     - Keep Upcoming small and concrete; do not plan more than a handful of turns ahead.
     - When a turn completes, move it to Completed and promote the next Upcoming turn.
-->

## Current Turn
<!-- filled by the agent at the start of each wake -->

## Upcoming Turns
<!-- 1–4 planned turns, in order -->

## Completed Turns
<!-- append-only history of recent turns -->
