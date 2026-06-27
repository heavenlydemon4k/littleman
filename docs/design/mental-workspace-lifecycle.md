# Design — The mental workspace lifecycle (refer, use, maintain)

Status: **theorycraft + implementation plan.** How the agent's inner construct becomes a living
working memory it refers to, uses, and maintains on **every** wake — not just First Light — and
how the agent is continuously onboarded to use it.

---

## 1. The problem this fixes

The construct (PRIORITIES / MACRO_PLAN / SELF / DIRECTIVE / REFLECTION) exists and is authored at
First Light, but in a normal wake it is **read but never updated**:

- `DIRECTIVE.md` is regenerated each wake (good).
- `REFLECTION.md` is appended each wake (good).
- `PRIORITIES.md`, `MACRO_PLAN.md`, `SELF.md` are written **only at First Light** and then frozen.

A frozen priority stack and a frozen self-model are not working memory — they are a one-time
snapshot. And `AGENT.md` (the manual that teaches the agent *how* to use the workspace) is only
in the First Light prompt, so on later wakes the agent is not reminded the workspace exists or
how to maintain it.

For the construct to be what the architecture intends, two things must hold on every wake:
**(A) the agent reads its construct and reasons from it, and (B) the agent updates its construct
to reflect what changed.** And the agent must be **onboarded continuously** — told, each wake,
that this is how it works.

---

## 2. The construct lifecycle (every wake)

```
WAKE
 ├─ READ      load PRIORITIES, MACRO_PLAN, SELF (+ AGENT.md core) into the reasoning context
 ├─ SITUATE   situation report reflects current priorities + state
 ├─ DIRECT    directive is formed FROM the priorities and plan (already reads the construct)
 ├─ EXECUTE   tasks run; the agent may read/write construct docs via its skills mid-task
 ├─ MAINTAIN  *** the missing half *** update the construct to reflect this wake:
 │              • PRIORITIES.md  — re-ranked: what matters now, given what just happened
 │              • SELF.md        — amended when something was learned (calibration, a limitation)
 │              • MACRO_PLAN.md  — revised only when the strategy actually shifted
 ├─ REFLECT   append REFLECTION.md (append-only)
 └─ SCHEDULE  write the next heartbeat(s), then sleep
```

The key addition is **MAINTAIN**. PRIORITIES is the doc the architecture says is "updated each
turn"; it must be rewritten every wake. SELF updates "continuously" — in practice, whenever the
wake produced a lesson or calibration signal. MACRO_PLAN changes rarely — only on a genuine
strategy shift, so it is conditional, not forced.

### Read vs maintain — who does it

- **Read** is already wired: the directive engine loads PRIORITIES/MACRO_PLAN/SELF. The situation
  report should also reflect them so the whole wake reasons from current priorities.
- **Maintain** is new: a bounded, deterministic-cost step at wake-end. PRIORITIES is rewritten
  by one focused LLM call given (current priorities + directive + what happened). SELF/MACRO are
  updated conditionally (the agent decides; "no change" is a valid, cheap outcome). The agent can
  also maintain its construct opportunistically *during* execution via `write_construct` /
  `append_reflection` (it has those skills), but MAINTAIN guarantees the priority stack never
  goes stale even if the agent forgets.

---

## 3. Continuous onboarding — the agent is reminded how to use the workspace

`AGENT.md` §3 is the canonical teaching of the workspace. For the agent to actually use it on
every wake, a **concise operating core** must be present in the working prompts (directive /
maintenance), not only at First Light. Options:

- **Distilled core in-prompt, full manual on demand.** A short "workspace operating core" (a few
  lines: what each doc is for, read at start / update at end, REFLECTION is append-only,
  PRIORITIES re-ranked each wake) is injected into the directive and maintenance prompts. The
  full `AGENT.md` stays available via `read_construct("AGENT.md")` and is loaded in full at First
  Light. This keeps tokens bounded while ensuring the agent is always oriented.

So "onboarded a way to use it" becomes: First Light gives the full manual + has the agent author
the construct; every wake thereafter carries the distilled core so the agent keeps using and
maintaining it.

---

## 4. The expanded docs (when they earn their place)

The architecture names more construct docs — HYPOTHESES, BLOCKERS, CALENDAR, EXPOSURE,
SKILL_NOTES. They are part of the same lifecycle but should be added **only when a real use
drives them**, each with: a template (self-documenting), a line in `AGENT.md`/the operating core
explaining when to read/write it, and inclusion in the read/maintain steps. Adding them before
the core five are genuinely maintained would be cargo-culting structure. Order of value:

1. Make the **core five** truly live (this doc).
2. **CALENDAR.md** next — it directly feeds self-scheduling (events/closes → heartbeats).
3. **EXPOSURE.md** — a readable risk map mirroring the world model for the agent to reason over.
4. HYPOTHESES / BLOCKERS / SKILL_NOTES as the agent's behaviour shows it needs them.

---

## 5. Implementation (this pass)

1. **`meta/maintain.py`** — `maintain_construct(db, directive, session_summary, exec_result)`:
   rewrites `PRIORITIES.md` from the current priorities + directive + outcomes (one focused text
   call); conditionally appends a `SELF.md` learning when the wake produced one. Skipped in fake
   mode (offline/tests); best-effort (never fails a wake).
2. **Wire into `session._run_pipeline`** between execution and scheduling.
3. **Workspace operating core** — a concise reminder injected into the directive prompt (and the
   maintenance prompt) so the agent is continuously onboarded to read/maintain its workspace.
4. The situation/directive read path already loads the construct; confirm PRIORITIES is in it.

Deferred: forced SELF/MACRO rewrites every wake (conditional is enough), and the expanded docs
(§4), built when their use is real.

---

## 6. Why this matters

Without MAINTAIN, the agent cannot *learn across wakes*: its priorities can't shift as positions
resolve, its self-model can't record that it was overconfident, its plan can't adapt. The
construct is the substrate of the agent's continuity. Making it live — read at the start,
maintained at the end, every wake, with the agent onboarded to do so — is what turns a sequence
of isolated wakes into a single agent that improves.
