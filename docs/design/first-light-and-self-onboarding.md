# Design — First Light read/write + self-onboarding for a context-less LLM

Status: **theorycraft**. How the agent reads and writes its own files during First Light, and
what documents make a *fresh LLM with no prior context* able to understand who it is, how the
system works, and what to do.

---

## 1. The problem

At First Light the model knows **nothing** except what we put in its prompt and what it can
read through skills. It is also possibly a small/cheap model. For it to bootstrap itself it
needs two things:

1. **The ability to read and write its own files** (not the Python harness doing it for it) —
   so First Light is genuinely the agent waking, reading its files, and authoring its cognition.
2. **A document stack that is self-onboarding** — enough, in plain language, that a context-less
   model reading it understands its identity, the platform's operating model, its files, and its
   skills, and can act.

Today (1) is scripted (Python reads/writes; the LLM only fills text), and (2) is missing the
single most important doc: an **agent-facing operating manual**.

---

## 2. The self-onboarding document stack

What a fresh LLM must be able to read. Two tiers: **always in the prompt** (core, capped by the
context budget) vs **read on demand** (detail, via skills).

| Doc | Tier | Provided by | Teaches the model |
|---|---|---|---|
| `AGENT.md` (operating manual) | **always** | platform (static) | *You are an autonomous agent on littleman.* The wake/sleep model, the mental construct, the turn cycle, how to use skills, how to schedule itself, the human/agent boundary, that hard limits are code. **This is the new, critical doc.** |
| `SOUL.md` | **always** | onboarding / operator | Who this specific agent is — mission (the purpose), values, domain knowledge, constraints. |
| Onboarding answers | **always at First Light** | onboarding (`Profile`) | The user's name, purpose, and guided answers, rendered so the agent reads them directly. |
| Mental construct (PRIORITIES/MACRO_PLAN/SELF/DIRECTIVE/REFLECTION) | **always** | agent (self-authored) | Its own current cognition. Empty at First Light; the agent fills it. |
| Construct **templates** | on demand | platform (static) | The format + instructions for each construct doc (already embedded as HTML-comment instructions). |
| `SKILLS.md` + `workspace/skills/*.md` | on demand | platform (static) | What each skill does and how to use it (`read_skill_doc`). |

The core insight: **`AGENT.md` is the missing piece.** SOUL.md says *who I am*; AGENT.md says
*how I work as a littleman agent*. A context-less model needs both.

### `AGENT.md` outline (the operating manual)

Written as imperative instructions **to** the agent, concise enough to always include:

1. **What you are** — an autonomous, self-directing agent; not a chatbot; you form your own
   intent and schedule.
2. **The wake/sleep model** — you are dormant; you wake on a heartbeat or a user message, act,
   then sleep. A wake costs tokens; be economical.
3. **Your mental construct** — the five docs, what each holds, when to read each (start of wake)
   and write each (PRIORITIES/DIRECTIVE each turn; SELF continuously; REFLECTION append-only).
4. **The turn cycle** — situate → directive → plan → execute → reflect → schedule-next.
5. **Skills** — you act only through skills; call `read_skill_doc(name)` before using a complex
   one; unavailable skills are hidden.
6. **Scheduling yourself** — write heartbeats for future work (resolution checks, research
   windows); the schedule is yours.
7. **The boundary** — the human gives identity + hard limits; you own intent, priorities,
   schedule, and self-assessment. Hard limits are enforced in code; do not try to circumvent.
8. **First Light specifically** — on your first wake: read SOUL.md + your onboarding answers,
   form your initial understanding, write your PRIORITIES/MACRO_PLAN/SELF, and greet the
   operator with your read of the mission.

---

## 3. Read/write capability — agent file skills

The agent needs skills (not just the Python harness) to touch its files. Add a small,
**safe, construct-scoped** set rather than raw filesystem access:

