# ADR 0001 — Adopt the Mental Construct; reject generational/parallel state

Status: Accepted
Date: 2026-06-22

## Context

A later architectural document ("LITTLEMAN — Complete Architectural Meta") proposed
several primitives beyond the original ARCHITECTURE.md:

1. **Self-Model** — a runtime-generated, agent-updated representation of the agent's own
   capabilities, knowledge, state, and identity, distinct from the static SOUL.md.
2. **Mental Construct** — a set of agent-authored markdown documents (PRIORITIES.md,
   MACRO_PLAN.md, SELF.md, DIRECTIVE.md, REFLECTION.md) that serve as explicit, inspectable
   cognitive scaffolding.
3. **First Light** — a bootstrap protocol that is re-invokable, not a one-time init, so the
   agent can re-ground itself from SOUL.md + external APIs at any time.
4. **Generational state** — append-only delta lineage (INSERT deltas with parent-generation
   references) instead of mutable state updates.
5. **Parallel-by-default contexts** — multiple heartbeats firing simultaneously spawn
   independent "contexts" that do not share mutable state and whose writes are merged at the
   data layer.

This ADR records which of these we adopt and why.

## Decision

### Adopt: Self-Model, Mental Construct, First Light

These three are high value and low risk. They make the agent's cognition explicit and
inspectable — a markdown file you can open and read beats an opaque vector store for a
system that must be auditable when it is trading real money. They extend the workspace-first
pattern already adopted from OpenClaw. They are implemented as:

- `workspace/construct/` — the five mental construct documents, created from templates at
  first light and owned by the agent thereafter.
- `littleman/meta/construct.py` — load/save/merge for the construct documents.
- `littleman/meta/first_light.py` — the bootstrap/re-grounding protocol.

The construct documents are loaded into the system prompt at the start of every session
and updated by the meta layer at session end.

### Reject (for now): Generational state and parallel-by-default contexts

We keep **serial-by-default execution** with the existing single mutable `world_model` row,
plus the existing append-only `observations` table for the audit trail. We do not implement
generational delta lineage or a merge layer.

Reasons:

1. **It contradicts the project's own stated principle** that complexity belongs in the
   cognition, not the infrastructure. Generational state with conflict-resolving merge
   semantics is a distributed-systems data model. The proposing document itself lists the
   merge algorithm as an unresolved open question — which is a strong signal not to build it
   speculatively.

2. **It is unjustified for a single-user agent.** There is exactly one operator and one
   wallet. The concurrency the generational model exists to support is not a requirement of
   this system. SQLite in WAL mode already handles the one-writer + one-reader (scheduler)
   case we actually have.

3. **Parallel contexts sharing a wallet is a financial hazard.** Two contexts starting from
   the same generation can each independently pass the risk governor against the same
   available balance and each place a bet, exceeding the intended exposure. "Last-generation
   wins" on capital allocation is a double-spend. For a system whose core responsibility is
   enforcing hard financial limits, capital operations must be evaluated against a single,
   consistent, serialized view.

### Allowance: read-only parallelism within a session

Concurrency is permitted for **read-only** work — e.g. fanning out several web-research
calls at once within a single session. This uses `asyncio.gather` inside one session and
writes results back through the single session transaction. No cross-session shared mutable
state, no merge layer. Execution skills (place_bet, cancel_position) remain strictly serial
and gated by the risk governor on the live world-model view.

## Consequences

- The agent gains an explicit, inspectable cognitive layer that the frontend can render and
  the operator can edit — consistent with the workspace editor already built.
- We avoid building (and debugging, and reasoning about the safety of) a concurrent state
  system that this single-user deployment does not need.
- If multi-instance or true-parallel operation is ever required, this ADR is the place to
  revisit. The append-only `observations` table and the heartbeat `spawned_by` lineage
  already provide the audit trail that a generational model's history would have provided,
  so the migration path is open.

## Revisit if

- Littleman is ever run as multiple coordinating instances against a shared goal.
- A single session's serial execution becomes a measured latency bottleneck (it will not be
  for a trading cadence measured in minutes-to-hours).
