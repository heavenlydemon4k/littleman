# Littleman measured against OpenClaw

A study of the actual [OpenClaw](https://github.com/openclaw/openclaw) repository and docs
(June 2026), recording where littleman stands relative to its inspiration and what was adopted
as a result. See also [ARCHITECTURE.md §3](ARCHITECTURE.md#3-relationship-to-openclaw) for the
original relationship and [ADR 0001](adr/0001-mental-construct-not-generational-state.md).

## What OpenClaw actually is (from the repo)

- A **TypeScript / Node** pnpm monorepo (`/src`, `/packages`, `/extensions`, `/apps`, `/ui`),
  ~61k commits. A general-purpose personal-assistant platform, multi-channel (WhatsApp,
  Slack, Discord, …), self-hosted, model-agnostic.
- Central **Gateway** control plane; agents run in isolated workspace sessions; non-primary
  sessions sandboxed (Docker/SSH/OpenShell).
- State in a single shared `state/openclaw.sqlite`.

## Mechanics that matter, and how littleman compares

| Dimension | OpenClaw (observed) | Littleman | Verdict |
|---|---|---|---|
| Config | Workspace files loaded each session (`SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`); flat `MEMORY.md` + `memory/YYYY-MM-DD.md` daily logs | Workspace-first **+ structured Mental Construct** (PRIORITIES/MACRO_PLAN/SELF/DIRECTIVE/REFLECTION) | Littleman ahead on cognition structure |
| Agent loop | ReAct: intake → context assembly → inference → tool exec → stream → persist; reasoning streamed separately; tool results size-sanitized | ReAct (`agent/loop.py`); thinking streamed separately in chat | Match |
| Scheduling | `HEARTBEAT.md` = optional static human checklist run on a fixed interval; separate cron for timed jobs | Agent-authored, time-targeted, **context-carrying** heartbeats with `spawned_by` cascade lineage | Littleman well ahead |
| Concurrency | Per-session lane (one active run/session) + global lanes with caps; **process-aware, file-based write lock** catches writers bypassing the in-process queue | Serial scheduler **+ cross-process `SessionLock`** (adopted) | Parity on the safety guarantee |
| Skills | `SKILL.md` + YAML frontmatter; precedence hierarchy; per-agent allowlists; **gating** on required env/binaries/OS (`metadata.openclaw`) | Static Python registry **+ requirement gating** (adopted) | OpenClaw richer (filesystem skills, allowlists); littleman now gates |
| Context budget | `bootstrapMaxChars` 20k / total 60k; truncation; "missing file" markers | **Per-doc + total char caps**, REFLECTION truncated to tail (adopted) | Parity |
| Queue modes | steer / followup / collect / interrupt for mid-run messages | Chat handles messages sequentially | OpenClaw ahead (not yet needed) |
| Financial risk | N/A (general purpose) | Hard-limit risk governor, circuit breaker, Kelly sizing | Littleman-only |

## Adopted

1. **Cross-process session lock** (`agent/lock.py`) — OpenClaw's file-based write lock is direct
   evidence for ADR 0001. Now `run_session` holds an O_EXCL lockfile (PID + acquired-at, stale
   takeover); the scheduler waits 60s then defers. The "one consistent capital view" guarantee
   now holds even if a manual run overlaps the scheduler.
2. **Skill gating** (`skills/registry.py`) — skills declare `requires=[…]`; unmet requirements
   make them unavailable (not offered to the model, dispatch refuses, SELF.md inventory shows
   it). Mirrors OpenClaw's `metadata.openclaw` gating.
3. **Context budget** (`meta/construct.py`) — per-doc and total caps on the injected construct;
   append-only `REFLECTION.md` truncated to its tail. Mirrors `bootstrapMaxChars`.
4. **Stale-RUNNING session cleanup** (`heartbeat/store.py`, `heartbeat/scheduler.py`) — OpenClaw
   detects runs that have been active too long and marks them failed. Without this, a heartbeat
   whose session process crashed (OOM, SIGKILL, machine reboot) without marking itself DONE
   would stay in RUNNING forever and silently halt the agent. Now each scheduler tick calls
   `get_stale_running_heartbeats(timeout_minutes)` and marks those heartbeats FAILED, triggering
   the existing exponential-backoff retry. Configurable via `STALE_SESSION_TIMEOUT_MINUTES`
   (default 30 min).

## Deliberately not adopted (yet)

- **Filesystem `SKILL.md` skills with precedence + allowlists.** Littleman's typed Python
  registry is simpler and safer for a single-operator agent. Revisit if third-party skills are
  wanted.
- **Queue modes (steer/collect/interrupt) for chat.** Only relevant once the operator sends
  messages mid-stream frequently. Sequential handling is fine for now.
- **Multi-channel Gateway / sandboxing.** Out of scope — littleman is single-user, one domain.

## Net assessment

OpenClaw is the more mature *platform* (breadth, ecosystem, channels, sandboxing). Littleman is
the more sophisticated *autonomous agent* for its niche: the dynamic heartbeat cascade and the
Mental Construct give it self-direction OpenClaw's static `HEARTBEAT.md` does not attempt. After
four hardening passes (lock, skill gating, context budget, stale-run cleanup), littleman matches
OpenClaw on the concurrency-safety and context-budget fundamentals that actually protect a
money-handling agent.