- `read_construct(doc)` — read one construct/workspace doc (SOUL.md, AGENT.md, PRIORITIES.md, …).
- `write_construct(doc, content)` — overwrite an OVERWRITE doc (PRIORITIES/MACRO_PLAN/SELF/
  DIRECTIVE); refuses SOUL/AGENT (operator-owned) unless on the custom path's self-config skill.
- `append_reflection(entry)` — append to REFLECTION.md.
- `list_workspace()` — enumerate readable docs.
- (existing) `read_skill_doc(name)`.

These wrap `meta/construct.py` + the workspace path guard already in `api/routes/workspace.py`
(allowed extensions, no traversal). Construct-scoped beats raw `write_file` because it is
auditable and can't let the model clobber arbitrary files.

The **custom path** additionally gets `update_self(soul_section, content)` so the agent can
write its own SOUL.md from the configuring conversation (operator-owned doc, gated to the
custom flow).

---

## 4. First Light as agentic read/write (with a safety net)

Reframe First Light from "scripted pipeline" to "agentic, verified":

```
1. Assemble the First-Light system prompt:
      AGENT.md (operating manual)
    + SOUL.md
    + onboarding answers (rendered from Profile)
    + the empty construct + a note: "this is your first wake; author your construct."
    + skill definitions (incl. read_construct / write_construct / append_reflection)
2. Run a bounded ReAct loop: the agent reads its files and writes PRIORITIES / MACRO_PLAN / SELF,
   then produces a greeting as its final message.
3. SAFETY NET (deterministic): after the loop, verify each required construct doc is non-empty.
   For any the agent skipped, fall back to the current scripted text-authoring for that doc.
4. Write the first heartbeat (deterministic, as today).
5. The greeting is narrated into the First-Light chat session.
```

Agentic-first gives the "reads and writes its own files" property the operator wants; the
safety net guarantees a usable construct even if a weak model underperforms. First Light stays
**idempotent / re-runnable** (the re-situate capability) — running it again re-reads and can
refresh the construct.

---

## 5. Context assembly — prompt vs on-demand

- **Always in the system prompt** (every wake, not just First Light): AGENT.md + SOUL.md +
  current construct summary. This is what a context-less model needs each time it wakes.
- **On demand**: construct templates, skill docs, KB entries — fetched via skills when needed.
- **Budgeted**: the existing `bootstrap_max_chars` / total cap (and REFLECTION tail-truncation)
  keep the always-in-prompt block bounded. AGENT.md must therefore be **concise** (a tight
  operating manual, not a treatise) — detail lives in on-demand docs.

This layering is exactly how a fresh model stays oriented without blowing the window: a small
always-loaded core ("who am I, how do I work, what's my state") plus pull-on-demand depth.

---

## 6. What to build (implementation sketch)

1. **`workspace/AGENT.md`** — the operating manual (static, platform-provided). Seeded for every
   instance regardless of application.
2. **Construct/file skills** — `read_construct`, `write_construct`, `append_reflection`,
   `list_workspace` registered in the skill registry (wrapping `meta/construct.py`).
3. **Onboarding render** — surface `Profile` (name/purpose/guided answers) to First Light, e.g.
   a rendered `ONBOARDING.md` or an injected context block.
4. **First Light rewrite** — agentic ReAct authoring + deterministic verification fallback;
   greeting narrated to the First-Light chat.
5. **Prompt assembly** — include AGENT.md + SOUL.md + construct in the wake system prompt
   (within the context budget).
6. **Custom self-config** — `update_self` skill gated to the custom path (also serves §Slice 4).

Order: (1) + (2) first (cheap, unlock the capability and the manual), then (4) the First Light
rewrite, then (3)/(5)/(6).

---

## 7. Open questions

- Should `AGENT.md` be a single doc or split (core always-loaded + extended on-demand)? Start
  single + concise; split only if the budget pressures.
- How much does a *small* model actually follow AGENT.md? Needs a live test with the cheap tier;
  the safety net covers underperformance but the greeting quality depends on it.
- Does the agent ever rewrite AGENT.md? No — platform-owned, like a kernel. SOUL.md is the
  editable identity; AGENT.md is the fixed operating model.
